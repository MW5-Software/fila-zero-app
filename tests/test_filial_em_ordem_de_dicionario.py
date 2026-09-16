"""A filial sai com a Matriz na frente e as outras em ordem de dicionário.

Porte do Portal de Vendas (16/09/2026), onde o cliente viu cadastros "fora de
ordem alfabética" por dois defeitos somados: uma coluna `ordem` que nenhuma
tela preenchia vinha antes do nome, e o `postgres:16-alpine` ordena texto
byte a byte ("Abacaxi | Zinco | bomba | Ágil | água"). A filial perdeu a
`ordem`, e o nome dela usa a colação ICU (`comum.alfabetica`).
"""

from comum.alfabetica import chave
from plataforma.models import Empresa, Filial

NOMES = ["Zinco", "água", "Abacaxi", "bomba", "Ágil"]
DICIONARIO = ["Abacaxi", "Ágil", "água", "bomba", "Zinco"]


def test_a_matriz_vem_na_frente_e_as_outras_em_ordem_de_dicionario(db):
    empresa = Empresa.objects.create(razao_social="Alfa Ltda")
    for nome in NOMES:
        Filial.objects.create(empresa=empresa, nome=nome, apelido=nome)
    assert list(Filial.objects.filter(empresa=empresa)
                .values_list("nome", flat=True)) == ["Matriz", *DICIONARIO]


def test_a_chave_em_python_ordena_como_o_banco():
    """Para lista ordenada em memória: o `sorted` cru põe "Água" depois de
    "Zinco"."""
    assert sorted(NOMES, key=chave) == DICIONARIO


def test_a_filial_nao_tem_mais_ordem():
    assert "ordem" not in {campo.name for campo in Filial._meta.get_fields()}
