"""O módulo Filiais nasce DESLIGADO neste produto.

O arquivo dizia o contrário, e estava certo enquanto este código era o
KRONOS.net: lá a filial é o que se escolhe no cabeçalho, e uma instalação sem
a tela dela sobe manca — a "Matriz" semeada e nenhum jeito de cadastrar a
segunda.

Aqui a empresa é o cadastro de clientes e é ela que se escolhe; filial não
tem papel por enquanto (ver o roadmap). A decisão foi **desligar, não
apagar**: o model, a FK `Filial.empresa` e as telas continuam de pé, e a
Matriz continua sendo semeada — no dia em que filial fizer sentido é uma
chavinha na tela de Módulos, não uma migração para trazer de volta uma tabela
apagada com o dado de quem já usava perdido no caminho.

Estes testes travam as duas metades dessa decisão: nasce desligada, e o que
faz dela algo religável continua existindo.
"""

import pytest
from tests.conftest import matriz_do_teste


@pytest.mark.django_db
def test_o_modulo_filiais_nasce_desligado():
    from plataforma.declaracao import declarados

    spec = next(m for m in declarados() if m.chave == "filiais")
    assert spec.ativo_por_padrao is False


@pytest.mark.django_db
def test_a_semeadura_real_deixou_o_modulo_desligado():
    """A prova de verdade: a linha que o `post_migrate` desta suíte criou
    para o módulo de `plataforma/modulo.py` — não um `ModuloSpec` de teste."""
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="filiais").ativo is False


@pytest.mark.django_db
def test_a_tela_de_filiais_responde_404_com_o_modulo_desligado():
    """Desligado é desligado também na rota, não só no menu: quem decorar o
    endereço bate na mesma porta."""
    from contas.models import Usuario
    from django.test import Client
    from django.urls import reverse

    Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "x"})

    assert c.get(reverse("filiais")).status_code == 404


@pytest.mark.django_db
def test_o_que_faz_dela_religavel_continua_existindo(modulo_filiais_ligado):
    """A outra metade da decisão. Se alguém "limpar" o model, a FK ou a
    semeadura da Matriz achando que filial não é usada, ligar a chavinha um
    dia deixaria de bastar — e aí a volta vira migração.
    """
    from django.urls import reverse
    from contas.models import Usuario
    from django.test import Client

    from plataforma.models import Filial

    matriz = matriz_do_teste()
    assert matriz.empresa is not None, "a Matriz semeada perdeu a empresa"

    Usuario.objects.create_superuser(email="raiz2@teste.com", password="x")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz2@teste.com", "senha": "x"})
    assert c.get(reverse("filiais")).status_code == 200
