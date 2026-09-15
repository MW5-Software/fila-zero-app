from django.apps import AppConfig


class NucleoConfig(AppConfig):
    """O design system: tema, componentes, layout.

    Não tem model nenhum nesta entrega, e é de propósito: o núcleo desenha
    tela, não guarda dado. Quem guarda é `plataforma` e `contas`.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "nucleo"
