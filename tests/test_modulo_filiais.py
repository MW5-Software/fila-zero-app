"""O módulo Filiais nasce LIGADO (17/09/2026).

Ele nasceu ligado no KRONOS.net, foi desligado aqui quando filial não tinha
papel neste produto — a empresa era o que se escolhia no cabeçalho — e voltou
a nascer ligado quando as duas coisas mudaram: a filial virou A LOJA da fila
(spec de 15/09/2026), e a conta passou a ter várias empresas, cada uma com as
lojas dela (spec de 17/09/2026). Sem esta tela, o titular não cadastra a loja
da segunda empresa, e esperar a MW5 ligar a chavinha em cada instalação é um
dia de loja sem fila.

Estes testes travam as duas metades da decisão: nasce ligada, e a tela
continua respondendo 404 quando alguém a desliga de propósito.
"""

import pytest
from tests.conftest import matriz_do_teste


@pytest.mark.django_db
def test_o_modulo_filiais_nasce_ligado():
    from plataforma.declaracao import declarados

    spec = next(m for m in declarados() if m.chave == "filiais")
    assert spec.ativo_por_padrao is True


@pytest.mark.django_db
def test_a_semeadura_real_deixou_o_modulo_ligado():
    """A prova de verdade: a linha que o `post_migrate` desta suíte criou
    para o módulo de `plataforma/modulo.py` — não um `ModuloSpec` de teste."""
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="filiais").ativo is True


@pytest.mark.django_db
def test_a_tela_de_filiais_responde_404_com_o_modulo_desligado():
    """Desligado é desligado também na rota, não só no menu: quem decorar o
    endereço bate na mesma porta. Nasce ligado, então este teste desliga."""
    from contas.models import Usuario
    from django.test import Client
    from django.urls import reverse

    from plataforma.models import Modulo

    Modulo.objects.filter(chave="filiais").update(ativo=False)
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
