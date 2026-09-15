"""A montagem de cenário dos testes da fila. Não é arquivo de teste.

Mora num arquivo só porque todo teste da fila precisa da mesma loja com a
mesma gente, e oito cópias da montagem divergiriam no primeiro ajuste.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as tz
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from tests.conftest import (
    abrir_conta, alocar, email_de, empresa_do_teste, matriz_do_teste)

SENHA = "segredo-de-teste"


def sylvia():
    """A empresa do teste com a Sylvia titular, a Matriz e as permissões
    diretas do nível (a tela de Usuários aplica ao gravar; o teste, à mão)."""
    from contas.fabrica import aplicar
    from contas.models import Nivel, Usuario

    empresa = empresa_do_teste()
    if empresa.dono_id is None:
        titular = abrir_conta(empresa, "sylvia", SENHA)
        aplicar(titular, Nivel.TITULAR)
        empresa.refresh_from_db()
    titular = Usuario.objects.get(pk=empresa.dono_id)
    return empresa, matriz_do_teste(), titular


def nova_loja(empresa, apelido):
    from plataforma.models import Filial

    return Filial.objects.create(empresa=empresa, nome=f"Loja {apelido}",
                                 apelido=apelido)


def pessoa_na_loja(login, empresa, filial, cargo="vendedor"):
    """Uma pessoa da conta, alocada NA LOJA com um cargo de fábrica."""
    from contas.models import Usuario

    pessoa = Usuario.objects.create_user(
        email=email_de(login), password=SENHA, nome=login.title(),
        dono_id=empresa.dono_id)
    alocar(pessoa, empresa, cargo, filial=filial)
    return pessoa


def cadastros(empresa):
    from fila.models import GrupoDeItem, MotivoDeNaoVenda, TipoDePausa

    return SimpleNamespace(
        grupo=GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás"),
        grupo2=GrupoDeItem.irrestritos.create(empresa=empresa, nome="Tapetes"),
        motivo=MotivoDeNaoVenda.irrestritos.create(empresa=empresa,
                                                   nome="Só olhando"),
        tipo=TipoDePausa.irrestritos.create(empresa=empresa, nome="Almoço"),
    )


def logado(login):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": email_de(login),
                                     "senha": SENHA})
    return cliente


@pytest.fixture
def relogio(monkeypatch):
    """Um relógio que anda um minuto a cada leitura.

    A ordem da fila é a hora em que se entrou nela. Com o relógio de verdade,
    duas ações seguidas num teste podem cair no mesmo microssegundo e a ordem
    vira sorteio; com este, cada ação acontece depois da anterior, sempre.
    """
    atual = [datetime(2026, 9, 15, 13, 0, tzinfo=tz.utc)]

    def agora():
        atual[0] += timedelta(minutes=1)
        return atual[0]

    import fila.acoes

    monkeypatch.setattr(fila.acoes, "_agora", agora)
    return atual
