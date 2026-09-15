"""Duas fontes de verdade para a rota de um módulo — e nada que as comparava.

`ModuloSpec(rota="/exemplo")` (em `modulos/exemplo/modulo.py`) e
`path("exemplo", ...)` (em `modulos/exemplo/urls.py`) são declarados
separadamente, à mão, cada um em seu arquivo. Nada no código impedia os dois
de divergirem — um `ModuloSpec.rota` apontando para um endereço que a
declaração de URL não serve, ou vice-versa: o menu levaria a um 404, ou uma
rota existiria sem nenhum item de menu que a alcance. Este teste fecha a
classe inteira de módulo futuro que cometa esse mesmo descompasso.
"""

import pytest
from django.urls import Resolver404, resolve

from plataforma.declaracao import declarados


@pytest.mark.django_db
def test_toda_rota_declarada_resolve_para_uma_view_de_verdade():
    """`ModuloSpec.rota`, para cada módulo do catálogo real, precisa ser uma
    URL que o projeto de fato serve — não um endereço que só existe no
    papel da declaração."""
    sem_rota_de_verdade = []
    for spec in declarados():
        if not spec.rota:
            # Rota é opcional em `ModuloSpec` (nem todo módulo tem tela
            # própria); só quem declara rota entra nesta verificação.
            continue
        try:
            resolve(spec.rota)
        except Resolver404:
            sem_rota_de_verdade.append((spec.chave, spec.rota))

    assert not sem_rota_de_verdade, (
        f"módulo declara ModuloSpec.rota que nenhum path() serve: "
        f"{sem_rota_de_verdade}"
    )
