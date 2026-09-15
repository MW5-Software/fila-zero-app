"""Os parâmetros de acesso desta instalação.

`so_mw5=True` nos dois, de propósito: política de acesso (quanto tempo a
sessão dura, quando a senha vence) é decisão de quem opera a plataforma —
o mesmo critério que faz `mw5.aparencia` não ser concedível pela tela de
Perfis. O cliente que quiser outro tempo fala com a MW5, que decide com
critério igual para as vinte instalações.
"""

from __future__ import annotations

from plataforma.parametro_declaracao import ParametroSpec
from django.utils.translation import gettext_lazy as _

__all__ = ["PARAMETRO_MINUTOS_DE_SESSAO", "PARAMETRO_DIAS_PARA_EXPIRAR_SENHA"]

#: Quanto tempo a sessão fica de pé SEM atividade (renovada a cada
#: requisição — é inatividade que derruba, não idade). `0` = o padrão do
#: Django (duas semanas), para quem não quer mexer em nada.
PARAMETRO_MINUTOS_DE_SESSAO = ParametroSpec(
    chave="minutos_de_sessao",
    rotulo=_("Minutos de sessão sem atividade"),
    tipo="numero",
    padrao=480,
    grupo="Acesso",
    ajuda="A sessão expira após este tempo PARADO; cada tela visitada "
          "renova a contagem. 0 usa o padrão do Django (2 semanas).",
    so_mw5=True,
)

#: Depois de tantos dias com a MESMA senha, o próximo login leva à troca
#: obrigatória. `0` = nunca expira.
PARAMETRO_DIAS_PARA_EXPIRAR_SENHA = ParametroSpec(
    chave="dias_para_expirar_senha",
    rotulo=_("Dias para a senha expirar"),
    tipo="numero",
    padrao=0,
    grupo="Acesso",
    ajuda="No login seguinte a este prazo, a pessoa é levada a trocar a "
          "própria senha antes de usar qualquer tela. 0 = nunca expira.",
    so_mw5=True,
)
