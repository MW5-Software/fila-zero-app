"""Logo e favicon no banco — item 20 do Bloco 3 do roadmap.

Hoje o design system já sabe desenhar logo em três lugares (login, barra
lateral, rodapé) e favicon no `<head>` — mas não há onde guardar nada: o
`Assets` do `Brand` nasce vazio e fica vazio para sempre. Aqui nasce o
guardado: bytes no banco (mesmo caminho de `Usuario.avatar`), tipo
decidido pelo CONTEÚDO (`nucleo.images.validar`) e uma rota que serve de
volta.

A rota é aberta de propósito, como a folha `/tema.css`: o logo da tela de
entrada e o favicon precisam existir ANTES de qualquer sessão. O que protege
não é guarda de login — é a peneira na gravação mais os cabeçalhos seguros
na resposta.
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

#: PNG mínimo pela assinatura — `validar` decide pelo prefixo, não pelo resto.
PNG = b"\x89PNG\r\n\x1a\n" + b"png de mentira, so a assinatura importa"
SVG_COM_SCRIPT = (
    "<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
).encode()


@pytest.mark.django_db
class TestOModelo:
    def test_guarda_por_lugar_e_devolve_os_bytes(self):
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        gravado = ImagemDaMarca.objects.get(lugar="login")
        assert bytes(gravado.conteudo) == PNG

    def test_o_tipo_e_decidido_pelo_conteudo(self):
        """O chamador pode afirmar o que quiser em `tipo`; quem decide é a
        leitura dos bytes — mesma regra do avatar e da tela inteira."""
        from plataforma.models import ImagemDaMarca

        linha = ImagemDaMarca(lugar="login", conteudo=PNG, tipo="image/svg+xml")
        linha.save()
        assert linha.tipo == "image/png"

    def test_svg_com_script_e_recusado(self):
        """SVG entra, mas sem código: a peneira é a do `nucleo.images`, e a
        recusa acontece no model — a tela não é a única porta."""
        from plataforma.models import ImagemDaMarca

        with pytest.raises(ValidationError):
            ImagemDaMarca(lugar="sidebar", conteudo=SVG_COM_SCRIPT).save()

    def test_arquivo_vazio_e_recusado(self):
        from plataforma.models import ImagemDaMarca

        with pytest.raises(ValidationError):
            ImagemDaMarca(lugar="sidebar", conteudo=b"").save()

    def test_formato_desconhecido_e_recusado(self):
        from plataforma.models import ImagemDaMarca

        with pytest.raises(ValidationError):
            ImagemDaMarca(lugar="favicon", conteudo=b"nao-e-imagem").save()

    def test_regravar_o_mesmo_lugar_substitui(self):
        """Reenviar troca a imagem de sempre; `lugar` único proíbe a segunda
        linha — um logo por lugar, nunca uma surpresa de qual vale."""
        from django.db import IntegrityError
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)
        with pytest.raises(IntegrityError):
            ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)


@pytest.mark.django_db
class TestARota:
    def test_serve_os_bytes_com_o_tipo_gravado_sem_login(self, db):
        """Aberta como `/tema.css`: o login precisa dela antes de sessão."""
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        resposta = Client().get(reverse("marca_imagem", args=["login"]))
        assert resposta.status_code == 200
        assert resposta.content == PNG
        assert resposta["Content-Type"] == "image/png"

    def test_traz_os_cabecalhos_seguros(self, db):
        """Bytes enviados por terceiro, servidos pela nossa origem: `nosniff`
        e a CSP com sandbox são a segunda tranca, igual ao avatar."""
        from plataforma.models import ImagemDaMarca

        svg_limpo = "<svg xmlns='http://www.w3.org/2000/svg'></svg>".encode()
        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=svg_limpo)
        resposta = Client().get(reverse("marca_imagem", args=["sidebar"]))
        assert resposta["X-Content-Type-Options"] == "nosniff"
        assert "sandbox" in resposta["Content-Security-Policy"]

    def test_sem_imagem_e_404(self, db):
        assert Client().get(reverse("marca_imagem", args=["login"])).status_code == 404

    def test_lugar_desconhecido_e_404(self, db):
        resposta = Client().get(reverse("marca_imagem", args=["cabecalho"]))
        assert resposta.status_code == 404


@pytest.mark.django_db
class TestAMarcaGanhaOsCaminhos:
    """A promessa inteira: gravou aqui, o sistema inteiro desenha."""

    def test_a_marca_da_instalacao_leva_os_assets_que_existem(self):
        from dataclasses import replace as substituir

        from plataforma.marca import (
            ASSETS_DO_PRODUTO, LOGO_DO_PRODUTO_MENU, marca_da_instalacao,
        )
        from plataforma.models import ImagemDaMarca

        antes = marca_da_instalacao()
        # O piso é o logo do produto, e não vazio: instalação nova nasce
        # vestida (ver `test_logo_do_produto.py`).
        assert antes.assets.login_logo == ASSETS_DO_PRODUTO.login_logo

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        depois = marca_da_instalacao()
        assert "/marca/imagem/login" in depois.assets.login_logo
        # O que não foi enviado continua no logo do PRÓPRIO lugar — nunca
        # caindo no logo de outro, que era o risco de um "logo geral".
        assert depois.assets.sidebar_logo == LOGO_DO_PRODUTO_MENU
        # E nada mais da marca mudou: assets entram por substituição da
        # dataclass, não por mutação.
        esperado = substituir(antes, assets=substituir(
            ASSETS_DO_PRODUTO, login_logo=depois.assets.login_logo))
        assert depois == esperado

    def test_o_favicon_aparece_no_head_da_tela_de_entrada(self):
        from plataforma.models import ImagemDaMarca

        ico = b"\x00\x00\x01\x00" + b"ico"
        ImagemDaMarca.objects.create(lugar="favicon", conteudo=ico)
        html = Client().get(reverse("entrar")).content.decode()
        assert 'rel="icon"' in html
        assert "/marca/imagem/favicon" in html

    def test_o_logo_do_login_aparece_na_tela_de_entrada(self):
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        html = Client().get(reverse("entrar")).content.decode()
        assert "/marca/imagem/login" in html

    def test_sem_imagem_nenhuma_o_html_nao_cita_a_rota(self):
        """Ausência limpa: sem upload, nem `<img>` órfão nem link de icon —
        o navegador fica com o favicon padrão, e não com um 404 por página."""
        html = Client().get(reverse("entrar")).content.decode()
        assert "/marca/imagem/" not in html

    def test_gravar_o_logo_muda_o_html_do_shell(self):
        """O teste que fecha o ciclo, como o da cor: a barra lateral lê
        `assets.logo_for("sidebar")` — tem que chegar lá sem tocar código."""
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)
        from contas.models import Usuario
        Usuario.objects.create_superuser(email="raiz@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
        html = c.get(reverse("home")).content.decode()
        assert "/marca/imagem/sidebar" in html


def _mw5(db):
    """A MW5 logada, mesmo molde de `test_tela_aparencia`."""
    from contas.models import Usuario

    Usuario.objects.create_superuser(email="raiz@teste.com", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
    return c


@pytest.mark.django_db
class TestOUploadNaAparencia:
    """Item 21 do Bloco 3: o logo por área se envia pela tela de Aparência.

    Um formulário por lugar — a marca que cabe na faixa lateral não é a
    mesma que cabe no cartão de entrada, e trocar uma não pode exigir
    reenviar as outras.
    """

    def test_a_tela_mostra_os_lugares_abertos_ao_cliente(self, db):
        # O rodapé não está aqui de propósito: o logo de lá é do produto e
        # não troca (ver `test_logo_do_produto.py`).
        html = _mw5(db).get(reverse("aparencia")).content.decode()
        assert "Tela de entrada" in html
        assert "Menu lateral" in html
        assert "Favicon" in html

    def test_a_tela_mostra_o_que_ja_esta_guardado(self, db):
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="login", conteudo=PNG)
        html = _mw5(db).get(reverse("aparencia")).content.decode()
        assert "/marca/imagem/login" in html

    def test_enviar_um_logo_grava_e_audita(self, db):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria
        from plataforma.models import ImagemDaMarca

        resposta = _mw5(db).post(reverse("aparencia_logo"), {
            "lugar": "login",
            "arquivo": SimpleUploadedFile("logo.png", PNG),
        })
        assert resposta.status_code == 302
        assert ImagemDaMarca.objects.get(lugar="login").tipo == "image/png"
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.LOGO_ALTERADO, alvo__contains="entrada").exists()

    def test_o_tipo_vem_do_conteudo_e_nao_do_nome_do_arquivo(self, db):
        """`logo.png` cheio de SVG é SVG: extensão é afirmação de quem
        envia, e a rota serve pelo que a leitura dos bytes decidiu."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from plataforma.models import ImagemDaMarca

        svg = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        _mw5(db).post(reverse("aparencia_logo"), {
            "lugar": "sidebar",
            "arquivo": SimpleUploadedFile("mentira.png", svg),
        })
        assert ImagemDaMarca.objects.get(lugar="sidebar").tipo == "image/svg+xml"

    def test_arquivo_invalido_e_recusado_com_frase_na_tela_e_nada_gravado(self, db):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from plataforma.models import ImagemDaMarca

        resposta = _mw5(db).post(reverse("aparencia_logo"), {
            "lugar": "sidebar",
            "arquivo": SimpleUploadedFile("lixo.png", b"nao-e-imagem"),
        })
        assert resposta.status_code == 200
        assert "Formato não reconhecido" in resposta.content.decode()
        assert ImagemDaMarca.objects.count() == 0

    def test_substituir_nao_duplica(self, db):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from plataforma.models import ImagemDaMarca

        c = _mw5(db)
        for i in range(2):
            c.post(reverse("aparencia_logo"), {
                "lugar": "login",
                "arquivo": SimpleUploadedFile(f"logo-{i}.png", PNG),
            })
        assert ImagemDaMarca.objects.filter(lugar="login").count() == 1

    def test_remover_apaga_e_audita(self, db):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria
        from plataforma.models import ImagemDaMarca

        ImagemDaMarca.objects.create(lugar="sidebar", conteudo=PNG)
        resposta = _mw5(db).post(reverse("aparencia_logo"),
                                 {"lugar": "sidebar", "acao": "remover"})
        assert resposta.status_code == 302
        assert not ImagemDaMarca.objects.filter(lugar="sidebar").exists()
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.LOGO_REMOVIDO, alvo__contains="Menu").exists()

    def test_remover_o_que_nao_existe_e_404(self, db):
        assert _mw5(db).post(
            reverse("aparencia_logo"), {"lugar": "favicon", "acao": "remover"}
        ).status_code == 404

    def test_sem_arquivo_o_post_e_recusado_com_frase_na_tela(self, db):
        """Sem arquivo o navegador nem manda o campo; recusar com frase,
        e não 500, é o que a pessoa entende."""
        resposta = _mw5(db).post(reverse("aparencia_logo"), {"lugar": "login"})
        assert resposta.status_code == 200
        assert "arquivo" in resposta.content.decode().lower()

    def test_get_na_rota_e_405(self, db):
        assert _mw5(db).get(reverse("aparencia_logo")).status_code == 405

    def test_lugar_desconhecido_e_404(self, db):
        from django.core.files.uploadedfile import SimpleUploadedFile

        resposta = _mw5(db).post(reverse("aparencia_logo"), {
            "lugar": "cabecalho",
            "arquivo": SimpleUploadedFile("x.png", PNG),
        })
        assert resposta.status_code == 404

    def test_quem_nao_e_da_mw5_recebe_404(self, db):
        """Mesma guarda da tela: acesso da MW5 vem de `is_superuser`, e quem
        não pode não descobre que a rota existe."""
        from contas.models import Usuario

        Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert c.post(reverse("aparencia_logo"), {"lugar": "login"}).status_code == 404
