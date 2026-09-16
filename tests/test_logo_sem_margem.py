"""O logo do menu da empresa perde a margem em volta do desenho (15/09/2026).

O logo da Normadin chegou num JPEG de 1280×905 com o desenho ocupando 24% da
altura: a barra ajusta o ARQUIVO inteiro à caixa do menu, e o desenho saía com
metade do tamanho que cabia, "distante". Cortar a margem no envio faz o desenho
preencher a caixa.
"""

import io

import pytest
from PIL import Image, ImageDraw

from plataforma.logo import sem_margem
from plataforma.models import AparenciaDaEmpresa, Empresa

pytestmark = pytest.mark.django_db


def _arquivo(formato: str, tamanho=(1280, 905), desenho=(175, 345, 1105, 561),
             fundo=(255, 255, 255), transparente=False) -> bytes:
    modo = "RGBA" if transparente else "RGB"
    cor_de_fundo = (0, 0, 0, 0) if transparente else fundo
    imagem = Image.new(modo, tamanho, cor_de_fundo)
    if desenho is not None:
        ImageDraw.Draw(imagem).rectangle(desenho, fill=(75, 187, 66, 255)[:len(modo)])
    saida = io.BytesIO()
    imagem.save(saida, formato, quality=92)
    return saida.getvalue()


def _tamanho(dados: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(dados)).size


class TestOCorte:

    def test_jpeg_com_fundo_branco_perde_a_margem(self):
        dados = sem_margem(_arquivo("JPEG"), "image/jpeg")
        largura, altura = _tamanho(dados)
        # O desenho tem 931×217; o corte deixa um respiro de poucos pixels para
        # não comer a borda suavizada do traço.
        assert 931 <= largura <= 931 + 2 * 12
        assert 217 <= altura <= 217 + 2 * 12

    def test_png_transparente_corta_pela_transparencia(self):
        dados = sem_margem(_arquivo("PNG", transparente=True), "image/png")
        largura, altura = _tamanho(dados)
        assert largura < 1000 and altura < 260
        assert Image.open(io.BytesIO(dados)).mode == "RGBA", (
            "a transparência precisa sobreviver ao corte")

    def test_o_formato_nao_muda(self):
        assert Image.open(io.BytesIO(
            sem_margem(_arquivo("JPEG"), "image/jpeg"))).format == "JPEG"
        assert Image.open(io.BytesIO(
            sem_margem(_arquivo("PNG", transparente=True), "image/png"))).format == "PNG"

    def test_sem_margem_devolve_os_mesmos_bytes(self):
        """Nada a cortar é nada a regravar: regravar um JPEG sem motivo só
        perderia qualidade."""
        original = _arquivo("PNG", tamanho=(400, 100), desenho=(0, 0, 399, 99))
        assert sem_margem(original, "image/png") == original

    def test_svg_nao_e_tocado(self):
        svg = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='9' height='9'/></svg>"
        assert sem_margem(svg, "image/svg+xml") == svg

    def test_imagem_toda_em_branco_nao_vira_nada(self):
        vazia = _arquivo("PNG", desenho=None)
        assert sem_margem(vazia, "image/png") == vazia


class TestNoSave:

    def test_o_logo_gravado_ja_vem_sem_margem(self):
        empresa = Empresa.objects.create(razao_social="Alfa")
        aparencia = AparenciaDaEmpresa.objects.create(
            empresa=empresa, logo=_arquivo("JPEG"))
        largura, altura = _tamanho(bytes(aparencia.logo))
        assert largura < 1000 and altura < 260
        assert aparencia.logo_tipo == "image/jpeg"


def test_arquivo_que_o_pillow_nao_abre_fica_como_veio():
    """Cortar margem é conforto: o que passou pela peneira de `validar` e o
    Pillow não decodifica não pode virar recusa nem erro 500."""
    estranho = b"\x89PNG\r\n\x1a\n" + b"so a assinatura"
    assert sem_margem(estranho, "image/png") == estranho
