"""As permissões de módulo, como linha no banco.

`ModuloSpec.permissoes` declara `("frete.ver", "frete.editar")`. Isso é o
vocabulário do núcleo; o Django guarda permissão com sublinhado, porque
`codename` não aceita ponto. Este módulo faz a ponte: cria a linha que a tela
de Perfis oferece e que `contas.backend.permissoes_de` traduz de volta.

Roda no mesmo `post_migrate` que semeia os módulos, pelo mesmo motivo: uma
migração de tiro único deixaria as instalações existentes sem a permissão do
módulo novo.
"""

from __future__ import annotations

from plataforma.declaracao import declarados

__all__ = ["CONTENT_TYPE", "materializar", "rotulo_de"]

#: A âncora das permissões de módulo. Elas não pertencem a um model — são do
#: sistema —, e o Django exige um `ContentType`. Usamos o de `Modulo` porque é
#: o mais próximo do que elas governam.
CONTENT_TYPE = ("plataforma", "modulo")


def rotulo_de(prefixo: str, acao: str) -> str:
    """O texto `f"{prefixo}: {ação}"` — o coringa `*` se escreve por extenso,
    "tudo". Público (e não `_rotulo`) porque `contas.caixas_de_permissao` precisa da
    MESMA regra do coringa, só que com o RÓTULO do módulo como prefixo, não a
    chave em minúsculo — duas cópias desta regrinha já divergiram uma vez
    (revisão da Task 8); não pode voltar a acontecer.
    """
    if acao == "*":
        return f"{prefixo}: tudo"
    return f"{prefixo}: {acao}"


def materializar(apps=None, using=None) -> int:
    """Cria a `Permission` faltante de cada permissão declarada.

    Além das declaradas, cria o coringa `<chave>_*` de cada módulo — a forma
    canônica de conceder o módulo inteiro, e a que faz um perfil não envelhecer
    quando a ação nova de amanhã aparecer.

    **Não apaga nada.** Módulo removido do código deixa a permissão para trás:
    apagá-la revogaria acesso de gente em vinte instalações no meio de uma
    atualização.
    """
    if apps is None:
        from django.apps import apps as apps_reais

        apps = apps_reais

    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    gerente = Permission.objects.db_manager(using) if using else Permission.objects
    gerente_ct = ContentType.objects.db_manager(using) if using else ContentType.objects

    app_label, model = CONTENT_TYPE
    tipo, _ = gerente_ct.get_or_create(app_label=app_label, model=model)

    querem: dict[str, str] = {}
    for spec in declarados():
        # Tela da MW5 não ganha linha de permissão, e é isso que guarda a
        # fronteira: sem `Permission` no banco não há o que marcar num
        # cargo, e `pode()` só libera para superusuário. Antes a garantia
        # vinha de as três estarem fora do catálogo — o que custava um grupo
        # inteiro na barra lateral. Agora é declarado (`ModuloSpec.so_mw5`)
        # em vez de emergir de uma ausência.
        if spec.so_mw5:
            continue
        querem[f"{spec.chave}_*"] = rotulo_de(spec.chave, "*")
        for permissao in spec.permissoes:
            _, _, acao = permissao.partition(".")
            if acao:
                querem[f"{spec.chave}_{acao}"] = rotulo_de(spec.chave, acao)

    existentes = set(
        gerente.filter(content_type=tipo, codename__in=querem)
        .values_list("codename", flat=True)
    )
    novas = [Permission(codename=c, name=n, content_type=tipo)
             for c, n in querem.items() if c not in existentes]
    gerente.bulk_create(novas)
    return len(novas)
