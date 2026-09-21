"""A trilha de auditoria: quem fez, o quê, e quando.

`RegistroDeAuditoria` (`contas/models.py`) já garante o append-only pelo
próprio model. O que mora aqui é a outra metade: um vocabulário fechado de
ações (`ACOES`), para nenhuma view escrever uma string solta que divergiria
de outra tela com o tempo, e uma função só para gravar (`registrar`).
"""

from __future__ import annotations


def _modelo():
    """`RegistroDeAuditoria`, buscado no registro de apps.

    Import tardio, e não `from contas.models import ...` no topo: este
    módulo é a camada de baixo, e a tabela mora em `contas`. Importar
    para cima na carga recriaria o ciclo que a extração de `comum/`
    desfez — e o registro de apps é exatamente o mecanismo que o Django
    oferece para alcançar um model sem amarrar a ordem de import.
    """
    from django.apps import apps

    return apps.get_model("contas", "RegistroDeAuditoria")

__all__ = ["ACOES", "ROTULOS", "declarar_acoes", "registrar", "vocabulario"]


class ACOES:
    """Todo valor que `RegistroDeAuditoria.acao` pode assumir.

    Uma classe usada só como namespace — nunca instanciada — para as views
    escreverem `ACOES.CARGO_CRIADO` em vez de `"cargo_criado"` batido à
    mão em quinze lugares diferentes.
    """

    ENTROU = "entrou"
    ENTRADA_RECUSADA = "entrada_recusada"
    SAIU = "saiu"
    USUARIO_CRIADO = "usuario_criado"
    USUARIO_EDITADO = "usuario_editado"
    USUARIO_DESATIVADO = "usuario_desativado"
    USUARIO_REATIVADO = "usuario_reativado"
    SENHA_RESETADA = "senha_resetada"
    SENHA_TROCADA = "senha_trocada"
    # Os cargos da conta (`contas/views_cargos.py`), desde 14/09/2026.
    CARGO_CRIADO = "cargo_criado"
    CARGO_EDITADO = "cargo_editado"
    CARGO_REMOVIDO = "cargo_removido"
    ALOCACAO_CRIADA = "alocacao_criada"
    ALOCACAO_REMOVIDA = "alocacao_removida"
    MODULO_LIGADO = "modulo_ligado"
    MODULO_DESLIGADO = "modulo_desligado"
    APARENCIA_ALTERADA = "aparencia_alterada"
    FOTO_ALTERADA = "foto_alterada"
    USUARIO_REMOVIDO = "usuario_removido"
    PERSONIFICACAO_INICIADA = "personificacao_iniciada"
    PERSONIFICACAO_ENCERRADA = "personificacao_encerrada"
    FILIAL_TROCADA = "filial_trocada"
    EMPRESA_EDITADA = "empresa_editada"
    #: Alguém pediu para VER a senha do banco de um cliente. Ler credencial é
    #: um ato, não uma consulta: quem viu e quando é a pergunta que se faz
    #: depois de um vazamento, e ela precisa ter resposta.
    SENHA_DO_BANCO_VISTA = "senha_do_banco_vista"
    FILIAL_CRIADA = "filial_criada"
    FILIAL_EDITADA = "filial_editada"
    FILIAL_ATIVADA = "filial_ativada"
    FILIAL_DESATIVADA = "filial_desativada"
    FILIAL_REMOVIDA = "filial_removida"
    PARAMETRO_ALTERADO = "parametro_alterado"
    PARAMETRO_RESTAURADO = "parametro_restaurado"
    LOGO_ALTERADO = "logo_alterado"
    LOGO_REMOVIDO = "logo_removido"
    #: Uma ação só para logo e cores do menu de uma empresa (15/09/2026): o
    #: `alvo` diz a empresa, e o que se mexe ali é sempre a mesma pergunta.
    MENU_DA_EMPRESA_ALTERADO = "menu_da_empresa_alterado"
    # As ações dos módulos de negócio de cada SaaS entram aqui, cada uma com o
    # rótulo em `ROTULOS` e o cenário que `tests/test_auditoria.py` exige.


#: O que a pessoa lê, por valor gravado no banco — a mesma tradução que a
#: tela de Perfis faz com os codenames de permissão: `usuario_criado` é
#: vocabulário de banco, `Usuário criado` é o da tela. Mora AO LADO do
#: vocabulário (`ACOES`), e não na view, para ação nova e rótulo novo
#: nascerem juntos; quem acrescentar uma ação sem o rótulo faz a caixa de
#: filtro da tela mostrar a chave crua — e é isso mesmo, é assim que falta
#: de tradução aparece.
ROTULOS = {
    ACOES.ENTROU: "Entrou",
    ACOES.ENTRADA_RECUSADA: "Tentativa de entrada recusada",
    ACOES.SAIU: "Saiu",
    ACOES.USUARIO_CRIADO: "Usuário criado",
    ACOES.USUARIO_EDITADO: "Usuário editado",
    ACOES.USUARIO_DESATIVADO: "Usuário desativado",
    ACOES.USUARIO_REATIVADO: "Usuário reativado",
    ACOES.SENHA_RESETADA: "Senha resetada",
    ACOES.SENHA_TROCADA: "Trocou a própria senha",
    ACOES.USUARIO_REMOVIDO: "Usuário removido",
    ACOES.CARGO_CRIADO: "Cargo criado",
    ACOES.CARGO_EDITADO: "Cargo editado",
    ACOES.CARGO_REMOVIDO: "Cargo removido",
    ACOES.ALOCACAO_CRIADA: "Alocação criada",
    ACOES.ALOCACAO_REMOVIDA: "Alocação removida",
    ACOES.MODULO_LIGADO: "Módulo ligado",
    ACOES.MODULO_DESLIGADO: "Módulo desligado",
    ACOES.APARENCIA_ALTERADA: "Aparência alterada",
    ACOES.FOTO_ALTERADA: "Foto alterada",
    ACOES.PERSONIFICACAO_INICIADA: "Personificação iniciada",
    ACOES.PERSONIFICACAO_ENCERRADA: "Personificação encerrada",
    ACOES.FILIAL_TROCADA: "Filial trocada",
    ACOES.EMPRESA_EDITADA: "Empresa editada",
    ACOES.SENHA_DO_BANCO_VISTA: "Senha do banco vista",
    ACOES.FILIAL_CRIADA: "Filial criada",
    ACOES.FILIAL_EDITADA: "Filial editada",
    ACOES.FILIAL_ATIVADA: "Filial ativada",
    ACOES.FILIAL_DESATIVADA: "Filial desativada",
    ACOES.FILIAL_REMOVIDA: "Filial removida",
    ACOES.PARAMETRO_ALTERADO: "Parâmetro alterado",
    ACOES.PARAMETRO_RESTAURADO: "Parâmetro restaurado",
    ACOES.LOGO_ALTERADO: "Logo alterado",
    ACOES.LOGO_REMOVIDO: "Logo removido",
    ACOES.MENU_DA_EMPRESA_ALTERADO: "Menu da empresa alterado",
}


#: Os vocabulários que os módulos de negócio declararam, na ordem em que
#: chegaram (`declarar_acoes`). O da base é `ACOES`, sempre o primeiro.
_DECLARADOS: list = []


def _nomes(namespace) -> dict[str, str]:
    return {nome: valor for nome, valor in vars(namespace).items()
            if not nome.startswith("_") and isinstance(valor, str)}


def vocabulario() -> dict[str, str]:
    """Toda ação que a trilha conhece, `{NOME: valor gravado}` — a da base e a
    de cada módulo de negócio."""
    todas = _nomes(ACOES)
    for namespace in _DECLARADOS:
        todas.update(_nomes(namespace))
    return todas


def declarar_acoes(namespace, rotulos: "dict[str, str]") -> None:
    """Acrescenta ao vocabulário as ações de um módulo de negócio.

    **A base não conhece os módulos** (`CLAUDE.md` §3), e as ações deles
    moravam aqui dentro — no Fila Zero, doze `FILA_*` na classe `ACOES`. Era o
    que impedia a base de voltar limpa para o produto: toda cópia dela trazia
    a fila junto, ou apagava o que a fila usava (auditoria de 21/09/2026).

    O módulo declara uma classe-namespace, como `ACOES`, e os rótulos, no
    `ready()` do app dele. Nome ou valor repetido é recusado: duas ações com o
    mesmo nome gravariam a mesma linha para dois fatos diferentes, e a trilha
    mentiria sem erro nenhum. Declarar de novo o MESMO namespace (o `ready()`
    roda mais de uma vez nos testes) não faz nada.
    """
    if namespace in _DECLARADOS:
        return
    ja = vocabulario()
    novas = _nomes(namespace)
    repetidos = sorted(set(novas) & set(ja)) + sorted(
        v for v in novas.values() if v in ja.values())
    if repetidos:
        raise ValueError(f"ações já declaradas: {repetidos}")
    sem_rotulo = sorted(v for v in novas.values() if v not in rotulos)
    if sem_rotulo:
        raise ValueError(f"ações sem rótulo: {sem_rotulo}")
    _DECLARADOS.append(namespace)
    ROTULOS.update(rotulos)


def _conta_de(autor, login: str):
    """O GUID da conta de `autor`, ou `None` para quem não é de conta nenhuma.

    Durante a personificação `autor` já é o ALVO (ver `registrar`), então a
    linha fica na conta de quem foi personificado — é nela que a ação
    aconteceu. A MW5 agindo por si mesma não tem conta, e a linha fica nula.

    O usuário do ORM já traz `conta_id`; o retrato do núcleo e a string crua
    não, e são achados pelo login. Uma consulta a mais por registro, contra
    uma trilha que não diz de que conta é.
    """
    if hasattr(autor, "conta_id"):
        return autor.conta_id
    if not login:
        return None
    from django.apps import apps
    from django.conf import settings

    Usuario = apps.get_model(settings.AUTH_USER_MODEL)
    return (Usuario._default_manager
            .filter(**{f"{Usuario.USERNAME_FIELD}__iexact": login})
            .values_list("conta", flat=True).first())


def _login_e_nome(autor) -> tuple[str, str]:
    """(`login`, `nome`) de `autor`, qualquer que seja a forma dele.

    `autor` chega por três caminhos diferentes, e os três precisam
    funcionar sem que quem chama precise saber qual é qual:

    - o `contas.models.Usuario` de verdade, no caminho comum das views
      (`request.usuario` é outra coisa — ver o próximo item — mas algumas
      views já têm o usuário do ORM em mãos, por exemplo depois de trocar a
      própria senha);
    - o `nucleo.permissoes.User`, que é o que `request.usuario` de fato é
      depois que a guarda (`contas/guardas.py`) reconstrói a sessão;
    - uma string crua, quando não existe usuário nenhum para descrever — o
      caso da entrada recusada: o login digitado pode não corresponder a
      ninguém, e mesmo assim precisa ficar registrado.
    """
    if isinstance(autor, str):
        return autor, ""

    # `email` no usuário do ORM (é o `USERNAME_FIELD` desde que o usuário
    # passou a ser nosso) e `login` no retrato congelado do núcleo. Os dois
    # nomes para o mesmo fato, porque quem chama não sabe qual está na mão.
    login = getattr(autor, "email", None)
    if login is None:
        login = getattr(autor, "login", "")

    obter_nome_completo = getattr(autor, "get_full_name", None)
    nome = obter_nome_completo() if obter_nome_completo is not None else ""
    if not nome:
        nome = getattr(autor, "name", "") or login

    return login, nome


def _truncado(nome_do_campo: str, valor: str) -> str:
    """`valor`, cortado no `max_length` que o próprio model declara para
    `nome_do_campo`.

    O Django não aplica `max_length` sozinho: isso é `full_clean()`, e
    `objects.create()` nunca passa por ali — é o `INSERT` cru que chega ao
    banco. SQLite (o das telas de teste) não reclama de `VARCHAR` estourado
    e deixa a linha entrar do mesmo jeito; Postgres (o de produção,
    `config/settings.py`) reclama, e `DataError` sobe (pela regra de não
    engolir exceção, acima). Um autor pode digitar qualquer coisa no campo
    de login da tela de entrada — inclusive mais que os 255 caracteres de
    `alvo` — e a entrada recusada tenta gravar esse texto inteiro. Cortar
    aqui, e não em cada view que chama `registrar`, é o que garante que as
    quinze chamadas herdam a correção junto: um limite mudado em
    `contas/models.py` vale para todo mundo sem precisar lembrar de mexer em
    quinze lugares.
    """
    limite = _modelo()._meta.get_field(nome_do_campo).max_length
    return valor if limite is None else valor[:limite]


def registrar(
    acao: str, autor, alvo: str = "", detalhe: str = "", *, request=None,
) -> None:
    """Grava uma linha na trilha de auditoria.

    Não engole exceção nenhuma — de propósito. Se a gravação falhar, o erro
    sobe para quem chamou, e a ação que originou o registro já aconteceu (é
    sempre chamada depois do efeito, nunca antes: ver os pontos de chamada
    em `contas/views.py` e companhia). Uma trilha de auditoria que falha em
    silêncio deixa de existir sem que ninguém perceba, e a primeira vez que
    alguém notaria seria exatamente na hora em que precisasse dela. Quem um
    dia se sentir tentado a embrulhar esta chamada num `try` devia reler
    este parágrafo antes.

    `request`, quando passado, é como esta função aprende se quem chamou
    estava personificando (Task 11): enquanto isso, `autor` já chega sendo o
    ALVO — é ele quem `usuario_da_sessao` devolve, e é o nome certo para o
    `autor_login`/`autor_nome` da linha, porque foi em nome dele que a ação
    aconteceu. Mas sozinho isso mentiria por omissão: a trilha pareceria
    dizer que o alvo decidiu fazer aquilo, quando foi o original personificando-o.
    Por isso a nota entra em `detalhe`, e entra bem AQUI — não em cada uma
    das quinze chamadas espalhadas por `contas/` e `plataforma/`, que teriam
    que lembrar de checar personificação uma a uma (e uma tela nova
    esqueceria). `request` é opcional e não muda a assinatura de quem já
    chama sem ele: `None` (o padrão) é só "esta chamada não sabe dizer se
    havia personificação em curso", nunca "havia e foi omitida".

    Import adiado (dentro do corpo, não no topo do arquivo): `personificacao`
    importa `ACOES` e `registrar` deste módulo para gravar o próprio início e
    fim da personificação, e um `import` no topo dos dois lados criaria um
    ciclo. Adiar aqui — só no caminho que de fato precisa, com `request`
    passado — resolve sem um terceiro módulo só para isto.
    """
    if request is not None:
        from .personificacao import original_de, personificando

        if personificando(request):
            original = original_de(request)
            nota = f"personificado por {original.login if original else '?'}"
            detalhe = f"{detalhe} ({nota})" if detalhe else nota

    login, nome = _login_e_nome(autor)
    _modelo().objects.create(
        conta_guid=_conta_de(autor, login),
        acao=_truncado("acao", acao),
        autor_login=_truncado("autor_login", login),
        autor_nome=_truncado("autor_nome", nome),
        alvo=_truncado("alvo", alvo),
        detalhe=_truncado("detalhe", detalhe),
    )
