"""`filiais.ativar` para quem já existe (25/09/2026).

O cliente: ativar e desativar filial "tem que liberar para dono da conta e
supervisor". A tela de Filiais passou a abrir por `filiais.ativar` — a menor
das duas, a que liga e desliga a loja —, e `filiais.editar` ficou com criar,
editar e remover. A semeadura só cria cargo que falta, e as permissões do
titular são diretas, aplicadas quando o nível é gravado; sem esta migração,
ninguém que já existia ganharia a nova, e quem abria a tela deixaria de abrir.

Só SOMA, e só a quem deve:

- todo titular ganha `filiais.ativar` e `filiais.editar` (o dono que por
  algum motivo ficou sem a de editar ganha também, que é o de fábrica);
- o Supervisor DE FÁBRICA ganha `filiais.ativar`.

Quem tem `filiais.editar` não precisa ganhar a nova: `contas.backend.traduzir`
a dá junto (`IMPLICADAS`), para o cargo de hoje e para o que o dono criar
amanhã marcando só "editar".

As permissões são criadas quando faltam, como na `0007`: elas nascem no
`post_migrate` (`contas.permissoes.materializar`), DEPOIS das migrações, e o
`materializar` não as duplica. `desfazer` não faz nada: tirar apagaria o que
alguém tenha dado à mão.
"""

from django.db import migrations

#: Congelados como literais: a migração roda com modelos históricos.
_TITULAR = 1
_PERMISSOES = {"filiais_ativar": "filiais: ativar", "filiais_editar": "filiais: editar"}


def _dar(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Usuario = apps.get_model("contas", "Usuario")
    Cargo = apps.get_model("contas", "Cargo")

    tipo, _criado = ContentType.objects.get_or_create(
        app_label="plataforma", model="modulo")
    permissoes = {
        codename: Permission.objects.get_or_create(
            codename=codename, content_type=tipo, defaults={"name": nome})[0]
        for codename, nome in _PERMISSOES.items()}
    ativar, editar = permissoes["filiais_ativar"], permissoes["filiais_editar"]

    for titular in Usuario.objects.filter(nivel=_TITULAR).iterator():
        titular.user_permissions.add(ativar, editar)
    for cargo in Cargo.objects.filter(nome="supervisor", de_fabrica=True).iterator():
        cargo.permissoes.add(ativar)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0008_alter_cargo_alcance"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(_dar, migrations.RunPython.noop),
    ]
