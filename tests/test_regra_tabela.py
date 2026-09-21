"""R46 (`docs/superpowers/decisoes-2026-08-20-fatia-fina.md`): toda tela que
lista registros numa tabela tem filtro, ordenação por coluna e paginação —
sem exceção, porque uma tabela sem as três funciona na instalação de
demonstração e para de funcionar no primeiro cliente de verdade.

A varredura irmã de `tests/test_guarda.py` (nenhuma tela nasce sem guarda) e
da varredura de personificação em `tests/test_personificacao.py` (nenhuma
tela 200 esconde o aviso): percorre toda rota do projeto, e para toda
resposta que contiver uma `<table>`, exige na mesma página o campo de
filtro, os controles de paginação e pelo menos um cabeçalho ordenável. Tela
nova que esqueça um dos três vira teste vermelho aqui, antes de virar
reclamação de cliente.

**O cabeçalho ordenável saiu das tabelas do app da fila** em 18/09/2026, a
pedido do cliente: o ranking já tem a ordem que interessa (vendido, do maior
para o menor) e as listas de cadastro saem na ordem delas. Filtro e paginação
continuam obrigatórios para todo mundo, e quem cobra os três nas telas da fila
são os testes de cada tela (`test_fila_tela_indicadores.py`,
`test_fila_historico.py`, `test_fila_cadastros.py`,
`test_fila_painel_do_vendedor.py`) — esta varredura não as alcança, porque
visita como superusuário sem empresa, e as telas da fila só desenham tabela
com uma loja no contexto.
"""

import re

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import get_resolver, reverse
from django.urls.resolvers import URLPattern, URLResolver

SENHA = "segredo-de-teste"

#: Marcadores estáveis de cada um dos três controles — a estrutura HTML dos
#: componentes do design system (`nucleo/templates/components/*.html`), não
#: o texto visível, para a varredura continuar valendo se a cópia mudar.
# O filtro de R46 é a barra acima da tabela, com um campo por coluna
# filtrável — o mesmo desenho do `sementes-premix` (`app/tela_grid.py`), e não
# uma busca livre única. O marcador é o `name` dos campos, que sempre começa
# com o prefixo do vocabulário de filtro: uma `FilterBar` vazia, ou com um
# `q` genérico, não passa por aqui.
_MARCADOR_FILTRO = 'name="f:'
_MARCADOR_PAGINACAO = 'class="pager"'  # `Pagination` — sempre desenha o
# `<div class="pager">`, mesmo com uma página só (só o `<nav>` de números é
# que só aparece com mais de uma).
_PADRAO_CABECALHO_ORDENAVEL = re.compile(r"<th[^>]*>\s*<a\b")  # um `<a>`
# dentro de um `<th>` só existe porque `Column.label` recebeu um `Markup`
# de link — ver `comum.listagem.montar_pagina` e o comentário de R46
# em `docs/superpowers/decisoes-2026-08-20-fatia-fina.md`.


def _caminho_concreto(padrao: URLPattern) -> "str | None":
    """Ver o par exato em `tests/test_personificacao.py::_caminho_concreto`
    — mesma regra, mesmo motivo: troca qualquer conversor de rota por um
    valor de mentira, para a varredura andar por cima de rota com argumento
    sem precisar de `reverse()`."""
    rota = str(padrao.pattern)

    def _valor_de_mentira(m: "re.Match") -> str:
        return {"int": "1", "slug": "x", "uuid":
                 "00000000-0000-0000-0000-000000000000"}.get(m.group(1), "x")

    return re.sub(r"<(\w+):\w+>", _valor_de_mentira, rota)


def _rotas_com_caminho():
    """Toda rota do projeto, como `(nome, caminho)` — mesma implementação e
    mesmo motivo de `tests/test_personificacao.py::_rotas_com_caminho`:
    caminha `get_resolver().url_patterns` recursivamente, nunca `reverse()`,
    para uma rota com argumento não ser pulada em silêncio."""

    def caminhar(padroes):
        for padrao in padroes:
            if isinstance(padrao, URLResolver):
                yield from caminhar(padrao.url_patterns)
            elif isinstance(padrao, URLPattern):
                yield padrao.name, _caminho_concreto(padrao)

    return list(caminhar(get_resolver().url_patterns))


@pytest.fixture
def raiz(db) -> Usuario:
    """Superusuário: alcança `/cargos` e `/usuarios` (módulos que nascem
    ligados, `ativo_por_padrao=True` — ver `contas.modulo`) e também as
    telas da MW5 (`aparencia`, `modulos`), que só respondem para
    `is_superuser`. Não precisa de nenhuma permissão concedida à mão."""
    return Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)


@pytest.fixture
def raiz_logado(raiz) -> Client:
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
    return c


@pytest.mark.django_db
class TestTodaTabelaTemFiltroOrdenacaoEPaginacao:
    #: Rotas onde uma `<table>` na página não precisa das três exigências,
    #: e o motivo de cada uma — mesmo espírito de `comum.guardas_de_acesso.
    #: TELAS_ABERTAS` e do `ISENTAS` de `tests/test_personificacao.py`: uma
    #: lista curta, com o motivo ao lado, para "esqueci" nunca ser a razão
    #: de um nome entrar aqui.
    ISENTAS = frozenset({
        # A vitrine de componentes (`nucleo/views.py::demonstracao`) desenha
        # uma `Table` de mentira ("Cidade"/"UF", duas linhas fixas) só para
        # mostrar como o componente parece — não lista registro nenhum, e
        # os cartões de `FilterBar` e `Pagination` da MESMA página são,
        # pelo mesmo motivo, outra vitrine avulsa, não o trio aplicado a
        # ESTA tabela. R46 é sobre telas que listam dados de verdade; isto
        # é a exceção explícita, e não um alargamento silencioso do padrão
        # de busca para não bater aqui.
        "demonstracao",
    })

    #: Rotas cujo cabeçalho NÃO é clicável, e o motivo (emenda à R46,
    #: 18/09/2026): a pedido do cliente, a ordem das colunas saiu das tabelas
    #: do app da fila. Filtro e paginação continuam exigidos para elas como
    #: para qualquer outra — o que a lista abaixo dispensa é SÓ a ordenação.
    #:
    #: A varredura hoje não alcança estas rotas (o superusuário dela não tem
    #: empresa, e as telas da fila só montam tabela com uma loja no contexto);
    #: a lista fica aqui porque é ela que diz o que fazer no dia em que
    #: alcançar, e `test_a_lista_so_tem_rota_que_existe` impede que um nome
    #: velho apodreça em silêncio.
    SEM_ORDENACAO = frozenset({
        "inicio", "fila_historico", "fila_grupos", "fila_motivos",
        "fila_pausas",
    })

    def test_a_lista_so_tem_rota_que_existe(self):
        """Uma isenção com nome de rota que mudou não isenta nada, e ainda
        esconde que a regra deixou de ser cobrada — o mesmo motivo de
        `test_toda_varredura_da_tabela_existe` no `CLAUDE.md`."""
        nomes = {nome for nome, _caminho in _rotas_com_caminho()}
        assert self.SEM_ORDENACAO <= nomes, (
            f"a lista de isenção cita rotas que não existem: "
            f"{sorted(self.SEM_ORDENACAO - nomes)}")

    def test_toda_tabela_tem_filtro_ordenacao_e_paginacao(self, raiz_logado):
        problemas = []
        for nome, caminho in _rotas_com_caminho():
            if nome in self.ISENTAS:
                continue
            resposta = raiz_logado.get("/" + caminho)
            if resposta.status_code != 200:
                continue
            if not resposta.get("Content-Type", "").startswith("text/html"):
                continue
            html = resposta.content.decode()
            if "<table" not in html:
                continue

            faltando = []
            if _MARCADOR_FILTRO not in html:
                faltando.append("filtro")
            if _MARCADOR_PAGINACAO not in html:
                faltando.append("paginação")
            if (nome not in self.SEM_ORDENACAO
                    and not _PADRAO_CABECALHO_ORDENAVEL.search(html)):
                faltando.append("cabeçalho ordenável")
            if faltando:
                problemas.append(f"{nome or caminho}: falta {', '.join(faltando)}")

        assert not problemas, (
            f"telas com <table> sem alguma das três exigências de R46 "
            f"(filtro, ordenação por coluna, paginação): {problemas}. Ou "
            f"monte a listagem com `comum.listagem.montar_pagina`, ou "
            f"justifique a isenção em `ISENTAS`."
        )


class TestTodaListaDaApiTemFiltroOrdenacaoEPaginacao:
    """A R46 para a API, lida do contrato (OpenAPI) e não das respostas.

    Toda resposta com `itens` precisa trazer o resto da página — sem isso, a
    lista funciona com doze linhas e para de funcionar no primeiro cliente de
    verdade, igual à tabela sem paginação. E nenhuma operação devolve lista
    crua: uma lista crua não tem onde pôr total, página nem colunas.
    """

    CAMPOS_DA_PAGINA = ("pagina", "por_pagina", "total", "ordenar", "colunas")

    def test_toda_lista_traz_a_pagina_inteira(self):
        from config.api import api

        doc = api.get_openapi_schema(path_prefix="/api/")
        esquemas = doc["components"]["schemas"]

        def resolver(no):
            while isinstance(no, dict) and "$ref" in no:
                no = esquemas[no["$ref"].rsplit("/", 1)[-1]]
            return no

        problemas, listas = [], 0
        for caminho, metodos in doc["paths"].items():
            for metodo, operacao in metodos.items():
                for status, resposta in operacao.get("responses", {}).items():
                    if not str(status).startswith("2"):
                        continue
                    esquema = resolver(resposta.get("content", {})
                                       .get("application/json", {}).get("schema", {}))
                    if esquema.get("type") == "array":
                        problemas.append(f"{metodo.upper()} {caminho}: lista crua")
                        continue
                    propriedades = esquema.get("properties", {})
                    if "itens" not in propriedades:
                        continue
                    listas += 1
                    faltando = [c for c in self.CAMPOS_DA_PAGINA if c not in propriedades]
                    if faltando:
                        problemas.append(f"{metodo.upper()} {caminho}: falta {faltando}")

        assert not problemas, (
            f"listas da API fora da R46: {problemas}. Herde de "
            f"`comum.esquemas_da_api.Pagina` e monte com `comum.listagem.listar_para_api`.")
        assert listas, "nenhuma lista na API — a varredura olharia o vazio"
