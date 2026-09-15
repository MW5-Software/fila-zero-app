from django.apps import AppConfig


class ExemploConfig(AppConfig):
    """O módulo de exemplo: existe só para provar o mecanismo da matriz.

    A declaração roda em `ready()`, não na importação de `modulo.py` — decisão
    documentada em `plataforma/declaracao.py`. Registrar no corpo do módulo
    faria o registro depender da ordem de import entre os apps, o que é
    frágil e quebra de um jeito difícil de diagnosticar. Em `ready()`, o
    Django garante que o registro de apps já está pronto e que ele roda
    exatamente uma vez por subida.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "modulos.exemplo"

    def ready(self) -> None:
        from plataforma.declaracao import registrar

        from .modulo import MODULO

        registrar(MODULO)
