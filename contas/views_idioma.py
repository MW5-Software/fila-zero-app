"""A troca de idioma — só a ação, sem tela própria.

**Duas portas, e o motivo de serem diferentes.**

Quem já entrou troca em Meu Perfil, por POST com CSRF: é mudança de estado da
CONTA (grava coluna), e mudança de estado nesta casa não anda por link. Um
`<img src="/idioma?es">` numa página qualquer trocaria o idioma de quem
abrisse — dano pequeno, defesa que já existe pronta.

Quem ainda NÃO entrou troca na própria tela de entrada, por link
(`/entrar?idioma=es`). Ali não há conta, não há coluna e não há o que
proteger: a escolha vale para a sessão anônima e some se ela sumir. Exigir
POST antes do login custaria uma tela a mais para o cliente paraguaio que
abriu o sistema pela primeira vez e não entende o que está escrito.

**Só a MOLDURA muda de idioma.** O catálogo é dado do cliente e continua na
língua em que foi cadastrado — ver `comum/idioma.py`.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect

from comum.guardas_de_acesso import exigir_login

# A regra saiu para `contas/idioma.py`, que o app também chama; os dois nomes
# continuam importáveis daqui para não mudar quem já os usa.
from .idioma import existe, guardar_escolha

__all__ = ["existe", "guardar_escolha", "idioma"]

#: Para onde voltar quando o pedido não disser.
PADRAO_DE_VOLTA = "/"


def _destino(request) -> str:
    """A tela de onde a pessoa veio, se ela for DESTA casa.

    Endereço absoluto vindo de fora é recusado: `?voltar=https://outro.site`
    faria desta rota um trampolim — o link sai do nosso domínio, e quem
    clicou jura que estava dentro do sistema.
    """
    bruto = (request.POST.get("voltar") or "").strip()
    # Barra invertida e caractere de controle também saem: o navegador lê `\`
    # como `/` e descarta tab e quebra de linha, e `/\outro.site` ou
    # `/<tab>/outro.site` viram `//outro.site` na barra de endereço — passavam
    # na trava do `//` (auditoria de 21/09/2026).
    if (bruto.startswith("/") and not bruto.startswith("//")
            and "\\" not in bruto
            and not any(ord(c) < 32 or ord(c) == 127 for c in bruto)):
        return bruto
    return PADRAO_DE_VOLTA


@exigir_login
def idioma(request) -> HttpResponse:
    """Grava o idioma de quem está logado e volta para onde ela estava."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    guardar_escolha(request, request.POST.get("idioma", ""))
    return HttpResponseRedirect(_destino(request))
