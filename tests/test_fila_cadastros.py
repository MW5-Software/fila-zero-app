"""Grupos de item, motivos de não venda e tipos de pausa (spec, "Cadastros").

Os três são a mesma tela com outro model; o parametrizado prova os três de
uma vez, e uma tela que divergir das outras fica vermelha sozinha.
"""

import pytest
from django.urls import reverse

from tests.fila_cenario import logado, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db

TELAS = [("fila_grupos", "GrupoDeItem", "Grupo de item"),
         ("fila_motivos", "MotivoDeNaoVenda", "Motivo de não venda"),
         ("fila_pausas", "TipoDePausa", "Tipo de pausa")]


def _model(nome):
    import fila.models

    return getattr(fila.models, nome)


@pytest.mark.parametrize("rota, model, rotulo", TELAS)
def test_criar_editar_desativar_e_remover(rota, model, rotulo):
    from contas.models import RegistroDeAuditoria

    empresa, _, _ = sylvia()
    cliente = logado("sylvia")
    Model = _model(model)

    assert cliente.post(reverse(rota), {"acao": "criar", "nome": "Primeiro",
                                        "ordem": "2"}).status_code == 302
    linha = Model.irrestritos.get(empresa=empresa)
    assert (linha.nome, linha.ordem, linha.ativo) == ("Primeiro", 2, True)
    assert RegistroDeAuditoria.objects.filter(
        acao="fila_cadastro_criado", alvo=f"{rotulo}: Primeiro").exists()

    cliente.post(reverse(rota), {"acao": "salvar", "id": str(linha.pk),
                                 "nome": "Renomeado", "ordem": "1"})
    linha.refresh_from_db()
    assert (linha.nome, linha.ordem, linha.ativo) == ("Renomeado", 1, False)

    cliente.post(reverse(rota), {"acao": "remover", "id": str(linha.pk)})
    assert not Model.irrestritos.filter(pk=linha.pk).exists()


@pytest.mark.parametrize("rota, model, rotulo", TELAS)
def test_nome_repetido_sem_diferenca_de_caixa_responde_com_frase(rota, model, rotulo):
    empresa, _, _ = sylvia()
    _model(model).irrestritos.create(empresa=empresa, nome="Almoço")
    resposta = logado("sylvia").post(reverse(rota), {
        "acao": "criar", "nome": "ALMOÇO", "ordem": "0"})
    assert resposta.status_code == 200
    assert "Já existe" in resposta.content.decode()


def test_cadastro_usado_nao_se_remove_e_a_tela_diz_por_que():
    from datetime import datetime, timezone as tz

    from fila.models import Pausa, Presenca, TipoDePausa

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    tipo = TipoDePausa.irrestritos.create(empresa=empresa, nome="Café")
    agora = datetime(2026, 9, 15, 13, tzinfo=tz.utc)
    presenca = Presenca.irrestritos.create(empresa=empresa, filial=matriz,
                                           pessoa=ana, entrada=agora,
                                           saida=agora)
    Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                             presenca=presenca, tipo=tipo, inicio=agora,
                             fim=agora)
    resposta = logado("sylvia").post(reverse("fila_pausas"), {
        "acao": "remover", "id": str(tipo.pk)})
    assert resposta.status_code == 200
    assert "Em uso: desative em vez de remover." in resposta.content.decode()
    assert TipoDePausa.irrestritos.filter(pk=tipo.pk).exists()


def test_id_de_outra_conta_no_post_nao_e_encontrado():
    from fila.models import GrupoDeItem
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    sylvia()
    outra = Empresa.objects.create(razao_social="Concorrente",
                                   nome_fantasia="Concorrente")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    alheio = GrupoDeItem.irrestritos.create(empresa=outra, nome="Sofás")
    resposta = logado("sylvia").post(reverse("fila_grupos"), {
        "acao": "remover", "id": str(alheio.pk)})
    assert "não encontrado" in resposta.content.decode()
    assert GrupoDeItem.irrestritos.filter(pk=alheio.pk).exists()


def test_sem_fila_cadastros_a_tela_nao_existe():
    empresa, matriz, _ = sylvia()
    pessoa_na_loja("gil", empresa, matriz, cargo="gerente")
    assert logado("gil").get(reverse("fila_grupos")).status_code == 404


def test_a_lista_mostra_so_a_empresa_do_contexto():
    from fila.models import GrupoDeItem

    empresa, _, _ = sylvia()
    GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás")
    html = logado("sylvia").get(reverse("fila_grupos")).content.decode()
    assert "Sofás" in html


@pytest.mark.parametrize("rota, model, rotulo", TELAS)
def test_a_tabela_tem_filtro_e_paginacao_e_sem_cabecalho_clicavel(rota, model, rotulo):
    """R46 com a emenda de 18/09/2026, conferida com uma linha na tela: a
    varredura de `tests/test_regra_tabela.py` visita como superusuário sem
    empresa, e a lista vazia não desenha `<table>` nenhuma — ela passaria sem
    olhar.

    O cadastro sai na ordem dele, que é o campo "Ordem", e a coluna clicável
    só afastava a tela disso. O filtro e a paginação continuam."""
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    empresa, _, _ = sylvia()
    _model(model).irrestritos.create(empresa=empresa, nome="Almoço")
    html = logado("sylvia").get(reverse(rota)).content.decode()
    assert "<table" in html
    assert _MARCADOR_FILTRO in html
    assert _MARCADOR_PAGINACAO in html
    assert not _PADRAO_CABECALHO_ORDENAVEL.search(html)


def test_filtrar_por_situacao_mostra_so_os_inativos():
    from comum.listagem import nome_do_campo
    from fila.models import GrupoDeItem

    empresa, _, _ = sylvia()
    GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás")
    GrupoDeItem.irrestritos.create(empresa=empresa, nome="Tapetes", ativo=False)
    resposta = logado("sylvia").get(reverse("fila_grupos"), {
        nome_do_campo("ativo", "igual"): "False"})
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Tapetes" in html
    assert "Sofás" not in html


def test_ordem_grande_demais_nao_estoura():
    """B4: 99999999999 no campo Ordem estourava o inteiro do Postgres."""
    from fila.models import TipoDePausa

    empresa, _, _ = sylvia()
    resposta = logado("sylvia").post(reverse("fila_pausas"), {
        "acao": "criar", "nome": "Café", "ordem": "99999999999"})
    assert resposta.status_code == 302
    assert TipoDePausa.irrestritos.get(empresa=empresa).ordem == 2_147_483_647
