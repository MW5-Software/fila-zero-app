"""Toda tabela NOSSA carrega um GUID.

Existe porque o pedido é "um identificador estável em todas as tabelas", e um
pedido desses só se cumpre por varredura: a tabela de amanhã nasce sem ele se
depender de alguém lembrar, e a falta só aparece no dia em que alguém de fora
pede o registro por um id que não existe.

As tabelas do Django (`auth_permission`, `django_content_type`,
`django_session`) ficam de fora porque não são nossas — não há onde
acrescentar coluna nelas, e é essa a mesma razão pela qual o usuário passou a
ser próprio.
"""

import pytest
from django.apps import apps

#: Os nossos apps. Um app novo entra aqui, e é de propósito que a lista seja
#: explícita: `INSTALLED_APPS` inteiro traria os do Django junto.
APPS_DA_CASA = ("contas", "plataforma", "comum", "fila")

#: Sem GUID, com o motivo ao lado. Uma isenção sem motivo vira gaveta, e
#: gaveta ninguém relê.
ISENTOS: dict[str, str] = {}


def _models_da_casa():
    for model in apps.get_models():
        if model._meta.app_label not in APPS_DA_CASA:
            continue
        if model._meta.auto_created:      # tabelas de ligação M2M
            continue
        yield model


def test_todo_model_nosso_tem_guid():
    faltando = [
        m._meta.label for m in _models_da_casa()
        if not any(f.name == "guid" for f in m._meta.fields)
        and m._meta.label not in ISENTOS
    ]
    assert faltando == [], (
        f"models sem GUID: {faltando}. Herde `comum.guid.ComGuid` — ou "
        f"acrescente a `ISENTOS` com o motivo escrito ao lado."
    )


def test_o_guid_e_unico_e_nao_editavel():
    """Único porque é ele que identifica a linha de fora; não editável porque
    um identificador que muda não identifica nada."""
    from plataforma.models import Empresa

    campo = Empresa._meta.get_field("guid")
    assert campo.unique is True
    assert campo.editable is False
