"""A promessa central da matriz: módulo declarado DEPOIS que a instalação já
rodou a semeadura ganha a linha sozinho, sem perder o que já estava ligado.

A migração `0002_semear_modulos` (Task 8) semeia uma vez só, no dia em que
roda — e por isso não cobre este caminho: ela já tinha rodado nas vinte
instalações antes de qualquer módulo novo existir no código. Quem fecha essa
lacuna é o receptor de `post_migrate` em `plataforma/apps.py`
(`_semear_apos_migrar`), que roda a cada `manage.py migrate`, mesmo quando
não há nenhuma migração nova para aplicar — o mesmo mecanismo que o Django
usa para semear `Permission` e `ContentType`.

Este é exatamente o buraco que apareceu ao rodar contra o banco real já
migrado deste repositório (ver o relatório da Task 10): nenhuma suíte que só
sobe num banco novo pega esta classe de defeito, porque um banco novo roda
todas as migrações em sequência, com o módulo já declarado antes da
primeira.
"""

import pytest

from plataforma.declaracao import ModuloSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


@pytest.mark.django_db
class TestOCaminhoDeAtualizacao:
    """O caminho que os nove passos de um roteiro de aceitação num banco
    novo nunca exercitam: declarar um módulo depois de a base já estar de
    pé, com outro módulo já ligado."""

    def test_modulo_declarado_depois_da_primeira_semeadura_ganha_linha_desligada(
        self, catalogo_limpo,
    ):
        """Chamando `semear()` de novo diretamente — o caminho essencial,
        independente de como ele é disparado (migração de tiro único, na
        primeira vez; `post_migrate`, todas as vezes seguintes)."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ModuloSpec(chave="frete", rotulo="Frete"))
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)

        # Só agora — depois de a instalação já ter rodado a semeadura e já
        # ter uma escolha feita — o código passa a declarar um segundo
        # módulo. É o que aconteceria ao acrescentar `modulos/exemplo/` (ou
        # qualquer módulo futuro) numa base que já tinha `plataforma`
        # migrada.
        registrar(ModuloSpec(chave="tardio", rotulo="Tardio"))
        semear()

        assert Modulo.objects.get(chave="tardio").ativo is False
        # E a escolha que já existia não foi mexida pela segunda semeadura.
        assert Modulo.objects.get(chave="frete").ativo is True

    def test_o_post_migrate_de_verdade_semeia_o_modulo_declarado_depois(
        self, catalogo_limpo,
    ):
        """A prova de que o gancho está de fato ligado: rodar `manage.py
        migrate` — sem nenhuma migração nova para aplicar — precisa deixar
        a linha do módulo criada, porque é o `post_migrate` (não uma
        migração) quem semeia agora."""
        from django.core.management import call_command

        from plataforma.models import Modulo

        registrar(ModuloSpec(chave="tardio", rotulo="Tardio"))
        assert not Modulo.objects.filter(chave="tardio").exists()

        call_command("migrate", verbosity=0)

        assert Modulo.objects.get(chave="tardio").ativo is False

    def test_o_receptor_repassa_o_using_do_sinal_para_semear(self, catalogo_limpo):
        """`_semear_apos_migrar` recebe `using` do sinal `post_migrate` — o
        banco que aquele `migrate` de fato migrou — e ignorá-lo faria a
        semeadura sempre acontecer no banco padrão, mesmo numa instalação
        com mais de um banco configurado. Mesmo padrão de
        `django.contrib.auth.management.create_permissions`, citado como
        precedente no docstring do receptor."""
        from unittest.mock import patch

        import plataforma.apps as apps_mod

        with patch("plataforma.catalogo.semear") as semear_falso:
            apps_mod._semear_apos_migrar(sender=None, apps=None, using="default")

        semear_falso.assert_called_once_with(None, using="default")
