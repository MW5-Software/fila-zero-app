"""Os campos de um formulário: o modelo, e a leitura tolerante.

O que se testa aqui é o contrato dos oito tipos e a teimosia do leitor: isto
roda a cada tecla digitada no editor do gerador, e um campo pela metade não
pode derrubar a prévia de quem ainda está digitando. `montar_campos` é o que
o `Resource` usa para desenhar formulário de verdade — daí morar aqui, junto
do resto de `nucleo`.

Os dois caminhos (a prévia desenhada aqui e o arquivo que `codigo_dos_campos`
escreve) continuam testados em `mw5_generator/tests/test_geracao_campos.py` —
é lá que `codigo_dos_campos` mora, porque só o gerador escreve arquivo.
"""

import re

import pytest

from nucleo import catalogo
from nucleo.campos import (
    Campo,
    TIPOS_DE_CAMPO,
    campos_de_json,
    montar_campos,
    nome_do_campo,
)
from nucleo.rendering import create_environment, use_environment


@pytest.fixture(autouse=True)
def env():
    ambiente = create_environment()
    with use_environment(ambiente):
        yield ambiente


def html(campos) -> str:
    return "".join(str(c.render()) for c in montar_campos(campos))


class TestOsNoveTipos:
    @pytest.mark.parametrize("tipo,marca", [
        ("texto", 'type="text"'),
        ("area", "<textarea"),
        ("numero", 'type="number"'),
        ("moeda", 'inputmode="decimal"'),
        ("data", 'type="date"'),
        ("selecao", "<select"),
        ("sim_nao", 'type="checkbox"'),
        ("arquivo", 'type="file"'),
        # A relacao desenha um `<select>` como a selecao — o que muda e de onde
        # vem a lista: a selecao traz as opcoes escritas a mao, a relacao busca
        # os registros do cadastro apontado.
        ("relacao", "<select"),
    ])
    def test_cada_um_desenha_o_seu(self, tipo, marca):
        assert marca in html([Campo(rotulo="Campo", tipo=tipo)])

    def test_a_tabela_tem_exatamente_nove(self):
        """Igualdade, e nao "pelo menos": um tipo declarado que nada desenha e
        uma opcao no painel que produz um campo em branco."""
        assert len(TIPOS_DE_CAMPO) == 9

    def test_a_selecao_leva_as_opcoes(self):
        marcacao = html([Campo(rotulo="Situação", tipo="selecao",
                               opcoes=["Ativo", "Inativo"])])
        assert "Ativo" in marcacao and "Inativo" in marcacao

    def test_a_selecao_tem_a_opcao_neutra(self):
        assert "Selecione" in html([Campo(rotulo="X", tipo="selecao",
                                          opcoes=["A"])])


class TestOsAtributosComuns:
    def test_o_rotulo_aparece(self):
        assert "Razão social" in html([Campo(rotulo="Razão social")])

    def test_o_name_sai_do_rotulo(self):
        assert 'name="razao_social"' in html([Campo(rotulo="Razão social")])

    def test_obrigatorio_marca_o_campo(self):
        assert "required" in html([Campo(rotulo="X", obrigatorio=True)])

    def test_nao_obrigatorio_nao_marca(self):
        assert "required" not in html([Campo(rotulo="X")])

    def test_a_ajuda_aparece(self):
        assert "Só números" in html([Campo(rotulo="CPF", ajuda="Só números")])

    def test_a_largura_vira_span(self):
        assert "c4" in html([Campo(rotulo="X", largura=4)])


class TestLeituraTolerante:
    def test_string_pura_vira_campo_de_texto(self):
        campos = campos_de_json(["Nome"])
        assert campos == [Campo(rotulo="Nome")]

    def test_lista_misturando_string_e_dicionario(self):
        campos = campos_de_json(["Nome", {"rotulo": "Nascimento", "tipo": "data"}])
        assert [c.tipo for c in campos] == ["texto", "data"]

    def test_dicionario_pela_metade_ganha_os_padroes(self):
        assert campos_de_json([{"rotulo": "X"}]) == [Campo(rotulo="X")]

    def test_json_em_texto_tambem_serve(self):
        assert campos_de_json('[{"rotulo": "X"}]') == [Campo(rotulo="X")]

    def test_lixo_devolve_lista_vazia(self):
        for cru in (None, "", "{", 42, {"a": 1}):
            assert campos_de_json(cru) == []

    @pytest.mark.parametrize("cru,esperado", [
        ({"rotulo": "X", "tipo": "bolha"}, "texto"),
        ({"rotulo": "X", "tipo": ""}, "texto"),
        ({"rotulo": "X"}, "texto"),
    ])
    def test_tipo_desconhecido_vira_texto(self, cru, esperado):
        assert campos_de_json([cru])[0].tipo == esperado

    @pytest.mark.parametrize("largura,esperada", [
        (12, 12), (6, 6), (4, 4), (3, 3),
        (5, 4), (10, 12), (1, 3), (99, 12), (0, 3),
        ("", 6), (None, 6), ("oito", 6),
    ])
    def test_largura_e_ajustada_e_nao_recusada(self, largura, esperada):
        assert campos_de_json([{"rotulo": "X", "largura": largura}])[0].largura == esperada

    def test_campo_sem_rotulo_vira_Campo(self):
        """Some enquanto alguém digita seria pior — a mesma escolha que o
        bloco de gráfico faz com um ponto sem rótulo."""
        assert campos_de_json([{"rotulo": ""}])[0].rotulo == "Campo"

    def test_selecao_sem_opcao_nao_quebra(self):
        assert "<select" in html([Campo(rotulo="X", tipo="selecao")])

    def test_item_que_nao_e_dicionario_nem_string_e_pulado(self):
        assert campos_de_json([{"rotulo": "A"}, 42, ["b"]]) == [Campo(rotulo="A")]


class TestNomeDoCampo:
    @pytest.mark.parametrize("rotulo,nome", [
        ("Razão social", "razao_social"),
        ("CPF/CNPJ", "cpf_cnpj"),
        ("E-mail", "e_mail"),
        ("  Nome  ", "nome"),
        ("1º contato", "n1o_contato"),
    ])
    def test_vira_identificador_valido(self, rotulo, nome):
        assert nome_do_campo(rotulo) == nome

    def test_nunca_comeca_com_digito(self):
        assert not nome_do_campo("2 vias")[0].isdigit()


class _FakePagina:
    def __init__(self, itens):
        self.itens = itens


class _FakeRepositorio:
    def __init__(self, itens):
        self._itens = itens

    def listar(self, por_pagina):
        return _FakePagina(self._itens)


class _FakeItem:
    def __init__(self, id):
        self.id = id


class _FakeResource:
    """Duplo mínimo do `Resource` que só chega na entrega 3 (`dados/resource.py`).

    `_opcoes_da_relacao` só lê três coisas de quem o catálogo devolve: `.rota`
    (para o registro), `.repositorio.listar(por_pagina=...)` e `.campos`
    (que `rotulo_do_registro` usa). Um objeto real do `Resource` traria muito
    mais do que este teste precisa."""

    def __init__(self, rota, itens):
        self.rota = rota
        self.campos = []
        self.repositorio = _FakeRepositorio(itens)


def _select_aberto(marcacao: str) -> str:
    """Só a tag `<select ...>`, sem as `<option>` de dentro.

    A opção neutra de toda Relação/Seleção carrega `disabled` sempre — é o
    que a impede de ser reescolhida depois que a pessoa já digitou algo. Por
    isso `"disabled" in marcacao` não distingue "o select inteiro está
    desabilitado" de "a opção neutra está desabilitada, como sempre está"."""
    return re.search(r"<select[^>]*>", marcacao).group()


class TestRelacaoNoCatalogoDestaEntrega:
    """Autoral — não vem da fonte.

    Nesta entrega o catálogo está sempre vazio: quem o povoa (`Resource`) só
    chega na entrega 3. Isso faz do ramo "alvo ausente" de
    `_opcoes_da_relacao`/`_relacao` o único que roda de verdade em produção
    hoje — e a suíte portada não o exercita: o `parametrize` de
    `TestOsNoveTipos` só confere que sai `<select`, o que passa igual pelos
    dois ramos. Cobre os dois lados porque olhar só o ramo vazio não
    distingue "desabilitou porque não achou o alvo" de "desabilita sempre"."""

    def setup_method(self):
        catalogo.esquecer_tudo()

    def teardown_method(self):
        catalogo.esquecer_tudo()

    def test_alvo_ausente_no_catalogo_desabilita_o_select(self):
        marcacao = html([Campo(rotulo="Cliente", tipo="relacao", alvo="/clientes")])
        assert "disabled" in _select_aberto(marcacao)
        assert "Cadastro não encontrado" in marcacao

    def test_alvo_presente_no_catalogo_habilita_o_select(self):
        catalogo.registrar(_FakeResource("/clientes", [_FakeItem(1), _FakeItem(2)]))
        marcacao = html([Campo(rotulo="Cliente", tipo="relacao", alvo="/clientes")])
        assert "disabled" not in _select_aberto(marcacao)
        assert "Cadastro não encontrado" not in marcacao
