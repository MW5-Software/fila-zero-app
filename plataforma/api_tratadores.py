"""Como a API responde quando algo dá errado — um formato só.

Os tratadores padrão do Ninja devolvem `{"detail": ...}` para schema e 404, e
para exceção fazem pior: com `DEBUG` engolem e mostram o traceback em texto
(a tela de Falhas não vê); sem `DEBUG` re-levantam, e o app recebe a página
500 em HTML. Aqui todos saem no formato de `comum.respostas_da_api.erro`.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError as ErroDoDjango
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from ninja.errors import HttpError, ValidationError as ErroDoNinja

from comum.respostas_da_api import erro, nao_existe

from .falhas import registrar_falha

__all__ = ["instalar_tratadores", "tratar_falha"]

_CONFIRA = _("Confira os campos destacados.")


def _validacao_do_django(request, exc):
    """Inclui a de `ModeloDaEmpresa.save` (empresa sem titular, conta errada)."""
    if hasattr(exc, "error_dict"):
        campos = exc.message_dict
    else:
        campos = {"__all__": exc.messages}
    return erro(422, "validacao", _CONFIRA, campos)


def _validacao_do_ninja(request, exc):
    campos: dict[str, list[str]] = {}
    for item in exc.errors:
        local = item.get("loc") or ("__all__",)
        campos.setdefault(str(local[-1]), []).append(str(item.get("msg", "")))
    return erro(422, "validacao", _CONFIRA, campos)


def _nao_existe(request, exc):
    """O texto do `Http404` fica de fora: pode dizer o que não se achou, e
    quem não pode não descobre nem isso."""
    return nao_existe()


def _http(request, exc):
    return erro(exc.status_code, "erro", str(exc))


def tratar_falha(request, exc):
    """Sem `DEBUG`, grava pela mesma porta do middleware e responde JSON com o
    GUID da falha — o que a pessoa passa ao suporte. Com `DEBUG`, re-levanta:
    quem grava é o `MiddlewareDeFalhas`, como na web, e o desenvolvedor vê a
    página técnica do Django."""
    if settings.DEBUG:
        raise exc
    falha = registrar_falha(request, exc)
    return erro(500, "falha",
                _("Algo inesperado aconteceu. O problema foi registrado."),
                extra={"id": str(falha.guid) if falha is not None else None})


def instalar_tratadores(api) -> None:
    api.add_exception_handler(Exception, tratar_falha)
    api.add_exception_handler(Http404, _nao_existe)
    api.add_exception_handler(HttpError, _http)
    api.add_exception_handler(ErroDoNinja, _validacao_do_ninja)
    api.add_exception_handler(ErroDoDjango, _validacao_do_django)
