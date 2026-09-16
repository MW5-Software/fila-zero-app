"""O banco da instalação existe e traz o que a autenticação precisa.

Um teste de fundação: se ele falha, nada mais desta entrega roda, e o erro
aparece aqui em vez de disfarçado três tarefas adiante.
"""

import pytest
from django.conf import settings


def test_os_apps_de_autenticacao_estao_instalados():
    for app in ("django.contrib.auth", "django.contrib.sessions",
                "django.contrib.contenttypes", "django.contrib.messages"):
        assert app in settings.INSTALLED_APPS


def test_os_apps_do_kronos_estao_instalados():
    assert "contas" in settings.INSTALLED_APPS
    assert "plataforma" in settings.INSTALLED_APPS


def test_o_middleware_de_sessao_e_de_autenticacao_esta_no_lugar():
    """A sessão pode vir por uma SUBCLASSE do `SessionMiddleware` — desde
    14/09/2026 é `comum.sessao_por_cabecalho.MiddlewareDeSessao`, que lê a
    chave do cabeçalho em `/api/`. O que não pode é a sessão sumir; o nome
    exato do Django não é o que importa, e conferir por ele recusava a
    subclasse."""
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.utils.module_loading import import_string

    assert any(issubclass(import_string(caminho), SessionMiddleware)
               for caminho in settings.MIDDLEWARE)
    assert "django.contrib.auth.middleware.AuthenticationMiddleware" in settings.MIDDLEWARE


def test_o_csrf_continua_ligado():
    """A entrega 1 achou o CsrfViewMiddleware removido por engano. Não volta a sair."""
    assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
    assert "django.middleware.clickjacking.XFrameOptionsMiddleware" in settings.MIDDLEWARE


@pytest.mark.django_db
def test_o_usuario_do_django_grava_e_le():
    from contas.models import Usuario
    
    Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
    assert Usuario.objects.filter(email="ana@teste.com").exists()


@pytest.mark.django_db
def test_a_senha_nao_fica_em_texto_puro():
    """O Perform ON guarda senha em texto puro. Aqui isso não acontece nem por acidente."""
    from contas.models import Usuario
    
    u = Usuario.objects.create_user(email="bruno@teste.com", password="segredo-de-teste")
    assert u.password != "segredo-de-teste"
    assert u.check_password("segredo-de-teste")
