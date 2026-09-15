"""Toda empresa tem a Matriz (spec 2026-09-14, D7).

A Matriz é marcada por `e_matriz`, e não pelo nome: o titular pode renomeá-la, e
uma regra que procurasse a palavra "Matriz" deixaria de achar a filial no dia do
primeiro "Loja Centro".
"""

import pytest
from django.db import IntegrityError


@pytest.fixture
def empresa(db):
    from plataforma.models import Empresa

    return Empresa.objects.create(razao_social="Alfa Ltda")


def test_empresa_nova_nasce_com_a_matriz(empresa):
    matriz = empresa.filiais.get(e_matriz=True)
    assert matriz.nome == "Matriz"
    assert matriz.ativa is True


def test_editar_a_empresa_nao_cria_outra_matriz(empresa):
    empresa.razao_social = "Alfa Comércio Ltda"
    empresa.save()
    assert empresa.filiais.filter(e_matriz=True).count() == 1


def test_uma_matriz_por_empresa(empresa):
    from plataforma.models import Filial

    with pytest.raises(IntegrityError):
        Filial.objects.create(empresa=empresa, nome="Outra", apelido="Outra",
                              e_matriz=True)


def test_duas_empresas_tem_cada_uma_a_sua(empresa, db):
    from plataforma.models import Empresa, Filial

    Empresa.objects.create(razao_social="Beta Ltda")
    assert Filial.objects.filter(e_matriz=True).count() == 2


def test_a_matriz_renomeada_continua_sendo_a_matriz(empresa):
    matriz = empresa.filiais.get(e_matriz=True)
    matriz.nome = "Loja Centro"
    matriz.apelido = "Centro"
    matriz.save()
    assert empresa.filiais.get(e_matriz=True).nome == "Loja Centro"
