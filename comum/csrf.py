"""O campo oculto do CSRF, para telas cujo template veio do design system.

Extraído daqui de `contas/views.py` e `plataforma/views.py`, onde vivia
duplicado verbatim — uma terceira tela (Meu Perfil) precisou dele e copiar
pela terceira vez deixaria de ser coincidência para virar dívida.
"""

from __future__ import annotations

from django.middleware.csrf import get_token
from django.utils.html import format_html

__all__ = ["campo_csrf"]


def campo_csrf(request) -> str:
    """O campo oculto do CSRF, pronto para entrar no HTML.

    Os templates portados do design system (`nucleo/templates/...`) não
    emitem `{% csrf_token %}` nem equivalente, e não dá para acrescentá-lo ali
    sem mexer em `nucleo/`. O caminho autorizado é este: montar o campo à mão
    (o mesmo HTML que `{% csrf_token %}` geraria) e injetá-lo via `Raw`, o
    componente que existe exatamente para HTML cru já confiável — como filho
    de um `Form`, ou na frente de uma lista de campos.
    """
    return format_html(
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
        get_token(request),
    )
