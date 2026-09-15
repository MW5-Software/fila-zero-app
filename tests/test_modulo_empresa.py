"""O módulo Empresa precisa nascer LIGADO em toda instalação nova.

Mesmo raciocínio de `tests/test_modulo_usuarios.py`: sem `ativo_por_padrao=True`
(`plataforma/modulo.py`), a instalação subiria com a própria tela de Empresa
inalcançável até a MW5 lembrar de ligar a chavinha — perigo de instalação, não
funcionalidade. Este teste trava o valor de verdade, e não um `ModuloSpec` de
laboratório: verifica o argumento real, e a linha que o `post_migrate` desta
suíte já semeou.
"""

import pytest


@pytest.mark.django_db
def test_o_modulo_empresa_declara_ativo_por_padrao():
    from plataforma.declaracao import declarados

    spec = next(m for m in declarados() if m.chave == "empresa")
    assert spec.ativo_por_padrao is True


@pytest.mark.django_db
def test_a_semeadura_real_ja_deixou_o_modulo_empresa_ligado():
    """A prova de verdade: a linha que o `post_migrate` desta suíte já criou
    para o módulo de `plataforma/modulo.py` — não um `ModuloSpec` de teste."""
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="empresa").ativo is True
