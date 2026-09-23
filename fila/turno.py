"""O turno da loja e a saída de quem ficou depois dele.

Decisão do cliente (23/09/2026): *"criar o parâmetro de turno da empresa/filial
por que vamos fazer automatizar se o vendedor não saiu da fila, depois de uma
hora do turno ele sai sozinho"*. Duas escolhas dele no mesmo dia:

- o horário é por **FILIAL** — loja que fecha mais tarde não tira ninguém da
  fila cedo;
- quem sai é quem está **na fila, em espera ou em pausa**. Quem está ATENDENDO
  fica: fechar sozinho um atendimento aberto perderia a venda que o vendedor
  está lançando.

**Sem relógio no sistema, a regra roda na LEITURA.** Não há cron nesta
instalação, e a página da fila consulta o estado a cada três segundos
(`fila/views.py`): `aplicar` é chamado no caminho de toda leitura da loja, e o
que ele faz é o que a loja já deveria ter feito. É idempotente — na segunda
passada a lista de quem sai está vazia.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

__all__ = ["PRAZO", "aplicar", "caixa", "definir", "fim_de", "ler_hora", "prazo"]

#: A carência depois do fim do turno: quem ainda está na loja uma hora depois
#: dele sai sozinho. É o número que o cliente pediu ("depois de uma hora do
#: turno"), e mora aqui para não ser reescrito em cada lugar que o pergunta.
PRAZO = timedelta(hours=1)

#: Quem assina a linha da trilha da saída automática. Não há usuário nenhum
#: por trás dela, e inventar um seria pior do que dizer que foi o sistema.
SISTEMA = "sistema"


def _agora():
    """A hora pelo MESMO ponto das ações (`acoes._agora`).

    Um relógio só (CLAUDE.md §10): com dois, quem saiu pelo turno apareceria
    depois de quem entrou na fila em seguida, e o teste que faz o relógio andar
    não alcançaria esta regra.
    """
    from .acoes import _agora as agora_das_acoes

    return agora_das_acoes()


def fim_de(filial) -> "time | None":
    """A hora em que o turno desta loja termina — ou `None`, que é "sem turno".

    Sem linha na tabela não há turno, e sem turno não há saída automática:
    nenhuma loja precisa de linha para funcionar como sempre funcionou (mesma
    forma de `fila.FluxoDaEmpresa`).
    """
    from .models import TurnoDaLoja

    if filial is None:
        return None
    turno = TurnoDaLoja.irrestritos.filter(filial=filial).first()
    return turno.fim if turno is not None else None


def ler_hora(texto: str) -> "time | None":
    """`HH:MM` do campo da filial; vazio é "sem turno".

    O campo é `type="time"`, mas quem digita pode mandar qualquer coisa no
    POST — e hora torta vira `ValidationError` com a frase da tela, e não 500.
    """
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        hora, minuto = (int(parte) for parte in texto.split(":")[:2])
        return time(hour=hora, minute=minuto)
    except (TypeError, ValueError):
        raise ValidationError(_("Escreva a hora do turno assim: 18:00."))


def definir(filial, fim: "time | None") -> None:
    """Grava o turno da loja — ou apaga, com `fim` vazio."""
    from .models import TurnoDaLoja

    if fim is None:
        TurnoDaLoja.irrestritos.filter(filial=filial).delete()
        return
    TurnoDaLoja.irrestritos.update_or_create(
        filial=filial, defaults={"empresa": filial.empresa, "fim": fim})


def prazo(filial, agora=None):
    """O último instante em que a fila desta loja deveria ter sido esvaziada,
    ou `None` quando ainda não passou de nenhum.

    É o fim do turno MAIS a carência, do dia de hoje ou de ONTEM: uma loja que
    fecha 23:30 tem prazo à 00:30 do dia seguinte, e às 00:15 quem ficou de
    ontem ainda está dentro do prazo — sem olhar ontem, essa gente só sairia no
    dia seguinte.
    """
    fim = fim_de(filial)
    if fim is None:
        return None
    agora = agora or _agora()
    hoje = timezone.localdate(agora)
    for dia in (hoje, hoje - timedelta(days=1)):
        limite = timezone.make_aware(datetime.combine(dia, fim)) + PRAZO
        if limite <= agora:
            return limite
    return None


def aplicar(filial, agora=None) -> int:
    """Tira da loja quem passou do turno, e devolve quantos saíram.

    A saída é gravada com a hora do PRAZO, e não com a hora em que alguém
    abriu a página: quem ficou até 00:30 não pode aparecer como tendo ficado
    até as 3h da manhã porque a primeira leitura do dia foi às 3h.
    """
    from comum.auditoria import registrar

    from .acoes import _sair, _travar
    from .auditoria import ACOES_DA_FILA
    from .correcoes import _alvo
    from .models import Estado, LugarNaFila

    limite = prazo(filial, agora)
    if limite is None:
        return 0

    sairam = 0
    with transaction.atomic():
        _travar(filial)
        lugares = list(
            LugarNaFila.irrestritos
            .filter(filial=filial, presenca__saida__isnull=True,
                    presenca__entrada__lt=limite)
            # Quem está ATENDENDO fica: o atendimento aberto é a venda que o
            # vendedor está lançando (decisão do cliente).
            .exclude(estado=Estado.ATENDENDO)
            .select_related("presenca", "pessoa"))
        for lugar in lugares:
            _sair(lugar, limite)
            registrar(ACOES_DA_FILA.FILA_SAIDA_POR_TURNO, SISTEMA,
                      alvo=_alvo(lugar, filial),
                      detalhe=_("fim do turno (%(hora)s) mais uma hora") % {
                          "hora": limite.strftime("%H:%M")})
            sairam += 1
    return sairam


def caixa(filial):
    """A caixa "Fim do turno" no formulário da filial (`caixas_da_filial`)."""
    from nucleo.components import TextInput

    fim = fim_de(filial)
    return TextInput(name="fim_do_turno", label=_("Fim do turno"), span=4,
                     type="time", value=fim.strftime("%H:%M") if fim else "",
                     help=_("Uma hora depois desta hora, quem estiver na fila, "
                            "em espera ou em pausa sai sozinho. Em branco, "
                            "esta loja não tem turno."))


def gravar_do_post(request, filial) -> None:
    """Lê o campo da caixa e grava o turno — `ValidationError` recusa."""
    definir(filial, ler_hora(request.POST.get("fim_do_turno", "")))