"""Onde a pessoa está, e o que ela pode ali.

A mudança que este módulo carrega (spec 2026-09-14, D1 e D9): a permissão
deixou de ser da PESSOA e passou a ser do CARGO da alocação dela NUM LUGAR. A
mesma Ana é Gerente na Centro e Vendedora na Norte, e o que ela pode depende de
onde está trabalhando agora.

**Funções sobre a linha do ORM, e não sobre a requisição.** Quem traduz a
requisição (sessão, empresa e filial atuais) para estas perguntas é a camada de
cima (`com_permissoes_do_lugar` e as funções `*_atual`, Task 2). Separado assim,
cada regra se testa com três linhas de cadastro, sem sessão nem cliente HTTP.

**O titular e a MW5 não têm cargo** (D3). Eles alcançam por serem quem são, e as
permissões deles continuam as de `contas/fabrica.py`. Se o dono dependesse de um
cargo, bastaria editar esse cargo para ele se trancar para fora da própria conta.

**Uma alocação só vale na conta atual da pessoa.** Toda consulta confere
`pessoa.dono_id == empresa.dono_id`. Mudar alguém de conta tem de valer na
requisição seguinte, sem depender de ninguém lembrar de apagar as alocações
antigas.
"""

from __future__ import annotations

from django.db.models import QuerySet

from nucleo.permissoes import User, pode
from plataforma.models import Empresa, Filial

from .backend import permissoes_de, traduzir
from .identidade import usuario_de
from .models import Alcance, Alocacao, Cargo, Nivel, Usuario

__all__ = [
    "alcance_atual", "alcance_em", "alocacao_vigente", "cargo_atual",
    "clientes_alcancados", "com_permissoes_do_lugar", "e_cliente",
    "tem_cargo_de_cliente", "empresas_da_pessoa", "filiais_da_pessoa",
    "permissoes_do_cargo", "permissoes_em", "pode_administrar", "pode_dar",
]

#: Do menor para o maior. "Poder dar" um cargo exige alcance igual ou menor que
#: o de quem dá (R7).
_TAMANHO_DO_ALCANCE = {Alcance.PROPRIOS: 0, Alcance.FILIAL: 1, Alcance.EMPRESA: 2}


def _ve_tudo(pessoa: Usuario) -> bool:
    return pessoa.is_superuser or pessoa.nivel == Nivel.MASTER


def _e_dono(pessoa: Usuario, empresa: Empresa) -> bool:
    return pessoa.nivel == Nivel.TITULAR and empresa.dono_id == pessoa.pk


def _membro_da_conta(pessoa: Usuario, empresa: Empresa) -> bool:
    return (pessoa.nivel > Nivel.TITULAR and not pessoa.is_superuser
            and pessoa.dono_id is not None and pessoa.dono_id == empresa.dono_id)


def empresas_da_pessoa(pessoa: "Usuario | None") -> "QuerySet[Empresa]":
    """As empresas que a pessoa alcança. MASTER: todas. Titular: as da conta
    dele. Membro: só onde tem alocação, e só na conta atual dele."""
    if pessoa is None or not pessoa.pk:
        return Empresa.objects.none()
    if _ve_tudo(pessoa):
        return Empresa.objects.all()
    if pessoa.nivel == Nivel.TITULAR:
        return Empresa.objects.filter(dono=pessoa)
    if pessoa.dono_id is None:
        return Empresa.objects.none()
    return Empresa.objects.filter(
        dono_id=pessoa.dono_id, alocacoes__pessoa=pessoa).distinct()


def filiais_da_pessoa(pessoa: "Usuario | None",
                      empresa: "Empresa | None") -> "QuerySet[Filial]":
    """As filiais ATIVAS de `empresa` que a pessoa alcança.

    Uma alocação na empresa inteira abre todas as filiais, inclusive as criadas
    depois (D8). Por isso a resposta é uma consulta às filiais da empresa, e não
    uma lista copiada no dia em que a pessoa foi alocada.
    """
    if pessoa is None or empresa is None or not pessoa.pk:
        return Filial.objects.none()
    ativas = Filial.objects.filter(empresa=empresa, ativa=True)
    if _ve_tudo(pessoa) or _e_dono(pessoa, empresa):
        return ativas
    if not _membro_da_conta(pessoa, empresa):
        return ativas.none()
    minhas = Alocacao.objects.filter(pessoa=pessoa, empresa=empresa)
    if minhas.filter(filial__isnull=True).exists():
        return ativas
    return ativas.filter(alocacoes__in=minhas).distinct()


def alocacao_vigente(pessoa, empresa, filial) -> "Alocacao | None":
    """A alocação que vale aqui: a da filial exata, senão a da empresa inteira.

    **A mais específica ganha; as duas não somam.** Quem é Supervisor da empresa
    e Vendedor na Norte é Vendedor quando está na Norte. Somar deixaria o cargo
    menor sem efeito nenhum, e ninguém conseguiria restringir alguém numa filial.
    """
    if pessoa is None or empresa is None or not _membro_da_conta(pessoa, empresa):
        return None
    minhas = Alocacao.objects.select_related("cargo").filter(
        pessoa=pessoa, empresa=empresa)
    if filial is not None and filial.empresa_id == empresa.pk:
        exata = minhas.filter(filial=filial).first()
        if exata is not None:
            return exata
    return minhas.filter(filial__isnull=True).first()


def permissoes_do_cargo(cargo: Cargo) -> frozenset[str]:
    from .backend import APP_DOS_MODULOS

    return traduzir(cargo.permissoes.filter(
        content_type__app_label=APP_DOS_MODULOS).values_list("codename", flat=True))


def permissoes_em(pessoa, empresa, filial) -> frozenset[str]:
    """O que a pessoa pode NESTE lugar.

    Titular: as de fábrica, só dentro da empresa dele. MASTER: as de fábrica em
    qualquer uma. Membro: as do cargo da alocação vigente, ou nenhuma.
    """
    if pessoa is None or empresa is None:
        return frozenset()
    if _ve_tudo(pessoa) or _e_dono(pessoa, empresa):
        return permissoes_de(pessoa)
    vigente = alocacao_vigente(pessoa, empresa, filial)
    return permissoes_do_cargo(vigente.cargo) if vigente else frozenset()


def alcance_em(pessoa, empresa, filial) -> str:
    """Quais registros a pessoa enxerga aqui. Sem alocação, `PROPRIOS`: ver de
    menos se corrige; ver de mais já vazou."""
    if pessoa is not None and empresa is not None and (
            _ve_tudo(pessoa) or _e_dono(pessoa, empresa)):
        return Alcance.EMPRESA
    vigente = alocacao_vigente(pessoa, empresa, filial)
    return vigente.cargo.alcance if vigente else Alcance.PROPRIOS


def pode_dar(editor, empresa, filial, cargo) -> bool:
    """Se `editor` pode alocar alguém com `cargo` neste lugar.

    As três travas do spec ("Quem pode mexer em quê"), conferidas aqui e não na
    tela, para o POST forjado passar pelo mesmo lugar que o formulário:

    1. o lugar é um que o editor alcança; na empresa inteira, só quem alcança a
       empresa inteira;
    2. o editor tem `usuarios.editar` ali e todas as permissões do cargo;
    3. o alcance do cargo não é maior que o do editor (R7).
    """
    if editor is None or empresa is None or cargo is None:
        return False
    if empresa.conta_id is None or cargo.conta_id != empresa.conta_id:
        return False
    if filial is not None and filial.empresa_id != empresa.pk:
        return False
    if _ve_tudo(editor):
        return True
    if editor.nivel == Nivel.TITULAR:
        return _e_dono(editor, empresa)
    if filial is None:
        if not Alocacao.objects.filter(pessoa=editor, empresa=empresa,
                                       filial__isnull=True).exists():
            return False
    elif not filiais_da_pessoa(editor, empresa).filter(pk=filial.pk).exists():
        return False
    retrato = User(id=str(editor.pk), name="",
                   permissions=permissoes_em(editor, empresa, filial))
    if not pode(retrato, "usuarios.editar"):
        return False
    if not all(pode(retrato, p) for p in permissoes_do_cargo(cargo)):
        return False
    if _TAMANHO_DO_ALCANCE[cargo.alcance] > _TAMANHO_DO_ALCANCE[
            alcance_em(editor, empresa, filial)]:
        return False
    # A lista do cargo de quem edita, quando ela existe (17/09/2026): o
    # gerente cria vendedor, e não outro gerente. Vazia é a regra de antes,
    # para nenhuma conta que já existe mudar de comportamento sozinha.
    vigente = alocacao_vigente(editor, empresa, filial)
    if vigente is None:
        return False
    concedidos = vigente.cargo.pode_conceder.all()
    return not concedidos.exists() or concedidos.filter(pk=cargo.pk).exists()


def pode_administrar(editor, alvo) -> bool:
    """Se `editor` pode editar, trocar a senha, desativar ou remover `alvo`.

    Para quem não é titular (R6): só se TODA alocação do alvo for uma que o
    editor poderia ter dado. Sem isto, um Gerente trocaria a senha de um
    Supervisor e entraria como ele. **Ninguém administra a si mesmo por esta
    porta**, e é isso que impede alguém de editar a própria alocação.
    """
    if editor is None or alvo is None or alvo.is_superuser:
        return False
    if _ve_tudo(editor):
        return True
    if alvo.pk == editor.pk or alvo.nivel <= Nivel.TITULAR:
        return False
    if editor.nivel == Nivel.TITULAR:
        return alvo.dono_id == editor.pk
    if alvo.dono_id is None or alvo.dono_id != editor.dono_id:
        return False
    alocacoes = list(alvo.alocacoes.select_related("empresa", "filial", "cargo"))
    return bool(alocacoes) and all(
        pode_dar(editor, a.empresa, a.filial, a.cargo) for a in alocacoes)


def com_permissoes_do_lugar(request, user: User) -> User:
    """O `user` da sessão com as permissões do cargo no lugar atual.

    Titular e MW5 voltam como vieram: as permissões deles são as de fábrica, que
    o backend já pôs. Para o membro, o cargo da alocação vigente na empresa e
    filial atuais, ou nenhuma permissão.
    """
    from dataclasses import replace

    from plataforma.contexto import empresa_atual, filial_atual

    pessoa = usuario_de(user)
    if pessoa is None or _ve_tudo(pessoa) or pessoa.nivel <= Nivel.TITULAR:
        return user
    vigente = alocacao_vigente(pessoa, empresa_atual(request), filial_atual(request))
    permissoes = permissoes_do_cargo(vigente.cargo) if vigente else frozenset()
    return replace(user, permissions=permissoes)


def _pessoa_e_lugar(request):
    from comum.sessao import identidade_da_sessao
    from plataforma.contexto import empresa_atual, filial_atual

    return (usuario_de(identidade_da_sessao(request)),
            empresa_atual(request), filial_atual(request))


def cargo_atual(request) -> "Cargo | None":
    """O cargo da alocação vigente de quem está olhando, no lugar atual."""
    from comum.memoria import lembrar

    def calcular():
        pessoa, empresa, filial = _pessoa_e_lugar(request)
        vigente = alocacao_vigente(pessoa, empresa, filial)
        return vigente.cargo if vigente else None

    return lembrar(request, "lugar:cargo", calcular)


def e_cliente(request) -> bool:
    """Substitui `tem_papel(usuario, Papel.COMPRADOR)` nos lugares que
    perguntavam isso (spec, `e_cliente`). É do cargo, e não do alcance: sem
    carteira, Vendedor e Cliente podem ter o mesmo alcance."""
    cargo = cargo_atual(request)
    return bool(cargo and cargo.e_cliente)


def alcance_atual(request) -> str:
    """O alcance de quem está olhando, no lugar atual."""
    pessoa, empresa, filial = _pessoa_e_lugar(request)
    return alcance_em(pessoa, empresa, filial)


def clientes_alcancados(request) -> "QuerySet[Usuario]":
    """Os clientes que quem está olhando enxerga na empresa atual.

    Substitui `compradores_alcancados`, que lia o papel do perfil e a carteira
    (D6: a carteira sai da regra e fica no banco, sem uso). Cliente é quem tem
    alocação com cargo `e_cliente` nesta empresa. Alocado na empresa inteira,
    ele pertence a todas as filiais.

    `dono_id=empresa.dono_id`: uma alocação que apontasse para esta empresa a
    partir de outra conta (gravada por fora do `save`, que a recusaria) não
    abre a pessoa de outro cliente.
    """
    from django.db.models import Q

    pessoa, empresa, filial = _pessoa_e_lugar(request)
    if pessoa is None or empresa is None:
        return Usuario.objects.none()
    alocacoes = Alocacao.objects.filter(empresa=empresa, cargo__e_cliente=True)
    alcance = alcance_em(pessoa, empresa, filial)
    if alcance == Alcance.FILIAL:
        if filial is None:
            return Usuario.objects.none()
        alocacoes = alocacoes.filter(Q(filial=filial) | Q(filial__isnull=True))
    clientes = Usuario.objects.filter(
        pk__in=alocacoes.values("pessoa_id"), dono_id=empresa.dono_id)
    if alcance == Alcance.PROPRIOS:
        return clientes.filter(pk=pessoa.pk)
    return clientes


def tem_cargo_de_cliente(usuario) -> bool:
    """Se a pessoa é cliente em algum lugar da conta dela.

    Existe ao lado de `e_cliente(request)` para a pergunta feita FORA de
    requisição, onde não há lugar atual. No Portal de Vendas, de onde a base
    saiu, é o preço negociado: o orçamento calcula o total pelo comprador dele,
    e a vitrine usa a mesma pergunta para o rótulo "Seu preço" não discordar do
    número que mostra.
    """
    pessoa = usuario_de(usuario)
    if pessoa is None or not pessoa.pk or pessoa.dono_id is None:
        return False
    return Alocacao.objects.filter(
        pessoa=pessoa, cargo__e_cliente=True,
        empresa__dono_id=pessoa.dono_id).exists()
