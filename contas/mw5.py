"""O usuário interno da MW5, que nasce com a instalação.

Vinte instalações, cada uma com o próprio banco: sem uma linha semeada, a
primeira entrada da MW5 numa instalação nova dependeria de alguém rodar
`createsuperuser` na mão em cada VPS, ou de uma senha padrão repetida nas
vinte — a mesma senha em vinte instalações não é senha nenhuma.
`garantir_usuario_mw5` cria esse usuário sem senha utilizável; a MW5 define a
dela na primeira vez que entra.

Roda no mesmo `post_migrate` que semeia módulos, materializa permissões e
semeia os cargos de fábrica — ver `plataforma/apps.py`.
"""

from __future__ import annotations

from django.contrib.auth.hashers import make_password

__all__ = ["EMAIL", "garantir_usuario_mw5"]

#: O login do usuário interno da MW5 — e o login é o E-MAIL desde que o
#: usuário passou a ser nosso (`contas.models.Usuario`). Fixo: o receptor de
#: `post_migrate` precisa achar sempre a mesma linha, em qualquer instalação.
#:
#: O domínio é o da própria MW5, e não o do cliente: a mesma imagem sobe em
#: vinte instalações, e um endereço com o domínio de uma delas seria o
#: endereço errado nas outras dezenove.
EMAIL = "mw5@mw5.com.br"


def garantir_usuario_mw5(apps=None, using=None) -> bool:
    """Cria o usuário da MW5 se ele ainda não existir. Devolve `True` se criou.

    Nasce superusuário e sem senha utilizável. `make_password(None)` é o que
    `set_unusable_password` faz por baixo dos panos — não dá para chamar o
    método em si porque `apps.get_model` (quando vem do receptor de
    `post_migrate`) devolve o model histórico, reconstruído só a partir dos
    campos: os métodos de conveniência do model de verdade não existem nele.

    Idempotente com três comportamentos distintos, de propósito:
    - não recria (evitaria duplicar a linha);
    - não reseta a senha que a MW5 já definiu (uma atualização não pode
      derrubar o próprio acesso dela a esta instalação);
    - **mas reativa**, porque desativar este usuário é exatamente como um
      cliente trancaria a MW5 do lado de dentro — a única forma de desfazer
      isso não pode ser a MW5 pedir para o cliente reativar.
    Reativar é o único ajuste feito numa linha já existente; nada mais nela é
    tocado.
    """
    if apps is None:
        from django.apps import apps as apps_reais

        apps = apps_reais

    # `("contas", "Usuario")` e não `("auth", "User")`: o usuário é deste
    # projeto desde a troca do `AUTH_USER_MODEL`, e o `auth_user` do Django
    # deixou de existir como tabela de gente nesta instalação.
    Usuario = apps.get_model("contas", "Usuario")
    gerente = Usuario.objects.db_manager(using) if using else Usuario.objects

    usuario, criado = gerente.get_or_create(
        email=EMAIL,
        defaults={
            "nome": "MW5",
            "password": make_password(None),
            # `nivel` MASTER, e não o padrão da coluna (COMPRADOR). Enquanto
            # o nível morava numa tabela ao lado, este usuário simplesmente
            # não tinha linha lá, e "sem nível" era a resposta certa. Agora
            # `nivel` é coluna com padrão, e deixá-lo em COMPRADOR faria a
            # MW5 aparecer como membro de conta nenhuma, e qualquer regra que
            # pergunte "é da MW5?" pelo nível responderia errado. `0` escrito por extenso porque `Nivel` é do model de
            # verdade, e este receptor recebe o model histórico do
            # `post_migrate`: o valor é o que a coluna guarda, e ele não pode
            # mudar de significado com o código.
            "nivel": 0,
            # `is_staff=True`: paridade com o que `create_superuser` do
            # próprio Django já faz, e a MW5 é exatamente quem ia querer o
            # admin se ele existisse. Hoje `django.contrib.admin` não está
            # instalado neste projeto, então a flag é inerte — não abre
            # porta nenhuma agora. O dia em que alguém instalar o admin,
            # este usuário já nasce com acesso irrestrito a ele.
            "is_staff": True,
            "is_superuser": True,
        },
    )
    if not criado and not usuario.is_active:
        usuario.is_active = True
        usuario.save(using=using, update_fields=["is_active"])

    return criado
