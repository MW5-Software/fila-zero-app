"""Quem está na sessão, e como entra e sai dela.

A sessão guarda **só o id**. O usuário é reconstruído a cada requisição pelo
`buscar` do backend — é isso que faz desativar alguém valer na hora, e não no
próximo login.

Duas chaves, não uma: `CHAVE` é sempre quem de fato entrou (o original), e
nunca muda enquanto a sessão durar — nem quando a Task 11 (personificação)
está em curso. `CHAVE_ALVO` é o id de quem o original está vendo como, e só
existe enquanto durar a personificação. Guardar as duas separadas, em vez de
trocar `CHAVE` pelo alvo e esconder o original em outro lugar, é o que faz
"voltar a ser eu" ser só apagar `CHAVE_ALVO`: o original nunca foi
substituído, então não existe nada para restaurar — e, por tabela, nada que
um cookie adulterado possa forjar no lugar dele.
"""

from __future__ import annotations

from django.utils import timezone

from nucleo.permissoes import User

from .memoria import lembrar


__all__ = [
    "CHAVE", "CHAVE_ALVO", "CHAVE_SENHA_EXPIRADA", "entrar_na_sessao",
    "identidade_da_sessao",
    "sair_da_sessao", "usuario_da_sessao", "usuario_original_da_sessao",
]

CHAVE = "usuario_id"
CHAVE_ALVO = "usuario_personificado_id"
CHAVE_SENHA_EXPIRADA = "senha_expirada"


def _renovar_sessao(request) -> None:
    """O relógio de inatividade do parâmetro `minutos_de_sessao`.

    `set_expiry` por requisição é o que faz o tempo ser de INATIVIDADE:
    cada tela visitada re-arma a contagem. `0` = não mexe (vale o padrão
    do Django). Uma consulta a mais por requisição — o mesmo preço que
    `itens_por_pagina` já paga em toda listagem.

    Sessão que não tem `set_expiry` (os testes de guarda injetam um dict
    cru no `request.session`) simplesmente não arma relógio — não há do
    que renovar.
    """
    from plataforma.parametro_catalogo import valor_de

    # Uma vez por requisição: `usuario_da_sessao` é chamada oito vezes numa
    # página, e re-armar o mesmo relógio oito vezes custava oito leituras do
    # parâmetro para gravar o mesmo prazo.
    minutos = lembrar(request, "sessao:minutos",
                      lambda: valor_de("minutos_de_sessao"))
    if not minutos:
        return
    set_expiry = getattr(request.session, "set_expiry", None)
    if callable(set_expiry):
        set_expiry(minutos * 60)


def _senha_vencida(user) -> bool:
    """A senha deste alguém venceu? `dias_para_expirar_senha` = 0 nunca
    vence; sem marca, conta do PRIMEIRO login (a senha pode ter sido
    definida fora do app, pelo `changepassword`)."""
    from datetime import timedelta

    from plataforma.parametro_catalogo import valor_de

    dias = valor_de("dias_para_expirar_senha")
    if not dias:
        return False
    from contas.models import Usuario

    agora = timezone.now()
    # `.values_list` e não a linha inteira: desde a Task 3 `Usuario` carrega
    # o avatar (os bytes da foto) como coluna, e esta pergunta — "há quanto
    # tempo a senha está definida?" — não precisa dele.
    marca = Usuario.objects.values_list(
        "senha_definida_em", flat=True).get(pk=user.id)
    if marca is None:
        # Sem marca: a senha pode ter sido definida fora do app
        # (`changepassword`). A contagem começa AGORA, no primeiro login
        # pelo app — recriar a cada login faria a expiração nunca vencer,
        # por isso é um `update` condicionado ao `None`, não incondicional.
        Usuario.objects.filter(pk=user.id).update(senha_definida_em=agora)
        marca = agora
    return marca < agora - timedelta(days=dias)


def entrar_na_sessao(request, user: User) -> None:
    """Grava quem entrou e gira o identificador da sessão.

    O `cycle_key` fecha a fixação de sessão: um identificador obtido antes do
    login deixa de valer no instante em que a pessoa entra.

    Também apaga `CHAVE_ALVO`, se houver. Um login é sempre um recomeço — a
    pessoa que acabou de provar a própria senha não pode herdar uma
    personificação de quem usou esta sessão antes dela. Sem isto: `raiz`
    (superusuário) personifica `zeca` e não encerra; `mario`, uma pessoa
    comum, loga na MESMA sessão com a própria senha válida; a sessão vira
    `{usuario_id: mario, usuario_personificado_id: zeca}`, e como
    `usuario_da_sessao` prefere `CHAVE_ALVO`, `mario` passa a ver as telas de
    `zeca` — e qualquer ação seguinte gravaria `autor_login="zeca"` com
    `detalhe="personificado por mario"`, uma trilha que afirma algo falso:
    que `mario` personificou `zeca`, quando `mario` nunca chamou a rota nem
    tinha a permissão para isso. Corrigido AQUI, e não na view `entrar`: um
    login é sempre este caminho, então qualquer entrada futura (SSO, outro
    backend) já nasce coberta — corrigir só na view resolveria esta rota e
    deixaria qualquer caminho de login futuro descoberto.

    Antes de apagar, `encerrar()`: um `.pop(CHAVE_ALVO, None)` cru fechava a
    personificação sem deixar linha nenhuma na trilha — a mesma falha da
    revisão final do branch que corrigiu `contas.views.sair`, e pelo mesmo
    motivo: nada fechava a janela em que ações tinham sido feitas em nome de
    outra pessoa. Chamado ANTES de `cycle_key`/sobrescrever `CHAVE`, porque
    `encerrar` lê o original pela chave AINDA em vigor (a de quem
    personificava antes deste login, não a de quem está entrando agora) — na
    ordem inversa, o registro atribuiria o encerramento à pessoa errada. Sem
    personificação em curso, `encerrar` já não faz nada (ver seu próprio
    docstring), então esta chamada é segura em todo login, sempre.
    """
    from .personificacao import encerrar

    encerrar(request)
    request.session.cycle_key()
    request.session[CHAVE] = user.id
    request.session.pop(CHAVE_ALVO, None)

    # Política de acesso (Bloco 7): o relógio de inatividade arma no login
    # (e se renova a cada requisição, em `usuario_da_sessao`). A marca da
    # senha nasce AQUI só na primeira vez — `_senha_vencida` só grava quando
    # a coluna está `None`, e não a cada login: recriar sempre faria a
    # expiração nunca vencer. E a senha vencida vira flag na SESSÃO — a
    # guarda é quem transforma a flag em porta.
    _renovar_sessao(request)
    if _senha_vencida(user):
        request.session[CHAVE_SENHA_EXPIRADA] = True
    else:
        request.session.pop(CHAVE_SENHA_EXPIRADA, None)


def sair_da_sessao(request) -> None:
    """Derruba a sessão inteira — o original e qualquer personificação em
    curso juntos. `flush()` não distingue as duas chaves; não precisa: sair
    de verdade encerra tudo, não só a metade de quem se está vendo como."""
    request.session.flush()


def _buscar_por_chave(request, chave: str, backend) -> "User | None":
    """A identidade guardada em `chave`, reconstruída do banco.

    **Uma vez por requisição, e não uma vez por pergunta** (ver
    `comum.memoria`): esta função é o fundo de toda guarda, de todo menu e de
    todo `do_contexto`, e era chamada oito vezes na mesma página — cada uma
    relendo a linha do usuário e refazendo o conjunto de permissões dele.

    A invariante continua de pé porque o memo dura uma requisição e morre em
    qualquer escrita: desativar alguém segue valendo na hora, e a tela que
    rebaixa o titular não fica servindo o retrato de antes do POST.

    **Só quando o backend é o padrão.** Um backend injetado é coisa de teste,
    e dois backends diferentes na mesma requisição devolveriam respostas
    diferentes para a mesma chave — memo com a chave errada é defeito que só
    aparece em teste que ninguém escreveu ainda.
    """
    user_id = request.session.get(chave)
    if not user_id:
        return None
    if backend is not None:
        return backend.buscar(user_id)
    return lembrar(request, f"sessao:{chave}:{user_id}",
                   lambda: _backend_padrao().buscar(user_id))


def usuario_original_da_sessao(request, backend=None) -> "User | None":
    """Quem de fato entrou nesta sessão — sempre o original, personificando
    ou não. É esta função, e não `usuario_da_sessao`, que "voltar a ser eu"
    usa para restaurar: o valor vem só de `CHAVE`, nunca de `CHAVE_ALVO` nem
    de nada que o cliente tenha mandado nesta requisição."""
    return _buscar_por_chave(request, CHAVE, backend)


def identidade_da_sessao(request, backend=None) -> "User | None":
    """QUEM esta requisição vê, sem as permissões do lugar — o alvo, se há personificação em curso;
    senão o original. `None` só quando nem um nem outro existe mais (por
    exemplo, os dois foram removidos ou desativados depois do login).

    Toda guarda (`contas/guardas.py`) e toda tela leem por aqui, nunca por
    `CHAVE` direto — é o que faz o menu, a permissão e o `request.usuario`
    inteiros virarem os do alvo sem que nenhuma delas precise saber que
    personificação existe.

    Se o alvo tiver sido desativado ou removido no meio da personificação, a
    leitura cai de volta para o original em vez de derrubar a sessão inteira:
    o mesmo espírito de `buscar` — o banco decide a cada requisição, nunca o
    que a sessão gravou no passado — e desativar o alvo não pode ser um jeito
    de trancar a MW5 para fora da própria sessão.

    Só honra `CHAVE_ALVO` quando o ORIGINAL ainda resolve e ainda é
    superusuário — as duas coisas, checadas de novo a CADA requisição, nunca
    só na hora em que `iniciar` abriu a personificação. Até esta correção,
    uma personificação em curso nunca voltava a olhar para `CHAVE`: com
    `alvo` resolvendo, a função devolvia o alvo direto, sem checar o
    original de novo — a mesma lacuna de fundo que a Task 11 já tinha
    fechado para o alvo (linha acima), só que do outro lado. Duas
    consequências, as duas erradas: desativar QUEM PERSONIFICA no meio da
    personificação não derrubava nada — a sessão seguia navegando como o
    alvo, porque nada aqui lia o original de novo para descobrir que ele
    tinha sumido; e rebaixar o original (deixar de ser superusuário, sem
    desativar a conta) também não fechava nada — a sessão continuava vendo
    e agindo como o alvo mesmo depois de perder a autoridade que abriu a
    personificação, e cada ação seguinte gravava `detalhe="personificado
    por <login>"` como se essa autoridade ainda existisse. Com a checagem
    de novo aqui, qualquer um dos dois casos faz a leitura cair para o
    original (ou para `None`, se ele também não resolve mais) — a mesma
    saída seguida quando o ALVO some, e pelo mesmo motivo: o banco decide a
    cada requisição, nunca o que a sessão gravou no passado.
    """
    _renovar_sessao(request)
    original = usuario_original_da_sessao(request, backend)
    alvo = _buscar_por_chave(request, CHAVE_ALVO, backend)
    if alvo is not None and original is not None and original.superuser:
        return alvo
    return original


def usuario_da_sessao(request, backend=None) -> "User | None":
    """Quem esta requisição VÊ, com o que essa pessoa pode NO LUGAR em que está.

    Duas etapas, e a ordem é imposta pela dependência (spec 2026-09-14, "Onde a
    pessoa está"): a permissão depende do lugar, e o lugar depende da pessoa.
    `identidade_da_sessao` resolve a pessoa; `contas.lugar` resolve o lugar e
    põe as permissões do cargo.

    Quem resolve o lugar (`plataforma.contexto`) lê `identidade_da_sessao`,
    NUNCA esta função. Senão perguntar o lugar pediria as permissões, e pedir as
    permissões perguntaria o lugar.

    Backend injetado (teste de guarda com gente de mentira) volta sem passar
    pelo lugar: a gente dele não existe no banco para ter alocação.
    """
    identidade = identidade_da_sessao(request, backend)
    if identidade is None or backend is not None:
        return identidade
    return lembrar(request, f"sessao:no-lugar:{identidade.id}",
                   lambda: _no_lugar(request, identidade))


def _no_lugar(request, identidade: User) -> User:
    """Import tardio pelo mesmo motivo de `_backend_padrao`: a sessão é
    infraestrutura, e o lugar é de `contas`."""
    from contas.lugar import com_permissoes_do_lugar

    return com_permissoes_do_lugar(request, identidade)


def _backend_padrao():
    """O backend concreto desta instalação.

    Import tardio pelo mesmo motivo de `comum.auditoria._modelo`: a
    sessão é infraestrutura, o backend é de `contas`, e importar para
    cima na carga refaria o ciclo. `usuario_da_sessao` já aceitava
    `backend=` injetado — isto só troca o padrão de valor fixo por
    resolução na hora.
    """
    from contas.backend import BackendDjango

    return BackendDjango()
