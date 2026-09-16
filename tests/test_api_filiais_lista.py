"""A lista de filiais pela API: a R46 com o mesmo vocabulário da tela."""

import pytest

from contas.fabrica import aplicar
from contas.models import Nivel, Usuario
from plataforma.models import Empresa, Filial, Modulo
from tests.conftest import abrir_conta, alocar, cargo_com, cliente_da_api, email_de

pytestmark = pytest.mark.django_db

SENHA = "segredo-de-teste"


@pytest.fixture
def cenario(modulo_filiais_ligado):
    alfa = Empresa.objects.create(razao_social="Alfa")
    # `abrir_conta` só cria o titular e liga a empresa; as permissões de
    # fábrica (entre elas `filiais.editar`) vêm de `aplicar`, como na tela de
    # Usuários.
    aplicar(abrir_conta(alfa, "tita", SENHA), Nivel.TITULAR)
    Filial.objects.create(empresa=alfa, nome="Norte", apelido="Norte")
    Filial.objects.create(empresa=alfa, nome="Sul", apelido="Sul", ativa=False)
    beta = Empresa.objects.create(razao_social="Beta")
    abrir_conta(beta, "bete", SENHA)
    Filial.objects.create(empresa=beta, nome="Loja Beta", apelido="Loja Beta")
    api, token = cliente_da_api(email_de("tita"), SENHA)
    return {"api": api, "alfa": alfa, "beta": beta}


def _lista(api, **parametros):
    resposta = api.get("/api/v1/filiais", parametros)
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


def test_o_titular_ve_so_as_da_propria_empresa(cenario):
    corpo = _lista(cenario["api"])
    esperadas = {str(f.guid) for f in Filial.objects.filter(empresa=cenario["alfa"])}
    assert {item["guid"] for item in corpo["itens"]} == esperadas
    assert corpo["total"] == len(esperadas)


def test_filtro_de_texto_com_o_vocabulario_da_tela(cenario):
    corpo = _lista(cenario["api"], **{"f:filial:contem": "nor"})
    assert [item["apelido"] for item in corpo["itens"]] == ["Norte"]


def test_filtro_de_opcoes(cenario):
    corpo = _lista(cenario["api"], **{"f:situacao:igual": "0"})
    assert [item["apelido"] for item in corpo["itens"]] == ["Sul"]


def test_ordenacao(cenario):
    corpo = _lista(cenario["api"], ordenar="-filial")
    apelidos = [item["apelido"] for item in corpo["itens"]]
    assert apelidos == sorted(apelidos, reverse=True)
    assert corpo["ordenar"] == "-filial"


def test_a_paginacao_segue_o_parametro_da_instalacao(cenario):
    from plataforma.models import Parametro

    Parametro.objects.update_or_create(chave="itens_por_pagina", defaults={"valor": "2"})
    primeira = _lista(cenario["api"])
    assert primeira["por_pagina"] == 2
    assert len(primeira["itens"]) == 2
    assert primeira["total"] == 3
    segunda = _lista(cenario["api"], pagina="2")
    assert segunda["pagina"] == 2
    assert len(segunda["itens"]) == 1


def test_as_colunas_descrevem_o_que_a_tela_declara(cenario):
    from plataforma.filiais import FILTRAVEIS, ORDENAVEIS

    colunas = {c["chave"]: c for c in _lista(cenario["api"])["colunas"]}
    assert set(colunas) == set(ORDENAVEIS) | set(FILTRAVEIS)
    assert colunas["filial"]["operadores"] == ["contem"]
    assert colunas["filial"]["ordenavel"] is True
    assert colunas["situacao"]["opcoes"] == [
        {"valor": "1", "rotulo": "Ativa"}, {"valor": "0", "rotulo": "Inativa"}]
    assert colunas["cnpj"]["operadores"] == []


def test_sem_permissao_e_modulo_desligado_tem_o_mesmo_404(cenario):
    ana = Usuario.objects.create_user(email=email_de("ana"), password=SENHA)
    alocar(ana, cenario["alfa"], cargo_com(cenario["alfa"], "usuarios.editar", nome="sem-filiais"))
    sem_permissao = cliente_da_api(email_de("ana"), SENHA)[0].get("/api/v1/filiais")

    Modulo.objects.filter(chave="filiais").update(ativo=False)
    desligado = cenario["api"].get("/api/v1/filiais")

    assert sem_permissao.status_code == desligado.status_code == 404
    assert sem_permissao.content == desligado.content
