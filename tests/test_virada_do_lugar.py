"""A permissão vem do cargo da alocação no lugar em que a pessoa está.

Prova, pelo cliente HTTP, as cinco propriedades do spec ("Como se prova"):
sem alocação não vê nada; lugar forjado cai no primeiro permitido; a mais
específica ganha; tirar a alocação vale na requisição seguinte; titular não
depende de cargo.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.models import Alocacao, Cargo, Nivel, Usuario
from nucleo.permissoes import pode

pytestmark = pytest.mark.django_db


@pytest.fixture
def conta():
    from contas.fabrica import aplicar
    from plataforma.models import Empresa, Filial

    titular = Usuario.objects.create_user(
        email="dono-virada@teste.com", password="x", nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=empresa, nome="Norte", apelido="Norte")
    sul = Filial.objects.create(empresa=empresa, nome="Sul", apelido="Sul")
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    return titular, empresa, norte, sul, cargos


def _entrar(email):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": email, "senha": "x"})
    return cliente


def _membro(titular, login):
    return Usuario.objects.create_user(
        email=f"{login}@teste.com", password="x", nivel=Nivel.MEMBRO, dono=titular)


def _user_da(cliente):
    """O `User` que a próxima requisição veria, montado como as guardas o montam."""
    from django.test import RequestFactory

    from comum.sessao import usuario_da_sessao

    request = RequestFactory().get("/")
    request.session = cliente.session
    return usuario_da_sessao(request)


def test_membro_sem_alocacao_nao_abre_usuarios(conta):
    titular, *_ = conta
    ana = _membro(titular, "ana")
    ana.user_permissions.set([])
    assert _entrar(ana.email).get("/usuarios").status_code == 404


def test_permissao_direta_de_membro_nao_vale_mais(conta):
    from django.contrib.auth.models import Permission

    titular, *_ = conta
    ana = _membro(titular, "ana")
    ana.user_permissions.add(Permission.objects.get(codename="usuarios_editar"))
    assert not pode(_user_da(_entrar(ana.email)), "usuarios.editar")


def test_a_mais_especifica_ganha_pela_filial_da_sessao(conta):
    from plataforma.contexto import CHAVE

    titular, empresa, norte, sul, cargos = conta
    ana = _membro(titular, "ana")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["supervisor"])
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=cargos["vendedor"])
    cliente = _entrar(ana.email)
    sessao = cliente.session
    sessao[CHAVE] = norte.pk
    sessao.save()
    assert not pode(_user_da(cliente), "usuarios.editar")
    sessao[CHAVE] = sul.pk
    sessao.save()
    assert pode(_user_da(cliente), "usuarios.editar")


def test_filial_forjada_cai_na_primeira_permitida(conta):
    from plataforma.contexto import CHAVE, filial_atual

    titular, empresa, norte, sul, cargos = conta
    ana = _membro(titular, "ana")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=cargos["vendedor"])
    cliente = _entrar(ana.email)
    sessao = cliente.session
    sessao[CHAVE] = sul.pk
    sessao.save()
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    request.session = cliente.session
    assert filial_atual(request) == norte


def test_tirar_a_alocacao_vale_na_requisicao_seguinte(conta):
    titular, empresa, norte, _s, cargos = conta
    ana = _membro(titular, "ana")
    alocacao = Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                       cargo=cargos["gerente"])
    cliente = _entrar(ana.email)
    assert cliente.get("/usuarios").status_code == 200
    alocacao.delete()
    assert cliente.get("/usuarios").status_code == 404


def test_titular_nao_depende_de_cargo(conta):
    titular, *_ = conta
    assert pode(_user_da(_entrar(titular.email)), "usuarios.editar")


def test_o_backend_ja_entrega_o_membro_sem_permissao(conta):
    """A segunda tranca, abaixo da sessão: quem chama o backend direto (o
    login, um comando) não recebe a permissão direta de um membro. Sem esta
    linha, a sessão ainda corrigiria — mas só enquanto todo caminho passasse
    por ela."""
    from django.contrib.auth.models import Permission

    from contas.backend import BackendDjango

    titular, *_ = conta
    ana = _membro(titular, "ana")
    ana.user_permissions.add(Permission.objects.get(codename="usuarios_editar"))
    assert BackendDjango().buscar(str(ana.pk)).permissions == frozenset()
    assert "usuarios.editar" in BackendDjango().buscar(str(titular.pk)).permissions
