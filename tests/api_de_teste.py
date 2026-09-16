"""Uma API de mentira, montada com as regras da de verdade (`criar_api`).

Existe para provar o que só se prova com uma rota que dá errado de propósito —
e rota assim não pode existir na API de verdade. Vai em `/api/teste/`, dentro
do prefixo, para passar pelo mesmo middleware de sessão; o resto das rotas é o
`config.urls` inteiro, para o login funcionar no mesmo teste.

Não é `test_*.py`: é um urlconf, usado com `@pytest.mark.urls("tests.api_de_teste")`.
"""

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.urls import include, path
from ninja import Router, Schema

from comum.guardas_da_api import api_exigir_login
from config.api import criar_api

router = Router()


class Quantidade(Schema):
    quantidade: int


@router.get("/explode")
def explode(request):
    raise RuntimeError("explodiu de propósito")


@router.get("/invalido")
def invalido(request):
    raise ValidationError({"quantidade": ["Deve ser maior que zero."]})


@router.get("/some")
def some(request):
    raise Http404("segredo do caminho")


@router.post("/corpo")
def corpo(request, dados: Quantidade):
    return {"quantidade": dados.quantidade}


@router.get("/guardada")
@api_exigir_login
def guardada(request):
    return HttpResponse(status=204)


api = criar_api(urls_namespace="api-de-teste", routers=[("", router)])

urlpatterns = [
    path("api/teste/", api.urls),
    path("", include("config.urls")),
]
