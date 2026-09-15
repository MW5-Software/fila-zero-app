"""As duas funções que respondem "o que esta pessoa alcança".

**Existem como funções, e não repetidas em cada view**, pelo motivo que o
`kronos-api2` já escreveu no equivalente dele: *"a regra vale para a PÁGINA,
para o polling e para o Reenviar — e uma delas esquecida é um usuário comum
reenviando envio de homologação com o `api_id` digitado na URL"*.

Aqui o equivalente seria um comprador lendo o orçamento — e o PREÇO — de
outro comprador, com o id digitado na barra do navegador.

**Alcançar a empresa não é enxergar tudo dela.** Vendedor e cliente alcançam
a MESMA empresa, e mesmo assim um cliente não vê os orçamentos do outro. A
fronteira do inquilino não isola nada dentro dele; quem isola por dentro é o
ALCANCE do cargo (`contas.lugar`, desde 14/09/2026 — antes era a carteira).

**O que mudou quando o usuário passou a ser nosso.** O nível, o alcance e a
carteira moravam numa linha à parte (`acesso_acesso`), e havia aqui uma
`usuario_de(usuario)` que a buscava. As colunas subiram para o próprio
`Usuario`. A tradução em si (`usuario_de`, `_id_de`) morou aqui até outro
módulo precisar dela também, e um módulo importando o outro para
pegá-la fechava um ciclo mascarado por import tardio — mudou para
`contas.identidade`, que fica ABAIXO dos dois, e este módulo importa de lá
e re-exporta `usuario_de` para não quebrar quem já fazia
`from contas.alcance import usuario_de`.
"""

from __future__ import annotations

from plataforma.models import Empresa

from .identidade import usuario_de
from .lugar import empresas_da_pessoa, pode_administrar
from .models import Usuario

__all__ = ["conta_de", "empresa_de",
           "empresas_alcancadas", "pessoas_alcancadas", "usuario_de"]


def _ve_tudo(usuario, pessoa: "Usuario | None") -> bool:
    """Quem enxerga o portal inteiro.

    O superusuário do Django entra aqui junto do MASTER, como na origem
    (`user.is_superuser or user.is_admin`): quem administra a instalação não
    pode ficar de fora do próprio sistema por falta de uma linha de cadastro.

    Os dois nomes do mesmo atributo porque os dois tipos de usuário o
    chamam diferente: `is_superuser` no do ORM, `superuser` na dataclass do
    design system.
    """
    if getattr(usuario, "is_superuser", False) or getattr(usuario, "superuser", False):
        return True
    return bool(pessoa and (pessoa.is_superuser or pessoa.e_master))


def conta_de(pessoa: "Usuario | None") -> "Usuario | None":
    """O Admin dono da conta desta pessoa — ou `None`.

    O ADMIN é a própria conta: `dono` nele é nulo de propósito (apontar para
    si mesmo seria um ciclo que toda consulta teria de tratar), e é aqui que
    esse nulo vira "ele mesmo". Quem chama não precisa saber da regra.

    O MASTER não tem conta: a MW5 não é cliente de nenhuma.
    """
    if pessoa is None or pessoa.is_superuser or pessoa.e_master:
        return None
    if pessoa.e_titular_ou_acima:
        return pessoa
    return pessoa.dono


def empresa_de(usuario) -> "Empresa | None":
    """A empresa desta pessoa: a primeira que ela alcança, ou nenhuma.

    A empresa não é guardada na pessoa (09/09/2026): é DERIVADA da conta, para o
    titular, e das alocações, para o membro (`contas.lugar.empresas_da_pessoa`).
    Guardar nos dois lados é o que deixa os dois divergirem.

    **`None` para o MASTER, e não "todas".** Ele não trabalha DENTRO de uma
    empresa; ele olha as contas de fora. Devolver "todas" aqui faria uma
    consulta de inquilino escrita com pressa (`filter(empresa=empresa_de(u))`)
    virar um vazamento silencioso no dia em que a MW5 abrisse a tela.
    """
    pessoa = usuario_de(usuario)
    if pessoa is None or _ve_tudo(usuario, pessoa):
        return None
    return empresas_da_pessoa(pessoa).first()


def empresas_alcancadas(usuario):
    """As empresas que esta pessoa alcança: todas para o MASTER, as da conta
    para o titular, e as das alocações para o membro.

    MASTER alcança todas **sem precisar de vínculo**. Alcance ilimitado
    concedido por linha seria uma linha que alguém marca sem querer; aqui ele
    vem do nível, que é decisão explícita de quem cadastrou.
    """
    pessoa = usuario_de(usuario)
    if _ve_tudo(usuario, pessoa):
        return Empresa.objects.all()
    return empresas_da_pessoa(pessoa)


def pessoas_alcancadas(usuario):
    """Quem esta pessoa pode ADMINISTRAR — cadastrar, editar, desativar.

    **É uma pergunta diferente de "de quem eu vejo os orçamentos"**
    (`contas.lugar.clientes_alcancados`): ver o pedido de um cliente não dá o
    direito de mexer na conta dele.

    - MASTER e superusuário: todo mundo, menos superusuário (a conta que
      administra a instalação não se mexe por esta tela — a mesma regra que
      o KRONOS já tinha para a MW5).
    - ADMIN: as pessoas da CONTA dele.
    - Membro: só quem ele poderia ter alocado (R6). Quem não tem
      `usuarios.editar` nem chega à tela.
    - Quem não está no banco: ninguém.
    """
    pessoa = usuario_de(usuario)

    if _ve_tudo(usuario, pessoa):
        return Usuario.objects.filter(is_superuser=False)

    if pessoa is None:
        return Usuario.objects.none()

    if not pessoa.e_titular_ou_acima:
        # Membro com `usuarios.editar` (Supervisor, Gerente): só quem ele
        # poderia ter alocado (`contas.lugar.pode_administrar`, R6 do plano 2).
        # Sem isto um Gerente trocaria a senha de um Supervisor e entraria como
        # ele. Em Python, e não numa consulta: a regra compara permissões e
        # alcance de cargo, e uma conta tem dezenas de pessoas, não milhares.
        # Quem não tem `usuarios.editar` nem abre a tela — a rota tranca antes.
        if pessoa.dono_id is None:
            return Usuario.objects.none()
        candidatos = Usuario.objects.filter(
            dono_id=pessoa.dono_id, is_superuser=False).prefetch_related(
            "alocacoes__empresa", "alocacoes__filial", "alocacoes__cargo")
        return Usuario.objects.filter(
            pk__in=[c.pk for c in candidatos if pode_administrar(pessoa, c)])

    # As pessoas DA CONTA dele — e ele próprio não entra: ninguém se
    # administra por esta tela, e o `dono` do Admin é nulo justamente porque
    # ele é a conta.
    return Usuario.objects.filter(is_superuser=False, dono=pessoa).distinct()
