"""O código diz quais parâmetros existem; o banco diz o que valem numa
instalação — o mesmo mecanismo do catálogo de módulos
(`tests/test_catalogo_de_modulos.py`), aplicado a R47.
"""

import pytest

from plataforma.parametro_declaracao import ParametroSpec, declarados, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import parametro_declaracao

    guardado = parametro_declaracao._DECLARADOS.copy()
    parametro_declaracao._DECLARADOS.clear()
    yield
    parametro_declaracao._DECLARADOS.clear()
    parametro_declaracao._DECLARADOS.update(guardado)


ESPECIE = ParametroSpec(
    chave="prazo_dias", rotulo="Prazo em dias", tipo="numero", padrao=30,
    grupo="Prazos",
)


class TestADeclaracao:
    def test_um_parametro_declarado_aparece(self, catalogo_limpo):
        registrar(ESPECIE)
        assert ESPECIE in declarados()

    def test_declarar_a_mesma_chave_duas_vezes_e_erro(self, catalogo_limpo):
        registrar(ESPECIE)
        with pytest.raises(ValueError):
            registrar(ESPECIE)

    def test_a_declaracao_e_imutavel(self, catalogo_limpo):
        with pytest.raises(Exception):
            ESPECIE.rotulo = "outro"

    def test_sem_chave_e_erro(self, catalogo_limpo):
        with pytest.raises(ValueError):
            ParametroSpec(chave="  ", rotulo="X", tipo="texto", padrao="")

    def test_sem_rotulo_e_erro(self, catalogo_limpo):
        with pytest.raises(ValueError):
            ParametroSpec(chave="x", rotulo=" ", tipo="texto", padrao="")

    def test_tipo_desconhecido_e_erro(self, catalogo_limpo):
        with pytest.raises(ValueError):
            ParametroSpec(chave="x", rotulo="X", tipo="cor", padrao="#000")

    def test_padrao_de_tipo_errado_e_erro(self, catalogo_limpo):
        """Um `numero` com `padrao="30"` (string, não int) só apareceria
        quebrado na hora de gravar ou de mostrar na tela — melhor quebrar na
        declaração, onde o autor do parâmetro está olhando."""
        with pytest.raises(ValueError):
            ParametroSpec(chave="x", rotulo="X", tipo="numero", padrao="30")

    def test_bool_nao_serve_de_padrao_para_numero(self, catalogo_limpo):
        """`bool` é subclasse de `int` em Python — sem a checagem extra,
        `padrao=True` passaria por um `numero` calado."""
        with pytest.raises(ValueError):
            ParametroSpec(chave="x", rotulo="X", tipo="numero", padrao=True)

    def test_sim_nao_exige_padrao_booleano(self, catalogo_limpo):
        with pytest.raises(ValueError):
            ParametroSpec(chave="x", rotulo="X", tipo="sim_nao", padrao=1)

    def test_texto_exige_padrao_string(self, catalogo_limpo):
        with pytest.raises(ValueError):
            ParametroSpec(chave="x", rotulo="X", tipo="texto", padrao=1)

    def test_so_mw5_e_false_por_padrao(self, catalogo_limpo):
        """Regra geral: parâmetro é do admin do cliente, até o autor decidir
        o contrário — mesmo raciocínio do `ativo_por_padrao=False` de
        `ModuloSpec` (a exceção precisa ser dita, não presumida)."""
        assert ParametroSpec(
            chave="x", rotulo="X", tipo="texto", padrao="",
        ).so_mw5 is False
