"""O usuário deste produto, o perfil, a foto e o registro de auditoria.

O usuário é NOSSO, e não o `auth.User` do Django. O motivo está inteiro no
docstring de `Usuario`, e a consequência prática mora aqui: `nivel`, o alcance
por empresa e a carteira de compradores moravam em `acesso_acesso`, uma tabela
1:1 ao lado, só porque não havia como acrescentar coluna à tabela do Django.
Quatro tabelas viraram uma.

O que continua nascendo aqui é o que nem o Django nem o `Usuario` deveriam
carregar: o perfil como unidade de permissão, e o registro do que foi feito.
A foto e a marca de quando a senha foi definida (Task 3) já não são tabela à
parte — viraram coluna do próprio `Usuario`, pelo mesmo motivo de `nivel` e do
alcance por empresa: existiam como tabela 1:1 só enquanto não havia onde
acrescentar coluna.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import (
    AbstractUser, BaseUserManager, Permission,
)
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from comum.guid import ComGuid

__all__ = [
    "Alcance", "Alocacao", "Cargo", "GerenteDeUsuario", "Nivel",
    "RegistroDeAuditoria", "RegistroImutavel", "Usuario",
]


class Nivel(models.IntegerChoices):
    """A ordem dos números é do mais poderoso para o menos, como na origem —
    é o que faz `nivel <= Nivel.TITULAR` significar "admin ou acima" sem ninguém
    precisar decorar a lista.

    Inteiro, e não texto: um campo de texto vira `"titular"`, `"Titular"` e
    `"ADMIN"` na mesma coluna, e a consulta passa a depender de qual deles o
    código usou naquele dia.
    """

    MASTER = 0, "Master"
    #: **Era `ADMIN` até 09/09/2026.** "Admin" descrevia um cargo de
    #: sistema — quem mexe nas configurações —, e esta pessoa não é isso:
    #: ela é o DONO da conta e da empresa dela, quem assinaria o SaaS, e
    #: quem distribui os usuários dela. Chamá-la de admin fazia a conversa
    #: escorregar toda hora para "admin de quê?".
    #:
    #: "Titular da conta" é o que ela é, e continua verdade antes de existir
    #: cobrança. **O número não muda**: o que estava gravado como 1 continua
    #: sendo 1, e por isso não há migração de dado — só de `choices`.
    TITULAR = 1, "Titular"
    #: **Quem é da conta sem ser o titular** (14/09/2026). Era VENDEDOR (2) e
    #: COMPRADOR (3): o que os dois diziam — o que a pessoa faz, e o que
    #: enxerga — passou a ser o CARGO da alocação (`contas.Cargo`), que muda
    #: por lugar. `contas/0017` levou o 3 para 2 e deu a cada um o cargo que o
    #: nível significava.
    #: **"Usuário" na tela desde 15/09/2026** — era "Membro", palavra que
    #: ninguém fora do código usava. O nome da constante e o número ficam: o
    #: banco guarda 2, e `MEMBRO` é o que o código inteiro já lê.
    MEMBRO = 2, "Usuário"


class GerenteDeUsuario(BaseUserManager):
    """`create_user` do Django exige `username`, que este model não tem.

    O manager próprio existe para isso e para a PORTA: trocar o campo de
    identidade por `email`, normalizá-lo, e fazer o login achar a pessoa em
    qualquer caixa. `normalize_email` baixa o DOMÍNIO para minúsculas e
    preserva a parte antes do @ — o domínio não diferencia maiúscula, a caixa
    postal pode —, e é `get_by_natural_key` que cuida do resto.
    """

    use_in_migrations = True

    def get_by_natural_key(self, email):
        """A pessoa cujo e-mail bate **sem olhar a caixa**.

        É o método que o `ModelBackend` do Django chama para achar quem está
        tentando entrar. `email__iexact` e não `email=` porque o e-mail deixou
        de ser CONTATO e virou a PORTA: cadastrada como `Ana@empresa.com`, a
        pessoa digitaria `ana@empresa.com` no dia seguinte, receberia
        "Credenciais inválidas" sem pista nenhuma, e o suporte não
        reproduziria — quem confere copia e cola do cadastro, na grafia certa.

        **A decisão anterior era não normalizar, e ela estava certa para o que
        o campo era.** `normalize_email` preserva a parte antes do @ de
        propósito: o RFC deixa a caixa postal diferenciar maiúscula, e
        reescrever o endereço de alguém é estragar um dado de contato. O que
        mudou não foi o RFC, foi o papel do campo. Então o que a pessoa
        digitou **continua gravado como ela digitou** — só a porta ficou
        insensível.

        Só a porta, e não a unicidade do banco: a coluna continua `unique=True`
        exata, e quem recusa a duplicata por caixa diferente são as duas
        portas de cadastro (`contas.views_usuarios._acao_criar` e
        `_acao_editar`, por `email__iexact`). Sem essa recusa lá, duas contas
        com a mesma grafia em caixas diferentes fariam este `get` levantar
        `MultipleObjectsReturned` — e o certo é não deixar as duas nascerem,
        não escolher uma delas aqui em silêncio.
        """
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": email})

    def _criar(self, email, nome, password, **extras):
        if not email:
            raise ValueError("O e-mail é o login: não pode ficar vazio.")
        pessoa = self.model(
            email=self.normalize_email(email), nome=nome, **extras)
        pessoa.set_password(password)
        pessoa.save(using=self._db)
        return pessoa

    def create_user(self, email, nome="", password=None, **extras):
        extras.setdefault("is_staff", False)
        extras.setdefault("is_superuser", False)
        return self._criar(email, nome, password, **extras)

    def create_superuser(self, email, nome="", password=None, **extras):
        extras.setdefault("is_staff", True)
        extras.setdefault("is_superuser", True)
        extras.setdefault("nivel", Nivel.MASTER)
        if not extras["is_staff"] or not extras["is_superuser"]:
            raise ValueError("Superusuário nasce com is_staff e is_superuser.")
        return self._criar(email, nome, password, **extras)


class Usuario(ComGuid, AbstractUser):
    """A pessoa, e — quando é Admin — a CONTA.

    Herda `AbstractUser` e não `AbstractBaseUser`: o Portal já tem tela de
    perfil, avatar, auditoria e personificação em cima do encanamento do
    Django (grupos, permissões, `date_joined`, `is_active`), e `AbstractUser`
    preserva tudo isso. O que muda é a identidade — `username` sai, `email`
    entra — e `first_name`/`last_name` viram um `nome` só, como no
    `kronos-api2`.

    `auth_user` nasce de uma migração DENTRO do pacote do Django: editar o
    arquivo some no próximo `uv sync`, `ALTER TABLE` cru dá uma coluna que o
    ORM não conhece, e reabrir a classe em tempo de execução quebra na próxima
    versão. Sobravam dois caminhos, e só dois — tabela 1:1 ao lado (o
    `acesso_acesso` de ontem) ou usuário próprio. Com o produto virando SaaS,
    a tabela ao lado ia receber mais três colunas.
    """

    username = None
    first_name = None
    last_name = None

    email = models.EmailField("e-mail", unique=True)
    nome = models.CharField("nome", max_length=255)
    telefone = models.CharField("telefone", max_length=20, blank=True, default="")

    nivel = models.IntegerField(
        "nível de acesso", choices=Nivel.choices, default=Nivel.MEMBRO)

    #: **O idioma da MOLDURA para esta pessoa** (09/09/2026, portal vendido
    #: também no Paraguai).
    #:
    #: Coluna na pessoa, e não variável de sessão: a preferência tem que
    #: sobreviver ao logout. Alguém que trabalha em castelhano não pode ter
    #: de escolher o idioma toda manhã — e, se dependesse da sessão, o
    #: primeiro `flush()` (trocar senha, personificação encerrada) devolveria
    #: a tela em português sem explicação.
    #:
    #: Não decide o idioma do CATÁLOGO: nome de peça é dado do cliente, mora
    #: em linha de tabela e nenhum arquivo de tradução alcança. Ver
    #: `LANGUAGES` em `config/settings.py`.
    idioma = models.CharField(
        "idioma", max_length=10, default="pt-br",
        choices=[("pt-br", "Português"), ("es", "Español")])

    #: **A CONTA de que esta pessoa faz parte — o Admin dono dela.**
    #:
    #: Substitui o M2M `empresas` (09/09/2026). Aquele guardava as empresas
    #: que a pessoa alcançava, e com ele a fronteira entre dois clientes
    #: dependia de uma variável de SESSÃO: a tela perguntava "em qual empresa
    #: você está agora?" e o inquilino lia a resposta. A trava funcionava, mas
    #: dependia de toda tela lembrar de passar por ela — e misturar dado de
    #: dois clientes é a única classe de defeito que este produto não pode
    #: ter.
    #:
    #: Agora a empresa é DERIVADA da conta (`contas.alcance.empresa_de`), e
    #: não há o que forjar: o valor não vem do pedido.
    #:
    #: **Nulo em dois casos, e os dois de propósito.** O MASTER é a MW5, que
    #: não é cliente de conta nenhuma. E o próprio ADMIN, que É a conta —
    #: apontar para si mesmo seria um ciclo que toda consulta teria de tratar
    #: ("suba até o dono, a menos que o dono seja você").
    dono = models.ForeignKey(
        "self", verbose_name="conta", on_delete=models.PROTECT,
        null=True, blank=True, related_name="pessoas_da_conta",
        help_text=_("O Admin dono da conta desta pessoa."))

    #: **A conta pelo GUID, na coluna `conta_guid`** (14/09/2026) — a mesma
    #: convenção de toda linha de negócio (`CLAUDE.md` §7), que o usuário não
    #: tinha: só apontava para a conta por `dono`, o id sequencial desta
    #: instalação, e integração nenhuma casa por id.
    #:
    #: **Derivada, e não gravada à mão** (`save`), como `Empresa.conta` deriva
    #: de `Empresa.dono`: guardar a mesma relação em duas colunas editáveis é o
    #: que deixa as duas divergirem.
    #:
    #: **Diferente de `dono`, o titular aponta para o PRÓPRIO GUID.** Toda linha
    #: da conta, inclusive a dele, tem o mesmo `conta_guid`, e
    #: `filter(conta=<guid>)` traz a conta inteira sem caso especial. Não é o
    #: ciclo que `dono` evita: ninguém "sobe" por esta coluna, ela só agrupa.
    #: A MW5 fica nula — não é cliente de conta nenhuma.
    #:
    #: `SET_NULL`, e não `PROTECT`: com `PROTECT` a linha do titular protegeria
    #: a si mesma e nunca sairia. Quem impede apagar um titular com equipe
    #: continua sendo `dono` (`PROTECT`).
    conta = models.ForeignKey(
        "self", verbose_name="conta por GUID", to_field="guid",
        db_column="conta_guid", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
        help_text=_("O GUID do titular da conta desta pessoa."))

    #: A carteira: quais CLIENTES este vendedor atende.
    #:
    #: **Sem uso na regra desde 14/09/2026** (spec de cargos, D6): quem isola
    #: por dentro da empresa é o alcance do cargo. Ficou no banco para o dia em
    #: que a carteira for redesenhada.
    #:
    #: `symmetrical=False` porque a relação tem lado: o vendedor atende o
    #: comprador, e o contrário não é verdade. Num M2M para `"self"` o Django
    #: assume simetria por padrão, e a simetria aqui daria ao comprador a
    #: carteira do vendedor dele.
    compradores = models.ManyToManyField(
        "self", verbose_name="compradores da carteira", symmetrical=False,
        related_name="vendedores", blank=True)

    #: A foto, como bytes no próprio banco. Não vai para uma pasta no disco
    #: porque, com vinte instalações, uma pasta é vinte lugares para lembrar
    #: de incluir no backup — e um deles sempre escapa.
    avatar = models.BinaryField("avatar", null=True, blank=True)
    #: O media type que `nucleo.images.validar` decidiu pelo CONTEÚDO — nunca
    #: o que o navegador declarou ao enviar.
    avatar_tipo = models.CharField("tipo do avatar", max_length=40,
                                   blank=True, default="")
    #: Quando a senha foi definida pela última vez. `None` até o primeiro
    #: login pelo app — a senha pode ter nascido fora dele, pelo
    #: `changepassword` do `manage.py`, e aí não há "quando" nenhum a
    #: registrar até essa pessoa aparecer.
    senha_definida_em = models.DateTimeField("senha definida em",
                                              null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    objects = GerenteDeUsuario()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ("nome", "email")
        constraints = [
            #: **A porta é insensível à caixa dos DOIS lados**: na hora de
            #: entrar (`GerenteDeUsuario.get_by_natural_key`, por `iexact`) e
            #: na hora de gravar, aqui. Uma metade sem a outra é uma
            #: contradição com consequência: com `unique=True` só na caixa
            #: exata, `ana@empresa.com` e `Ana@empresa.com` nasciam como duas
            #: contas, e aí `get_by_natural_key` achava as DUAS — a tela de
            #: entrada estourava com `MultipleObjectsReturned`, e as duas
            #: contas ficavam inacessíveis sem nenhuma mensagem que
            #: explicasse.
            #:
            #: **No BANCO, e não só na view.** É a regra da casa: a tela dá a
            #: FRASE, o banco dá a TRANCA — a mesma divisão que
            #: `contas.views_usuarios._acao_criar` já descreve para o
            #: `max_length` ("quem recusa é o Postgres") e que `Empresa.save`
            #: aplica com `full_clean`. Uma garantia que more só na view não é
            #: garantia: um `INSERT` por shell, por script de carga ou por
            #: migração de dados passa por baixo dela. As duas continuam
            #: existindo, e é de propósito: `_login_ocupado` recusa com uma
            #: frase que a pessoa entende, e isto aqui é a rede embaixo.
            #:
            #: **Só a COMPARAÇÃO ignora a caixa.** O que a pessoa digitou
            #: continua gravado como ela digitou — `normalize_email` segue
            #: baixando só o domínio, porque o RFC deixa a caixa postal
            #: diferenciar maiúscula e reescrever o endereço de alguém é
            #: estragar um dado de contato. O que mudou não foi o RFC, foi o
            #: papel do campo: ele deixou de ser contato e virou login.
            #:
            #: `Lower("email")` e não uma coluna a mais com o e-mail em
            #: minúsculas: a segunda coluna precisaria ser mantida em sincronia
            #: por alguém, e o dia em que alguém esquecer é o dia em que a
            #: unicidade some sem ninguém notar. O índice funcional não tem
            #: como sair de sincronia — é o próprio Postgres que o calcula.
            models.UniqueConstraint(
                Lower("email"), name="email_unico_sem_caixa",
                violation_error_message="Já existe alguém com este e-mail."),
        ]

    def __str__(self) -> str:
        return self.nome or self.email

    def get_full_name(self) -> str:
        """O `AbstractUser` monta o nome juntando `first_name` e `last_name`,
        que aqui não existem. Sem esta linha, toda tela que mostra o nome de
        alguém mostraria string vazia."""
        return self.nome

    def get_short_name(self) -> str:
        return self.nome.split(" ")[0] if self.nome else self.email

    def _conta_derivada(self):
        """O GUID que `conta` deve ter, lido de `nivel` e `dono`."""
        if self.is_superuser or self.nivel == Nivel.MASTER:
            return None
        if self.nivel == Nivel.TITULAR:
            return self.guid
        if self.dono_id is None:
            return None
        return (Usuario.objects.filter(pk=self.dono_id)
                .values_list("guid", flat=True).first())

    def save(self, *args, **kwargs):
        """Grava `conta` junto, derivada de `nivel` e `dono`.

        **Acrescenta `conta` ao `update_fields` quando ela muda.** As telas
        gravam com `update_fields=["dono"]` ou `["nivel"]`; sem isto o objeto
        mudaria em memória e o banco ficaria com a conta antiga, em silêncio.

        `QuerySet.update(dono=...)` não passa por aqui — quem usar precisa
        acertar `conta` junto.
        """
        conta = self._conta_derivada()
        if self.conta_id != conta:
            self.conta_id = conta
            campos = kwargs.get("update_fields")
            if campos is not None:
                kwargs["update_fields"] = {*campos, "conta"}
        super().save(*args, **kwargs)

    # -- as perguntas, com nome ------------------------------------------
    #
    # `nivel == 0` espalhado pelo código é uma comparação que ninguém lê e
    # que ninguém acha no dia em que o vocabulário mudar. Vieram do `Acesso`
    # sem mudar de forma: o que mudou foi a linha em que moram.

    @property
    def e_master(self) -> bool:
        return self.nivel == Nivel.MASTER

    @property
    def e_titular_ou_acima(self) -> bool:
        return self.nivel <= Nivel.TITULAR

    # `e_vendedor` e `e_comprador` saíram de propósito: o que a pessoa é no
    # negócio mora no CARGO da alocação (`contas.lugar.e_cliente`), e não no
    # nível. Uma propriedade com esse nome responderia a pergunta errada.


class Alcance(models.TextChoices):
    """Quais registros um cargo enxerga.

    Mora no cargo, e não no código, por uma decisão do desenho (spec
    2026-09-14, D5): cargo criado depois pelo titular escolhe o alcance numa
    caixa, e nenhuma regra do sistema depende do NOME de um cargo. Um
    "Coordenador" criado amanhã enxerga a filial porque alguém marcou "a
    filial", e não porque um `if` conhece a palavra.
    """

    PROPRIOS = "proprios", "Os próprios"
    FILIAL = "filial", "A filial"
    EMPRESA = "empresa", "A empresa"


class Cargo(ComGuid):
    """O que uma pessoa pode fazer, e quais registros enxerga, NUM LUGAR.

    Substitui o `Perfil` (spec 2026-09-14, D9). A diferença que importa não é o
    nome: o perfil valia para a pessoa no sistema inteiro, e o cargo vale na
    alocação — a mesma pessoa pode ser Gerente numa filial e Vendedora noutra
    (D1). O cargo em si não sabe de lugar; quem liga cargo a lugar é
    `Alocacao`.

    **É daqui que vem a permissão de todo membro de uma conta**, no lugar em
    que ele está (`contas.lugar`). Titular e MW5 não têm cargo.
    """

    #: A conta dona do cargo, pela identidade estável — o GUID do titular, na
    #: coluna `conta_guid`, a mesma convenção de toda linha de negócio desde
    #: 14/09/2026.
    #:
    #: `CASCADE`: apagar o titular leva os cargos da conta. Na prática isso não
    #: acontece sozinho — `Empresa.dono` é `PROTECT` e `Alocacao.cargo` também —,
    #: e um cargo sem conta não teria a quem pertencer.
    conta = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.CASCADE,
        related_name="cargos_da_conta",
        help_text=_("A conta dona deste cargo, pelo GUID do titular."))

    nome = models.SlugField("nome", max_length=60)
    rotulo = models.CharField("rótulo", max_length=120)
    permissoes = models.ManyToManyField(
        Permission, verbose_name="permissões", blank=True,
        related_name="cargos")
    #: `PROPRIOS` como padrão: ver de menos se corrige na tela; ver de mais já
    #: vazou.
    alcance = models.CharField(
        "alcance", max_length=20, choices=Alcance.choices,
        default=Alcance.PROPRIOS)
    #: O cargo se comporta como CLIENTE da empresa (no Portal de Vendas: preço
    #: negociado, compra na vitrine, orçamento próprio). Existe porque o alcance não diz isso — um Vendedor
    #: pode enxergar "os próprios" e não ser cliente de ninguém.
    e_cliente = models.BooleanField("é cliente", default=False)
    #: Veio da semeadura (`contas/cargos_de_fabrica.py`). A tela não oferece
    #: apagar: a próxima semeadura o recriaria em silêncio.
    de_fabrica = models.BooleanField("de fábrica", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "cargo"
        verbose_name_plural = "cargos"
        ordering = ("rotulo",)
        constraints = [
            models.UniqueConstraint(
                fields=("conta", "nome"), name="cargo_unico_por_conta",
                violation_error_message=(
                    "Já existe um cargo com este nome nesta conta.")),
        ]

    def __str__(self) -> str:
        return self.rotulo


class Alocacao(ComGuid):
    """Esta pessoa, neste lugar, com este cargo.

    O cargo é da alocação, e não da pessoa (spec 2026-09-14, D1): a mesma Ana é
    Gerente na filial Centro e Vendedora na Norte. `filial` vazia é a empresa
    inteira, inclusive as filiais criadas depois (D8).

    **A unicidade são DUAS restrições parciais.** `NULL` não é igual a `NULL`
    numa unicidade do Postgres, e a filial vazia é justamente a alocação mais
    ampla: com uma restrição só, a mesma pessoa poderia ter duas alocações "na
    empresa inteira" com cargos diferentes, e "qual cargo vale" deixaria de ter
    resposta. As duas restrições permitem, de propósito, uma alocação na empresa
    inteira E outra numa filial — é o que dá sentido a "a mais específica ganha".

    **O titular e a MW5 não são alocados** (D3). O dono alcança tudo por ser
    dono; alocá-lo daria a ele um cargo capaz de tirar dele o acesso à própria
    conta.

    Não herda `ModeloDaEmpresa`, embora tenha `empresa`: o manager dele lê o
    lugar da requisição, e é JUSTAMENTE a alocação que decide o lugar. Herdar
    faria a pergunta "onde a pessoa está?" depender da resposta.
    """

    conta = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.CASCADE, related_name="+",
        help_text=_("A conta dona desta alocação, pelo GUID do titular."))
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="pessoa",
        on_delete=models.CASCADE, related_name="alocacoes")
    empresa = models.ForeignKey(
        "plataforma.Empresa", verbose_name="empresa",
        on_delete=models.PROTECT, related_name="alocacoes")
    #: Vazia é a empresa inteira.
    filial = models.ForeignKey(
        "plataforma.Filial", verbose_name="filial", null=True, blank=True,
        on_delete=models.PROTECT, related_name="alocacoes")
    #: `PROTECT`: cargo com gente dentro não se apaga pelo banco, e não só pela
    #: frase da tela — a tela nunca é a única porta.
    cargo = models.ForeignKey(
        Cargo, verbose_name="cargo", on_delete=models.PROTECT,
        related_name="alocacoes")
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "alocação"
        verbose_name_plural = "alocações"
        constraints = [
            models.UniqueConstraint(
                fields=("pessoa", "empresa", "filial"),
                condition=models.Q(filial__isnull=False),
                name="alocacao_unica_na_filial"),
            models.UniqueConstraint(
                fields=("pessoa", "empresa"),
                condition=models.Q(filial__isnull=True),
                name="alocacao_unica_na_empresa_inteira"),
        ]

    def clean(self) -> None:
        """As quatro recusas. Cada uma protege a fronteira entre contas, que é a
        única classe de defeito que este produto não pode ter."""
        super().clean()
        if not self.empresa_id:
            return
        erros = {}
        empresa = self.empresa
        if empresa.conta_id is None:
            erros["empresa"] = ("A empresa precisa ter um titular antes de "
                                "receber alocações.")
        else:
            if self.cargo_id and self.cargo.conta_id != empresa.conta_id:
                erros["cargo"] = "Este cargo não é da conta desta empresa."
            if self.pessoa_id:
                pessoa = self.pessoa
                if pessoa.nivel <= Nivel.TITULAR:
                    erros["pessoa"] = ("O titular e a MW5 não são alocados: "
                                       "eles alcançam a conta inteira.")
                elif pessoa.dono_id != empresa.dono_id:
                    erros["pessoa"] = "Esta pessoa não é desta conta."
        if self.filial_id and self.filial.empresa_id != self.empresa_id:
            erros["filial"] = "Esta filial não é desta empresa."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        """A conta vem da empresa — nunca de quem chama —, e então valida.

        `validate_constraints=False`: a unicidade é decidida pelo BANCO, sem
        corrida entre duas requisições, como em `ModeloDaEmpresa.save`.
        """
        if self.empresa_id:
            self.conta_id = self.empresa.conta_id
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        onde = self.filial or self.empresa
        return f"{self.pessoa} — {self.cargo} em {onde}"


class RegistroImutavel(Exception):
    """Uma tentativa de alterar ou apagar uma linha de `RegistroDeAuditoria`.

    Existe para ser o tipo que `save()`/`delete()` levantam — e não um
    `Exception` genérico — porque um teste que capturasse `Exception` puro
    passaria igual contra um `AttributeError` de erro de digitação, sem
    provar nada sobre o append-only de verdade.
    """


class RegistroDeAuditoria(ComGuid):
    """Uma linha da trilha: quem fez o quê, e quando.

    `autor_login` e `autor_nome` são texto, nunca uma chave estrangeira para
    `auth_user`. É essa a diferença que importa: um `ForeignKey` com
    `on_delete=SET_NULL` manteria a linha, mas perderia justamente quem fez
    — e é exatamente da pessoa removida que alguém vai perguntar, seis meses
    depois. Guardado como texto, o registro sobrevive à pessoa.

    Append-only por construção, não só por convenção: `save()` recusa
    regravar uma linha que já tem `pk`, e `delete()` recusa sempre. Nenhum
    dos dois é um detalhe de implementação incidental — são a garantia em
    si, porque "nenhum caminho no código altera ou apaga uma linha" só se
    prova lendo todo o código de novo a cada mudança, e isso envelhece mal.

    A garantia tem limite, e é bom nomeá-lo em vez de deixar alguém achar
    que ela é absoluta: `queryset.update()`, `queryset.delete()` e
    `bulk_create(update_conflicts=True)` operam direto no SQL, sem passar
    por `save()`/`delete()` de instância nenhuma — nenhum dos três levanta
    `RegistroImutavel`. Nenhum código desta aplicação os usa contra este
    model hoje; a defesa aqui é só a de instância, e fechar os três exigiria
    outra camada (um sinal, ou revogar `UPDATE`/`DELETE` no papel do banco),
    que não foi construída.
    """

    quando = models.DateTimeField("quando", auto_now_add=True)
    acao = models.CharField("ação", max_length=40)
    autor_login = models.CharField("login do autor", max_length=150, blank=True)
    autor_nome = models.CharField("nome do autor", max_length=150, blank=True)
    alvo = models.CharField("alvo", max_length=255, blank=True)
    detalhe = models.CharField("detalhe", max_length=255, blank=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        ordering = ("-quando",)
        #: A mesma ordem de `ordering`, descendente: é como a tela de
        #: leitura (ainda por vir) vai listar — mais recente primeiro — e
        #: como este teto de crescimento (a tabela só cresce, nunca encolhe)
        #: vai precisar paginar sem varrer tudo.
        indexes = [models.Index(fields=["-quando"], name="idx_auditoria_quando")]

    def __str__(self) -> str:
        return f"{self.acao} por {self.autor_login or '?'} em {self.quando}"

    def save(self, *args, **kwargs) -> None:
        if self.pk is not None:
            raise RegistroImutavel(
                "RegistroDeAuditoria é append-only: uma linha já gravada "
                "não pode ser alterada. Grave uma linha nova se precisa "
                "registrar outro fato."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        raise RegistroImutavel(
            "RegistroDeAuditoria é append-only: nenhuma linha desta tabela "
            "pode ser apagada, mesmo a mais antiga."
        )
