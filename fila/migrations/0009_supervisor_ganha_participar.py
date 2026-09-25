"""O Supervisor de fábrica que já existe ganha `fila.participar` (25/09/2026).

O cliente: "supervisor não cadastrou gerente". A lista `pode_conceder` do
Supervisor diz Vendedor e Gerente, mas `contas.lugar.pode_dar` também exige que
quem concede tenha TODAS as permissões do cargo concedido, e os dois trazem
`fila.participar`, que o Supervisor não trazia. `contas/cargos_de_fabrica.py`
já nasce com ela; esta migração leva a mesma linha às contas que existem,
porque a semeadura só cria cargo que falta e nunca mexe no que existe.

Ele continua sem bater o ponto: quem tem `fila.gerenciar` não atende
(`fila/quem_atende.py`), e o Supervisor tem.

**Só o cargo DE FÁBRICA chamado `supervisor`**, e só SOMA a linha: um cargo
que o titular criou é dele, e o que ele tirou ou pôs no Supervisor continua.

A permissão é criada quando falta, como na `contas.0007`: ela nasce no
`post_migrate` (`contas.permissoes.materializar`), DEPOIS das migrações, e numa
instalação nova ainda não estaria lá. A linha é a mesma que o `materializar`
criaria, e ele não a duplica.

`desfazer` não faz nada: tirar a permissão apagaria também a de quem a ganhou
pela mão do titular.
"""

from django.db import migrations

#: Congelados como literais: a migração roda com modelos históricos.
_CODENAME = "fila_participar"
#: O nome que `contas.permissoes.rotulo_de("fila", "participar")` escreveria.
_NOME = "fila: participar"


def _dar(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Cargo = apps.get_model("contas", "Cargo")

    tipo, _criado = ContentType.objects.get_or_create(
        app_label="plataforma", model="modulo")
    permissao, _criada = Permission.objects.get_or_create(
        codename=_CODENAME, content_type=tipo, defaults={"name": _NOME})
    for cargo in Cargo.objects.filter(nome="supervisor", de_fabrica=True).iterator():
        cargo.permissoes.add(permissao)


class Migration(migrations.Migration):

    dependencies = [
        ("fila", "0008_turnodaloja"),
        ("contas", "0008_alter_cargo_alcance"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(_dar, migrations.RunPython.noop),
    ]
