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
        from contas.entrada import destino_depois_de_entrar
        from plataforma.declaracao import registrar
        from plataforma.filiais import antes_de_desativar
        from plataforma.parametro_declaracao import registrar as registrar_parametro

        from .modulo import MODULO
        from .parametro import PARAMETRO_META_PARA_GESTOR
        from .sinais import destino_do_vendedor, recusar_desativar_loja_com_gente

        registrar(MODULO)
        # O parâmetro entra pelo mesmo caminho do módulo, e pelo mesmo motivo:
        # declarar no corpo de `parametro.py` faria o registro depender da
        # ordem de import entre os apps. Ele NÃO semeia linha nenhuma — o
        # banco só ganha linha quando uma instalação muda o valor
        # (`plataforma.models.Parametro`).
        registrar_parametro(PARAMETRO_META_PARA_GESTOR)
        # `dispatch_uid`: o `ready()` pode rodar mais de uma vez nos testes, e
        # o receptor ligado duas vezes responderia duas vezes.
        antes_de_desativar.connect(recusar_desativar_loja_com_gente,
                                   dispatch_uid="fila_loja_com_gente")
        destino_depois_de_entrar.connect(destino_do_vendedor,
                                         dispatch_uid="fila_destino_do_vendedor")
