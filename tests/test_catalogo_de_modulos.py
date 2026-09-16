"""O código diz quais módulos existem; o banco diz quais estão ligados.

Esta é a peça central da spec. Sem ela, um módulo novo custa vinte
intervenções manuais — e é exatamente esse custo que o KRONOS.net existe para
eliminar.
"""

import pytest

from plataforma.declaracao import ModuloSpec, declarados, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


ESPECIE = ModuloSpec(
    chave="frete", rotulo="Frete", icone="truck", grupo="Consultas",
    rota="/frete", permissoes=("frete.ver", "frete.editar"),
)


class TestADeclaracao:
    def test_um_modulo_declarado_aparece(self, catalogo_limpo):
        registrar(ESPECIE)
        assert ESPECIE in declarados()

    def test_declarar_a_mesma_chave_duas_vezes_e_erro(self, catalogo_limpo):
        """Duas pastas com a mesma chave dariam menu duplicado e permissão
        ambígua. Melhor quebrar na subida."""
        registrar(ESPECIE)
        with pytest.raises(ValueError):
            registrar(ESPECIE)

    def test_a_declaracao_e_imutavel(self, catalogo_limpo):
        with pytest.raises(Exception):
            ESPECIE.rotulo = "outro"


@pytest.mark.django_db
class TestASemeadura:
    def test_o_modulo_novo_nasce_desligado(self, catalogo_limpo):
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        assert semear() == 1
        assert Modulo.objects.get(chave="frete").ativo is False

    def test_ativo_por_padrao_nasce_ligado(self, catalogo_limpo):
        """A saída de `ModuloSpec.ativo_por_padrao=True` — sem ela, TODO
        módulo nasceria desligado, inclusive um da própria plataforma sem o
        qual a instalação nasce manca (ver `contas/modulo.py`). Regressão que
        a revisão da Task 8 pediu depois de flipar o valor de verdade e ver
        a suíte inteira continuar verde."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ModuloSpec(
            chave="frete", rotulo="Frete", ativo_por_padrao=True))
        assert semear() == 1
        assert Modulo.objects.get(chave="frete").ativo is True

    def test_semear_duas_vezes_nao_duplica(self, catalogo_limpo):
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        assert semear() == 0
        assert Modulo.objects.filter(chave="frete").count() == 1

    def test_semear_nao_desliga_o_que_ja_estava_ligado(self, catalogo_limpo):
        """A atualização que traz o módulo novo não pode apagar a escolha que
        a MW5 já tinha feito nos outros."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)
        semear()
        assert Modulo.objects.get(chave="frete").ativo is True


@pytest.mark.django_db
class TestOsLigados:
    def test_so_vem_o_que_esta_ligado(self, catalogo_limpo):
        from plataforma.catalogo import modulos_ligados, semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        assert modulos_ligados() == ()

        Modulo.objects.filter(chave="frete").update(ativo=True)
        assert [m.chave for m in modulos_ligados()] == ["frete"]

    def test_linha_no_banco_sem_declaracao_no_codigo_e_ignorada(self, catalogo_limpo):
        """Um módulo removido do código deixa a linha para trás. Ela não pode
        virar item de menu apontando para rota que não existe."""
        from plataforma.catalogo import modulos_ligados
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=True)
        assert modulos_ligados() == ()

    def test_desligar_nao_apaga_dado(self, catalogo_limpo):
        """Desligar some da tela; não apaga registro. Apagar dado de cliente
        numa chavinha seria caro demais."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)
        Modulo.objects.filter(chave="frete").update(ativo=False)
        assert Modulo.objects.filter(chave="frete").exists()


@pytest.mark.django_db
class TestAMesclagem:
    """A regra "o banco vence o código" mora em `modulos_ligados()`, não em
    quem a consome — é o que impede o menu e a tela de Módulos de terem cada
    um sua própria ideia do que é um módulo nesta instalação."""

    def test_sem_sobrescrita_vence_o_codigo(self, catalogo_limpo):
        from plataforma.catalogo import modulos_ligados, semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)

        ligado = modulos_ligados()[0]
        assert ligado.rotulo == "Frete"
        assert ligado.grupo == "Consultas"

    def test_com_sobrescrita_vence_o_banco(self, catalogo_limpo):
        from plataforma.catalogo import modulos_ligados, semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(
            ativo=True, rotulo="Transporte", grupo="Logística", ordem=5,
        )

        ligado = modulos_ligados()[0]
        assert ligado.rotulo == "Transporte"
        assert ligado.grupo == "Logística"
        assert ligado.ordem == 5

    def test_icone_rota_e_permissoes_nunca_vem_do_banco(self, catalogo_limpo):
        """Ícone e rótulo são aparência, o cliente pode pedir. Rota e
        permissão são contrato — o banco não tem como field para isso, e
        `ModuloLigado` sempre os traz do código."""
        from plataforma.catalogo import modulos_ligados, semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)

        ligado = modulos_ligados()[0]
        assert ligado.icone == "truck"
        assert ligado.rota == "/frete"
        assert ligado.permissoes == ("frete.ver", "frete.editar")


class TestAChaveDoModulo:
    """A chave vira prefixo de permissão, e o prefixo é cortado no primeiro
    sublinhado. Chave com sublinhado quebraria a concessão em silêncio."""

    def test_chave_com_sublinhado_e_recusada(self):
        with pytest.raises(ValueError, match="sublinhado"):
            ModuloSpec(chave="nota_fiscal", rotulo="Nota Fiscal")

    def test_a_mensagem_diz_o_motivo(self):
        """Quem esbarrar nisso precisa entender na hora, não ir ler o código."""
        with pytest.raises(ValueError) as erro:
            ModuloSpec(chave="nota_fiscal", rotulo="Nota Fiscal")
        assert "permiss" in str(erro.value).lower()

    def test_chave_sem_sublinhado_passa(self):
        assert ModuloSpec(chave="notafiscal", rotulo="Nota Fiscal").chave == "notafiscal"

    def test_hifen_e_aceito_como_separador(self):
        """`nota-fiscal` funciona: o corte é no sublinhado, não no hífen."""
        assert ModuloSpec(chave="nota-fiscal", rotulo="Nota Fiscal").chave == "nota-fiscal"
