"""O módulo Usuários precisa nascer LIGADO em toda instalação nova.

Sem `ativo_por_padrao=True` (`contas/modulo.py`), a instalação subiria com o
titular sem como cadastrar nem alocar ninguém até a MW5 lembrar de ligar a
chavinha na tela de Módulos — um perigo na instalação, não uma
funcionalidade. Este teste trava o valor de verdade, e não um `ModuloSpec` de
laboratório.
"""

import pytest


@pytest.mark.django_db
def test_o_modulo_usuarios_declara_ativo_por_padrao():
    from plataforma.declaracao import declarados

    spec = next(m for m in declarados() if m.chave == "usuarios")
    assert spec.ativo_por_padrao is True


@pytest.mark.django_db
def test_a_semeadura_real_ja_deixou_o_modulo_usuarios_ligado():
    """A prova de verdade: a linha que o `post_migrate` desta suíte já criou
    para o `MODULO_USUARIOS` de `contas/modulo.py` — não um `ModuloSpec` de
    teste."""
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="usuarios").ativo is True
