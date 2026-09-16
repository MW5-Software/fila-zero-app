"""A faixa de contexto no cabeçalho: **a empresa e a filial, cada uma como
seletor só quando há o que escolher**, e os rótulos vindos da marca — nunca
escritos à mão em código.

A filial saiu do cabeçalho em 27/08/2026, quando não tinha papel neste
produto, e voltou em 14/09/2026: desde a virada dos cargos o que a pessoa pode
depende da filial em que está.

`construir_context_switcher` é testada isolada (só `Brand` e uma lista de
`NivelDeContexto` de mentira — nada de sessão, nada de banco): é o jeito de
provar "os rótulos seguem `Brand.context_labels`" sem depender do dia em que
a tela de Aparência ganhar campo para editá-los.
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

from nucleo.permissoes import NivelDeContexto, OpcaoDeContexto
from nucleo.theme import Brand
from nucleo.theme.brand import HeaderBrand
from tests.conftest import por_na_conta

SENHA = "segredo-de-teste"


def _niveis(opcoes=()):
    return [
        NivelDeContexto(nivel=0, rotulo="Empresa", atual="1",
                        opcoes=list(opcoes)),
    ]


class TestConstruirContextSwitcher:
    def test_empresa_sem_opcao_nenhuma_vira_texto(self):
        """`ContextLevel` sem opções vira texto sozinho. Quem alcança uma
        empresa só não recebe um seletor de um item — que seria um controle
        que não controla nada."""
        from plataforma.site import construir_context_switcher

        html = str(construir_context_switcher(Brand(client_name="X"), _niveis()))
        assert "Empresa:" in html

    def test_empresa_com_opcoes_renderiza_como_seletor(self):
        from plataforma.site import construir_context_switcher

        opcoes = [OpcaoDeContexto("1", "Alfa Ltda"), OpcaoDeContexto("2", "Beta Ltda")]
        html = str(construir_context_switcher(Brand(client_name="X"), _niveis(opcoes)))

        assert "<select" in html
        assert 'name="empresa_id"' in html
        assert 'value="1" selected' in html
        assert "Alfa Ltda" in html and "Beta Ltda" in html

    def test_sem_nivel_de_filial_nao_ha_seletor_de_filial(self):
        """Só a empresa na lista: nenhum `filial_id` no HTML. Quem decide se a
        filial aparece é `niveis_de_contexto`, e o componente não inventa um
        segundo nível."""
        from plataforma.site import construir_context_switcher

        opcoes = [OpcaoDeContexto("1", "Alfa Ltda")]
        html = str(construir_context_switcher(Brand(client_name="X"), _niveis(opcoes)))

        assert 'name="filial_id"' not in html
        assert "Filial" not in html

    def test_so_a_filial_vai_para_a_rota_da_filial(self):
        """Sem nível de empresa, o formulário manda para `filial_trocar`, e o
        select se chama como a rota lê."""
        from plataforma.site import construir_context_switcher

        niveis = [NivelDeContexto(nivel=1, rotulo="Filial", atual="7", opcoes=[
            OpcaoDeContexto("7", "Norte"), OpcaoDeContexto("8", "Sul")])]
        html = str(construir_context_switcher(Brand(client_name="X"), niveis))

        assert 'name="filial_id"' in html
        assert f'action="{reverse("filial_trocar")}"' in html
        assert ">Filial</label>" in html

    def test_rotulos_seguem_brand_context_labels(self):
        """Uma rede chama de bandeira e loja — o texto não pode estar preso
        a "Empresa"/"Filial" em lugar nenhum do código."""
        from plataforma.site import construir_context_switcher

        marca = Brand(client_name="X", header=HeaderBrand(
            context_labels=("Bandeira", "Loja"),
        ))
        html = str(construir_context_switcher(marca, _niveis()))

        assert "Bandeira:" in html
        assert "Empresa:" not in html

    def test_show_context_desligado_esconde_a_faixa_inteira(self):
        from plataforma.site import construir_context_switcher

        marca = Brand(client_name="X", header=HeaderBrand(show_context=False))
        assert construir_context_switcher(marca, _niveis()) == ""


@pytest.mark.django_db
class TestNoCabecalhoDeVerdade:
    """Fim a fim: uma pessoa logada, olhando para o HTML que o servidor
    manda — não só o componente isolado."""

    @pytest.fixture
    def cliente_logado(self, db):
        """Ana é a MW5 — a única que alcança mais de uma.

        Era uma ADMIN com duas empresas, e esse cenário deixou de existir em
        09/09/2026: uma conta tem uma empresa. Quem ainda tem o que escolher
        no cabeçalho é só a MW5, e a pergunta dela é outra — qual CONTA está
        olhando. Sem essa troca, estes testes fim a fim passariam a exercitar
        um seletor que a tela não desenha mais para ninguém.
        """
        from contas.models import Nivel
        from plataforma.models import Empresa

        ana = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        Empresa.objects.create(razao_social="Alfa Ltda")
        Empresa.objects.create(razao_social="Beta Ltda")
        ana.nivel = Nivel.MASTER
        ana.save(update_fields=["nivel"])

        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        return c

    def test_a_home_mostra_a_empresa_como_seletor(self, cliente_logado):
        html = cliente_logado.get(reverse("home")).content.decode()

        # `Empresa` sem dois-pontos: o `:` é do modo TEXTO. Com opções, o
        # rótulo vira `<label>` do seletor — ver `ContextLevel`.
        assert ">Empresa</label>" in html
        assert "<select" in html and 'name="empresa_id"' in html
        assert "Alfa Ltda" in html and "Beta Ltda" in html

    def test_o_cabecalho_nao_oferece_empresa_que_a_pessoa_nao_alcanca(self, db):
        """Fim a fim, por ataque: uma empresa fora da conta dela não pode nem
        aparecer — aparecer já conta que ela existe.

        Agora a prova é mais forte do que era: não é que a alheia fique fora
        da lista, é que **não há lista**. Quem é de uma conta não recebe
        seletor nenhum, então não há nem o que filtrar errado.
        """
        from contas.models import Nivel
        from plataforma.models import Empresa

        dona = Usuario.objects.create_user(
            email="dona@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        minha = Empresa.objects.create(razao_social="Alfa Ltda")
        por_na_conta(dona, minha)
        Empresa.objects.create(razao_social="Gama Ltda")

        c = Client()
        c.post(reverse("entrar"), {"usuario": "dona@teste.com", "senha": SENHA})
        html = c.get(reverse("home")).content.decode()

        assert "Gama Ltda" not in html
        assert 'name="empresa_id"' not in html, (
            "conta com uma empresa não tem o que trocar; um seletor aqui é "
            "um botão que não faz nada")

    def test_marca_com_rotulos_proprios_aparece_no_cabecalho_de_verdade(
        self, cliente_logado, monkeypatch,
    ):
        """O mesmo cenário acima, mas com a marca da tela
        (`plataforma.marca.marca_da_requisicao`, o único lugar que
        `plataforma.site.montar_site` consulta desde 15/09/2026 — antes era
        `marca_da_instalacao`) devolvendo rótulos trocados — como uma rede que
        chama de bandeira e loja faria."""
        import plataforma.site as site_mod

        marca_custom = Brand(client_name="Rede X", header=HeaderBrand(
            context_labels=("Bandeira", "Loja"),
        ))
        monkeypatch.setattr(site_mod, "marca_da_requisicao",
                            lambda request: marca_custom)

        html = cliente_logado.get(reverse("home")).content.decode()

        # Ana alcança duas empresas, então o nível vira SELETOR — e o
        # seletor põe o rótulo num `<label>`, sem os dois-pontos do modo
        # texto (ver `nucleo/templates/layout/context_switcher.html`).
        assert ">Bandeira</label>" in html
        assert ">Empresa</label>" not in html
        # O segundo rótulo da marca ("Loja") não aparece: as empresas deste
        # cenário só têm a Matriz, e não há filial para escolher.
        assert ">Loja</label>" not in html

    def test_o_seletor_do_cabecalho_chega_na_rota_que_troca(self, cliente_logado):
        """O laço fechado: o `name` que o cabeçalho manda é o `name` que a
        rota lê.

        As duas pontas já tinham teste — o cabeçalho desenha o seletor, a
        rota valida o id — e mesmo assim trocar de empresa dava 404 em toda
        tentativa: o `<form method="get">` enviava `empresa_id` e a rota lia
        `empresa`. Testar as pontas não prova a emenda. Por isso este teste
        lê o `action` e o `name` DO HTML em vez de repeti-los: se um dos
        lados mudar de nome sozinho outra vez, ele fica vermelho.
        """
        import re

        from plataforma.models import Empresa

        html = cliente_logado.get(reverse("home")).content.decode()
        formulario = re.search(
            r'<form class="ctx" action="([^"]+)" method="get">', html)
        assert formulario, "o cabeçalho não desenhou o formulário de troca"
        campo = re.search(r'<select class="ctx-sel"[^>]*name="([^"]+)"', html)
        assert campo, "o seletor de empresa não tem `name`"

        beta = Empresa.objects.get(razao_social="Beta Ltda")
        resposta = cliente_logado.get(
            formulario.group(1), {campo.group(1): str(beta.pk)})

        assert resposta.status_code == 200
        assert "Beta Ltda" in resposta.content.decode()


@pytest.mark.django_db
class TestOSeletorDeFilial:
    """Desde a virada dos cargos o que a pessoa pode depende da filial em que
    está, e o cabeçalho é onde ela escolhe (14/09/2026)."""

    def _conta(self):
        from contas.models import Nivel
        from plataforma.models import Empresa, Filial

        titular = Usuario.objects.create_user(
            email="dono-cab@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
        norte = Filial.objects.create(empresa=alfa, nome="Norte", apelido="Norte")
        sul = Filial.objects.create(empresa=alfa, nome="Sul", apelido="Sul")
        return titular, alfa, norte, sul

    def _html(self, email):
        c = Client()
        c.post(reverse("entrar"), {"usuario": email, "senha": SENHA})
        return c.get(reverse("home")).content.decode()

    def test_membro_em_duas_filiais_escolhe_entre_elas(self, db):
        from tests.conftest import alocar

        _t, alfa, norte, sul = self._conta()
        ana = Usuario.objects.create_user(email="ana-cab@teste.com", password=SENHA)
        # Representante, e não Vendedor: no Fila Zero quem só tem a fila de
        # vendedor cai em /fila ao pedir a raiz, e esta tela é a do shell.
        # Os dois cargos têm o mesmo alcance, que é o que o seletor lê.
        alocar(ana, alfa, "representante", filial=norte)
        alocar(ana, alfa, "representante", filial=sul)

        html = self._html("ana-cab@teste.com")
        assert 'name="filial_id"' in html
        assert f'value="{norte.pk}" selected' in html
        assert ">Sul</option>" in html
        assert 'name="empresa_id"' not in html

    def test_membro_numa_filial_so_nao_tem_seletor(self, db):
        from tests.conftest import alocar

        _t, alfa, norte, _s = self._conta()
        ana = Usuario.objects.create_user(email="ana-uma@teste.com", password=SENHA)
        alocar(ana, alfa, "vendedor", filial=norte)

        assert 'name="filial_id"' not in self._html("ana-uma@teste.com")

    def test_titular_escolhe_entre_as_filiais_da_empresa_dele(self, db):
        self._conta()
        html = self._html("dono-cab@teste.com")
        assert 'name="filial_id"' in html
        assert ">Matriz</option>" in html and ">Norte</option>" in html
        assert 'name="empresa_id"' not in html
