"""`Empresa` e `Filial`: a forma da tabela, e o `__str__` que a tela usa.

A regra de acesso (alocação, superusuário sem linha) e a regra de sessão ficam em
`tests/test_contexto_filial.py` — aqui é só o model, isolado do resto.
"""

import pytest
from contas.models import Usuario

pytestmark = pytest.mark.django_db


class TestEmpresa:
    def test_str_prefere_o_nome_fantasia(self):
        from plataforma.models import Empresa

        empresa = Empresa(razao_social="Transportes Aurora Ltda", nome_fantasia="Aurora")
        assert str(empresa) == "Aurora"

    def test_str_cai_para_a_razao_social_sem_nome_fantasia(self):
        from plataforma.models import Empresa

        empresa = Empresa(razao_social="Transportes Aurora Ltda")
        assert str(empresa) == "Transportes Aurora Ltda"

    def test_cnpj_invalido_e_recusado(self):
        """O item do roadmap chegou (Bloco 5): o dígito verificador é
        verificado no model — a tela nunca é a única porta."""
        from django.core.exceptions import ValidationError

        from plataforma.models import Empresa

        with pytest.raises(ValidationError):
            Empresa.objects.create(razao_social="X", cnpj="qualquer coisa")


class TestFilial:
    def test_str_prefere_o_apelido(self):
        from plataforma.models import Filial

        filial = Filial(nome="Filial Zona Norte — Depósito 2", apelido="Zona Norte")
        assert str(filial) == "Zona Norte"

    def test_str_cai_para_o_nome_sem_apelido(self):
        from plataforma.models import Filial

        filial = Filial(nome="Matriz")
        assert str(filial) == "Matriz"

    def test_nasce_ativa(self):
        from plataforma.models import Filial

        from plataforma.models import Empresa

        empresa = Empresa.objects.create(razao_social="Alfa Ltda")
        filial = Filial.objects.create(empresa=empresa, nome="Loja 2", apelido="Loja 2")
        assert filial.ativa is True

    def test_ordering_e_a_matriz_na_frente_e_depois_o_nome(self):
        from plataforma.models import Empresa, Filial

        empresa = Empresa.objects.create(razao_social="Alfa Ltda")
        Filial.objects.create(empresa=empresa, nome="B", apelido="B")
        Filial.objects.create(empresa=empresa, nome="A", apelido="A")

        assert list(empresa.filiais.values_list("nome", flat=True)) == [
            "Matriz", "A", "B"]
