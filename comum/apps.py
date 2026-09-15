from django.apps import AppConfig


class ComumConfig(AppConfig):
    """A infraestrutura que as telas de qualquer app usam.

    Nasceu de uma auditoria de dependências: `contas` e `plataforma` se
    importavam nos DOIS sentidos — 17 imports de topo num, 25 no outro — e
    dezesseis imports tardios, dentro de funções, existiam só para contornar
    a ordem de carga que isso criava.

    O diagnóstico foi que não eram duas camadas, e sim duas metades de uma
    camada só: listagem, exportação, filtros, CSRF e as guardas de rota não
    pertencem nem a "contas" nem a "plataforma" — são o chão em que as duas
    pisam. Aqui não mora regra de negócio nem model: se algo neste pacote
    precisar importar `contas` ou `plataforma`, é sinal de que não era deste
    pacote.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "comum"

    def ready(self) -> None:
        """Liga a invalidação da memória de pedido (`comum.memoria`).

        Sem `sender`: qualquer escrita em qualquer tabela avança a geração.
        O porquê de ser assim, e não uma lista de tabelas, está escrito no
        módulo — em resumo, lista de tabelas que decidem identidade é a
        coisa que envelhece calada.

        `dispatch_uid` porque `ready()` pode rodar mais de uma vez (o
        autoreload do runserver, um `django.setup()` num teste), e sem ele o
        mesmo receptor entraria duas vezes na lista de sinais.
        """
        from django.db.models.signals import (
            m2m_changed, post_delete, post_save,
        )

        from .memoria import esquecer

        for sinal in (post_save, post_delete, m2m_changed):
            sinal.connect(esquecer, dispatch_uid="comum.memoria.esquecer")
