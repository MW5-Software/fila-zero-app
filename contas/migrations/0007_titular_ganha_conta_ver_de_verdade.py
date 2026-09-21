"""Os titulares que já existem ganham `conta.ver` — de verdade desta vez.

A `0006` dava a permissão só quando ela já existia, e numa instalação que já
estava no ar ela não existia: `conta_ver` é de um módulo NOVO (a tela de
Conta), e só nasce no `post_migrate` (`contas.permissoes.materializar`),
DEPOIS das migrações. O `post_migrate` cria a linha, mas não a dá a ninguém, e
nenhum titular que já existia ganhava a tela (achado em 21/09/2026, ao levar a
tela ao Portal de Vendas). A `0006` fica como está, porque já rodou onde rodou;
esta cria a linha quando falta e dá a permissão.

A linha criada aqui é a mesma que o `materializar` criaria (mesmo `codename`,
mesmo tipo, mesmo nome), e ele não a duplica: só cria o que não existe.

**Acrescenta, e não reescreve.** `aplicar` troca o conjunto inteiro pelo da
fábrica, e rodá-lo aqui apagaria o que a MW5 tenha concedido à mão.
Rodar de novo num titular que já a tem não muda nada.

`desfazer` não faz nada: tirar a permissão aqui desfaria também o que a `0006`
deu, e ela continua aplicada.
"""

from django.db import migrations

#: Congelados como literais: a migração roda com modelos históricos, e a escala
#: de `Nivel` já mudou duas vezes.
_TITULAR = 1
_CODENAME = "conta_ver"
#: O nome que `contas.permissoes.rotulo_de("conta", "ver")` escreveria.
_NOME = "conta: ver"


def _dar(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Usuario = apps.get_model("contas", "Usuario")

    tipo, _criado = ContentType.objects.get_or_create(
        app_label="plataforma", model="modulo")
    permissao, _criada = Permission.objects.get_or_create(
        codename=_CODENAME, content_type=tipo, defaults={"name": _NOME})
    for titular in Usuario.objects.filter(nivel=_TITULAR).iterator():
        titular.user_permissions.add(permissao)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0006_titular_ganha_conta_ver"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(_dar, migrations.RunPython.noop),
    ]
