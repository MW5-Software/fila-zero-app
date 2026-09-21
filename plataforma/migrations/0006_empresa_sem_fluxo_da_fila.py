"""A coluna `fluxo_da_fila` sai da empresa: o fluxo agora é da fila.

Ela mora em `fila.FluxoDaEmpresa` desde 21/09/2026, e a base não carrega mais
um campo de módulo de negócio. Depende de `fila/0007`, que copia o fluxo das
empresas antes: é a ordem que garante que nenhum fluxo escolhido se perde.

**A KRONOS base tem uma cópia desta migração e da `0005`, com o mesmo nome**
(e sem a dependência da fila, que lá não existe): somadas, as duas não mudam
nada, e é isso que mantém a história de `plataforma` igual nos dois produtos —
sem elas, a próxima migração da base colidiria com estas aqui.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("plataforma", "0005_fluxo_da_fila"),
        ("fila", "0007_fluxo_da_empresa"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="empresa",
            name="fluxo_da_fila",
        ),
    ]
