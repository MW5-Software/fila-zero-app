"""O caminho completo de um módulo, do código até a tela.

Este é o teste que prova o mecanismo da matriz: o módulo se declara no
código, a migração cria a linha desligada, a MW5 liga na tela, e ele aparece
no menu de quem tem permissão — sem ninguém editar código.
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import dar_permissoes


@pytest.mark.django_db
class TestOCicloCompleto:
    def test_o_modulo_esta_declarado_no_codigo(self):
        from plataforma.declaracao import declarados

        assert "exemplo" in [m.chave for m in declarados()]

    def test_a_migracao_criou_a_linha_desligada(self):
        from plataforma.models import Modulo

        assert Modulo.objects.get(chave="exemplo").ativo is False

    def test_desligado_a_rota_nao_existe_nem_para_o_superusuario(self):
        """Módulo desligado não é só menu escondido: a porta está trancada."""
        Usuario.objects.create_superuser(
            email="raiz@teste.com", password="segredo-de-teste")
        c = Client()
        # A chave lida por `entrar` é `usuario`, não `login` — ver o
        # comentário em `contas/views.py`.
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 404

    def test_ligado_e_com_permissao_a_tela_abre(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        ana = Usuario.objects.create_user(
            email="ana@teste.com", password="segredo-de-teste")
        # Concessão por `Permission` direta, não por nome de grupo: o nome
        # de grupo não concede nada (correção final da revisão de branch).
        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        # `get_or_create`, não `create`: desde a Task 2, `post_migrate` já
        # materializa esta permissão — `create` colidiria com a linha que o
        # próprio `migrate` da suíte acabou de criar.
        permissao, _ = Permission.objects.get_or_create(
            codename="exemplo_ver", content_type=tipo,
            defaults={"name": "ver exemplo"})
        dar_permissoes(ana, permissao.codename)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 200

    def test_ligado_e_com_permissao_pelo_cargo_sem_grupo_a_tela_abre(self):
        """O caminho canônico de conceder é uma `Permission` num cargo — sem
        grupo nenhum de permeio. Ponta a ponta por
        requisição HTTP, não no nível da função: é a porta que a gestão de
        usuários da entrega 2 vai usar de verdade."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        carla = Usuario.objects.create_user(
            email="carla@teste.com", password="segredo-de-teste")
        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        # `get_or_create`: ver comentário no teste acima.
        permissao, _ = Permission.objects.get_or_create(
            codename="exemplo_ver", content_type=tipo,
            defaults={"name": "ver exemplo"})
        dar_permissoes(carla, permissao.codename)

        assert carla.groups.count() == 0

        c = Client()
        c.post(reverse("entrar"),
               {"usuario": "carla@teste.com", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 200

    def test_ligado_e_sem_permissao_a_tela_nao_abre(self):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        Usuario.objects.create_user(
            email="bruno@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "bruno@teste.com", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 404


@pytest.mark.django_db
class TestORotuloEOMenu:
    """O rótulo "Exemplo" precisa ser exclusivo dele — sem isto, um teste
    baseado em `"Exemplo" in html` poderia passar pelo motivo errado, como
    aconteceu com "Frete" na Task 9.
    """

    def test_o_rotulo_nao_colide_com_texto_decorativo(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        ana = Usuario.objects.create_user(
            email="ana@teste.com", password="segredo-de-teste")
        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        # `get_or_create`: ver comentário em `TestOCicloCompleto` acima.
        permissao, _ = Permission.objects.get_or_create(
            codename="exemplo_ver", content_type=tipo,
            defaults={"name": "ver exemplo"})
        dar_permissoes(ana, permissao.codename)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        html = c.get("/exemplo").content.decode()

        # As quatro fontes legítimas do rótulo nesta página: a <title> da
        # aba, o item do menu lateral, a migalha de pão (breadcrumb) e o
        # <h1> do cabeçalho — todas vindas do próprio `ModuloSpec`, nenhuma
        # de texto decorativo de outro lugar. Contar em vez de só checar
        # presença é o que garante que não há colisão com nenhum outro texto
        # da tela, como aconteceu com "Frete" na Task 9.
        assert html.count("Exemplo") == 4

    def test_ligar_faz_o_modulo_aparecer_no_menu(self):
        """A promessa da entrega, do outro lado: ligar aqui muda a tela de
        lá — sem ninguém editar código."""
        from plataforma.models import Modulo

        raiz = Usuario.objects.create_superuser(
            email="raiz@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})

        antes = c.get("/").content.decode()
        assert "Exemplo" not in antes

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        depois = c.get("/").content.decode()
        assert "Exemplo" in depois
