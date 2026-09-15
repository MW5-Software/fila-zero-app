"""A geometria de um gráfico, antes de virar desenho.

Testada aqui sozinha, sem renderizar nada, porque é onde os erros de gráfico
moram: uma fatia que não fecha o círculo, um eixo que termina em 1.284 em vez
de 2.000, uma barra que não é proporcional à vizinha.
"""

import math
import re

import pytest

from nucleo.components import Chart, DataPoint
from nucleo.components.charts import (
    arco,
    fatias,
    formatar_numero,
    marcas_do_eixo,
    maximo_redondo,
    pontos_da_linha,
)
from nucleo.rendering import create_environment, use_environment


@pytest.fixture(autouse=True)
def env():
    environment = create_environment()
    with use_environment(environment):
        yield environment


def html(componente) -> str:
    return str(componente.render())


DOIS = [DataPoint(label="Concluídas", value=947),
        DataPoint(label="Em aberto", value=337)]


class TestMaximoRedondo:
    """O topo do eixo tem que ser um número que uma pessoa lê."""

    @pytest.mark.parametrize("maior,esperado", [
        (1284, 2000),
        (947, 1000),
        (100, 100),
        (7, 10),
        (0.4, 0.5),
        (2400, 2500),
    ])
    def test_sobe_ate_o_proximo_numero_redondo(self, maior, esperado):
        assert maximo_redondo([maior]) == pytest.approx(esperado)

    def test_usa_o_maior_valor_da_lista(self):
        assert maximo_redondo([10, 947, 3]) == pytest.approx(1000)

    def test_lista_vazia_nao_quebra(self):
        assert maximo_redondo([]) == 1.0

    def test_tudo_zero_nao_divide_por_zero(self):
        assert maximo_redondo([0, 0, 0]) == 1.0

    def test_infinito_nao_estoura(self):
        """Um valor com 309 dígitos vira `inf` em ponto flutuante, e
        `math.floor(math.log10(inf))` levanta `OverflowError`. Isso derrubaria
        a prévia inteira — que roda a cada tecla digitada."""
        assert maximo_redondo([float("inf")]) == 1.0
        assert maximo_redondo([float("inf"), 947]) == pytest.approx(1000)

    def test_negativo_nao_puxa_o_eixo_para_baixo(self):
        assert maximo_redondo([-50, 80]) == pytest.approx(100)


class TestMarcasDoEixo:
    def test_vao_de_zero_ao_maximo(self):
        marcas = marcas_do_eixo(2000)
        assert marcas[0] == 0 and marcas[-1] == pytest.approx(2000)

    def test_sao_igualmente_espacadas(self):
        marcas = marcas_do_eixo(1000, quantas=4)
        assert marcas == [0, 250, 500, 750, 1000]


class TestFatias:
    def test_fecham_o_circulo(self):
        pedacos = fatias([947, 337, 120])
        assert pedacos[0][0] == 0
        assert pedacos[-1][1] == pytest.approx(360)

    def test_sao_proporcionais(self):
        (a_ini, a_fim), (b_ini, b_fim) = fatias([75, 25])
        assert a_fim - a_ini == pytest.approx(270)
        assert b_fim - b_ini == pytest.approx(90)

    def test_encostam_uma_na_outra(self):
        pedacos = fatias([1, 2, 3])
        for anterior, seguinte in zip(pedacos, pedacos[1:]):
            assert anterior[1] == pytest.approx(seguinte[0])

    def test_um_ponto_so_ocupa_o_circulo_inteiro(self):
        assert fatias([5]) == [(0.0, 360.0)]

    def test_sem_valor_positivo_nao_ha_fatia(self):
        assert fatias([]) == []
        assert fatias([0, 0]) == []

    def test_negativo_conta_como_zero(self):
        """Fatia negativa não existe num círculo; some sem levar as outras."""
        pedacos = fatias([-10, 50, 50])
        assert pedacos[0][0] == pedacos[0][1]
        assert pedacos[-1][1] == pytest.approx(360)


class TestArco:
    def test_comeca_as_doze_horas(self):
        """Meia-noite, e não três horas: é de onde o olho começa a ler."""
        d = arco(0, 90, raio=10, centro=(0, 0))
        assert "0,-10" in d.replace(" ", "")

    def test_marca_o_arco_grande_acima_de_meia_volta(self):
        assert " 1 1 " in arco(0, 270, raio=10)
        assert " 0 1 " in arco(0, 90, raio=10)

    def test_a_pizza_fecha_no_centro(self):
        assert arco(0, 90, raio=10).startswith("M 0")

    def test_o_donut_nao_passa_pelo_centro(self):
        d = arco(0, 90, raio=10, raio_interno=6)
        assert d.count("A") == 2

    def test_a_volta_inteira_vira_dois_arcos(self):
        """Um arco de 360° tem começo e fim no mesmo ponto e não desenha nada."""
        assert arco(0, 360, raio=10).count("A") == 2


class TestPontosDaLinha:
    def test_o_primeiro_encosta_na_esquerda_e_o_ultimo_na_direita(self):
        pontos = pontos_da_linha([1, 2, 3], maximo=3, largura=300, altura=100)
        assert pontos[0][0] == 0
        assert pontos[-1][0] == pytest.approx(300)

    def test_valor_maximo_encosta_no_topo(self):
        pontos = pontos_da_linha([0, 100], maximo=100, largura=10, altura=80)
        assert pontos[1][1] == pytest.approx(0)

    def test_valor_zero_encosta_na_base(self):
        pontos = pontos_da_linha([0, 100], maximo=100, largura=10, altura=80)
        assert pontos[0][1] == pytest.approx(80)

    def test_um_ponto_so_fica_no_meio(self):
        assert pontos_da_linha([5], maximo=10, largura=300, altura=100)[0][0] == 150

    def test_sem_ponto_nenhum(self):
        assert pontos_da_linha([], maximo=10, largura=300, altura=100) == []

    def test_maximo_zero_nao_divide_por_zero(self):
        pontos = pontos_da_linha([0, 0], maximo=0, largura=10, altura=80)
        assert all(y == 80 for _, y in pontos)


class TestFormatarNumero:
    @pytest.mark.parametrize("valor,texto", [
        (1284, "1.284"),
        (947, "947"),
        (0, "0"),
        (1284.5, "1.284,50"),
    ])
    def test_no_padrao_brasileiro(self, valor, texto):
        assert formatar_numero(valor) == texto


class TestConstrucao:
    def test_tipo_desconhecido_falha_na_construcao(self):
        with pytest.raises(ValueError, match="kind"):
            Chart(points=DOIS, kind="bolha")

    def test_legenda_desconhecida_falha_na_construcao(self):
        with pytest.raises(ValueError, match="legend"):
            Chart(points=DOIS, legend="flutuante")

    def test_altura_fora_da_faixa_falha(self):
        with pytest.raises(ValueError, match="height"):
            Chart(points=DOIS, height=20)


class TestDesenho:
    def test_a_barra_desenha_um_retangulo_por_ponto(self):
        assert html(Chart(points=DOIS, kind="bar")).count("<rect") >= 2

    def test_a_pizza_desenha_um_path_por_fatia(self):
        assert html(Chart(points=DOIS, kind="pie")).count("<path") == 2

    def test_o_donut_tem_furo(self):
        """Duas curvas por fatia; a pizza tem uma."""
        assert html(Chart(points=DOIS, kind="donut")).count(" A ") == 4

    def test_o_donut_de_uma_fatia_so_tambem_tem_furo(self):
        """Uma categoria só ocupa o círculo inteiro — `_volta_inteira` com raio
        interno é o caso que a Task 1 deixou sem teste. Aqui, com o componente
        de verdade, ele tem que continuar sendo um donut, não uma pizza."""
        um = [DataPoint(label="Total", value=100)]
        marcacao = html(Chart(points=um, kind="donut"))
        assert marcacao.count(" A ") == 4
        assert marcacao.count("<path") == 1

    def test_a_linha_desenha_uma_curva_so(self):
        marcacao = html(Chart(points=DOIS, kind="line"))
        assert marcacao.count("<polyline") == 1

    def test_o_titulo_aparece(self):
        assert "Ordens" in html(Chart(points=DOIS, title="Ordens"))


class TestBarraDeitada:
    """A barra horizontal desenhada de verdade.

    Nenhum teste do ramo chegava a renderizar uma `bar_h`, e foi por isso que
    ela ficou sem rótulo nenhum: os 44 de margem esquerda existiam vazios, e
    com `legend="none"` o gráfico não dizia que barra era qual.
    """

    def test_desenha_um_retangulo_por_ponto(self):
        assert html(Chart(points=DOIS, kind="bar_h")).count("<rect") >= 2

    def test_cada_barra_ganha_o_rotulo_dela(self):
        marcacao = html(Chart(points=DOIS, kind="bar_h", legend="none"))
        assert "Concluí…" in marcacao   # truncado para caber na margem
        assert "Em aber…" in marcacao

    def test_o_rotulo_fica_no_eixo_y(self):
        """Encostado na margem esquerda e ancorado no fim: é o que faz o texto
        crescer para dentro da margem em vez de entrar por cima da barra."""
        marcacao = html(Chart(points=DOIS, kind="bar_h", legend="none"))
        assert re.search(r'<text x="40" y="[\d.]+" class="tk fim">Em aber…</text>',
                         marcacao)

    def test_a_ultima_marca_do_eixo_nao_sai_pela_borda(self):
        """Ela cai exatamente em x=320, a borda do viewBox. Centrada ali,
        metade do número ficaria fora do desenho."""
        marcacao = html(Chart(points=DOIS, kind="bar_h"))
        assert '<text x="320.0" y="174" class="tk meio">' not in marcacao
        assert '<text x="320.0" y="174" class="tk fim">1.000</text>' in marcacao

    def test_o_rotulo_longo_trunca_mais_curto_do_que_no_eixo_x(self):
        """Deitada, o rótulo divide os 44 da margem com nada; em pé ele tem o
        vão inteiro da coluna. Catorze caracteres a 9px passariam da borda."""
        longo = "Ordens encerradas sem cobrança"
        deitada = html(Chart(points=[DataPoint(label=longo, value=1)], kind="bar_h"))
        em_pe = html(Chart(points=[DataPoint(label=longo, value=1)], kind="bar"))
        assert "Ordens…" in deitada
        assert "Ordens encerr…" in em_pe


class TestEscala:
    def test_o_desenho_escala_igual_nos_dois_eixos(self):
        """`preserveAspectRatio="none"` esticava o texto de 9px, os cantos do
        `rx` e a espessura da linha pela razão entre a caixa e os 320 do
        viewBox — num card de 600px, quase o dobro na horizontal."""
        assert "preserveAspectRatio" not in html(Chart(points=DOIS, kind="bar"))

    def test_o_grafico_de_eixos_e_o_redondo_tem_classes_diferentes(self):
        """As regras de tamanho são opostas: um ocupa a largura toda, o outro
        tem 132px fixos ao lado da legenda. Com uma regra só em `.chart svg`,
        o `width: 100%` ganhava do `.donutwrap` por especificidade e o donut
        engolia a caixa inteira."""
        assert 'class="plot"' in html(Chart(points=DOIS, kind="bar"))
        assert 'class="donutwrap"' in html(Chart(points=DOIS, kind="donut"))
        assert 'class="plot"' not in html(Chart(points=DOIS, kind="donut"))

    def test_a_folha_de_estilo_so_estica_o_grafico_de_eixos(self):
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8")
        assert ".chart svg.plot" in css
        assert ".chart svg {" not in css


class TestCor:
    def test_sem_cor_o_ponto_usa_o_token_da_posicao(self):
        marcacao = html(Chart(points=DOIS, kind="pie"))
        assert "var(--chart-1)" in marcacao and "var(--chart-2)" in marcacao

    def test_a_cor_do_ponto_ganha_do_token(self):
        pontos = [DataPoint(label="A", value=1, color="#c2410c"),
                  DataPoint(label="B", value=1)]
        marcacao = html(Chart(points=pontos, kind="pie"))
        assert "#c2410c" in marcacao and "var(--chart-2)" in marcacao

    def test_a_paleta_cicla(self):
        """O nono ponto volta ao `--chart-1`.

        Olhar só se `--chart-1` aparece não prova nada: o índice 0 já o usa.
        A pergunta é o que a nona posição resolve — são oito tokens, e depois
        do oitavo a paleta tem que dar a volta em vez de pedir um `--chart-9`
        que não existe no tema.
        """
        pontos = [DataPoint(label=str(i), value=1) for i in range(9)]
        grafico = Chart(points=pontos, kind="pie")
        assert grafico.cor_de(8) == "var(--chart-1)"
        assert grafico.cor_de(7) == "var(--chart-8)"
        assert "var(--chart-9)" not in html(grafico)

    def test_a_linha_usa_uma_cor_so(self):
        marcacao = html(Chart(points=DOIS, kind="line"))
        assert "var(--chart-2)" not in marcacao


class TestLegenda:
    def test_aparece_com_os_rotulos(self):
        marcacao = html(Chart(points=DOIS, legend="right"))
        assert "Concluídas" in marcacao and "Em aberto" in marcacao

    def test_desligada_nao_aparece(self):
        assert "class=\"leg\"" not in html(Chart(points=DOIS, legend="none"))

    def test_a_linha_nunca_tem_legenda(self):
        """Legenda de uma série só é ruído."""
        assert "class=\"leg\"" not in html(Chart(points=DOIS, kind="line", legend="right"))


class TestBordas:
    def test_sem_ponto_nenhum_diz_que_nao_ha_dados(self):
        marcacao = html(Chart(points=[]))
        assert "Sem dados" in marcacao
        assert "<svg" not in marcacao

    def test_tudo_zero_nao_quebra(self):
        pontos = [DataPoint(label="A", value=0), DataPoint(label="B", value=0)]
        assert "<svg" in html(Chart(points=pontos, kind="bar"))
        assert "<svg" in html(Chart(points=pontos, kind="donut"))

    def test_rotulo_longo_trunca_no_eixo_mas_nao_no_titulo(self):
        longo = "Ordens de serviço encerradas sem cobrança no trimestre"
        marcacao = html(Chart(points=[DataPoint(label=longo, value=1)], kind="bar"))
        assert "…" in marcacao
        assert longo in marcacao   # inteiro no <title>


class TestAcessibilidade:
    def test_o_svg_se_descreve(self):
        marcacao = html(Chart(points=DOIS, kind="pie", title="Ordens"))
        assert 'role="img"' in marcacao
        assert "aria-label" in marcacao
        assert "Concluídas 947" in marcacao

    def test_cada_forma_tem_tooltip_nativo(self):
        assert html(Chart(points=DOIS, kind="pie")).count("<title>") == 2


class TestEscape:
    def test_rotulo_com_html_nao_escapa(self):
        pontos = [DataPoint(label="<script>x</script>", value=1)]
        assert "<script>" not in html(Chart(points=pontos, kind="pie"))
