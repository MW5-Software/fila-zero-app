"""O rótulo do alcance do cargo diz o que se enxerga (18/09/2026).

As OPÇÕES mudaram de nome — "Os próprios", "A filial" e "A empresa" viraram
"Só os registros da própria pessoa", "Os registros da filial" e "Os registros
da empresa" —, e o `choices` do campo é estado do modelo: sem esta migração o
`makemigrations --check` da suíte fica vermelho, e é ele que diz que o banco
está atrás do código.

**Nada muda no banco.** Os VALORES gravados são os mesmos (`proprios`,
`filial`, `empresa`), e não há dado a converter: o que mudou foi só o que a
tela escreve em cima deles.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0007_titular_ganha_conta_ver_de_verdade'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cargo',
            name='alcance',
            field=models.CharField(choices=[('proprios', 'Só os registros da própria pessoa'), ('filial', 'Os registros da filial'), ('empresa', 'Os registros da empresa')], default='proprios', max_length=20, verbose_name='alcance'),
        ),
    ]