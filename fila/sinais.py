"""O que a fila responde aos sinais da base.

Mora à parte de `acoes.py` porque não é uma ação do vendedor: é a base
perguntando se pode mexer numa loja, e a resposta liga no `ready()` do app.
"""

from __future__ import annotations

from django.utils.translation import ngettext

__all__ = ["recusar_desativar_loja_com_gente"]


def recusar_desativar_loja_com_gente(sender, filial, **kwargs) -> "str | None":
    """Loja com presença aberta não se desativa (revisão final, 15/09/2026).

    Quem estava presente numa loja desativada ficava preso: o ponto em outra
    loja recusa enquanto a presença está aberta, e a página da fila da loja
    desativada não abre para ninguém fechá-la. Recusar foi a regra escolhida
    pelo João, em vez de fechar as presenças junto: fechar escondido tiraria
    da fila quem está no meio de um atendimento, sem lançamento.

    Conta também a presença esquecida de outro dia: ela prende do mesmo jeito.
    """
    from .models import Presenca

    if filial.empresa_id is None:
        return None
    presentes = (Presenca.objects.da_empresa(filial.empresa)
                 .filter(filial=filial, saida__isnull=True).count())
    if not presentes:
        return None
    return ngettext(
        "Há %(n)s pessoa presente nesta loja. Tire-a da loja na página da "
        "fila antes de desativar.",
        "Há %(n)s pessoas presentes nesta loja. Tire todas da loja na página "
        "da fila antes de desativar.", presentes) % {"n": presentes}
