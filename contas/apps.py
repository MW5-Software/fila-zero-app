from django.apps import AppConfig


class ContasConfig(AppConfig):
    """Login, sessão e a tradução do usuário do Django para o do núcleo.

    Não define model de usuário: o `auth_user` do Django já existe, já guarda
    a senha em hash, e reescrevê-lo seria perder isso.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"

    def ready(self) -> None:
        # A declaração roda em `ready()`, não na importação de `modulo.py` —
        # mesmo motivo de `modulos.exemplo.apps.ExemploConfig.ready()`:
        # registrar no corpo do módulo dependeria da ordem de import entre os
        # apps, e em `ready()` o Django já garante o registro de apps pronto
        # e uma única execução por subida.
        from plataforma.declaracao import registrar
        from plataforma.parametro_declaracao import registrar as registrar_parametro

        from .modulo import MODULO_AUDITORIA, MODULO_CARGOS, MODULO_USUARIOS
        from .parametro import (
            PARAMETRO_DIAS_PARA_EXPIRAR_SENHA, PARAMETRO_MINUTOS_DE_SESSAO,
        )

        registrar(MODULO_CARGOS)
        registrar(MODULO_USUARIOS)
        registrar(MODULO_AUDITORIA)

        # Os parâmetros de acesso seguem a mesma regra de declaração dos
        # módulos: em `ready()`, nunca na importação (ver o comentário de
        # cima). Não semear linha nenhuma — a ausência É o padrão.
        registrar_parametro(PARAMETRO_MINUTOS_DE_SESSAO)
        registrar_parametro(PARAMETRO_DIAS_PARA_EXPIRAR_SENHA)

        from django.db.models.signals import post_save

        # `dispatch_uid` para o receptor não ser ligado duas vezes se `ready()`
        # for chamado de novo num teste — a conta nova nasceria semeada duas
        # vezes, e a segunda bateria na unicidade `cargo_unico_por_conta`.
        post_save.connect(_semear_cargos_do_titular, sender="contas.Usuario",
                          dispatch_uid="contas_semear_cargos_do_titular")


def _semear_cargos_do_titular(sender, instance, **kwargs):
    """A conta nova nasce com os cinco cargos de fábrica.

    Em todo `save`, e não só no `created`: `dar_acesso` e a tela de usuários
    promovem a titular com `save(update_fields=["nivel"])`. A semeadura é
    idempotente — só cria o que falta —, então o custo nos outros saves é uma
    consulta.

    **Menos um save, e não menos zero.** `update_last_login`
    (`django.contrib.auth`) grava `save(update_fields=["last_login"])` a CADA
    login — sem esta saída antecipada, o titular pagaria a consulta de
    semeadura em todo login, para nunca achar cargo faltando. `update_fields`
    presente e sem `"nivel"` é o sinal de que esta chamada não pode ter
    promovido ninguém: só uma mudança de `nivel` cria cargo novo.
    """
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "nivel" not in update_fields:
        return

    from .models import Nivel

    if instance.nivel != Nivel.TITULAR:
        return
    from .cargos_de_fabrica import semear_cargos

    semear_cargos(instance)
