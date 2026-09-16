"""Filial por nome e com a conta; aparência da empresa com a conta (16/09/2026).

Porte do Portal de Vendas (`plataforma/0011` e `0012` de lá), numa migração só
porque aqui as duas chegam juntas.

- A `ordem` da filial sai: nenhuma tela a preenchia, e a lista saía na ordem
  de cadastro. A Matriz vem na frente e as outras pelo nome, com colação ICU
  (`comum.alfabetica`), porque o Postgres do Alpine ordena byte a byte.
- Filial e AparenciaDaEmpresa ganham `conta_guid`, o GUID do titular, como
  toda linha ligada a uma conta. Nulo só enquanto a empresa não tem titular.
  O preenchimento copia a conta da empresa de cada linha.

Voltar recria a `ordem` com zero e remove a conta, que se recalcula da
empresa.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def preencher(apps, schema_editor):
    Empresa = apps.get_model("plataforma", "Empresa")
    for nome in ("Filial", "AparenciaDaEmpresa"):
        modelo = apps.get_model("plataforma", nome)
        for empresa_id, conta_id in (Empresa._default_manager
                                     .exclude(conta__isnull=True)
                                     .values_list("pk", "conta_id")):
            modelo._default_manager.filter(empresa_id=empresa_id).update(
                conta_id=conta_id)


class Migration(migrations.Migration):

    dependencies = [
        ('plataforma', '0002_aparencia_da_empresa'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='filial',
            options={'ordering': ('-e_matriz', 'nome'), 'verbose_name': 'filial', 'verbose_name_plural': 'filiais'},
        ),
        migrations.RemoveField(
            model_name='filial',
            name='ordem',
        ),
        migrations.AddField(
            model_name='aparenciadaempresa',
            name='conta',
            field=models.ForeignKey(blank=True, db_column='conta_guid', help_text='O GUID da conta titular da empresa desta linha.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, to_field='guid', verbose_name='conta'),
        ),
        migrations.AddField(
            model_name='filial',
            name='conta',
            field=models.ForeignKey(blank=True, db_column='conta_guid', help_text='O GUID da conta titular da empresa desta linha.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, to_field='guid', verbose_name='conta'),
        ),
        migrations.AlterField(
            model_name='filial',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', max_length=120, verbose_name='nome'),
        ),
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
