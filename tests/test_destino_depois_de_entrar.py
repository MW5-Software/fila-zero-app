"""Para onde a pessoa vai depois de entrar (spec 2026-09-16, V2).

A base não conhece os módulos de negócio e não pode importá-los: ela pergunta
por um sinal. Estes testes ligam um receptor de mentira, porque a regra que se
prova aqui é a da BASE (quem responde decide, resposta estranha é ignorada), e
não a da fila.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.entrada import destino_depois_de_entrar
from contas.models import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        email="ana@teste.com", password="segredo-de-teste", nome="Ana")


@pytest.fixture
def responder():
    """Liga um receptor que responde `destino`, e desliga no fim: um receptor
    esquecido ligado mandaria todo login da suíte para outro lugar."""
    ligados = []

    def ligar(destino):
        def receptor(sender, request, **kwargs):
            return destino
        uid = f"teste-destino-{len(ligados)}"
        destino_depois_de_entrar.connect(receptor, dispatch_uid=uid, weak=False)
        ligados.append(uid)

    yield ligar
    for uid in ligados:
        destino_depois_de_entrar.disconnect(dispatch_uid=uid)


def _entrar():
    return Client().post(reverse("entrar"), {
        "usuario": "ana@teste.com", "senha": "segredo-de-teste"})


def test_sem_resposta_vai_para_a_raiz(ana):
    assert _entrar()["Location"] == "/"


def test_o_caminho_respondido_decide(ana, responder):
    responder("/fila")
    assert _entrar()["Location"] == "/fila"


@pytest.mark.parametrize("fora", [
    "https://fora.example/", "//fora.example/", "/\\fora.example",
    "fila", "", 42])
def test_resposta_que_nao_e_caminho_interno_e_ignorada(ana, responder, fora):
    """O sinal nunca pode virar redirecionamento aberto."""
    responder(fora)
    assert _entrar()["Location"] == "/"


def test_o_receptor_ve_a_pessoa_ja_dentro_da_sessao(ana):
    """O negócio decide pelas permissões de quem entrou: quando o sinal sai,
    a sessão já tem a pessoa."""
    from comum.sessao import identidade_da_sessao

    vistos = []

    def receptor(sender, request, **kwargs):
        vistos.append(identidade_da_sessao(request))
    destino_depois_de_entrar.connect(receptor, dispatch_uid="teste-ve", weak=False)
    try:
        _entrar()
    finally:
        destino_depois_de_entrar.disconnect(dispatch_uid="teste-ve")
    assert [str(p.id) for p in vistos] == [str(ana.pk)]


def test_senha_errada_nao_pergunta_nada(ana, responder):
    responder("/fila")
    resposta = Client().post(reverse("entrar"), {
        "usuario": "ana@teste.com", "senha": "errada"})
    assert resposta.status_code == 200
