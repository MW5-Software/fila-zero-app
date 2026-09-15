"""A guarda de "módulo ligado", em `comum/guardas_de_modulo.py`.

Reutilizável de propósito: todo módulo futuro vai precisar dela, não só o
Exemplo. Por isso ela é testada aqui, isolada — sem depender de nenhuma rota
de `modulos/exemplo/` — e qualquer módulo novo que a componha com
`exigir_permissao` já sai coberto pelo mesmo comportamento.

A segunda metade deste arquivo (`TestNenhumaRotaDeModuloNasceSemAGuarda`) é a
varredura irmã da de `tests/test_guarda.py`: aquela prova que toda rota exige
login ou permissão; esta prova que toda rota que pertence a um `ModuloSpec`
declarado também carrega a marca `.modulo` que `exigir_modulo_ligado`
grava — sem essa marca, um autor de módulo que esquecesse o decorator
entregaria uma tela que abre com o módulo desligado, e não haveria como
perguntar isso depois do fato.

Não filtra por pacote (`modulos.*`): a versão original desta varredura
filtrava assim, e `perfis`/`usuarios` moram em `contas/` — passaram batido, e
foi exatamente esse buraco que deixou as duas rotas responderem 200 com o
módulo desligado (revisão final do branch, o item mais crítico dela). A
varredura agora caminha `plataforma.declaracao.declarados()`, a fonte de
verdade de "isto é um módulo", e resolve a `ModuloSpec.rota` de cada um até a
view de verdade — não importa em qual pacote ela mora.
"""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory


@pytest.mark.django_db
class TestExigirModuloLigado:
    def test_modulo_desligado_responde_como_inexistente(self):
        from comum.guardas_de_modulo import exigir_modulo_ligado
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=False)

        @exigir_modulo_ligado("fantasma")
        def tela(request):
            return HttpResponse("segredo")

        resposta = tela(RequestFactory().get("/fantasma"))
        assert resposta.status_code == 404

    def test_modulo_sem_linha_nenhuma_no_banco_tambem_e_404(self):
        """Fail closed: nenhuma linha para a chave não pode significar
        "libera" — significa que a instalação nunca ligou (ou nunca
        recebeu) este módulo."""
        from comum.guardas_de_modulo import exigir_modulo_ligado

        @exigir_modulo_ligado("nunca-existiu")
        def tela(request):
            return HttpResponse("segredo")

        resposta = tela(RequestFactory().get("/nunca-existiu"))
        assert resposta.status_code == 404

    def test_modulo_ligado_deixa_passar(self):
        from comum.guardas_de_modulo import exigir_modulo_ligado
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=True)

        @exigir_modulo_ligado("fantasma")
        def tela(request):
            return HttpResponse("segredo")

        resposta = tela(RequestFactory().get("/fantasma"))
        assert resposta.status_code == 200
        assert resposta.content == b"segredo"

    def test_desligar_de_volta_tranca_de_novo(self):
        """A guarda lê o banco a cada chamada, não uma vez só: desligar
        depois de ter ligado tranca a rota de novo, na mesma instalação, sem
        reiniciar processo nenhum."""
        from comum.guardas_de_modulo import exigir_modulo_ligado
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=True)

        @exigir_modulo_ligado("fantasma")
        def tela(request):
            return HttpResponse("segredo")

        pedido = RequestFactory().get("/fantasma")
        assert tela(pedido).status_code == 200

        Modulo.objects.filter(chave="fantasma").update(ativo=False)
        assert tela(pedido).status_code == 404

    def test_a_guarda_marca_a_chave_do_modulo_na_view(self):
        """A marca que permite perguntar, depois do fato, se a guarda foi
        aplicada — espelha `.permissao` em `comum.guardas_de_acesso.exigir_permissao`."""
        from comum.guardas_de_modulo import exigir_modulo_ligado

        @exigir_modulo_ligado("fantasma")
        def tela(request):
            return HttpResponse("segredo")

        assert tela.modulo == "fantasma"


class TestNenhumaRotaDeModuloNasceSemAGuarda:
    """A varredura irmã da de `tests/test_guarda.py`."""

    def test_toda_rota_declarada_carrega_a_guarda_de_modulo(self):
        """Caminha o catálogo (não o pacote): qualquer `ModuloSpec` com
        `rota`, esteja ela em `modulos/exemplo/` ou em `contas/`, precisa
        resolver para uma view que carregue `.modulo` — a mesma marca que
        `test_a_guarda_marca_a_chave_do_modulo_na_view`, acima, prova que
        `exigir_modulo_ligado` grava."""
        from django.urls import resolve
        from plataforma.declaracao import declarados
        from comum.guardas_de_modulo import SEM_GUARDA_DE_MODULO

        desprotegidas = []
        for spec in declarados():
            if not spec.rota:
                # Rota é opcional em `ModuloSpec` (nem todo módulo tem tela
                # própria) — sem rota, não há view nenhuma para cobrar a
                # marca. `tests/test_rota_do_modulo_bate_com_url.py` já cobre
                # que toda `rota` declarada resolve para algo real.
                continue
            correspondencia = resolve(spec.rota)
            if correspondencia.url_name in SEM_GUARDA_DE_MODULO:
                continue
            if getattr(correspondencia.func, "modulo", None) != spec.chave:
                desprotegidas.append(correspondencia.url_name or spec.rota)

        assert not desprotegidas, (
            f"rotas de módulo declarado sem a guarda de módulo ligado: "
            f"{desprotegidas}. Ou decore a view com @exigir_modulo_ligado, ou "
            f"declare em SEM_GUARDA_DE_MODULO (comum/guardas_de_modulo.py) dizendo "
            f"por quê."
        )


@pytest.mark.django_db
class TestAIsencaoDasTelasDaMw5:
    """A lista de isenção não pode virar gaveta.

    As três telas da MW5 entraram nela quando viraram módulos declarados. O
    motivo está escrito ao lado da lista; estes testes seguram que ele
    continua VERDADE — uma isenção cujo motivo deixou de valer é pior que
    nenhuma, porque ninguém relê a lista.
    """

    def test_a_isencao_cobre_exatamente_as_telas_da_mw5(self):
        from comum.guardas_de_modulo import SEM_GUARDA_DE_MODULO
        from plataforma.declaracao import declarados

        da_casa = {spec.chave for spec in declarados() if spec.so_mw5}
        assert SEM_GUARDA_DE_MODULO == da_casa

    def test_nenhum_modulo_de_negocio_esta_isento(self):
        """Ali desligar é o que a tela de Módulos faz, e a rota precisa
        travar junto — senão o interruptor é enfeite."""
        from comum.guardas_de_modulo import SEM_GUARDA_DE_MODULO
        from plataforma.declaracao import declarados

        por_chave = {spec.chave: spec for spec in declarados()}
        for chave in SEM_GUARDA_DE_MODULO:
            assert por_chave[chave].so_mw5, chave
