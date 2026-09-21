"""O fluxo da fila sai de `plataforma.Empresa` e vem para a tabela da fila.

Cria `fila.FluxoDaEmpresa` e copia para ela o fluxo das empresas que NÃO estão
no padrão (quem está no padrão não precisa de linha: sem linha é `VOLTA`). A
coluna antiga só sai depois, na `plataforma/0006`, que depende desta — a ordem
é o que garante que nenhum fluxo escolhido se perde no caminho.

`conta` é preenchida à mão: o model histórico não tem o `save()` de
`ModeloDaEmpresa`, que é quem a deriva da empresa.
"""

import django.db.models.deletion
import django.db.models.manager
import uuid
from django.conf import settings
from django.db import migrations, models


_PADRAO = "volta_para_a_fila"


def _copiar(apps, schema_editor):
    Empresa = apps.get_model("plataforma", "Empresa")
    FluxoDaEmpresa = apps.get_model("fila", "FluxoDaEmpresa")
    for empresa in (Empresa.objects.exclude(fluxo_da_fila=_PADRAO)
                    .exclude(fluxo_da_fila="").iterator()):
        FluxoDaEmpresa._default_manager.create(
            empresa_id=empresa.pk, conta_id=empresa.conta_id,
            fluxo=empresa.fluxo_da_fila)


def _devolver(apps, schema_editor):
    Empresa = apps.get_model("plataforma", "Empresa")
    FluxoDaEmpresa = apps.get_model("fila", "FluxoDaEmpresa")
    for linha in FluxoDaEmpresa._default_manager.iterator():
        Empresa.objects.filter(pk=linha.empresa_id).update(
            fluxo_da_fila=linha.fluxo)


class Migration(migrations.Migration):

    dependencies = [
        ('fila', '0006_correcao_por_na_fila'),
        ('plataforma', '0005_fluxo_da_fila'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FluxoDaEmpresa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Identificador estável desta linha para fora do sistema.', unique=True, verbose_name='GUID')),
                ('fluxo', models.CharField(choices=[('volta_para_a_fila', 'Volta para o fim da fila'), ('espera', 'Fica em espera e entra na fila quando quiser')], default='volta_para_a_fila', max_length=20, verbose_name='fluxo da fila')),
                ('conta', models.ForeignKey(db_column='conta_guid', help_text='A conta dona desta linha, identificada pelo GUID.', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, to_field='guid', verbose_name='conta')),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='plataforma.empresa', verbose_name='empresa')),
            ],
            options={
                'verbose_name': 'fluxo da fila da empresa',
                'verbose_name_plural': 'fluxos da fila das empresas',
                'abstract': False,
                'base_manager_name': 'irrestritos',
                'default_manager_name': 'irrestritos',
                'constraints': [models.UniqueConstraint(fields=('empresa',), name='fila_um_fluxo_por_empresa')],
            },
            managers=[
                ('irrestritos', django.db.models.manager.Manager()),
            ],
        ),
        migrations.RunPython(_copiar, _devolver),
    ]
