"""A regra do condomínio: toda tabela de dado de NEGÓCIO carrega a empresa.

Varredura irmã de `test_guarda.py` (nenhuma tela nasce sem guarda),
`test_regra_tabela.py` (R46) e `test_sem_nome_de_cliente.py`. Todas existem
pelo mesmo motivo: a regra que depende de alguém lembrar é a regra que um dia
alguém esquece — e aqui o esquecimento não dá erro, dá vazamento.

Este portal atende várias empresas na MESMA instalação. Um model de negócio
sem a coluna do inquilino não tem como ser filtrado, e a primeira tela que o
listar mostra o dado de todos para todos. É por isso que a varredura roda
ANTES de existir a primeira tabela de negócio: depois dela, cada model novo é
mais uma chance de esquecer, e a varredura vira dívida em vez de trava.

**Como passar:** herde `contas.inquilino.ModeloDaEmpresa`. Ele traz a coluna,
o manager que falha vazio e esta varredura de uma vez.
"""

import pytest
from django.apps import apps

from contas.inquilino import ModeloDaEmpresa
from tests.app_do_inquilino.models import ProdutoDeTeste
from tests.conftest import por_na_conta


@pytest.fixture
def produto_de_teste(db):
    """Duas linhas em duas empresas.

    Duas de propósito: com uma só, um manager que devolvesse tudo passaria em
    todos os testes.
    """
    from contas.models import Nivel, Usuario
    from plataforma.models import Empresa

    dono_alfa = Usuario.objects.create_user(
        email="dono-alfa@teste.com", password="x", nivel=Nivel.TITULAR)
    dono_beta = Usuario.objects.create_user(
        email="dono-beta@teste.com", password="x", nivel=Nivel.TITULAR)
    alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=dono_alfa)
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=dono_beta)
    ProdutoDeTeste.irrestritos.create(nome="da alfa", empresa=alfa)
    ProdutoDeTeste.irrestritos.create(nome="da beta", empresa=beta)
    return ProdutoDeTeste, alfa, beta

#: Os apps que NÃO são de negócio — a plataforma.
#:
#: Lista de EXCEÇÃO, e não lista de inclusão, e a diferença já se provou
#: importante: a primeira versão desta varredura listava os apps de negócio
#: ("modulos",), e o app `catalogo` do Portal de Vendas nasceu FORA dela. A varredura teria
#: ficado verde sem olhar para a primeira tabela de negócio de verdade — o
#: pior estado possível para uma trava, parecendo que protege.
#:
#: **Isto cobra o MANAGER do inquilino, não a coluna da conta.** Isentar as
#: apps inteiras deixou Filial e AparenciaDaEmpresa sem `conta_guid` até
#: 16/09/2026; a coluna é cobrada tabela a tabela em
#: `test_toda_linha_da_conta_leva_o_guid.py`, que não isenta app nenhuma.
#:
#: Invertida, um app novo já nasce coberto, e ficar de fora exige escrever o
#: nome aqui com o motivo. `contas`, `plataforma` e `nucleo` estão fora
#: porque usuário, perfil, marca, módulo, parâmetro e a própria empresa são
#: globais desta instalação de propósito — `plataforma.Empresa` com uma FK
#: para si mesma seria absurdo.
APPS_DA_PLATAFORMA = {
    "admin": "do Django",
    "auth": "do Django",
    # O vínculo pessoa × empresa mora aqui desde que o usuário passou a ser
    # nosso — e é ele que DEFINE o inquilino, então não pode carregar um.
    "contas": "gente, perfil, vínculo e trilha — globais da instalação",
    "contenttypes": "do Django",
    "nucleo": "o design system, sem model de dado",
    "plataforma": "empresa, marca, módulo e parâmetro — a instalação em si",
    "sessions": "do Django",
}

#: Model de negócio que pode viver sem a coluna, e o motivo de cada um.
#: Lista curta e explícita, para que qualquer nome que entre aqui doa um
#: pouco — mesmo espírito de `SEM_GUARDA_DE_MODULO` e `TELAS_ABERTAS`.
SEM_EMPRESA = {}


def _models_de_negocio():
    for model in apps.get_models():
        if model._meta.app_label not in APPS_DA_PLATAFORMA:
            yield model


class TestTodoModelDeNegocioCarregaAEmpresa:
    def test_a_varredura_enxerga_algum_model(self):
        """A varredura precisa OLHAR para alguma coisa.

        Uma lista vazia fica verde para sempre — o pior estado possível para
        uma trava: parecendo que protege. Foi o que aconteceu quando ela
        listava os apps de NEGÓCIO e o `catalogo` nasceu fora da lista.
        """
        assert list(_models_de_negocio()), "a varredura não achou model nenhum"

    def test_o_app_de_teste_esta_coberto(self):
        """A base não tem módulo de negócio com tabela — cada SaaS traz os
        dele —, então quem garante que a varredura olha para ALGO é o app de
        mentira `tests/app_do_inquilino`. Ele fica DE FORA da lista de
        exceção de propósito: se alguém o isentar para "fazer passar", a
        varredura fica cega na base, e este teste acusa."""
        rotulos = {m._meta.app_label for m in _models_de_negocio()}
        assert "app_do_inquilino" in rotulos

    def test_toda_isencao_de_app_tem_motivo(self):
        vazias = [k for k, v in APPS_DA_PLATAFORMA.items() if not str(v).strip()]
        assert not vazias, f"app isento sem motivo escrito: {vazias}"

    def test_nenhum_model_de_negocio_sem_a_coluna(self):
        desprotegidos = [
            f"{m._meta.app_label}.{m.__name__}"
            for m in _models_de_negocio()
            if not issubclass(m, ModeloDaEmpresa)
            and f"{m._meta.app_label}.{m.__name__}" not in SEM_EMPRESA
        ]
        assert not desprotegidos, (
            f"model de negócio sem a coluna do inquilino: {desprotegidos}. "
            f"Herde `contas.inquilino.ModeloDaEmpresa`, ou declare em "
            f"SEM_EMPRESA (aqui) dizendo por quê."
        )

    def test_toda_isencao_tem_motivo(self):
        vazias = [k for k, v in SEM_EMPRESA.items() if not str(v).strip()]
        assert not vazias, f"isenção sem motivo escrito: {vazias}"


@pytest.mark.django_db
class TestOManagerFalhaVazio:
    """O modo de falha é escolhido: esquecer o contexto dá tela vazia, nunca
    tela cheia com dado dos outros.

    Os testes usam um model concreto criado só para isto — não um de
    negócio, que ainda não existe. É o mesmo recurso de
    `tests/test_guarda.py`, que testa `exigir_permissao` sem depender de uma
    URL registrada.
    """

    def test_all_sem_contexto_vem_vazio(self, produto_de_teste):
        Produto, alfa, beta = produto_de_teste
        assert Produto.irrestritos.count() == 2
        assert Produto.objects.count() == 0

    def test_da_empresa_traz_so_a_dela(self, produto_de_teste):
        Produto, alfa, beta = produto_de_teste
        nomes = {p.nome for p in Produto.objects.da_empresa(alfa)}
        assert nomes == {"da alfa"}

    def test_da_empresa_com_none_vem_vazio(self, produto_de_teste):
        """Sessão sem empresa escolhida não pode virar "todas"."""
        Produto, _, _ = produto_de_teste
        assert not Produto.objects.da_empresa(None).exists()

    def test_da_conta_traz_todas_as_linhas_com_o_mesmo_guid(
            self, produto_de_teste):
        Produto, alfa, beta = produto_de_teste
        linhas = list(Produto.objects.da_conta(alfa.dono))
        assert {p.nome for p in linhas} == {"da alfa"}
        assert {p.conta_id for p in linhas} == {alfa.dono.guid}

    def test_a_linha_guarda_guid_proprio_e_guid_da_conta(
            self, produto_de_teste):
        Produto, alfa, beta = produto_de_teste
        produto = Produto.irrestritos.get(nome="da alfa")
        assert produto.guid != produto.conta_id
        assert produto.conta_id == alfa.dono.guid

    def test_recusa_empresa_sem_conta(self, db):
        from django.core.exceptions import ValidationError
        from plataforma.models import Empresa

        empresa = Empresa.objects.create(razao_social="Sem titular")
        with pytest.raises(ValidationError, match="conta titular"):
            ProdutoDeTeste.irrestritos.create(nome="órfão", empresa=empresa)

    def test_recusa_conta_diferente_da_titular(
            self, produto_de_teste, db):
        from django.core.exceptions import ValidationError

        Produto, alfa, beta = produto_de_teste
        with pytest.raises(ValidationError, match="não é a titular"):
            Produto.irrestritos.create(
                nome="misturado", empresa=alfa, conta=beta.dono)

    def test_transferir_empresa_troca_o_guid_de_todas_as_linhas(
            self, produto_de_teste, db):
        from contas.models import Nivel, Usuario

        Produto, alfa, beta = produto_de_teste
        nova = Usuario.objects.create_user(
            email="nova-dona@teste.com", password="x", nivel=Nivel.TITULAR)
        alfa.dono = nova
        alfa.save(update_fields=["dono"])

        produto = Produto.irrestritos.get(nome="da alfa")
        assert alfa.conta_id == nova.guid
        assert produto.conta_id == nova.guid

    def test_de_usa_o_mesmo_alcance_das_outras_telas(self, produto_de_teste, db):
        from contas.models import Usuario
        
        from contas.models import Nivel

        Produto, alfa, beta = produto_de_teste
        pessoa = alfa.dono

        nomes = {p.nome for p in Produto.objects.de(pessoa)}
        assert nomes == {"da alfa"}

    def test_de_sem_acesso_cadastrado_vem_vazio(self, produto_de_teste, db):
        from contas.models import Usuario
        
        Produto, _, _ = produto_de_teste
        solto = Usuario.objects.create_user(email="solto@teste.com", password="x")
        assert not Produto.objects.de(solto).exists()

    def test_o_default_manager_enxerga_tudo(self, produto_de_teste):
        """O `dumpdata` e o comando de backup usam `_default_manager`. Se ele
        fosse o vazio, o backup desta instalação exportaria zero linhas — em
        silêncio, e só se descobriria no dia de restaurar.

        `ProdutoDeTeste` declara a própria `Meta` (precisa de `app_label`),
        e por isso NÃO herda `default_manager_name` do model abstrato — o que
        torna este teste ainda melhor: ele prova que a propriedade sobrevive
        ao esquecimento mais comum, porque vem da ORDEM em que os managers
        são declarados, não do nome.
        """
        Produto, _, _ = produto_de_teste
        assert Produto._default_manager.count() == 2

    def test_a_ordem_dos_managers_e_o_que_protege(self):
        """A trava por trás do teste acima, dita em voz alta.

        Se alguém trocar a ordem em `ModeloDaEmpresa` — pondo `objects`
        primeiro —, todo model filho que declare a própria `Meta` passa a
        exportar zero linhas no backup. Este teste é o que transforma essa
        troca de uma linha num vermelho.
        """
        declarados = [
            nome for nome, _ in ModeloDaEmpresa._meta.managers_map.items()
        ] if hasattr(ModeloDaEmpresa._meta, "managers_map") else []
        primeiro = ModeloDaEmpresa._meta.managers[0].name if \
            ModeloDaEmpresa._meta.managers else None
        assert primeiro == "irrestritos", (
            f"o primeiro manager de ModeloDaEmpresa é {primeiro!r} — ele é o "
            f"`_default_manager`, e o backup depende dele enxergar tudo. "
            f"({declarados})"
        )
