"""A tela onde a MW5 liga o que o cliente comprou."""

import pytest
from django.contrib.auth.models import Group
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

from plataforma.declaracao import ModuloSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


@pytest.fixture
def cliente_mw5(db, catalogo_limpo):
    from plataforma.catalogo import semear

    registrar(ModuloSpec(chave="financeiro", rotulo="Financeiro", icone="truck",
                         grupo="Consultas", rota="/financeiro",
                         permissoes=("financeiro.ver",)))
    semear()
    u = Usuario.objects.create_superuser(
        email="raiz@teste.com", password="segredo-de-teste")
    c = Client()
    # A chave lida por `entrar` é `usuario`, não `login` — é esse o `name`
    # que `LoginPage.campos_da_marca()` realmente emite (ver `contas/views.py`).
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
    return c


class TestQuemEntra:
    def test_a_mw5_abre(self, cliente_mw5):
        assert cliente_mw5.get(reverse("modulos")).status_code == 200

    def test_o_admin_do_cliente_nao_ve(self, db, catalogo_limpo):
        Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert c.get(reverse("modulos")).status_code == 404

    def test_grupo_chamado_mw5_nao_da_acesso(self, db, catalogo_limpo):
        """A porta que esta regra fecha: quando a gestão de usuários existir,
        o admin do cliente vai poder criar grupos. Se o acesso da MW5 viesse
        do nome do grupo, ele cunharia a própria promoção."""
        u = Usuario.objects.create_user(
            email="esperto@teste.com", password="segredo-de-teste")
        u.groups.add(Group.objects.create(name="mw5"))
        c = Client()
        c.post(reverse("entrar"),
               {"usuario": "esperto@teste.com", "senha": "segredo-de-teste"})
        assert c.get(reverse("modulos")).status_code == 404


class TestLigarEDesligar:
    def test_a_tela_lista_os_modulos_declarados(self, cliente_mw5):
        assert "Financeiro" in cliente_mw5.get(reverse("modulos")).content.decode()

    def test_ligar_grava(self, cliente_mw5):
        from plataforma.models import Modulo

        cliente_mw5.post(reverse("modulos"), {"ligados": ["financeiro"]})
        assert Modulo.objects.get(chave="financeiro").ativo is True

    def test_desligar_grava(self, cliente_mw5):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="financeiro").update(ativo=True)
        cliente_mw5.post(reverse("modulos"), {"ligados": []})
        assert Modulo.objects.get(chave="financeiro").ativo is False

    def test_desligar_nao_apaga_a_linha(self, cliente_mw5):
        from plataforma.models import Modulo

        cliente_mw5.post(reverse("modulos"), {"ligados": []})
        assert Modulo.objects.filter(chave="financeiro").exists()

    def test_ligar_modulo_sem_linha_ainda_no_banco_nao_e_noop(
            self, cliente_mw5, catalogo_limpo):
        """Módulo declarado depois da semeadura (fora de ordem com o
        `post_migrate` — R18) ainda não tem linha quando a MW5 tenta ligá-lo.
        Sem `semear()` no início do POST, `filter().update()` atualiza zero
        linhas em silêncio, e a caixa volta desmarcada sem explicação
        nenhuma."""
        from plataforma.models import Modulo

        registrar(ModuloSpec(chave="tardio", rotulo="Tardio"))
        assert not Modulo.objects.filter(chave="tardio").exists()

        cliente_mw5.post(reverse("modulos"), {"ligados": ["tardio"]})

        assert Modulo.objects.get(chave="tardio").ativo is True


class TestNavDasTelasMw5:
    """As duas telas da MW5 montavam `Site(...)` sem `nav`: a barra lateral
    saía vazia, e a única forma de sair era o logo."""

    def test_a_tela_de_modulos_mostra_o_menu(self, cliente_mw5):
        """"Financeiro" já aparece na tela como rótulo do checkbox — a marca
        que só o menu emite é o link para a rota do módulo."""
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="financeiro").update(ativo=True)
        html = cliente_mw5.get(reverse("modulos")).content.decode()
        assert 'href="/financeiro"' in html

    def test_a_tela_de_aparencia_mostra_o_menu(self, cliente_mw5):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="financeiro").update(ativo=True)
        assert "Financeiro" in cliente_mw5.get(reverse("aparencia")).content.decode()


@pytest.mark.django_db
def test_ligar_faz_o_modulo_aparecer_no_menu(cliente_mw5):
    """A promessa da entrega, do outro lado: ligar aqui muda a tela de lá."""
    antes = cliente_mw5.get("/").content.decode()
    assert "Financeiro" not in antes

    cliente_mw5.post(reverse("modulos"), {"ligados": ["financeiro"]})
    depois = cliente_mw5.get("/").content.decode()
    assert "Financeiro" in depois


@pytest.fixture
def mw5_com_as_telas_da_casa(db, catalogo_limpo):
    """Como `cliente_mw5`, mas com as telas da MW5 declaradas de verdade.

    Sem isto o teste não enxerga o defeito que ele existe para pegar:
    `catalogo_limpo` esvazia as declarações, e aí `declarados()` e
    `_opcionais()` devolvem o MESMO conjunto — trocar um pelo outro no código
    passaria despercebido. Os specs vêm de `plataforma/modulo.py`, e não de
    cópias escritas aqui: um teste que redeclarasse "Aparência" continuaria
    verde depois de alguém apagar o spec de verdade.
    """
    from plataforma.catalogo import semear
    from plataforma.modulo import (
        MODULO_APARENCIA, MODULO_FALHAS, MODULO_MODULOS,
    )

    registrar(MODULO_APARENCIA)
    registrar(MODULO_MODULOS)
    registrar(MODULO_FALHAS)
    registrar(ModuloSpec(chave="financeiro", rotulo="Financeiro", icone="truck",
                         grupo="Consultas", rota="/financeiro",
                         permissoes=("financeiro.ver",)))
    semear()
    Usuario.objects.create_superuser(
        email="raiz@teste.com", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
    return c


@pytest.mark.django_db
class TestAsTelasDaMw5FicamDeFora:
    """A tela de Módulos grava por AUSÊNCIA: o que não voltar marcado no POST
    é desligado.

    Quando as telas da MW5 viraram módulos declarados, isso abriu um alçapão:
    elas entram em `declarados()`, mas não são coisa que o cliente compra e
    não podem aparecer aqui. Se aparecessem, alguém desmarcaria a própria
    tela de Módulos e perderia o meio de religar qualquer coisa; se NÃO
    aparecessem mas continuassem no conjunto que o POST varre, o primeiro
    salvar as desligaria sem ninguém tocar em nada — e a Aparência sumiria
    do menu de todas as instalações no primeiro clique de "Salvar".

    A defesa é uma lista só (`views._opcionais`) servindo ao desenho e à
    gravação: as duas pontas não têm como divergir.
    """

    def test_a_tela_nao_oferece_as_tres(self, mw5_com_as_telas_da_casa):
        html = mw5_com_as_telas_da_casa.get(reverse("modulos")).content.decode()
        for chave in ("aparencia", "modulos", "falhas"):
            assert f'value="{chave}"' not in html, chave

    def test_salvar_sem_marcar_nada_nao_desliga_as_tres(self, mw5_com_as_telas_da_casa, db):
        """O caminho que quebraria: a MW5 abre a tela, desmarca tudo o que é
        de negócio, salva — e as telas da casa continuam de pé."""
        from plataforma.models import Modulo

        resposta = mw5_com_as_telas_da_casa.post(reverse("modulos"), {"ligados": []})
        assert resposta.status_code == 302

        ativos = dict(Modulo.objects.values_list("chave", "ativo"))
        for chave in ("aparencia", "modulos", "falhas"):
            assert ativos[chave] is True, chave

    # O terceiro teste natural aqui — "e o menu continua mostrando as três" —
    # não cabe: `cliente_mw5` usa `catalogo_limpo`, e sem declaração no
    # código o menu ignora a linha do banco de propósito (ver
    # `catalogo.modulos_ligados`). Quem cobre isso é
    # `test_menu.py::TestABaseEUmGrupoSo`, que monta o catálogo com os specs
    # de verdade.
