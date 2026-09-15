from django.apps import AppConfig


class FilaConfig(AppConfig):
    """A fila da vez das lojas — o produto do Fila Zero.

    O registro do módulo roda em `ready()`, e não na importação de `modulo.py`,
    pelo motivo escrito em `modulos/exemplo/apps.py`: registrar no corpo do
    arquivo faria o registro depender da ordem de import entre os apps.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "fila"
    verbose_name = "Fila da vez"

    def ready(self) -> None:
        from plataforma.declaracao import registrar
        from plataforma.filiais import antes_de_desativar

        from .modulo import MODULO
        from .sinais import recusar_desativar_loja_com_gente

        registrar(MODULO)
        # `dispatch_uid`: o `ready()` pode rodar mais de uma vez nos testes, e
        # o receptor ligado duas vezes responderia duas vezes.
        antes_de_desativar.connect(recusar_desativar_loja_com_gente,
                                   dispatch_uid="fila_loja_com_gente")
