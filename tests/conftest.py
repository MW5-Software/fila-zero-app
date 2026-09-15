"""Fixtures compartilhadas da suíte.

Existe por causa de uma decisão deste produto: **o módulo de filiais nasce
desligado** (ver `plataforma/modulo.py` e o roadmap). O model, as telas e as
regras continuam de pé para o dia em que filial fizer sentido — e os testes
delas continuam valendo. O que muda é que agora elas precisam LIGAR o módulo
que testam, como qualquer módulo de negócio faria.
"""

import pytest


@pytest.fixture(autouse=True)
def midia_isolada(tmp_path, monkeypatch):
    """Toda foto que a suíte gravar vai para uma pasta descartável.

    `autouse` de propósito: a alternativa é cada teste que envia foto lembrar
    de pedir a fixture, e o que se paga por esquecer não aparece no teste —
    aparece na pasta do projeto, semanas depois, como megabytes de foto de
    teste que ninguém sabe de onde vieram. Já aconteceu na primeira rodada
    desta mudança (10/09/2026): 256 KB dentro de `midia/` do repositório.

    `tmp_path` é por teste, então uma foto gravada num não é vista pelo
    seguinte — que é a mesma promessa que o banco já dá.
    """
    monkeypatch.setenv("KRONOS_MIDIA", str(tmp_path / "midia"))


@pytest.fixture
def modulo_filiais_ligado(db):
    """Liga o módulo de filiais para o teste que precisa da tela dele.

    Sem isto, `exigir_modulo_ligado("filiais")` responde 404 — e é esse o
    comportamento certo: neste produto a filial está desligada por padrão.
    Um teste que precisa da tela é um teste sobre o módulo LIGADO, e dizer
    isso em voz alta é melhor do que ligar por baixo do pano para todos.
    """
    from plataforma.models import Modulo

    Modulo.objects.filter(chave="filiais").update(ativo=True)


@pytest.fixture
def empresa_do_teste(db):
    """A empresa que a suíte usa como "a empresa desta instalação".

    É a semeada pelo `post_migrate` — não uma nova. Assim os testes herdados
    do KRONOS.net, escritos quando existia uma empresa só, continuam falando
    da mesma linha que eles sempre falaram.
    """
    from plataforma.models import Empresa

    return Empresa.objects.first()


#: O domínio dos e-mails de teste. Existe como constante porque o e-mail
#: virou o LOGIN (`contas.models.Usuario.USERNAME_FIELD`), e a suíte inteira
#: passou a precisar de um endereço onde antes bastava um apelido: dezenas de
#: fixtures montam "ana" + isto, e um domínio digitado à mão em cada uma seria
#: dezenas de lugares para divergir.
DOMINIO_DE_TESTE = "teste.com"


def email_de(login: str) -> str:
    """`"ana"` -> `"ana@teste.com"`.

    As fixtures continuam falando em apelido curto porque é o que as
    asserções leem melhor ("o vendedor da alfa"); o banco precisa do e-mail.
    Esta função é a única tradução entre os dois.
    """
    return f"{login}@{DOMINIO_DE_TESTE}"


#: "Ninguém disse nível nenhum" — e é diferente de "disseram MEMBRO".
#:
#: `None` não serve como sentinela aqui, e `Nivel.MEMBRO` muito menos:
#: quem chama `dar_acesso(comprador, empresas=[alfa])` só para dar o vínculo
#: estaria pedindo um ADMIN sem saber, porque "não informado" e "MEMBRO"
#: seriam o mesmo valor. Um objeto próprio não colide com nível nenhum.
_NAO_INFORMADO = object()


def empresa_do_teste():
    """A empresa que o `post_migrate` semeava até 09/09/2026.

    A semeadura acabou porque criava empresa SEM DONO (ver
    `plataforma/apps.py`), e vários arquivos faziam `Empresa.objects.first()`
    contando com ela. Criar aqui é necessidade do TESTE — semear em produção
    para servir a suíte seria deixar o defeito em pé nas sessenta
    instalações.
    """
    from plataforma.models import Empresa

    return Empresa.objects.first() or Empresa.objects.create(
        razao_social="Empresa do Teste")


def matriz_do_teste():
    """A filial "Matriz" que o `post_migrate` semeava até 09/09/2026.

    A semeadura acabou junto com a da empresa (ver `plataforma/apps.py`): ela
    criava uma filial pendurada numa empresa SEM DONO, e sem a empresa criaria
    uma filial órfã.

    Dez arquivos faziam `Filial.objects.get(nome="Matriz")` contando com ela.
    Criar aqui é o mesmo raciocínio de `dar_acesso`: a suíte precisa de uma
    filial para falar de filial, e isso é necessidade do TESTE — semear em
    produção para servir a suíte seria deixar o defeito em pé nas sessenta
    instalações para não mexer em dez arquivos.

    Desde 14/09/2026 a empresa nasce com a Matriz, e esta função devolve a
    que já existe em vez de criar uma segunda.
    """
    from plataforma.models import Empresa, Filial

    ja = Filial.objects.filter(e_matriz=True).first() or \
        Filial.objects.filter(nome="Matriz").first()
    if ja is not None:
        return ja
    empresa = Empresa.objects.first() or Empresa.objects.create(
        razao_social="Empresa do Teste")
    # A empresa nasce com a Matriz desde 14/09/2026 (`plataforma/apps.py`).
    # Uma empresa que já existia antes do teste pode não ter — por isso o
    # `or create`, e com `e_matriz` para não haver duas.
    return (empresa.filiais.filter(e_matriz=True).first()
            or Filial.objects.create(nome="Matriz", apelido="Matriz",
                                     empresa=empresa, e_matriz=True))


def dar_acesso(pessoa, nivel=_NAO_INFORMADO, empresas=None):
    """Dá a `pessoa` nível e vínculo de empresa — sem eles, ela não alcança
    nada.

    Existe porque a base herdada do KRONOS.net não tinha esta noção: lá a
    instalação é de UM cliente, e quem tem a permissão administra todo mundo.
    Aqui o portal atende várias empresas, e administrar gente exige dizer
    **de qual empresa** — `contas.alcance.pessoas_alcancadas` devolve vazio
    para quem não tem vínculo, e é essa a regra certa.

    Os testes herdados chamam isto nas fixtures de admin deles. Não é
    contorno: é o cadastro que este produto passou a exigir, dito em voz alta
    onde antes era implícito.

    Gravava numa linha de `Acesso` ao lado da pessoa; agora grava na PRÓPRIA
    pessoa. O nome da função ficou: quem a chama continua pedindo a mesma
    coisa, e renomear 60 chamadas para dizer o mesmo não paga o ruído.
    Devolve a pessoa, e não mais o `Acesso` que deixou de existir.

    **O contrato, em duas linhas:** sem `nivel`, esta pessoa vira ADMIN da
    empresa; com `nivel`, ela fica exatamente no nível pedido — inclusive
    MEMBRO. Quem só quer o vínculo de uma pessoa que já tem nível diz o
    nível dela junto; a função nunca adivinha pelo estado atual.
    """
    from contas.models import Nivel
    from plataforma.models import Empresa

    # **Sem `nivel`, promove a ADMIN; com `nivel`, grava o que pediram.** É a
    # tradução fiel do que a versão anterior fazia: ela criava a linha de
    # `Acesso` com ADMIN quando não havia nenhuma, e gravava o nível pedido
    # quando havia um.
    #
    # A pergunta é "informaram ou não", e **não** "o nível atual é o padrão da
    # coluna": os dois eram indistinguíveis enquanto a condição olhava
    # `pessoa.nivel == Nivel.MEMBRO`, e quem criasse um comprador de
    # propósito e chamasse `dar_acesso(pessoa, empresas=[alfa])` só para dar o
    # vínculo recebia um ADMIN em silêncio, com todas as permissões de fábrica
    # junto. `_NAO_INFORMADO` separa os dois.
    pedido = Nivel.TITULAR if nivel is _NAO_INFORMADO else nivel
    pessoa.nivel = pedido
    pessoa.save(update_fields=["nivel"])

    # **`empresas` continua sendo uma LISTA na assinatura, e só a primeira
    # conta** (09/09/2026). Uma conta tem uma empresa; a lista sobreviveu
    # porque cinquenta chamadas na suíte passam `empresas=[alfa]`, e trocar
    # todas por `empresa=alfa` seria cinquenta oportunidades de errar num
    # trabalho que não prova nada. Quem passa duas recebe a primeira, em
    # silêncio: o cenário de "pessoa em duas empresas" deixou de existir, e
    # um teste que ainda o monte está descrevendo um mundo que não há.
    # **Sem `empresas`, cria uma.** Antes ela vinha da empresa que o
    # `post_migrate` semeava em toda instalação — e essa semeadura acabou em
    # 09/09/2026, porque produzia empresa SEM DONO (ver `plataforma/apps.py`).
    #
    # Criar aqui, e não voltar a semear em produção: a suíte precisa de UMA
    # empresa para pendurar gente, e isso é necessidade do teste, não do
    # produto. Semear para servir a suíte seria deixar o defeito em pé nas
    # sessenta instalações para não mexer em cinquenta chamadas.
    if empresas is not None:
        alvo = list(empresas)[:1]
    else:
        alvo = [empresa_do_teste()]
    por_na_conta(pessoa, alvo[0] if alvo else None)
    # Desde a virada dos cargos, o que o membro pode mora no cargo da
    # alocação. Sem esta linha, os testes que pedem "um membro" criariam
    # alguém sem permissão nenhuma, e o vermelho pareceria defeito da tela.
    # Cliente é o cargo de quem só vê o catálogo e os próprios orçamentos — o
    # que o nível COMPRADOR, que o membro substituiu, dava.
    if alvo and pedido == Nivel.MEMBRO:
        alocar(pessoa, alvo[0], "cliente")
    return pessoa


def por_na_conta(pessoa, empresa) -> None:
    """Liga `pessoa` à conta dona de `empresa`, criando a conta se preciso.

    A suíte inteira monta empresa e gente sem nunca dizer "quem é o dono
    disto" — e não deveria dizer: o dono é detalhe do modelo de contas, e
    quase todo teste fala de outra coisa. Aqui a conta nasce sozinha quando
    falta, do mesmo jeito que a empresa já nascia.

    MASTER não entra em conta nenhuma: a MW5 não é cliente. ADMIN vira o dono
    da empresa — ele É a conta.
    """
    from contas.models import Nivel, Usuario

    if empresa is None or pessoa.nivel == Nivel.MASTER or pessoa.is_superuser:
        return

    if pessoa.nivel == Nivel.TITULAR:
        if empresa.dono_id is None:
            empresa.dono = pessoa
            empresa.save(update_fields=["dono"])
        elif empresa.dono_id != pessoa.pk:
            # A empresa já é de outro Admin. Este fica sem empresa, que é o
            # que o banco permite — dois donos para a mesma empresa é o que
            # `uma_empresa_por_conta` recusa.
            pass
        return

    if empresa.dono_id is None:
        empresa.dono = Usuario.objects.create_user(
            email=f"dono-{empresa.pk}@teste.com", password="x",
            nivel=Nivel.TITULAR)
        empresa.save(update_fields=["dono"])
    pessoa.dono_id = empresa.dono_id
    pessoa.save(update_fields=["dono"])


def abrir_conta(empresa, login: str, senha: str = "x"):
    """Cria o titular e liga a empresa antes de ela receber dado de negócio."""
    from contas.models import Nivel, Usuario

    titular = Usuario.objects.create_user(
        email=email_de(login), password=senha, nivel=Nivel.TITULAR)
    empresa.dono = titular
    empresa.save(update_fields=["dono"])
    return titular


def dar_papel(pessoa, papel, dono=None):
    """Aloca `pessoa` com o cargo que corresponde ao papel pedido.

    O papel morava no Perfil e virou cargo (spec 2026-09-14): "comprador" é o
    cargo Cliente, "vendedor" é o Vendedor. O nome da função ficou para não
    mexer em dezenas de chamadas que continuam pedindo a mesma coisa. `dono`
    ficou na assinatura pelo mesmo motivo e não é mais usado.
    """
    from plataforma.models import Empresa

    empresa = (Empresa.objects.filter(dono_id=pessoa.dono_id).first()
               if pessoa.dono_id else None) or empresa_do_teste()
    return alocar(pessoa, empresa,
                  "cliente" if papel == "comprador" else "vendedor")


def _nivel_de_membro():
    """O nível de quem é membro de uma conta."""
    from contas.models import Nivel

    return Nivel.MEMBRO


def cargo_com(empresa, *chaves, nome="cargo-de-teste", alcance="empresa",
              e_cliente=False):
    """Um cargo da conta de `empresa` com exatamente as permissões pedidas
    (`"modulo.acao"`). Para o teste que precisa de "alguém que pode X" sem
    depender do que os cargos de fábrica trazem hoje."""
    from django.contrib.auth.models import Permission

    from contas.models import Cargo

    cargo, _ = Cargo.objects.get_or_create(
        conta_id=empresa.conta_id, nome=nome,
        defaults={"rotulo": nome.title(), "alcance": alcance,
                  "e_cliente": e_cliente})
    cargo.permissoes.set(Permission.objects.filter(
        content_type__app_label="plataforma",
        codename__in=[c.replace(".", "_") for c in chaves]))
    return cargo


def alocar(pessoa, empresa=None, cargo="cliente", filial=None):
    """Aloca `pessoa` em `empresa` (filial vazia = empresa inteira) com `cargo`,
    que pode ser o nome de um cargo de fábrica ou um `Cargo`.

    É o cadastro que dá permissão a um membro desde a virada. Sem ele, um teste
    que só criava a pessoa com permissão direta passaria a tomar 404 e parecer
    defeito da tela. Idempotente por lugar: chamar de novo troca o cargo.
    """
    from contas.models import Alocacao, Cargo

    empresa = empresa or empresa_do_teste()
    if pessoa.nivel <= 1 or pessoa.is_superuser:
        pessoa.nivel = _nivel_de_membro()
        pessoa.is_superuser = False
        pessoa.save(update_fields=["nivel", "is_superuser"])
    por_na_conta(pessoa, empresa)
    empresa.refresh_from_db()
    if isinstance(cargo, str):
        cargo = Cargo.objects.get(conta_id=empresa.conta_id, nome=cargo)
    alocacao, _ = Alocacao.objects.update_or_create(
        pessoa=pessoa, empresa=empresa, filial=filial,
        defaults={"cargo": cargo})
    return alocacao


def _membro_provisorio(pessoa):
    """`pessoa` com nível de membro gravado, para `por_na_conta` criar o titular
    da empresa em vez de fazer dela a dona."""
    if pessoa.nivel <= 1 and not pessoa.is_superuser:
        pessoa.nivel = _nivel_de_membro()
        pessoa.save(update_fields=["nivel"])
    return pessoa


def dar_permissoes(pessoa, *codenames, empresa=None):
    """Dá a `pessoa` exatamente estas permissões, pelo único caminho que vale
    para um membro desde a virada: um cargo com elas, alocado na empresa
    inteira.

    Substitui `pessoa.user_permissions.add(...)` nos testes que só precisam de
    "alguém que pode X": a permissão direta de membro deixou de contar, e o
    teste que continuasse gravando nela tomaria 404 e pareceria defeito da
    tela. Aceita `"modulo_acao"` ou `"modulo.acao"`. O cargo leva o nome das
    permissões, para duas pessoas com conjuntos diferentes não dividirem um
    cargo e uma sobrescrever a outra.
    """
    empresa = empresa or empresa_do_teste()
    if empresa.dono_id is None:
        # A conta nasce ANTES do cargo (o cargo é da conta), e nasce de um
        # titular à parte: se a própria pessoa virasse dona aqui, `alocar`
        # a rebaixaria logo em seguida e a empresa ficaria com um dono membro.
        por_na_conta(_membro_provisorio(pessoa), empresa)
        empresa.refresh_from_db()
    chaves = sorted(c.replace(".", "_") for c in codenames)
    nome = ("com-" + "-".join(chaves).replace("_", "-").replace("*", "tudo"))[:60]
    cargo = cargo_com(empresa, *chaves, nome=nome)
    return alocar(pessoa, empresa, cargo)
