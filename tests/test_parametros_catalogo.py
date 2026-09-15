"""`plataforma.parametro_catalogo`: o cruzamento entre o que o código
declara e o que o banco valeu — a peça central de R47 para parâmetros,
irmã de `tests/test_catalogo_de_modulos.py` para módulos.
"""

import pytest

from plataforma.parametro_declaracao import ParametroSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import parametro_declaracao

    guardado = parametro_declaracao._DECLARADOS.copy()
    parametro_declaracao._DECLARADOS.clear()
    yield
    parametro_declaracao._DECLARADOS.clear()
    parametro_declaracao._DECLARADOS.update(guardado)


NUMERO = ParametroSpec(
    chave="prazo_dias", rotulo="Prazo em dias", tipo="numero", padrao=30,
    grupo="Prazos", ajuda="Quantos dias.",
)
SIM_NAO = ParametroSpec(
    chave="cobra_juros", rotulo="Cobra juros", tipo="sim_nao", padrao=False,
    grupo="Prazos",
)
TEXTO = ParametroSpec(
    chave="apelido_sistema", rotulo="Apelido do sistema", tipo="texto",
    padrao="Kronos", grupo="Geral",
)


@pytest.mark.django_db
class TestValorDe:
    def test_sem_linha_no_banco_devolve_o_padrao_do_codigo(self, catalogo_limpo):
        from plataforma.parametro_catalogo import valor_de

        registrar(NUMERO)
        assert valor_de("prazo_dias") == 30

    def test_linha_no_banco_vence_o_padrao(self, catalogo_limpo):
        from plataforma.parametro_catalogo import definir, valor_de

        registrar(NUMERO)
        definir("prazo_dias", "45")
        assert valor_de("prazo_dias") == 45

    def test_numero_volta_como_int_de_verdade(self, catalogo_limpo):
        from plataforma.parametro_catalogo import definir, valor_de

        registrar(NUMERO)
        definir("prazo_dias", "45")
        assert isinstance(valor_de("prazo_dias"), int)

    def test_sim_nao_volta_como_bool(self, catalogo_limpo):
        from plataforma.parametro_catalogo import definir, valor_de

        registrar(SIM_NAO)
        definir("cobra_juros", "1")
        assert valor_de("cobra_juros") is True
        definir("cobra_juros", "0")
        assert valor_de("cobra_juros") is False

    def test_texto_volta_como_string(self, catalogo_limpo):
        from plataforma.parametro_catalogo import definir, valor_de

        registrar(TEXTO)
        definir("apelido_sistema", "Aurora")
        assert valor_de("apelido_sistema") == "Aurora"

    def test_chave_nao_declarada_e_erro(self, catalogo_limpo):
        from plataforma.parametro_catalogo import valor_de

        with pytest.raises(ValueError):
            valor_de("nao-existe")


@pytest.mark.django_db
class TestRestaurar:
    def test_restaurar_apaga_a_linha_e_o_valor_volta_ao_padrao(self, catalogo_limpo):
        from plataforma.parametro_catalogo import definir, restaurar, valor_de
        from plataforma.models import Parametro

        registrar(NUMERO)
        definir("prazo_dias", "45")
        restaurar("prazo_dias")

        assert not Parametro.objects.filter(chave="prazo_dias").exists()
        assert valor_de("prazo_dias") == 30

    def test_restaurar_o_que_nunca_foi_mudado_nao_quebra(self, catalogo_limpo):
        from plataforma.parametro_catalogo import restaurar

        registrar(NUMERO)
        restaurar("prazo_dias")  # não levanta


@pytest.mark.django_db
class TestParametrosEfetivos:
    def test_todo_declarado_aparece_mesmo_sem_linha(self, catalogo_limpo):
        from plataforma.parametro_catalogo import parametros_efetivos

        registrar(NUMERO)
        efetivos = parametros_efetivos()
        assert [e.chave for e in efetivos] == ["prazo_dias"]
        assert efetivos[0].valor == 30
        assert efetivos[0].no_padrao is True

    def test_com_linha_no_banco_no_padrao_fica_falso(self, catalogo_limpo):
        from plataforma.parametro_catalogo import definir, parametros_efetivos

        registrar(NUMERO)
        definir("prazo_dias", "45")
        efetivo = parametros_efetivos()[0]
        assert efetivo.valor == 45
        assert efetivo.no_padrao is False

    def test_linha_no_banco_sem_declaracao_no_codigo_e_ignorada(self, catalogo_limpo):
        """Mesma regra de `plataforma.catalogo.modulos_ligados`, e pelo
        mesmo motivo: um parâmetro removido do código deixa a linha para
        trás, e ela não pode voltar a valer sozinha."""
        from plataforma.parametro_catalogo import parametros_efetivos
        from plataforma.models import Parametro

        Parametro.objects.create(chave="fantasma", valor="1")
        assert parametros_efetivos() == ()

    def test_carrega_grupo_ajuda_e_so_mw5_do_codigo(self, catalogo_limpo):
        from plataforma.parametro_catalogo import parametros_efetivos

        so_mw5 = ParametroSpec(
            chave="x", rotulo="X", tipo="texto", padrao="", grupo="Técnico",
            ajuda="Só a MW5 mexe.", so_mw5=True,
        )
        registrar(so_mw5)
        efetivo = parametros_efetivos()[0]
        assert efetivo.grupo == "Técnico"
        assert efetivo.ajuda == "Só a MW5 mexe."
        assert efetivo.so_mw5 is True


class TestNormalizar:
    """Validação pura, sem banco — o que a tela chama ANTES de abrir a
    transação que grava (ver `plataforma.views_parametros.parametros`)."""

    def test_numero_valido_normaliza(self):
        from plataforma.parametro_catalogo import normalizar

        assert normalizar("numero", "45") == ("45", None)

    def test_numero_invalido_e_recusado(self):
        from plataforma.parametro_catalogo import normalizar

        valor, erro = normalizar("numero", "abc")
        assert valor is None
        assert erro

    def test_sim_nao_ausente_vira_zero(self):
        """Um `Checkbox` desmarcado não manda o campo — `bruto` chega
        `None`, e isso precisa virar "0", não um erro."""
        from plataforma.parametro_catalogo import normalizar

        assert normalizar("sim_nao", None) == ("0", None)

    def test_sim_nao_presente_vira_um(self):
        from plataforma.parametro_catalogo import normalizar

        assert normalizar("sim_nao", "on") == ("1", None)

    def test_texto_aceita_qualquer_string(self):
        from plataforma.parametro_catalogo import normalizar

        assert normalizar("texto", "qualquer coisa") == ("qualquer coisa", None)
