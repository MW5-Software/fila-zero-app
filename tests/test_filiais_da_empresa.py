"""O titular cadastra as filiais da empresa DELE — e só as dela.

Até 14/09/2026 a tela de Filiais era só da MW5, e por um motivo sério: ela
listava `Filial.objects.all()`, as filiais da INSTALAÇÃO inteira. Dar
`filiais.editar` a um titular com a tela assim seria entregar a ele as filiais
de todos os outros clientes. Por isso as duas coisas mudam juntas: a tela passa a
enxergar só a empresa do contexto, e só então o titular ganha a permissão.

Toda consulta e toda ação da tela é testada com DUAS empresas de contas
diferentes: com uma só, uma tela que ignorasse a empresa passaria em tudo.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.fabrica import aplicar
from contas.models import Nivel, Usuario

SENHA = "segredo-de-teste"


def _titular_com_empresa(login, razao):
    """Um titular de verdade: nível TITULAR com as permissões de fábrica dele
    (`contas.fabrica.aplicar`) e a empresa da conta. É como a tela de usuários
    cria um titular — e é isso que prova que a fábrica dá `filiais.editar`."""
    from plataforma.models import Empresa

    titular = Usuario.objects.create_user(
        email=f"{login}@teste.com", password=SENHA, nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social=razao, dono=titular)
    return titular, empresa


def _entrar(login):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": f"{login}@teste.com",
                                     "senha": SENHA})
    return cliente


@pytest.fixture
def cenario(db, modulo_filiais_ligado):
    from plataforma.models import Filial

    _, alfa = _titular_com_empresa("dono-alfa", "Alfa Ltda")
    _, beta = _titular_com_empresa("dono-beta", "Beta Ltda")
    loja_beta = Filial.objects.create(empresa=beta, nome="Loja da Beta",
                                      apelido="SoDaBeta")
    return {"alfa": alfa, "beta": beta, "loja_beta": loja_beta,
            "cliente": _entrar("dono-alfa")}


class TestOTitularEntra:
    def test_a_fabrica_do_titular_da_filiais_editar(self):
        from contas.fabrica import DE_FABRICA

        assert "filiais.editar" in DE_FABRICA[Nivel.TITULAR]

    def test_o_titular_abre_a_tela(self, cenario):
        assert cenario["cliente"].get(reverse("filiais")).status_code == 200


class TestSoAEmpresaDele:
    def test_a_lista_mostra_so_as_filiais_da_empresa_dele(self, cenario):
        html = cenario["cliente"].get(reverse("filiais")).content.decode()
        assert "Matriz" in html
        assert "SoDaBeta" not in html

    def test_a_exportacao_so_leva_as_filiais_da_empresa_dele(self, cenario):
        resposta = cenario["cliente"].get(reverse("filiais"),
                                          {"formato": "impressao"})
        # O 200 e a Matriz presentes são o que impede este teste de passar
        # vazio: sem eles, uma resposta 404 também não conteria "SoDaBeta".
        assert resposta.status_code == 200
        html = resposta.content.decode("utf-8", "replace")
        assert "Matriz" in html
        assert "SoDaBeta" not in html

    def test_a_filial_criada_nasce_na_empresa_dele(self, cenario):
        from plataforma.models import Filial

        cenario["cliente"].post(reverse("filiais"), {
            "acao": "criar", "nome": "Loja Centro", "apelido": "Centro"})
        assert Filial.objects.get(apelido="Centro").empresa == cenario["alfa"]

    @pytest.mark.parametrize("acao", ["salvar", "desativar", "remover"])
    def test_filial_de_outra_empresa_pedida_pelo_id_nao_e_tocada(self, cenario,
                                                                 acao):
        """O id vem do POST. Sem o filtro pela empresa, ele alcança a filial de
        qualquer cliente da instalação."""
        from plataforma.models import Filial

        alvo = cenario["loja_beta"]
        resposta = cenario["cliente"].post(reverse("filiais"), {
            "acao": acao, "filial": str(alvo.pk),
            "nome": "Invadida", "apelido": "Invadida"})

        assert "Filial não encontrada" in resposta.content.decode()
        alvo = Filial.objects.get(pk=alvo.pk)
        assert alvo.apelido == "SoDaBeta"
        assert alvo.ativa is True


class TestAMatriz:
    def test_a_matriz_nao_se_remove(self, cenario):
        from plataforma.models import Filial

        matriz = cenario["alfa"].filiais.get(e_matriz=True)
        Filial.objects.create(empresa=cenario["alfa"], nome="Loja 2",
                              apelido="Loja 2")
        resposta = cenario["cliente"].post(reverse("filiais"), {
            "acao": "remover", "filial": str(matriz.pk)})

        assert Filial.objects.filter(pk=matriz.pk).exists()
        assert "A Matriz não pode ser removida" in resposta.content.decode()

    def test_a_matriz_se_renomeia(self, cenario):
        matriz = cenario["alfa"].filiais.get(e_matriz=True)
        cenario["cliente"].post(reverse("filiais"), {
            "acao": "salvar", "filial": str(matriz.pk),
            "nome": "Loja Centro", "apelido": "Centro"})
        matriz.refresh_from_db()
        assert matriz.apelido == "Centro"
        assert matriz.e_matriz is True


class TestAUltimaAtivaEDaEmpresa:
    def test_filiais_ativas_de_outra_empresa_nao_liberam_desativar(self, cenario):
        """Contada pela instalação, a Beta com duas filiais ativas deixaria a
        Alfa desativar a única que tem — e ficar sem filial nenhuma."""
        from plataforma.filiais import pode_desativar

        matriz = cenario["alfa"].filiais.get(e_matriz=True)
        assert "última filial ativa" in (pode_desativar(matriz) or "")


class TestRemoverNaoDa500:
    def test_a_recusa_generica_enxerga_qualquer_protect(self, cenario):
        """A base não conhece os módulos de negócio de cada SaaS, e mesmo assim
        não pode deixar um `PROTECT` deles virar 500 (no Portal de Vendas, o
        orçamento aponta para a filial). `_protegida` pergunta ao Django o que
        um `delete()` recusaria — provado aqui com a alocação, que é a tabela
        da base que protege a filial."""
        from contas.models import Alocacao, Cargo
        from plataforma.filiais import _protegida
        from plataforma.models import Filial

        alfa = cenario["alfa"]
        loja = Filial.objects.create(empresa=alfa, nome="Loja 3",
                                     apelido="Loja 3")
        assert _protegida(loja) is False

        membro = Usuario.objects.create_user(
            email="membro-prot@teste.com", password=SENHA,
            nivel=Nivel.MEMBRO, dono=alfa.dono)
        Alocacao.objects.create(pessoa=membro, empresa=alfa, filial=loja,
                                cargo=Cargo.objects.get(conta_id=alfa.conta_id,
                                                        nome="vendedor"))
        assert _protegida(loja) is True

    def test_filial_com_alocacao_nao_se_remove(self, cenario):
        from contas.models import Alocacao, Cargo
        from plataforma.models import Filial

        alfa = cenario["alfa"]
        loja = Filial.objects.create(empresa=alfa, nome="Loja 2",
                                     apelido="Loja 2")
        membro = Usuario.objects.create_user(
            email="membro-fil@teste.com", password=SENHA,
            nivel=Nivel.MEMBRO, dono=alfa.dono)
        Alocacao.objects.create(pessoa=membro, empresa=alfa, filial=loja,
                                cargo=Cargo.objects.get(conta=alfa.dono,
                                                        nome="vendedor"))

        resposta = cenario["cliente"].post(reverse("filiais"), {
            "acao": "remover", "filial": str(loja.pk)})

        assert resposta.status_code == 200
        assert Filial.objects.filter(pk=loja.pk).exists()
        assert "alocad" in resposta.content.decode()

