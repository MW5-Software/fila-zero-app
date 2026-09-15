"""A guarda de "módulo ligado".

`comum.guardas_de_acesso.exigir_permissao` tranca por permissão; esta tranca por outro
motivo, independente: o cliente pode ter a permissão e mesmo assim o módulo
estar desligado nesta instalação (não comprado, ou desligado na tela de
Módulos). As duas guardas são complementares, e todo módulo futuro precisa
das duas — por isso esta mora em `plataforma/`, e não dentro de um módulo
específico como `modulos/exemplo/`.
"""

from __future__ import annotations

from functools import wraps

from django.http import HttpResponseNotFound
from django.utils.translation import gettext_lazy as _


__all__ = ["SEM_GUARDA_DE_MODULO", "exigir_filial", "exigir_modulo_ligado"]

#: As rotas de módulo declarado que podem viver sem `exigir_modulo_ligado`,
#: e o motivo de cada uma — mesmo espírito de
#: `comum.guardas_de_acesso.TELAS_ABERTAS`: uma lista curta e explícita, para
#: que qualquer nome que entre aqui doa um pouco.
#:
#: As três são as telas da MW5 (`ModuloSpec.so_mw5`), e o motivo é o mesmo
#: nas três: elas não aparecem na tela de Módulos, então "desligado" é um
#: estado que não se alcança pelo produto — a guarda seria código morto. E
#: se uma linha fosse a `ativo=False` por outro caminho, a guarda trancaria
#: com 404 justamente a tela que conserta as coisas, sem volta que não fosse
#: SQL na mão. Módulo de negócio continua obrigado à guarda: ali desligar é
#: exatamente o que a tela de Módulos faz.
SEM_GUARDA_DE_MODULO: frozenset[str] = frozenset({
    "aparencia", "modulos", "falhas",
})


def exigir_modulo_ligado(chave: str):
    """Sem o módulo `chave` ligado nesta instalação, a rota responde como se
    não existisse.

    404 e não 403 — mesma razão de `comum.guardas_de_acesso.exigir_permissao`: quem não
    pode usar não precisa descobrir que a tela existe. E 404 mesmo para o
    superusuário: ligar e desligar é exatamente o que a tela de Módulos
    controla, e ela perderia sentido se um interruptor desligado não
    trancasse a porta para a própria MW5 dentro da instalação do cliente —
    para ligar, o caminho é a tela de Módulos, não visitar a rota direto.

    Não decide sozinha sobre login: quem chega sem sessão nenhuma continua
    sendo assunto de `exigir_permissao` (ou de `exigir_login`), que já sabe
    redirecionar para a tela de entrada. Esta guarda só sabe travar por
    módulo desligado, e é para isso que ela deve ser composta com uma das
    outras duas — nunca sozinha, ou uma rota sem permissão nenhuma abriria
    para qualquer um que tivesse sessão.
    """

    def decorar(view):
        @wraps(view)
        def guardada(request, *args, **kwargs):
            if not _modulo().objects.filter(chave=chave, ativo=True).exists():
                return HttpResponseNotFound()
            return view(request, *args, **kwargs)

        # Espelha o que `comum.guardas_de_acesso.exigir_permissao` faz com
        # `.permissao`: sem marcar a chave na própria view, não há como a
        # varredura de `tests/test_guarda_modulo.py` perguntar, depois do
        # fato, se esta guarda foi de fato aplicada. Sem a marca, um autor de
        # módulo que decorasse a tela só com `@exigir_permissao` entregaria
        # uma rota que abre com o módulo desligado — falha aberta, e
        # silenciosa.
        guardada.modulo = chave
        return guardada

    return decorar


def exigir_filial(view):
    """Sem nenhuma filial para operar, a tela avisa em vez de rodar.

    Diferente de `exigir_modulo_ligado` e de `comum.guardas_de_acesso.exigir_permissao`
    — as duas respondem 404, porque ali é a pessoa que NÃO PODE. Aqui não é
    isso: a pessoa entrou, e o módulo até estaria ligado para ela — só falta
    o cadastro (nenhuma linha em `Filial.usuarios` a alcança, ou toda filial
    dela foi desativada). Não é erro dela, é dado faltando, e por isso a
    resposta é 200 com uma tela dizendo o que fazer — a mesma leitura do
    desenho (`docs/superpowers/specs/2026-08-21-empresa-filial-design.md`,
    seção "Contexto na requisição"), e o mesmo espírito de qualquer
    `EmptyState` do sistema.

    Este é o mecanismo que o primeiro módulo de negócio vai herdar — hoje
    não há tela de negócio nenhuma para compor com ele (só a Task seguinte
    traz a primeira), então esta guarda ainda não está presa a rota
    nenhuma; `tests/test_contexto_filial.py` a exercita direto, do mesmo
    jeito que `tests/test_guarda.py::TestExigirPermissao` testa
    `exigir_permissao` sem depender de uma URL registrada.

    Composta depois de `exigir_login` (ou `exigir_permissao`), nunca
    sozinha: supõe `request.usuario` já preenchido — mesma regra de
    `exigir_modulo_ligado`, acima.
    """

    @wraps(view)
    def guardada(request, *args, **kwargs):
        from nucleo.components import EmptyState
        from comum.ambiente import ambiente
        from nucleo.rendering import use_environment
        from nucleo.resposta import render

        from plataforma.contexto import filial_atual
        from plataforma.site import montar_site

        if filial_atual(request) is not None:
            return view(request, *args, **kwargs)

        env = ambiente()
        with use_environment(env):
            site = montar_site(request)
            pagina = site.page(
                title=_("Sem filial"),
                content=EmptyState(
                    title=_("Nenhuma filial liberada para você"),
                    message=(
                        "Sua conta ainda não tem acesso a nenhuma filial "
                        "ativa nesta instalação. Peça a um administrador "
                        "para liberar pelo menos uma filial na tela de "
                        "Usuários."
                    ),
                ),
                user=request.usuario,
            )
            return render(pagina)

    guardada.exige_filial = True
    return guardada

def _modulo():
    """`Modulo`, buscado no registro de apps.

    Mesmo motivo de `comum.auditoria._modelo`: este pacote é a
    camada de baixo e a tabela mora em `plataforma`. Um import de topo
    aqui refaria o ciclo que a extração desfez.
    """
    from django.apps import apps

    return apps.get_model("plataforma", "Modulo")
