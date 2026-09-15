"""O Perfil saiu (14/09/2026: "Não tem mais perfil, é tudo cargo agora").

Tranca a volta por descuido: um import, uma rota ou um módulo que o traga de
volta fica vermelho aqui antes de virar dois jeitos de dar permissão — o
defeito que o `Group` do Django já tinha causado nesta casa.
"""

import pytest
from django.urls import NoReverseMatch, reverse


def test_nao_existe_mais_model_perfil_nem_papel():
    import contas.models as modelos

    assert not hasattr(modelos, "Perfil")
    assert not hasattr(modelos, "Papel")


def test_nao_existe_mais_rota_de_perfis():
    with pytest.raises(NoReverseMatch):
        reverse("perfis")


def test_modulo_perfis_nao_e_declarado():
    from plataforma.declaracao import declarados

    assert "perfis" not in {spec.chave for spec in declarados()}


def test_niveis_sao_master_titular_e_membro():
    from contas.models import Nivel

    assert [(n.value, n.name) for n in Nivel] == [
        (0, "MASTER"), (1, "TITULAR"), (2, "MEMBRO")]


def test_filial_nao_tem_mais_usuarios():
    from plataforma.models import Filial

    assert "usuarios" not in {f.name for f in Filial._meta.get_fields()}
