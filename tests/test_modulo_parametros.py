"""O módulo Parâmetros precisa nascer LIGADO em toda instalação nova.

Mesmo raciocínio de `tests/test_modulo_empresa.py`: sem `ativo_por_padrao=True`
(`plataforma/modulo.py`), a instalação subiria com a própria tela que resolve
"este cliente é diferente" (R47) inalcançável até a MW5 lembrar de ligar a
chavinha.
"""

import pytest


@pytest.mark.django_db
def test_o_modulo_parametros_declara_ativo_por_padrao():
    from plataforma.declaracao import declarados

    spec = next(m for m in declarados() if m.chave == "parametros")
    assert spec.ativo_por_padrao is True


@pytest.mark.django_db
def test_a_semeadura_real_ja_deixou_o_modulo_parametros_ligado():
    """A prova de verdade: a linha que o `post_migrate` desta suíte já criou
    para o módulo de `plataforma/modulo.py` — não um `ModuloSpec` de teste."""
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="parametros").ativo is True
