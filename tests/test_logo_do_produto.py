"""O logo do KRONOS: piso em toda instalação, e fixo no rodapé.

Duas regras, e a segunda é a que custa se for esquecida:

1. **Instalação nova nasce vestida.** Entrada, menu e rodapé mostram o logo
   do KRONOS desde o `migrate`. Antes disto uma instalação recém-criada
   abria com a faixa da barra em branco e o cartão de entrada sem marca —
   parecia quebrada no primeiro minuto de vida, que é justamente quando
   alguém está decidindo se confia nela.

2. **O rodapé não troca.** Ele é a assinatura de quem FEZ o sistema, e é a
   mesma nas vinte instalações. Enquanto esteve aberto ao envio, qualquer
   cliente podia apagá-la sem querer — e a tela de Aparência oferecia o
   campo, o que era um convite. O que o cliente envia cobre a entrada e o
   menu, e para no rodapé.

Os arquivos e as medidas vieram do painel GED, onde esta marca já estava
resolvida: ela é EMPILHADA, e os 56px/24px que o design system reserva foram
pensados para marca deitada.
"""

from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from plataforma.marca import (
    AREAS_DO_LOGO_DO_PRODUTO,
    ASSETS_DO_PRODUTO,
    LOGO_DO_PRODUTO_ENTRADA,
    LOGO_DO_PRODUTO_MENU,
    LOGO_DO_PRODUTO_RODAPE,
    MARCA_PADRAO,
    marca_da_instalacao,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"png de mentira, so a assinatura importa"


class TestOsArquivos:
    def test_os_tres_arquivos_existem_no_disco(self):
        """Um caminho que não existe é um `<img>` apontando para 404 — a
        faixa fica vazia e nada no código acusa."""
        raiz = Path(__file__).resolve().parent.parent
        for caminho in (LOGO_DO_PRODUTO_ENTRADA, LOGO_DO_PRODUTO_MENU,
                        LOGO_DO_PRODUTO_RODAPE):
            arquivo = raiz / "plataforma" / caminho.replace("/static/", "static/")
            assert arquivo.exists(), caminho
            assert arquivo.stat().st_size > 0, caminho

    def test_cada_lugar_tem_o_seu_arquivo(self):
        """Um arquivo por lugar, como o `Assets` já divide: o que cabe numa
        faixa de 84px não é o que cabe num rodapé de 40px."""
        assert ASSETS_DO_PRODUTO.login_logo == LOGO_DO_PRODUTO_ENTRADA
        assert ASSETS_DO_PRODUTO.sidebar_logo == LOGO_DO_PRODUTO_MENU
        assert ASSETS_DO_PRODUTO.footer_logo == LOGO_DO_PRODUTO_RODAPE


@pytest.mark.django_db
class TestAInstalacaoNova:
    def test_nasce_com_o_logo_nos_tres_lugares(self, db):
        marca = marca_da_instalacao()
        assert marca.assets.logo_for("login") == LOGO_DO_PRODUTO_ENTRADA
        assert marca.assets.logo_for("sidebar") == LOGO_DO_PRODUTO_MENU
        assert marca.assets.logo_for("footer") == LOGO_DO_PRODUTO_RODAPE

    def test_a_marca_padrao_ja_carrega_os_logos(self):
        # Sem banco nenhum: quem importa `MARCA_PADRAO` direto (a tela de
        # entrada antes do primeiro `migrate`, os testes de tema) recebe a
        # mesma cara.
        assert MARCA_PADRAO.assets.logo_for("footer") == LOGO_DO_PRODUTO_RODAPE


@pytest.mark.django_db
class TestAsMedidas:
    """A marca empilhada não cabe nas medidas de marca deitada.

    Nos 56px da barra o nome sai com ~16px e a linha "ERP | CRM" com 4px; nos
    24px do rodapé, ~7px e 2px. O limite não é o arquivo, é o espaço.
    """

    def test_o_rodape_manda_na_propria_medida_sempre(self, db):
        from plataforma.models import ImagemDaMarca

        # Mesmo com a marca do cliente inteira no ar: o logo do rodapé
        # continua o do produto, então a medida dele também.
        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)
        areas = marca_da_instalacao().logo_areas
        assert areas["logo-footer-h"] == "40px"
        assert areas["logo-footer-w"] == "72px"

    def test_a_barra_usa_84px_enquanto_o_logo_for_o_do_produto(self, db):
        assert marca_da_instalacao().logo_areas["logo-side-h"] == \
            AREAS_DO_LOGO_DO_PRODUTO["logo-side-h"]

    def test_e_devolve_a_medida_do_design_system_quando_o_cliente_envia(self, db):
        """84px é a conta da marca EMPILHADA do KRONOS. A marca deitada de um
        cliente nessa altura vira um retângulo gordo no alto do menu."""
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)
        assert "logo-side-h" not in marca_da_instalacao().logo_areas


@pytest.mark.django_db
class TestOQueOClienteEnvia:
    def test_cobre_a_entrada_e_o_menu(self, db):
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)

        marca = marca_da_instalacao()
        assert marca.assets.logo_for("login") == "/marca/imagem/login"
        assert marca.assets.logo_for("sidebar") == "/marca/imagem/sidebar"

    def test_e_nao_alcanca_o_rodape(self, db):
        """A prova da regra: com a marca do cliente inteira no ar, o rodapé
        continua sendo o do produto."""
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)

        assert marca_da_instalacao().assets.logo_for("footer") == \
            LOGO_DO_PRODUTO_RODAPE

    def test_o_modelo_recusa_o_rodape(self, db):
        from django.core.exceptions import ValidationError
        from plataforma.models import ImagemDaMarca

        with pytest.raises(ValidationError, match="footer"):
            ImagemDaMarca(lugar="footer", conteudo=PNG).save()


def _mw5(db):
    """A MW5 logada, mesmo molde de `test_marca_imagem`."""
    from contas.models import Usuario

    Usuario.objects.create_superuser(
        email="raiz@teste.com", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
    return c


@pytest.mark.django_db
class TestATelaDeAparencia:
    def test_nao_oferece_o_rodape(self, db):
        """Um campo de envio para o rodapé seria uma promessa que o sistema
        não cumpre: o arquivo seria recusado na gravação."""
        html = _mw5(db).get(reverse("aparencia")).content.decode()
        assert "Tela de entrada" in html
        assert "Menu lateral" in html
        assert "Rodapé" not in html

    def test_a_rota_recusa_o_envio_para_o_rodape(self, db):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from plataforma.models import ImagemDaMarca

        resposta = _mw5(db).post(reverse("aparencia_logo"), {
            "lugar": "footer",
            "arquivo": SimpleUploadedFile("logo.png", PNG),
        })
        assert resposta.status_code == 404
        assert not ImagemDaMarca.objects.filter(lugar="footer").exists()


@pytest.mark.django_db
class TestOAltDoRodape:
    """Quem usa leitor de tela ouve o nome certo.

    O `alt` do logo vem do nome do cliente no design system — correto para a
    entrada e o menu, onde a imagem é do cliente. No rodapé a imagem é a do
    produto e não troca: anunciar o nome do cliente ali seria descrever a
    imagem errada para a única pessoa que depende do `alt`.
    """

    def test_o_rodape_anuncia_o_produto_e_nao_o_cliente(self, db):
        from plataforma.marca import NOME_DO_PRODUTO
        from plataforma.models import Marca
        from plataforma.site import SiteDoProduto

        Marca.objects.create(client_name="Cliente Qualquer")
        rodape = SiteDoProduto(brand=marca_da_instalacao()).footer()
        assert rodape.logo_alt == NOME_DO_PRODUTO
        assert "Cliente Qualquer" not in rodape.logo_alt

    def test_a_entrada_e_o_menu_continuam_com_o_nome_do_cliente(self, db):
        from plataforma.models import Marca
        from plataforma.site import SiteDoProduto

        Marca.objects.create(client_name="Cliente Qualquer")
        site = SiteDoProduto(brand=marca_da_instalacao())
        assert site.sidebar().logo_alt == "Cliente Qualquer"


@pytest.mark.django_db
class TestAsCoresDaCasa:
    """A cara do produto sobrevive a alguém salvar a Aparência sem mexer.

    Os padrões da `Marca` vinham do `Brand` do design system, e o destaque de
    lá é `#872d00` — um marrom que veio do Sementes Premix. O menu vinha
    vazio, que quer dizer "herda do tema": um azul derivado da primária, e não
    o azul-marinho DO LOGO.

    Efeito prático antes: abrir a Aparência e clicar em salvar, sem trocar
    nada, trocava a cor da marca do KRONOS. Ninguém escolheu isso — só salvou.
    """

    def test_uma_marca_nova_nasce_com_as_cores_do_produto(self, db):
        from plataforma.marca import ACCENT_DO_PRODUTO, AREAS_DO_PRODUTO
        from plataforma.models import Marca

        marca = Marca.objects.create(client_name="Cliente Qualquer")
        assert marca.accent == ACCENT_DO_PRODUTO
        assert marca.sidebar_bg == AREAS_DO_PRODUTO.sidebar_bg

    def test_o_marrom_do_design_system_nao_volta(self, db):
        from nucleo.theme import Brand
        from plataforma.models import Marca

        marca = Marca.objects.create(client_name="Cliente Qualquer")
        assert marca.accent != Brand.__dataclass_fields__["accent"].default

    def test_o_menu_chega_ao_css_com_o_azul_do_logo(self, db):
        from nucleo.theme import render_theme_css
        from plataforma.marca import AREAS_DO_PRODUTO, marca_da_instalacao

        css = render_theme_css(marca_da_instalacao())
        assert f"--sidebar-bg:{AREAS_DO_PRODUTO.sidebar_bg}" in css


class TestOTamanhoDoDesenho:
    """O desenho cresce dentro da faixa; a faixa não se mexe.

    O logo aparecia pequeno no meio de espaço grande — 84px numa faixa de
    132px, 40px num rodapé de 80px — e o caminho normal para crescer não
    servia: `logo_areas` (em `plataforma/marca.py`) alimenta o desenho E a
    faixa ao mesmo tempo, porque `nucleo/theme/tokens.py` monta
    `sidebar-brand-h` somando o respiro à altura do logo. Subir lá sobe a
    tela inteira.

    A correção está em `plataforma/static/plataforma/kronos.css`, que
    redefine só as variáveis do DESENHO — as alturas de faixa saem do Python
    já resolvidas em números, então não acompanham.

    Estes testes existem para o passo seguinte, que é o perigoso: subir mais
    um pouco e o desenho transbordar a faixa, com a borda de baixo cortando
    a marca. A conta que prova que ainda cabe é feita aqui, não no olho.
    """

    FOLHA = Path("plataforma/static/plataforma/kronos.css")

    def _px(self, texto: str) -> float:
        """Resolve as duas formas em que uma medida chega: `108px` e o
        `calc(84px + 24px * 2)` que o `tokens.build` escreve."""
        import re

        numeros = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)px", texto)]
        if "*" in texto:
            # `calc(A + B * 2)` — a única forma que o `build` produz.
            assert len(numeros) == 2, f"calc inesperado: {texto!r}"
            return numeros[0] + numeros[1] * 2
        assert len(numeros) == 1, f"medida inesperada: {texto!r}"
        return numeros[0]

    def _tokens_servidos(self) -> dict[str, str]:
        css = Client().get(reverse("tema")).content.decode()
        return {
            nome.strip(): valor.strip()
            for nome, valor in (
                parte.split(":", 1)
                for parte in css.replace("{", ";").replace("}", ";").split(";")
                if parte.count(":") == 1 and parte.strip().startswith("--")
            )
        }

    def _override(self, nome: str) -> str:
        import re

        folha = self.FOLHA.read_text()
        achado = re.search(rf"{re.escape(nome)}\s*:\s*([^;]+);", folha)
        assert achado, f"{nome} não está sobrescrito em {self.FOLHA}"
        return achado.group(1)

    @pytest.mark.django_db
    def test_o_desenho_da_barra_cabe_na_faixa_reservada(self):
        faixa = self._px(self._tokens_servidos()["--sidebar-brand-h"])
        desenho = self._px(self._override("--logo-side-h"))
        respiro = self._px(self._override("--sidebar-brand-pad"))

        # `.side-brand` é `padding: var(--sidebar-brand-pad) 16px` dentro de
        # uma caixa de `--sidebar-brand-h`: o desenho tem a faixa menos os
        # dois respiros, e um pixel a mais já encosta na borda de baixo.
        assert desenho + respiro * 2 <= faixa, (
            f"o logo da barra ({desenho}px + {respiro}px de respiro dos dois "
            f"lados) não cabe na faixa de {faixa}px"
        )

    @pytest.mark.django_db
    def test_o_desenho_do_rodape_cabe_na_barra_do_rodape(self):
        barra = self._px(self._tokens_servidos()["--footer-h"])
        desenho = self._px(self._override("--logo-footer-h"))

        assert desenho <= barra, (
            f"o logo do rodapé ({desenho}px) não cabe na barra de {barra}px"
        )

    def test_a_largura_maxima_do_rodape_acompanha_a_proporcao(self):
        """`.footer-marca img` é `width: auto` com
        `max-width: min(var(--logo-footer-w), 100%)`. Um teto menor que a
        largura que a altura pede não encolhe o desenho: espreme-o — a altura
        obedece, a largura não, e a marca sai estreita."""
        from PIL import Image

        arquivo = Image.open("plataforma/static/plataforma/marca/kronos-footer.png")
        proporcao = arquivo.size[0] / arquivo.size[1]

        altura = self._px(self._override("--logo-footer-h"))
        teto = self._px(self._override("--logo-footer-w"))

        assert teto >= altura * proporcao, (
            f"com {altura}px de altura o desenho pede {altura * proporcao:.0f}px "
            f"de largura, e o teto é {teto}px — sairia espremido"
        )

    def test_os_arquivos_tem_resolucao_para_a_medida_em_que_sao_desenhados(self):
        """Um logo desenhado com 108px vindo de um arquivo de 108px fica
        borrado em qualquer tela retina. O piso é 3x — abaixo disso o
        navegador está esticando, não encolhendo."""
        from PIL import Image

        base = Path("plataforma/static/plataforma/marca")
        alturas = {
            "kronos-sidebar.png": self._px(self._override("--logo-side-h")),
            "kronos-footer.png": self._px(self._override("--logo-footer-h")),
            "kronos-login.png": self._px(self._override("--logo-login-h")),
        }
        for nome, desenhado in alturas.items():
            arquivo = Image.open(base / nome)
            densidade = arquivo.size[1] / desenhado
            assert densidade >= 3, (
                f"{nome} tem {arquivo.size[1]}px de altura para ser desenhado "
                f"com {desenhado}px — {densidade:.1f}x, abaixo do piso de 3x"
            )
