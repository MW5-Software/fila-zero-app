"""O esquema da API, em texto — o contrato de que o app gera os tipos.

Comando, e não rota: `config/api.py` desliga o `openapi_url` para não publicar
o mapa das rotas. E comando em `config/`, e não um `management/commands` de
`plataforma`, porque gerar o esquema importa `config.api`, que junta os
routers de negócio — e a base não importa negócio.

Uso, depois de mudar qualquer operação ou schema:

    DJANGO_DEBUG=1 .venv/bin/python -m config.openapi

No SaaS que tiver app, `tests/test_tipos_do_app_conferem.py` fica vermelho
enquanto não rodar. A base não tem a pasta `app/`: aqui o comando serve para
ler o contrato (`esquema()`), e é isso que `tests/test_api_nao_expoe_id.py`
usa.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["DESTINO", "esquema", "esquema_em_texto"]

#: Onde o arquivo é gravado quando o SaaS tem app. A base não tem a pasta, e
#: gravar aqui é o passo que o produto com app dá — não a base.
DESTINO = Path(__file__).resolve().parent.parent / "app" / "openapi.json"


def esquema() -> dict:
    from config.api import api

    return api.get_openapi_schema(path_prefix="/api/")


def esquema_em_texto() -> str:
    """Chaves ordenadas e fim de linha no fim: o arquivo vai para o git, e um
    diff que muda de ordem a cada geração esconde a mudança de verdade.
    `default=str` para texto preguiçoso (`gettext_lazy`) que chegue a uma
    descrição."""
    return json.dumps(esquema(), ensure_ascii=False, indent=2, sort_keys=True,
                      default=str) + "\n"


def main() -> None:
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text(esquema_em_texto(), encoding="utf-8")
    print(f"gravado: {DESTINO}")


if __name__ == "__main__":
    main()
