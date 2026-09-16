"""A trilha de auditoria passa a guardar o GUID da conta (16/09/2026).

Porte do Portal de Vendas (`contas/0021` de lá). Valor, e não chave
estrangeira — ver `RegistroDeAuditoria.conta_guid`. As linhas antigas acham a
conta pelo `autor_login`; login que não é de ninguém, ou é da MW5, fica nulo.
Usa `update()` em lote, que não passa pelo `save()` append-only da trilha: é a
única escrita permitida nela, e acontece uma vez, aqui. Voltar só remove a
coluna.
"""

from django.db import migrations, models


def preencher(apps, schema_editor):
    Usuario = apps.get_model("contas", "Usuario")
    Registro = apps.get_model("contas", "RegistroDeAuditoria")
    for email, conta_id in (Usuario._default_manager
                            .exclude(conta__isnull=True)
                            .values_list("email", "conta_id")):
        Registro._default_manager.filter(autor_login__iexact=email).update(
            conta_guid=conta_id)


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0003_o_membro_se_chama_usuario'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrodeauditoria',
            name='conta_guid',
            field=models.UUIDField(blank=True, db_index=True, null=True, verbose_name='GUID da conta'),
        ),
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
