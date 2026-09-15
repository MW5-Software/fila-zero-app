"""O ambiente Jinja da página da fila, criado uma vez por processo.

A página da fila é a única, com a de entrar, fora do shell do dashboard, e os
templates dela moram em `fila/templates/`. `comum.ambiente.ambiente()` com
loader extra criaria um ambiente NOVO a cada requisição (o custo medido no
cabeçalho de `comum/ambiente.py`), e a fila é consultada a cada 3 segundos
por todo vendedor da rede. Por isso o app guarda o dele.

`_ensinar_a_traduzir` é importado de `comum.ambiente` mesmo sendo privado: é
o único jeito de o `traduzir(...)` dos templates daqui ser o mesmo da casa, e
um segundo mecanismo de tradução divergiria em silêncio.
"""

from __future__ import annotations

from functools import lru_cache

__all__ = ["ambiente_da_fila"]


@lru_cache(maxsize=1)
def ambiente_da_fila():
    from django.conf import settings
    from jinja2 import FileSystemLoader

    from comum.ambiente import _ensinar_a_traduzir
    from comum.estaticos import versionado
    from nucleo.rendering import create_environment

    from .tela import ha_quanto, hora_local, pessoas_na_frente
    from .valores import em_reais

    env = create_environment(
        FileSystemLoader(str(settings.BASE_DIR / "fila" / "templates")),
        FileSystemLoader(str(settings.BASE_DIR / "plataforma" / "templates")))
    _ensinar_a_traduzir(env)
    env.filters["ha_quanto"] = ha_quanto
    env.filters["hora"] = hora_local
    env.filters["reais"] = em_reais
    env.filters["na_frente"] = pessoas_na_frente
    env.globals["estatico"] = versionado
    return env
