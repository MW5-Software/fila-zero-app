"""O módulo Auditoria precisa nascer LIGADO em toda instalação nova.

Mesmo raciocínio de `tests/test_modulo_filiais.py`: a trilha grava desde a
primeira ação de sempre (o primeiro login), então uma instalação que sobe
com a tela de leitura desligada tem um registro que ninguém consegue ler —
a auditoria só presta quando quem responde pelas pessoas consegue consultá-la.
"""

import pytest


@pytest.mark.django_db
def test_o_modulo_auditoria_declara_ativo_por_padrao():
    from plataforma.declaracao import declarados

    spec = next(m for m in declarados() if m.chave == "auditoria")
    assert spec.ativo_por_padrao is True


@pytest.mark.django_db
def test_a_semeadura_real_ja_deixou_o_modulo_auditoria_ligado():
    """A prova de verdade: a linha que o `post_migrate` desta suíte já criou
    para o módulo declarado em `contas/modulo.py`."""
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="auditoria").ativo is True
