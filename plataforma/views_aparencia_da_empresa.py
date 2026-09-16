"""O menu de uma empresa — logo, fundo e texto —, configurado pela MW5.

Mora na tela de Empresas, num modal por linha, e não na Aparência: a
Aparência é a cara da INSTALAÇÃO, e isto é o que UM cliente tem por cima dela
(15/09/2026). Mesma permissão (`mw5.aparencia`) porque é a mesma decisão: a
cara de um cliente é assunto da MW5, e o titular não mexe.

Cores e logo são dois formulários, pelo motivo de `views_marca.cartao_de_logos`:
o `<input type="file">` volta sempre vazio depois do POST, e um formulário
único obrigaria a reescolher o arquivo para trocar uma cor.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import (
    HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.guardas_de_acesso import exigir_permissao

from .marca import conferir_legibilidade, marca_da_instalacao
from .models import AparenciaDaEmpresa, Empresa

__all__ = ["menu_da_empresa"]


def _conferir_contraste(aparencia: AparenciaDaEmpresa) -> None:
    """A mesma conferência da Aparência, com o que VAI valer: o campo em branco
    herda da instalação, então o par a conferir é o efetivo."""
    instalacao = marca_da_instalacao().tokens("light")
    aviso = conferir_legibilidade(
        aparencia.sidebar_bg or instalacao["sidebar-bg"],
        aparencia.sidebar_text or instalacao["sidebar-text"])
    if aviso:
        raise ValidationError(aviso)


@exigir_permissao("mw5.aparencia")
def menu_da_empresa(request, pk: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    empresa = Empresa.objects.filter(pk=pk).first()
    if empresa is None:
        return HttpResponseNotFound()

    acao = request.POST.get("acao", "")
    if acao not in ("cores", "logo", "remover_logo"):
        return HttpResponseNotFound()

    try:
        # A linha nasce DENTRO da transação: uma cor recusada não deixa uma
        # aparência vazia para trás.
        with transaction.atomic():
            aparencia, _criada = AparenciaDaEmpresa.objects.get_or_create(
                empresa=empresa)
            if acao == "cores":
                aparencia.sidebar_bg = request.POST.get("sidebar_bg", "").strip()
                aparencia.sidebar_text = request.POST.get("sidebar_text", "").strip()
                aparencia.clean()
                _conferir_contraste(aparencia)
            elif acao == "logo":
                arquivo = request.FILES.get("arquivo")
                if arquivo is None:
                    raise ValidationError(_("Escolha um arquivo antes de enviar."))
                aparencia.logo = arquivo.read()
            else:
                aparencia.logo = None
            aparencia.save()
            registrar(ACOES.MENU_DA_EMPRESA_ALTERADO, request.usuario,
                      alvo=str(empresa), request=request)
    except ValidationError as erro:
        from .views_empresa import desenhar_com_erro

        return desenhar_com_erro(request, "; ".join(erro.messages))
    return HttpResponseRedirect(reverse("empresa"))
