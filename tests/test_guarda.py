"""Nenhuma tela nasce aberta.

O teste que mais importa aqui é o último: ele percorre TODAS as rotas do
sistema e exige que cada uma esteja protegida. Uma tela nova sem guarda vira
teste vermelho antes de virar porta aberta — que é o contrário de descobrir
pelo telefone.
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import dar_permissoes


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")


@pytest.fixture
def logada(ana):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
    return c


class TestExigirLogin:
    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get("/")
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_quem_entrou_passa(self, logada):
        assert logada.get("/").status_code == 200

    def test_a_tela_de_login_nao_exige_login(self, db):
        assert Client().get(reverse("entrar")).status_code == 200

    def test_a_folha_de_tema_nao_exige_login(self, db):
        """A tela de login precisa dela antes de qualquer sessão existir."""
        assert Client().get(reverse("tema")).status_code == 200


class TestExigirPermissao:
    def test_sem_a_permissao_a_rota_responde_como_inexistente(self, db, ana):
        """404 e não 403: quem não pode não descobre que a tela existe."""
        from comum.guardas_de_acesso import exigir_permissao
        from django.http import HttpResponse
        from django.test import RequestFactory
        from comum.sessao import CHAVE

        @exigir_permissao("frete.ver")
        def tela(request):
            return HttpResponse("segredo")

        pedido = RequestFactory().get("/frete")
        pedido.session = {CHAVE: str(ana.pk)}
        assert tela(pedido).status_code == 404

    def test_com_a_permissao_passa(self, db, ana):
        from comum.guardas_de_acesso import exigir_permissao
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.http import HttpResponse
        from django.test import RequestFactory
        from comum.sessao import CHAVE
        from plataforma.declaracao import ModuloSpec, registrar, _DECLARADOS

        # `permissoes_de` só traduz permissão de módulo que exista no
        # catálogo: sem declarar `frete`, a `Permission` abaixo não viraria
        # `frete.ver`. Este `frete` é só de fachada, para este teste — não é
        # um módulo do catálogo real, não procure por ele em nenhum
        # `modulos/`. A concessão é por `Permission` direta, e não por nome
        # de grupo: o nome de grupo não concede nada (correção final da
        # revisão de branch — ver o docstring de `contas.backend.permissoes_de`).
        registrar(ModuloSpec(chave="frete", rotulo="Frete"))
        try:
            tipo, _ = ContentType.objects.get_or_create(
                app_label="plataforma", model="modulo")
            Permission.objects.create(
                codename="frete_ver", name="ver frete", content_type=tipo)
            # Pelo cargo: desde a virada, a permissão direta de um membro não
            # conta (`contas.backend._para_o_nucleo`).
            dar_permissoes(ana, "frete_ver")

            @exigir_permissao("frete.ver")
            def tela(request):
                return HttpResponse("segredo")

            pedido = RequestFactory().get("/frete")
            pedido.session = {CHAVE: str(ana.pk)}
            assert tela(pedido).status_code == 200
        finally:
            _DECLARADOS.pop("frete", None)

    def test_sem_sessao_a_rota_protegida_por_permissao_manda_para_o_login(self, db):
        """Sem sessão, `exigir_permissao` redireciona como `exigir_login` —
        e não responde 404. São dois casos diferentes: quem não entrou precisa
        saber onde entrar; quem entrou e não pode não precisa saber que a tela
        existe."""
        from comum.guardas_de_acesso import exigir_permissao
        from django.http import HttpResponse
        from django.test import RequestFactory

        @exigir_permissao("frete.ver")
        def tela(request):
            return HttpResponse("segredo")

        pedido = RequestFactory().get("/frete")
        pedido.session = {}
        resposta = tela(pedido)
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]


class TestNenhumaTelaNasceAberta:
    """A rede que pega a tela nova que alguém esqueceu de proteger."""

    def test_toda_rota_exige_login_ou_esta_declarada_aberta(self):
        from comum.guardas_de_acesso import TELAS_ABERTAS

        desprotegidas = []
        for nome, view in _rotas_do_projeto():
            if nome in TELAS_ABERTAS:
                continue
            if view is None:
                desprotegidas.append(f"{nome} (view não descoberta)")
                continue
            if not getattr(view, "exige_login", False):
                desprotegidas.append(nome or "<rota sem nome>")

        assert not desprotegidas, (
            f"rotas sem guarda: {desprotegidas}. Ou decore a view com "
            f"@exigir_login, ou declare em TELAS_ABERTAS dizendo por quê."
        )


class TestNenhumaOperacaoDaApiNasceAberta:
    """A mesma rede, para a API: toda operação exige sessão ou está declarada
    aberta com o motivo em `comum.guardas_da_api.ABERTAS_DA_API`."""

    def test_toda_operacao_exige_login_ou_esta_declarada_aberta(self):
        from comum.guardas_da_api import ABERTAS_DA_API
        from tests.conftest import operacoes_da_api

        desprotegidas = [
            f"{'/'.join(op.methods)} {caminho} ({op.view_func.__name__})"
            for caminho, op in operacoes_da_api()
            if op.view_func.__name__ not in ABERTAS_DA_API
            and not getattr(op.view_func, "exige_login", False)
        ]
        assert not desprotegidas, (
            f"operações de API sem guarda: {desprotegidas}. Decore com "
            f"@api_exigir_login/@api_exigir_permissao, ou declare em "
            f"ABERTAS_DA_API dizendo por quê.")

    def test_a_varredura_enxerga_operacoes(self):
        from tests.conftest import operacoes_da_api

        assert operacoes_da_api(), "nenhuma operação — a varredura olharia o vazio"

    def test_nenhuma_isencao_aponta_para_operacao_que_nao_existe(self):
        """Isenção de algo que não existe mais é gaveta: ninguém relê, e no
        dia em que uma operação nova ganhar o mesmo nome ela nasce aberta."""
        from comum.guardas_da_api import ABERTAS_DA_API
        from tests.conftest import operacoes_da_api

        nomes = {op.view_func.__name__ for resto, op in operacoes_da_api()}
        assert ABERTAS_DA_API <= nomes, sorted(ABERTAS_DA_API - nomes)


def _rotas_do_projeto():
    """Toda rota do projeto, como (nome, view).

    Caminha os padrões recursivamente em vez de usar `reverse()`: rota que
    exige argumento faria `reverse()` sem args levantar, e a varredura
    pularia a rota **em silêncio** — o pior defeito possível numa rede de
    segurança, porque ela continua parecendo completa.

    **Pula o `include` do Ninja (`app_name == "ninja"`).** Lá, uma view só
    atende todas as operações de um caminho, e a marca da guarda mora na
    função de cada operação — esta varredura não a enxergaria e acusaria toda
    rota da API. Quem cobra a API é `TestNenhumaOperacaoDaApiNasceAberta`,
    logo abaixo, operação por operação.
    """
    from django.urls import get_resolver
    from django.urls.resolvers import URLPattern, URLResolver

    def caminhar(padroes):
        for padrao in padroes:
            if isinstance(padrao, URLResolver):
                if padrao.app_name == "ninja":
                    continue
                yield from caminhar(padrao.url_patterns)
            elif isinstance(padrao, URLPattern):
                yield padrao.name, padrao.callback

    return list(caminhar(get_resolver().url_patterns))
