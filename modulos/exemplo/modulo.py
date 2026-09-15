"""O que o módulo Exemplo diz sobre si.

Só a declaração mora aqui — quem registra é `apps.ExemploConfig.ready()`, e
não a importação deste arquivo. Ver o comentário lá para o motivo.
"""

from __future__ import annotations

from plataforma.declaracao import ModuloSpec
from django.utils.translation import gettext_lazy as _

#: "Eu sou o Exemplo. Meu ícone é o círculo de visto. Eu moro no grupo Geral.
#: Minha rota é /exemplo. Eu crio as permissões exemplo.ver e exemplo.editar."
#:
#: Este é o módulo que prova o mecanismo inteiro da matriz — do código até a
#: tela — e nada mais. "Exemplo" é escolhido como rótulo também porque não
#: colide com nenhum texto decorativo da tela de demonstração do núcleo
#: (`nucleo/views.py`, `_miolo()`), que usa "Frete" em vários lugares — a
#: mesma colisão que a Task 9 encontrou.
MODULO = ModuloSpec(
    chave="exemplo",
    rotulo=_("Exemplo"),
    icone="check-circle",
    grupo="Geral",
    rota="/exemplo",
    permissoes=("exemplo.ver", "exemplo.editar"),
)
