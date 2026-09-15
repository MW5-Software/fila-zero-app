"""Traduz o usuário do Django para o retrato que o núcleo desenha.

Implementa o contrato `AuthBackend` que o `mw5_admin` já definia — dois
métodos, `autenticar` e `buscar` — e é isto que permite trocar a origem da
gente sem que nada acima perceba. Hoje é a base do Django; a entrega que
ligar o Oracle do cliente escreve outro backend e mais nada muda.
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from django.urls import reverse

from nucleo.permissoes import User

from .models import Nivel, Usuario

__all__ = ["APP_DOS_MODULOS", "BackendDjango", "permissoes_de", "traduzir"]

#: O app onde moram as permissões de módulo. Só as deste app ganham a
#: tradução `modulo_acao` -> `modulo.acao`. As permissões nativas do Django,
#: de qualquer outro app, não entram no vocabulário do núcleo — ver o
#: docstring de `permissoes_de` para o motivo.
APP_DOS_MODULOS = "plataforma"


def permissoes_de(usuario: Usuario) -> frozenset[str]:
    """As permissões da pessoa, no vocabulário do núcleo: `modulo.acao`.

    **Só as permissões de módulo entram.** As permissões nativas do Django
    (`auth.add_user`, `contenttypes.delete_contenttype`) continuam valendo no
    mundo do Django, por `user.has_perm`, e não são traduzidas para cá.

    O motivo é uma colisão real: se as permissões do Django entrassem no
    mesmo conjunto que as de módulo, e `pode()` trata `X.*` como cobrindo
    `X.qualquer` — então uma permissão `auth.*` (se algum dia existisse)
    cobriria `auth.add_user` e `auth.delete_user` dentro do vocabulário do
    núcleo. Um vocabulário só elimina essa mistura por construção.

    **Só as permissões DIRETAS, e só valem para o titular e a MW5.** Desde a
    virada dos cargos (spec 2026-09-14, D9), são as de `contas/fabrica.py`.
    A permissão de quem é membro de uma conta vem do cargo da alocação no
    lugar em que ele está (`contas.lugar.com_permissoes_do_lugar`). Por isso
    `_para_o_nucleo` nem chama esta função para um membro.

    `Group` não entra: dois jeitos de conceder a mesma coisa era o defeito
    que ele já tinha causado aqui. (O `Perfil`, que existia por isso, saiu em
    14/09/2026 junto com a virada para cargos.) Conceder um módulo inteiro
    continua sendo uma `Permission` com `codename="<modulo>_*"` (por exemplo
    `frete_*`), que vira `frete.*` em `traduzir`; `pode()` já trata `X.*`
    como cobrindo `X.qualquer`.

    Existiu aqui, até esta correção, um segundo caminho: o **nome** do grupo
    virava coringa sozinho (`Group(name="frete")` → `frete.*`), sem
    `Permission` nenhuma envolvida. Foi removido — era redundante (o que ele
    fazia, a `Permission` acima já faz, pelo caminho normal) e frágil de dois
    jeitos: o nome de um grupo é rótulo cosmético que qualquer administração
    de usuários deixa renomear, então renomear um perfil de `frete` para
    `Frete` revogaria acesso em silêncio; e conceder acesso pelo *nome* de um
    grupo é conceder sem passar por nenhuma verificação de permissão —
    bastava alguém batizar um grupo, o que numa gestão de usuários que deixa
    o admin do cliente criar grupos livremente é uma porta de escalação de
    privilégio pela entrada da frente.

    **As permissões que o Django cria sozinho para os models do próprio app
    de plataforma** (`add_marca`, `view_modulo` e por aí) também não entram:
    o critério é bater o codename inteiro com `{verbo}_{model}`, lido do
    registro de apps (`model._meta.default_permissions`) — não uma lista
    fixa de verbos, então a próxima tabela que nascer já sai coberta, e uma
    permissão de módulo legítima cujo sufixo *coincida* com o nome de um
    model (como `plataforma.frete_marca`) não é descartada por engano.

    **Módulo desligado não revoga permissão nenhuma daqui — decisão, não
    esquecimento.** O filtro de catálogo, acima (`chaves = {spec.chave for
    spec in declarados()}`), é `declarados()`: todo módulo que o CÓDIGO
    conhece, ligado ou não nesta instalação. Não é `modulos_ligados()` — que
    é o filtro certo em `contas.caixas_de_permissao.permissoes_oferecidas` (o que a
    tela OFERECE para conceder) e é irrelevante aqui, porque o que impede o
    uso de um módulo desligado é a rota (`comum.guardas_de_modulo.
    exigir_modulo_ligado`), não a permissão. Uma permissão de um módulo
    desligado por MW5 continua sendo traduzida por esta função e continua
    valendo para `pode()` — só dorme, porque a rota que ela abriria já
    responde como inexistente por outro motivo. Ligar o módulo de volta
    acorda essa permissão sem que ninguém precise conceder nada de novo.

    A alternativa — revogar de verdade ao desligar — apagaria a configuração
    do cliente por causa de uma ação que a própria MW5 pode desfazer um
    minuto depois, e recriar tudo do zero ao religar não é o que "desligar"
    devia significar. É o mesmo raciocínio, virado para este lugar, que já
    forçou a correção de `_salvar_permissoes` (Task 8): um `.set()` que
    arranca em silêncio o que está fora da tela também é uma revogação que
    ninguém decidiu. "Desligado" quer dizer: a rota recusa e o item some do
    menu; o que já foi concedido fica gravado, adormecido, esperando.
    """
    # `.values_list(..., "codename")` em vez de `get_all_permissions()`:
    # este último devolve string `"app.codename"` e dispararia uma consulta
    # extra por permissão para saber o app.
    return traduzir(
        Permission.objects.filter(
            user=usuario, content_type__app_label=APP_DOS_MODULOS)
        .values_list("codename", flat=True)
        .distinct())


def traduzir(codenames) -> frozenset[str]:
    """Codenames de `Permission` do app de módulos -> `modulo.acao`.

    Uma tradução só, usada pela permissão direta e pela do cargo: duas
    tradutoras com o mesmo filtro divergiriam no dia em que o filtro mudasse
    numa só — e o filtro é o que impede `mw5_aparencia` de virar acesso.
    """
    from django.apps import apps as apps_registrados

    from plataforma.declaracao import declarados

    codenames_autogerados = {
        f"{verbo}_{modelo._meta.model_name}"
        for modelo in apps_registrados.get_app_config(APP_DOS_MODULOS).get_models()
        for verbo in modelo._meta.default_permissions
    }

    chaves = {spec.chave for spec in declarados()}

    concedidas: set[str] = set()
    for codename in codenames:
        if codename in codenames_autogerados:
            # `add_modulo`, `change_marca` etc.: permissão que o Django gera
            # sozinho para o model, não permissão de módulo de negócio.
            # Viraria `add.modulo` — sem sentido no vocabulário.
            continue
        # `plataforma.frete_ver` -> `frete.ver`. O Django não aceita ponto em
        # codename, então a permissão de módulo se escreve com sublinhado no
        # banco e ganha o ponto aqui.
        modulo, separador, acao = codename.partition("_")
        if not separador:
            # Codename sem sublinhado nenhum não é `modulo_acao` — não há o
            # que traduzir, e não é permissão de módulo (essas sempre nascem
            # de `ModuloSpec.permissoes`, que é sempre `modulo.acao`).
            continue
        # Permissão de módulo só vale se o módulo existir. Sem isso, criar a
        # permissão `plataforma.mw5_aparencia` e concedê-la daria acesso às
        # telas da MW5 por permissão direta.
        if modulo not in chaves:
            continue
        concedidas.add(f"{modulo}.{acao}")

    return frozenset(concedidas)


def _para_o_nucleo(usuario: Usuario) -> User:
    # `usuario.nome or usuario.email`: o nome é um campo só desde que o
    # usuário passou a ser nosso, e o e-mail é o login — a conta recém-criada
    # sem nome preenchido continua tendo COMO ser chamada na tela.
    nome = usuario.nome.strip() or usuario.email
    # NUNCA `bool(usuario.avatar)` aqui: `_para_o_nucleo` roda em TODA
    # requisição autenticada (`buscar`, chamado por `usuario_da_sessao` a
    # cada uma), e `buscar` adia a coluna `avatar` (`.defer`, abaixo) — ela é
    # o `BinaryField` com a imagem inteira, e a decisão de mostrar o link ou
    # não não precisa dos BYTES, só de saber se existem. Tocar em
    # `usuario.avatar` aqui disparia o `SELECT` adiado, trazendo a imagem
    # inteira de volta e anulando o `.defer` — o mesmo custo de antes, só que
    # em duas consultas em vez de uma. `avatar_tipo` é a coluna barata que
    # anda junto: as duas só são gravadas juntas (`views_perfil.py::
    # perfil_foto`), nunca uma sem a outra, e por isso ela serve de sinal.
    tem_avatar = bool(usuario.avatar_tipo)
    url_avatar = reverse("avatar", args=[usuario.pk]) if tem_avatar else ""
    # Membro nasce SEM permissão: a dele depende do lugar, e o lugar só se
    # resolve com a requisição na mão (`comum.sessao.usuario_da_sessao`). Um
    # `User` de membro que saísse daqui com permissão seria a porta por onde
    # uma permissão direta esquecida continuaria valendo.
    manda_por_si = usuario.is_superuser or usuario.nivel <= Nivel.TITULAR
    return User(
        id=str(usuario.pk),
        name=nome,
        login=usuario.email,
        superuser=usuario.is_superuser,
        permissions=permissoes_de(usuario) if manda_por_si else frozenset(),
        avatar=url_avatar,
    )


class BackendDjango:
    """A gente desta instalação, vinda da base do próprio sistema."""

    def autenticar(self, login: str, senha: str) -> "User | None":
        """`None` para login inexistente, senha errada e usuário inativo — sem
        distinguir os três. Quem chama não pode descobrir quais logins existem.
        """
        # `username=` e não `email=`, mesmo com o login sendo o e-mail: é o
        # parâmetro que o `ModelBackend` do Django lê PRIMEIRO, e ele o aplica
        # ao `USERNAME_FIELD` seja qual for o nome do campo. `email=` também
        # funciona hoje — o `ModelBackend` cai em
        # `kwargs.get(USERNAME_FIELD)` quando `username` vem vazio, e aqui o
        # `USERNAME_FIELD` É `email` —, e é justamente por isso que a escolha
        # precisa estar escrita: os dois passam agora, e só um continua
        # passando no dia em que o campo de identidade mudar de nome de novo.
        usuario = authenticate(username=login, password=senha)
        if usuario is None or not usuario.is_active:
            return None
        return _para_o_nucleo(usuario)

    def buscar(self, user_id: str) -> "User | None":
        """Reconstrói a sessão a cada requisição, sem senha.

        É o que faz desativar alguém valer na hora. `None` derruba a sessão.
        """
        try:
            # `.defer("avatar")`: esta consulta roda em toda requisição
            # autenticada, e a imagem inteira (o `BinaryField`) não tem
            # nenhuma serventia aqui — só a rota `avatar` (`views_perfil.py`)
            # precisa dos bytes, e só quando alguém de fato pede a foto.
            usuario = Usuario.objects.defer("avatar").get(
                pk=int(user_id), is_active=True)
        except (Usuario.DoesNotExist, ValueError, TypeError):
            return None
        return _para_o_nucleo(usuario)
