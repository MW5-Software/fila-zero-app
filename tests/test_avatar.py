"""A foto de perfil: gravada no banco, servida por rota própria.

O teste que mais importa é o do tipo por conteúdo: extensão e `Content-Type`
são o que quem envia AFIRMA, e afirmação não é verificação.

Desde a Task 3, `avatar`/`avatar_tipo` são colunas do próprio `Usuario` — não
mais uma tabela `Avatar` à parte. `ana.refresh_from_db()` aparece nos testes
que gravam pela view e depois leem pela instância do fixture, porque a
gravação passa por outra instância (a que a view busca) e a do fixture não
sabe disso sozinha.
"""

import base64

import pytest
from contas.models import Usuario
from django.apps import apps
from django.test import Client
from django.urls import reverse

SENHA = "segredo-de-teste"

#: Assinaturas de verdade, corpo de mentira: `validar` decide pelo prefixo,
#: então isto basta para exercitar o caminho sem carregar imagem de verdade.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64


def url_de_dados(tipo: str, bruto: bytes) -> str:
    return f"data:{tipo};base64," + base64.b64encode(bruto).decode()


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(email="ana@teste.com", password=SENHA)


@pytest.fixture
def logada(ana):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
    return c


@pytest.mark.django_db
def test_o_avatar_e_coluna_do_usuario_e_nao_tabela():
    """Duas tabelas 1:1 a mais fariam toda consulta sobre uma pessoa juntar
    quatro. É o "o que podia ser coluna vira coluna" da spec de 02/09."""
    assert any(f.name == "avatar" for f in Usuario._meta.fields)
    assert any(f.name == "avatar_tipo" for f in Usuario._meta.fields)
    assert not apps.is_installed("contas") or not any(
        m._meta.model_name == "avatar" for m in apps.get_models())


class TestEnviar:
    def test_grava_a_foto(self, logada, ana):
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        ana.refresh_from_db()
        assert bytes(ana.avatar) == PNG
        assert ana.avatar_tipo == "image/png"

    def test_reenviar_substitui_em_vez_de_duplicar(self, logada, ana):
        """Não há mais linha para duplicar — só a coluna de sempre, que a
        segunda gravação sobrescreve."""
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/webp", WEBP)})
        ana.refresh_from_db()
        assert bytes(ana.avatar) == WEBP
        assert ana.avatar_tipo == "image/webp"

    def test_o_que_nao_e_imagem_e_recusado_pelo_conteudo(self, logada, ana):
        """O tipo declarado diz `image/png`; os bytes dizem outra coisa. Quem
        decide são os bytes."""
        veneno = b"<?php system($_GET['c']); ?>"
        logada.post(reverse("perfil_foto"),
                    {"recorte": url_de_dados("image/png", veneno)})
        ana.refresh_from_db()
        assert not ana.avatar

    def test_svg_e_recusado_mesmo_sendo_imagem(self, logada, ana):
        """SVG é XML e pode carregar script, e o avatar é desenhado num `<img>`
        no cabeçalho de toda página."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'
        logada.post(reverse("perfil_foto"),
                    {"recorte": url_de_dados("image/svg+xml", svg)})
        ana.refresh_from_db()
        assert not ana.avatar

    def test_grande_demais_e_recusada_dizendo_o_limite(self, logada, ana):
        """A mensagem precisa dizer o limite: 'falhou' sem número manda a
        pessoa tentar de novo às cegas."""
        gigante = b"\x89PNG\r\n\x1a\n" + b"\x00" * (1024 * 1024 + 10)
        resposta = logada.post(reverse("perfil_foto"),
                               {"recorte": url_de_dados("image/png", gigante)},
                               follow=True)
        ana.refresh_from_db()
        assert not ana.avatar
        assert "KB" in resposta.content.decode()

    def test_so_aceita_post(self, logada):
        assert logada.get(reverse("perfil_foto")).status_code == 405

    def test_base64_corrompido_e_recusado_dizendo_isso_e_nao_vazio(self, logada, ana):
        """`b64decode` falha, e o corpo NÃO é vazio — é corrompido. Confundir
        os dois manda a pessoa procurar um arquivo que sumiu, quando o
        problema de verdade é o recorte que não terminou de chegar."""
        resposta = logada.post(reverse("perfil_foto"),
                                {"recorte": "data:image/png;base64,!!!nao-e-base64!!!"},
                                follow=True)
        ana.refresh_from_db()
        assert not ana.avatar
        assert "O arquivo está vazio" not in resposta.content.decode()
        assert "Não foi possível ler o arquivo enviado." in resposta.content.decode()


class TestServir:
    def test_devolve_os_bytes_com_o_tipo_certo(self, logada, ana):
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        resposta = logada.get(reverse("avatar", args=[ana.pk]))
        assert resposta.status_code == 200
        assert resposta.content == PNG
        assert resposta["Content-Type"] == "image/png"

    def test_traz_os_cabecalhos_seguros(self, logada, ana):
        """Bytes enviados por terceiro servidos pela nossa origem: `nosniff` e
        a CSP com `sandbox` são a segunda tranca."""
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        resposta = logada.get(reverse("avatar", args=[ana.pk]))
        assert resposta["X-Content-Type-Options"] == "nosniff"
        assert "sandbox" in resposta["Content-Security-Policy"]

    def test_quem_nao_tem_foto_da_404(self, logada, ana):
        assert logada.get(reverse("avatar", args=[ana.pk])).status_code == 404

    def test_a_foto_de_uma_pessoa_nao_sai_no_lugar_da_de_outra(self, logada, ana, db):
        from tests.conftest import empresa_do_teste, por_na_conta

        bruno = Usuario.objects.create_user(email="bruno@teste.com", password=SENHA)
        # Da mesma conta: foto de outra conta não se serve (ver o teste abaixo).
        empresa = empresa_do_teste()
        por_na_conta(ana, empresa)
        por_na_conta(bruno, empresa)
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        outro = Client()
        outro.post(reverse("entrar"), {"usuario": "bruno@teste.com", "senha": SENHA})
        outro.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/webp", WEBP)})

        assert logada.get(reverse("avatar", args=[bruno.pk])).content == WEBP
        assert logada.get(reverse("avatar", args=[ana.pk])).content == PNG

    def test_foto_de_outra_conta_nao_se_serve(self, logada, ana, db):
        """A rota só exigia login: quem entrasse em qualquer conta baixava as
        fotos de todas as outras percorrendo os ids, e a fila do Fila Zero
        publica esses ids no HTML (revisão final, 15/09/2026). Mesmo 404 de
        quem não tem foto, para não dizer que a pessoa existe."""
        from plataforma.models import Empresa
        from tests.conftest import abrir_conta, empresa_do_teste, por_na_conta

        por_na_conta(ana, empresa_do_teste())
        outra = Empresa.objects.create(razao_social="Concorrente", nome_fantasia="C")
        carla = abrir_conta(outra, "carla", SENHA)
        dela = Client()
        dela.post(reverse("entrar"), {"usuario": carla.email, "senha": SENHA})
        dela.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        assert dela.get(reverse("avatar", args=[carla.pk])).status_code == 200
        assert logada.get(reverse("avatar", args=[carla.pk])).status_code == 404

    def test_quem_nao_entrou_nao_ve(self, ana, db):
        assert Client().get(reverse("avatar", args=[ana.pk])).status_code == 302

    def test_usuario_id_inexistente_da_404_igual_a_quem_nao_tem_foto(self, logada):
        """De propósito indistinguível de `test_quem_nao_tem_foto_da_404`: se
        um id inexistente respondesse diferente de um id existente sem foto,
        a rota viraria um jeito de descobrir, por tentativa, quais usuários
        existem no sistema — o mesmo motivo pelo qual `exigir_permissao`
        devolve 404 e não 403."""
        assert logada.get(reverse("avatar", args=[999999])).status_code == 404


class TestATela:
    def test_o_formulario_da_foto_tambem_traz_o_token(self, logada):
        """Cada formulário da tela precisa do SEU token. Sem o da foto, o
        envio morre em 403.

        São QUATRO desde 09/09/2026: foto, senha, o seletor de idioma desta
        tela e o do CABEÇALHO, que aparece em toda página (ver
        `tests/test_idioma.py`). O número exato é de propósito — um
        formulário novo sem token passaria despercebido num `>= 1`."""
        html = logada.get(reverse("perfil")).content.decode()
        assert html.count("csrfmiddlewaretoken") == 4

    def test_o_backend_publica_a_url_da_foto(self, logada, ana):
        from contas.backend import BackendDjango

        assert BackendDjango().buscar(str(ana.pk)).avatar == ""
        logada.post(reverse("perfil_foto"), {"recorte": url_de_dados("image/png", PNG)})
        assert BackendDjango().buscar(str(ana.pk)).avatar == reverse("avatar", args=[ana.pk])

    def test_o_sinalizador_de_foto_nunca_ecoa_o_valor(self, logada):
        """Mesma regra de `?ok=` (`tests/test_meu_perfil.py`): a tela lê a
        PRESENÇA de `?foto=`, nunca o valor — colar qualquer coisa na URL não
        pode voltar refletido no HTML."""
        from contas.views_perfil import MENSAGEM_FOTO_SALVA

        html = logada.get(reverse("perfil") + "?foto=<script>alert(1)</script>").content.decode()
        assert MENSAGEM_FOTO_SALVA in html
        assert "<script>alert(1)</script>" not in html
