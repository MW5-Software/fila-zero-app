"""O titular que já existe ganha `conta.ver` (spec 2026-09-17, E4).

As permissões do titular são DIRETAS, e vêm de `contas.fabrica.aplicar` no
momento em que o nível é gravado. Quem já era titular antes desta tela não
passa por lá de novo, e a tela de Conta nasceria inalcançável justamente para
quem ela existe — o mesmo tropeço que a fila já teve com `fila.relatorios`.

**Acrescenta, e não reescreve.** `aplicar` troca o conjunto inteiro pelo da
fábrica, e rodá-lo aqui apagaria o que a MW5 tenha concedido à mão a um
titular. Esta migração só soma a linha que falta.

A permissão pode ainda não existir como `Permission`: ela é materializada no
`post_migrate` (`contas.permissoes.materializar`), que roda DEPOIS das
migrações. Quando falta, a migração não faz nada e o `post_migrate` seguinte
resolve — é por isso que ela não levanta erro aqui.
"""

from django.db import migrations

#: Nível TITULAR congelado como literal, pelo mesmo motivo de
#: `contas/cargos_de_fabrica.py`: esta migração roda com modelos históricos, e
#: a escala de `Nivel` já mudou duas vezes.
_TITULAR = 1


def _dar_conta_ver(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Usuario = apps.get_model("contas", "Usuario")
    usando = schema_editor.connection.alias

    permissao = (Permission.objects.using(usando)
                 .filter(codename="conta_ver").first())
    if permissao is None:
        return
    for titular in Usuario.objects.using(usando).filter(nivel=_TITULAR):
        titular.user_permissions.add(permissao)


def _tirar_conta_ver(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Usuario = apps.get_model("contas", "Usuario")
    usando = schema_editor.connection.alias

    permissao = (Permission.objects.using(usando)
                 .filter(codename="conta_ver").first())
    if permissao is None:
        return
    for titular in Usuario.objects.using(usando).filter(nivel=_TITULAR):
        titular.user_permissions.remove(permissao)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0005_cargo_pode_conceder"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(_dar_conta_ver, _tirar_conta_ver),
    ]
