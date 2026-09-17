"""O que os ajudantes da suíte prometem. Um ajudante que descarta metade do
cenário em silêncio faz todo teste que depende dele passar sem provar nada —
foi o que `dar_acesso` fazia com a segunda empresa até 17/09/2026."""

import pytest

from tests.conftest import dar_acesso, empresa_do_teste

pytestmark = pytest.mark.django_db


def test_dar_acesso_aloca_em_todas_as_empresas_pedidas():
    from contas.models import Nivel, Usuario
    from plataforma.models import Empresa

    alfa = empresa_do_teste()
    titular = Usuario.objects.filter(pk=alfa.dono_id).first()
    if titular is None:
        from tests.conftest import abrir_conta

        titular = abrir_conta(alfa, "dona-ajuda")
        alfa.refresh_from_db()
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    pessoa = Usuario.objects.create_user(email="dois-lugares@teste.com",
                                         password="x", nivel=Nivel.MEMBRO,
                                         dono=titular)
    dar_acesso(pessoa, empresas=[alfa, beta], nivel=Nivel.MEMBRO)
    assert set(pessoa.alocacoes.values_list("empresa_id", flat=True)) == {alfa.pk, beta.pk}
