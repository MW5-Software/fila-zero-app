"""A identidade desta instalação, em banco.

Uma linha de `Marca` por instalação. Os nomes das colunas são os mesmos
campos do `brand.yaml` da entrega 1 — de propósito: `Brand.from_dict` já sabe
ler essa forma, já valida cor e já recusa campo desconhecido. A tabela não
reimplementa nada disso.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from comum.alfabetica import DE_DICIONARIO
from comum.guid import ComGuid
from nucleo.theme import Brand

from .documentos import documento_limpo, erro_de_cep, erro_de_cnpj, erro_de_ie
from .marca import ACCENT_DO_PRODUTO, AREAS_DO_PRODUTO
from .uf import erro_de_uf

__all__ = ["AparenciaDaEmpresa", "Empresa", "Filial", "ImagemDaMarca", "LUGARES_DA_IMAGEM",
           "Marca", "Modulo", "Parametro"]


#: Os campos de documento que Empresa e Filial compartilham: (coluna, tipo
#: do validador, o nome que a pessoa lê na mensagem de erro).
CAMPOS_DE_DOCUMENTO = (
    ("cnpj", "cnpj", "CNPJ"),
    ("inscricao_estadual", "ie", "Inscrição Estadual"),
    ("cep", "cep", "CEP"),
)


#: O conferidor de cada tipo de documento. `cpf` não tem: o campo existe no
#: cadastro (o cliente pode ser pessoa física), e conferir dígito de CPF é
#: coisa que ainda não foi decidida — declarar `None` aqui é mais honesto que
#: um `if tipo != "cpf"` escondido no laço.
_CONFERIDORES = {
    "cnpj": erro_de_cnpj,
    "cep": erro_de_cep,
    "ie": erro_de_ie,
    "cpf": lambda _: None,
}


def _conferir_documento(objeto, campo: str, tipo: str) -> "str | None":
    """Confere UM documento e, se ele passa, normaliza no lugar.

    Normalizar aqui (e não só na entrada da tela) é o que garante que
    `04.252.011/0001-10` e `04252011000110` são UM dado — a tela nunca é a
    única porta: shell, script e a importação dos legados gravam direto.
    """
    bruto = getattr(objeto, campo, "")
    if not bruto:
        return None

    erro = _CONFERIDORES[tipo](bruto)
    if erro:
        return erro

    normalizado = documento_limpo(tipo, bruto)
    if normalizado != bruto:
        setattr(objeto, campo, normalizado)
    return None


def _conferir_uf(objeto) -> "str | None":
    """A sigla tem que EXISTIR (as 27 do IBGE, `plataforma.uf`) — "XX" não é
    estado. Minúscula grava em maiúsculas."""
    uf = (objeto.uf or "").strip()
    if not uf:
        return None
    erro = erro_de_uf(uf)
    if erro is not None:
        return erro
    if uf != uf.upper():
        objeto.uf = uf.upper()
    return None


def _validar_documentos(objeto) -> None:
    """Valida e NORMALIZA os campos de documento de uma linha.

    A validação mora no model, não na tela, pelo motivo de sempre: a tela
    nunca é a única porta — shell, script e a futura importação dos legados
    gravam direto. Normalizar também aqui (e não só na entrada da tela) é o
    que garante que `04.252.011/0001-10` e `04252011000110` são UM dado.
    """
    from django.core.exceptions import ValidationError

    erros = {}
    for campo, tipo, rotulo in CAMPOS_DE_DOCUMENTO:
        erro = _conferir_documento(objeto, campo, tipo)
        if erro:
            erros[campo] = ValidationError(f"{erro} Campo: {rotulo}.")

    erro_uf = _conferir_uf(objeto)
    if erro_uf:
        erros["uf"] = ValidationError(erro_uf + " Campo: UF.")

    if erros:
        raise ValidationError(erros)

#: Todo lugar onde o CLIENTE pode enviar uma imagem: a entrada, o menu e o
#: favicon do `<head>`.
#:
#: O rodapé fica de fora de propósito, e não por esquecimento: ele é a
#: assinatura do PRODUTO, e a mesma em toda instalação — o logo de lá vem de
#: `plataforma/marca.py::LOGO_DO_PRODUTO` e não tem por onde ser trocado. O
#: design system continua sabendo desenhar os três (`LUGARES_DO_LOGO`, no
#: `nucleo`, é do design system e não desta decisão); quem escolhe quais
#: estão abertos ao cliente é esta linha.
LUGARES_DA_IMAGEM = ("login", "sidebar", "favicon")


class Marca(ComGuid):
    """A cara desta instalação. Só a MW5 edita."""

    client_name = models.CharField("nome do cliente", max_length=120)
    system_name = models.CharField("nome do sistema", max_length=120, blank=True)

    # O padrão vem do próprio `Brand`, e não de um literal repetido aqui.
    # Repetir a cor criaria duas fontes do mesmo valor: se o padrão do
    # framework mudar, o default da coluna divergiria em silêncio, sem teste
    # nenhum pegando. A migração congela o valor — isso é correto, migração é
    # registro histórico; o que precisa ser único é a fonte no código.
    primary = models.CharField(
        "cor primária", max_length=9,
        default=Brand.__dataclass_fields__["primary"].default,
    )
    # O destaque foge da regra acima, e o motivo é o oposto dela: o padrão do
    # `Brand` é `#872d00`, um marrom que veio do Sementes Premix. Herdá-lo
    # aqui faria toda instalação que ABRISSE a Aparência e salvasse trocar o
    # ciano da marca do KRONOS por aquele marrom, sem pedir. A fonte única
    # continua existindo — só que é a da CASA, em `plataforma/marca.py`.
    accent = models.CharField(
        "cor de destaque", max_length=9, default=ACCENT_DO_PRODUTO,
    )

    #: 6px, e não os 12px de antes: o cliente pediu menos arredondado, e este
    #: é o lugar certo para essa escolha — a marca vem do banco, então cada
    #: instalação ajusta a sua sem publicar versão nova.
    radius = models.CharField("arredondamento", max_length=8, default="6px")
    #: O arredondamento dos controles (botão, campo). Existe à parte porque
    #: um cartão de 6px com um botão de 9px dentro fica visivelmente torto.
    radius_control = models.CharField(
        "arredondamento dos controles", max_length=8, default="4px")
    density = models.CharField("densidade", max_length=16, default="normal")
    sidebar_width = models.CharField("largura do menu", max_length=8, default="256px")
    shadows = models.BooleanField("sombras", default=True)
    zebra = models.BooleanField("tabela listrada", default=False)

    # As cores por área. Em branco significa "herda do tema" — que é como
    # quase tudo fica. O Sementes Premix, por exemplo, tem a primária azul e
    # o menu verde, e é só isto que ele preenche.
    # Menu com cor própria por padrão, e não em branco: `blank` aqui quer
    # dizer "herda do tema", e herdar deixaria o menu num azul derivado da
    # primária em vez do azul-marinho DO LOGO. Quem abre a Aparência e salva
    # sem mexer não escolheu perder a cor da marca — só salvou.
    sidebar_bg = models.CharField(
        "fundo do menu", max_length=9, blank=True,
        default=AREAS_DO_PRODUTO.sidebar_bg,
    )
    sidebar_text = models.CharField(
        "texto do menu", max_length=9, blank=True,
        default=AREAS_DO_PRODUTO.sidebar_text,
    )
    header_bg = models.CharField("fundo do cabeçalho", max_length=9, blank=True)
    header_text = models.CharField("texto do cabeçalho", max_length=9, blank=True)
    content_bg = models.CharField("fundo do conteúdo", max_length=9, blank=True)
    footer_bg = models.CharField("fundo do rodapé", max_length=9, blank=True)
    footer_text = models.CharField("texto do rodapé", max_length=9, blank=True)

    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    # Os rótulos do contexto no cabeçalho (item 7 do Bloco 3): a rede que
    # fala "bandeira e loja" escreve aqui, e o seletor de toda tela segue —
    # o design system já lia `Brand.header.context_labels`; o que faltava
    # era onde o cliente escreve. Em branco herda o padrão da casa, como as
    # cores de área acima.
    rotulo_da_empresa = models.CharField(
        "rótulo da empresa", max_length=40, blank=True)
    rotulo_da_filial = models.CharField(
        "rótulo da filial", max_length=40, blank=True)

    class Meta:
        verbose_name = "marca"
        verbose_name_plural = "marcas"

    def __str__(self) -> str:
        return self.client_name

    #: Os campos de cor por área, na ordem em que a tela os mostra.
    AREAS = (
        "sidebar_bg", "sidebar_text", "header_bg", "header_text",
        "content_bg", "footer_bg", "footer_text",
    )

    def para_brand(self) -> Brand:
        """Monta o `Brand` que o design system consome.

        Campo em branco é **omitido** do dicionário, e não passado como `""`:
        o `Brand` tem o próprio padrão para cada um, e mandar string vazia
        viraria um token vazio no CSS — borda que some, texto invisível.
        """
        dados: dict = {
            "client_name": self.client_name,
            "primary": self.primary,
            "accent": self.accent,
            "radius": self.radius,
            "radius_control": self.radius_control,
            "density": self.density,
            "sidebar_width": self.sidebar_width,
            "shadows": self.shadows,
            "zebra": self.zebra,
        }
        if self.system_name:
            dados["system_name"] = self.system_name

        areas = {campo: getattr(self, campo) for campo in self.AREAS
                 if getattr(self, campo)}
        if areas:
            dados["areas"] = areas

        # Os rótulos do contexto: só entram quando ALGUM foi preenchido —
        # mandar o par padrão seria o mesmo que nada, mas com uma fonte a
        # mais para divergir. Slot em branco herda o padrão do `HeaderBrand`.
        rotulos = (self.rotulo_da_empresa, self.rotulo_da_filial)
        if any(rotulos):
            padroes = Brand.from_dict({"client_name": "x"}).header.context_labels
            dados["header"] = {"context_labels": (
                self.rotulo_da_empresa or padroes[0],
                self.rotulo_da_filial or padroes[1],
            )}

        return Brand.from_dict(dados)

    def clean(self) -> None:
        """Recusa marca que não vira `Brand`, no idioma que o Django espera:
        `ValidationError`, que um `ModelForm` transforma em erro de campo em
        vez de estourar 500 na cara de quem preencheu o formulário.

        A regra não é reescrita: `para_brand()` chama `Brand.from_dict`, que
        já valida cor e recusa campo desconhecido — só traduz o `ValueError`
        que ele levanta para o vocabulário de validação do Django.
        """
        super().clean()
        try:
            self.para_brand()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def save(self, *args, **kwargs):
        """Recusa gravar marca que não vira `Brand`.

        A tela de Aparência já valida no POST, mas ela não é a única porta:
        shell, migração e qualquer script gravam direto. Uma cor inválida que
        atravessasse aqui só apareceria na primeira requisição a `/tema.css` —
        com 500 para todo visitante, inclusive na tela de login, que carrega
        essa folha. O erro sairia longe da causa.

        `full_clean()` chama `clean()` (que valida a cor, acima) e também
        `clean_fields()`/`validate_unique()` — o restante da validação normal
        de model que gravar direto nunca passava antes.
        """
        self.full_clean()
        super().save(*args, **kwargs)


class Modulo(ComGuid):
    """O interruptor de um módulo nesta instalação.

    A linha nasce **desligada** e é criada pela migração, a partir do que o
    código declara. É o que impede um módulo novo de custar vinte
    intervenções manuais.

    Desligar não apaga dado nenhum: some da tela, e ligar de volta traz tudo.
    """

    chave = models.CharField("chave", max_length=60, unique=True)
    ativo = models.BooleanField("ligado", default=False)

    # Sobrescritas por cliente. Em branco significa "usa o que o código
    # declarou". Existem porque cliente pede nome e ordem próprios, e isso no
    # código viraria exceção por cliente — o custo que a matriz elimina.
    rotulo = models.CharField("rótulo", max_length=120, blank=True)
    grupo = models.CharField("grupo", max_length=120, blank=True)
    ordem = models.IntegerField("ordem", default=0)

    class Meta:
        verbose_name = "módulo"
        verbose_name_plural = "módulos"
        ordering = ("ordem", "chave")

    def __str__(self) -> str:
        return self.rotulo or self.chave


class Parametro(ComGuid):
    """O valor que ESTA instalação deu a um parâmetro declarado no código
    (`plataforma.parametro_declaracao.ParametroSpec`).

    Só existe linha aqui para quem foi mudado. Diferente de `Modulo`, esta
    tabela **não é semeada**: lá a linha precisa nascer desligada para
    existir algo a ligar pela tela; aqui a ausência já É a resposta certa —
    "use o padrão do código" —, e criar a linha adiantada faria um padrão
    novo (o código de uma versão futura) nunca alcançar quem nunca mexeu
    no valor antigo, porque a linha gravada esconderia o padrão que mudou.

    `valor` é sempre texto. Quem o converte para número ou sim/não é
    `plataforma.parametro_catalogo`, a partir do `tipo` que o `ParametroSpec`
    declara — nunca ao contrário, ou duas telas divergiriam sobre o que
    "0" quer dizer.
    """

    chave = models.CharField("chave", max_length=60, unique=True)
    valor = models.TextField("valor")

    class Meta:
        verbose_name = "parâmetro"
        verbose_name_plural = "parâmetros"

    def __str__(self) -> str:
        return self.chave


class Empresa(ComGuid):
    """Uma empresa atendida por esta instalação, com a conexão de onde o cron
    lê os dados dela no Kronos legado.

    **VÁRIAS LINHAS, e isto é uma divergência declarada do KRONOS.net.** Lá a
    empresa é uma só por instalação — dado da instalação, como a marca —, e
    por isso não existe FK de empresa em tabela nenhuma
    (`docs/superpowers/specs/2026-08-21-empresa-filial-design.md`). Aquela
    spec previu este dia e disse o custo: *"o dia em que um cliente for grupo
    econômico de verdade... o custo é acrescentar a coluna de empresa em
    `Filial`, não reescrever o modelo"*. Este é o dia, aqui, e é barato agora
    porque ainda não existe nenhuma tabela de negócio — daqui a dez telas
    seriam dez migrações.

    **A conexão é dado DA empresa, não de uma área à parte.** É como o
    `kronos-api2` sempre modelou: `api_conexao` é literalmente empresa mais
    conexão numa linha só. Uma tela de "integração" separada partiria em dois
    o que na origem sempre foi um, e obrigaria a casar os dois lados por
    nome.

    A senha é guardada CIFRADA — use `definir_senha()` / `senha_clara`, nunca
    atribua `senha` direto. `clean()` recusa o que não passou por lá.
    """

    razao_social = models.CharField("razão social", max_length=180)
    nome_fantasia = models.CharField("nome fantasia", max_length=180, blank=True)

    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    inscricao_estadual = models.CharField("inscrição estadual", max_length=20, blank=True)

    logradouro = models.CharField("logradouro", max_length=180, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    complemento = models.CharField("complemento", max_length=80, blank=True)
    bairro = models.CharField("bairro", max_length=80, blank=True)
    municipio = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)

    # -- de onde o cron lê -------------------------------------------------
    #
    # Nomes iguais aos de `api_conexao` no `kronos-api2`: o cron casa os dois
    # lados pelo NOME da coluna, e um `host` que virasse `servidor` aqui
    # quebraria a sincronia em silêncio, meses depois. Ver
    # `tests/test_empresa_esquema.py`, que trava isso.
    host = models.CharField("host", max_length=255, blank=True, default="")
    porta = models.CharField("porta", max_length=10, blank=True, default="")
    banco = models.CharField("banco", max_length=100, blank=True, default="")
    tabela = models.CharField("tabela", max_length=100, blank=True, default="")
    usuario = models.CharField("usuário", max_length=255, blank=True, default="")
    #: Cifrada. O tamanho é o da origem; o conteúdo é Fernet, não texto claro
    #: — ver `plataforma/cifra.py` para o porquê.
    senha = models.CharField("senha (cifrada)", max_length=255, blank=True, default="")

    #: **O Admin dono desta empresa — a CONTA.** Uma conta tem VÁRIAS
    #: empresas desde 17/09/2026 (spec
    #: `2026-09-17-varias-empresas-por-conta`): o que separa o dado de negócio
    #: é a coluna `empresa` de cada linha, e o `conta_guid` diz de QUEM ela é.
    #:
    #: **Nulo é um estado de verdade**, não um buraco: a MW5 cadastra a
    #: empresa antes de existir o Admin dela, e a empresa órfã (a que sobrou
    #: de um Admin que tinha duas) aparece só para a MW5, que decide o que
    #: fazer. Empresa apagada não apareceria em lugar nenhum.
    #:
    #: `PROTECT`: apagar o Admin com a empresa pendurada nele levaria junto
    #: catálogo, orçamento e o histórico inteiro daquele cliente.
    dono = models.ForeignKey(
        "contas.Usuario", verbose_name="conta", on_delete=models.PROTECT,
        null=True, blank=True, related_name="empresas_da_conta",
        help_text=_("O Admin dono desta empresa."))

    #: A mesma relação acima na identidade estável da conta. `dono_id` fica
    #: durante a transição para não quebrar as instalações existentes; toda
    #: integração nova deve usar esta coluna UUID.
    conta = models.ForeignKey(
        "contas.Usuario", verbose_name="conta por GUID", to_field="guid",
        db_column="conta_guid", on_delete=models.PROTECT, null=True,
        blank=True, related_name="+",
        help_text=_("O GUID da conta titular desta empresa."))

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        ordering = ("razao_social",)
        constraints = [
            #: Duas empresas com o mesmo CNPJ são a MESMA empresa cadastrada
            #: duas vezes — e, num condomínio, duas gavetas separadas de
            #: catálogo, usuário e orçamento para um cliente só. O erro não
            #: aparece no dia em que acontece: aparece semanas depois, quando
            #: metade dos pedidos está numa e metade na outra, e juntar as
            #: duas exige mexer em linha de orçamento fechado.
            #:
            #: `condition` deixa o vazio de fora: o CNPJ é opcional (um
            #: cliente entra no cadastro antes de o documento chegar), e sem
            #: a condição a SEGUNDA empresa sem CNPJ seria recusada.
            models.UniqueConstraint(
                fields=("cnpj",), condition=~models.Q(cnpj=""),
                name="cnpj_unico_por_instalacao",
                violation_error_message=(
                    "Já existe uma empresa com este CNPJ.")),
            #: **Não há trava de "uma empresa por conta"** desde 17/09/2026:
            #: a conta é o cliente, e o cliente pode ter mais de uma pessoa
            #: jurídica. Quem separa o dado de negócio é a coluna `empresa`
            #: de cada linha, conferida em `contas.inquilino.ModeloDaEmpresa`;
            #: o `conta_guid` continua obrigatório e derivado da empresa.
        ]

    def __str__(self) -> str:
        return self.nome_fantasia or self.razao_social

    # -- a senha do Kronos legado -----------------------------------------

    #: Como todo texto cifrado por Fernet começa. Serve para distinguir uma
    #: senha guardada certo de uma atribuída direto na coluna.
    _PREFIXO_FERNET = "gAAAAA"

    def definir_senha(self, claro: str) -> None:
        """A ÚNICA porta por onde uma senha entra nesta tabela."""
        from .cifra import cifrar

        self.senha = cifrar(claro)

    @property
    def senha_clara(self) -> str:
        """A senha pelo tempo de uma conexão. Nunca guardada, nunca logada."""
        from .cifra import decifrar

        return decifrar(self.senha)

    def clean(self) -> None:
        super().clean()
        # A validação de dígito verificador EXISTE agora (item 28) — o
        # comentário antigo sobre a ausência dela não descreve mais este
        # código.
        _validar_documentos(self)
        # O model de origem confia num comentário ("nunca atribua `senha`
        # direto"). Comentário não impede ninguém: basta um
        # `Empresa(senha=...)` num shell, ou um formulário novo que esqueça
        # da regra, e a credencial do cliente fica em claro sem nada acusar.
        if self.senha and not self.senha.startswith(self._PREFIXO_FERNET):
            raise ValidationError({
                "senha": "a senha precisa ser gravada por `definir_senha()` — "
                         "atribuir a coluna direto a deixaria em texto claro."
            })

    def save(self, *args, **kwargs):
        """Mesma porta do `Marca.save`: recusa gravar documento inválido,
        porque a tela nunca é a única porta — e um CNPJ errado que
        atravessasse só seria descoberto na nota fiscal."""
        dono_anterior = None
        if self.pk is not None:
            dono_anterior = type(self).objects.filter(pk=self.pk).values_list(
                "dono_id", flat=True).first()

        if self.dono_id is None:
            self.conta_id = None
        else:
            self.conta_id = self.dono.guid

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "dono" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"conta"}

        self.full_clean()
        from django.apps import apps
        from django.db import router, transaction

        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        dono_mudou = self.pk is not None and dono_anterior != self.dono_id
        # A alocação liga uma PESSOA e um CARGO de UMA conta (D1/D3 da spec de
        # cargos). Reatribuir `conta_guid` em silêncio, como o laço abaixo faz
        # com todo model de negócio, deixaria a alocação com `conta` da conta
        # NOVA enquanto `pessoa.dono` e `cargo.conta` continuam da conta
        # ANTIGA — uma linha que `Alocacao.clean()` recusaria se alguém
        # tentasse criá-la assim. Por isso a troca é recusada de saída,
        # enquanto houver alocação: elas saem antes (D10).
        if dono_mudou and self.alocacoes.exists():
            raise ValidationError({
                "dono": "Esta empresa tem pessoas alocadas. Remova as "
                        "alocações antes de trocar o titular."
            })
        with transaction.atomic(using=using):
            # Deixar órfã uma empresa vazia continua permitido. Com dados de
            # negócio, `conta_guid` é NOT NULL: a atualização abaixo recusa e
            # reverte também a troca da empresa, sem relação pela metade.
            super().save(*args, **kwargs)
            if dono_mudou:
                for modelo in apps.get_models():
                    nomes = {campo.name for campo in modelo._meta.fields}
                    if "empresa" not in nomes or "conta" not in nomes:
                        continue
                    modelo._base_manager.using(using).filter(
                        empresa_id=self.pk).update(conta_id=self.conta_id)


def _conta_da_empresa(linha, kwargs) -> None:
    """Copia para `linha.conta` a conta da empresa dela, e recusa a divergente.

    A mesma regra de `contas.inquilino.ModeloDaEmpresa.save`, para as duas
    tabelas da conta que moram na plataforma (Filial e AparenciaDaEmpresa),
    com uma diferença: aqui a empresa pode ainda não ter titular, e a linha
    fica sem conta em vez de ser recusada. Uma filial não é dado de negócio
    — é o lugar onde ele vai acontecer, e ele mesmo recusa empresa sem conta.

    Não importa `contas.inquilino`: `plataforma` fica ABAIXO de `contas`
    (`test_camadas_nao_se_invertem`), e são quatro linhas.
    """
    # Sem empresa não há de quem herdar, e quem recusa é o `full_clean` logo
    # depois, com a frase do campo. Ler `linha.empresa` aqui levantaria
    # `RelatedObjectDoesNotExist` antes dele — um 500 no lugar da mensagem.
    if linha.empresa_id is None:
        return
    conta_da_empresa = linha.empresa.conta_id
    if linha.conta_id is not None and linha.conta_id != conta_da_empresa:
        raise ValidationError({
            "conta": "A conta informada não é a titular desta empresa."})
    linha.conta_id = conta_da_empresa
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "empresa" in update_fields:
        kwargs["update_fields"] = set(update_fields) | {"conta"}


class Filial(ComGuid):
    """Uma unidade da empresa — o que a pessoa escolhe e troca no cabeçalho.

    `apelido` é o que aparece no seletor: mais curto que `nome`, porque
    ninguém quer "Filial Zona Norte — Depósito 2" inteiro disputando espaço
    no cabeçalho com o resto da faixa.

    `cnpj` é próprio da filial, e não herdado de `Empresa`: no Brasil cada
    filial tem o seu (mesma raiz, dígitos finais diferentes) — repetir o da
    empresa aqui seria um dado errado, não um atalho.
    """

    #: A empresa dona desta filial.
    #:
    #: No KRONOS.net esta coluna não existe: lá a empresa é uma só por
    #: instalação, e a filial não precisa dizer de quem é. Aqui a empresa é
    #: um cadastro de várias, e sem esta FK uma filial ficaria pendurada no
    #: ar — e o seletor do cabeçalho não teria como oferecer só as filiais
    #: da empresa escolhida.
    #:
    #: `PROTECT`: apagar uma empresa que ainda tem filial não pode levar as
    #: filiais junto em silêncio. Quem quiser apagar, apaga as filiais
    #: primeiro, sabendo o que está fazendo.
    #:
    #: **Obrigatória desde 14/09/2026** (`plataforma/0008`). Era `null=True`
    #: para a migração de 27/08 passar em base com filial gravada; com a filial
    #: virando lugar de alocação, filial sem empresa não teria a quem
    #: pertencer, e `contas/0017` para a atualização se encontrar alguma.
    empresa = models.ForeignKey(
        "plataforma.Empresa", verbose_name="empresa", on_delete=models.PROTECT,
        related_name="filiais")

    nome = models.CharField("nome", max_length=120, db_collation=DE_DICIONARIO)
    apelido = models.CharField("apelido", max_length=60)

    #: **O GUID da conta dona, como em toda linha da conta** (16/09/2026).
    #: Derivado da empresa em `save` (`_conta_da_empresa`), nunca gravado à
    #: mão. Nulo só enquanto a empresa não tem titular — empresa nasce antes
    #: dele, e a Matriz nasce junto com ela; quando o titular chega, `Empresa.save`
    #: regrava esta coluna com as de todas as tabelas que têm `empresa` e
    #: `conta`.
    conta = models.ForeignKey(
        "contas.Usuario", verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.PROTECT, null=True,
        blank=True, related_name="+",
        help_text=_("O GUID da conta titular da empresa desta linha."))

    # O dígito verificador é verificado de verdade (item 28) — e o que
    # grava é normalizado: só dígitos.
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)

    logradouro = models.CharField("logradouro", max_length=180, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    complemento = models.CharField("complemento", max_length=80, blank=True)
    bairro = models.CharField("bairro", max_length=80, blank=True)
    municipio = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)

    #: Desligar não apaga nada, e some do seletor e das consultas de
    #: `plataforma.contexto.filiais_de` — mesmo espírito de `Modulo.ativo`.
    ativa = models.BooleanField("ativa", default=True)

    #: A filial com que a empresa nasceu (spec 2026-09-14, D7). Marcada por
    #: campo e não pelo nome: o titular pode renomeá-la, e uma regra que
    #: procurasse "Matriz" deixaria de achá-la no primeiro "Loja Centro".
    e_matriz = models.BooleanField("é a matriz", default=False)

    def clean(self) -> None:
        super().clean()
        _validar_documentos(self)

    def save(self, *args, **kwargs):
        """Mesma porta do `Empresa.save`: documento inválido não grava.

        `validate_constraints=False`: a unicidade de `uma_matriz_por_empresa` é
        decidida pelo BANCO, sem corrida entre duas requisições — mesmo
        raciocínio de `Alocacao.save`. Sem isto, `full_clean` barraria a
        segunda Matriz com `ValidationError` antes de chegar ao banco, e o
        teste que prova a restrição (`test_uma_matriz_por_empresa`) deixaria
        de ver o `IntegrityError` que é a prova de que é o BANCO quem trava.
        """
        _conta_da_empresa(self, kwargs)
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "filial"
        verbose_name_plural = "filiais"
        # A Matriz na frente e as outras pelo nome (16/09/2026). A `ordem` que
        # vinha antes nenhuma tela preenchia, e a lista saía na ordem de
        # cadastro. Ver `comum.alfabetica` para a colação do nome.
        ordering = ("-e_matriz", "nome")
        constraints = [
            # Parcial: só as linhas marcadas contam. Sem `condition`, a
            # restrição proibiria a segunda filial NÃO matriz da mesma empresa.
            models.UniqueConstraint(
                fields=("empresa",), condition=models.Q(e_matriz=True),
                name="uma_matriz_por_empresa"),
        ]

    def __str__(self) -> str:
        return self.apelido or self.nome


class ImagemDaMarca(ComGuid):
    """Os bytes de um logo (ou do favicon) desta instalação.

    Mesmo caminho de `Usuario.avatar`, em `contas`: bytes no banco, e não em
    pasta — com vinte VPS, pasta é vinte lugares para lembrar de fazer
    backup; no banco, o backup do banco leva tudo, e a máquina vira
    descartável.

    Uma linha por lugar (`login`, `sidebar`, `footer`, `favicon`) — não há
    logo "geral": a marca que cabe na faixa da barra lateral não é a mesma
    que cabe no cartão de login, e o design system já reserva tamanho
    próprio para cada um. Reenviar substitui; o `lugar` único proíbe a
    segunda linha.
    """

    lugar = models.CharField("lugar", max_length=20, unique=True)
    conteudo = models.BinaryField("conteúdo")
    #: O media type que `nucleo.images.validar` decidiu lendo os bytes na
    #: gravação — nunca o que quem enviou afirmou. A rota serve com este
    #: valor, então ele é parte da defesa, não uma etiqueta.
    tipo = models.CharField("tipo", max_length=40)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "imagem da marca"
        verbose_name_plural = "imagens da marca"
        ordering = ("lugar",)

    def __str__(self) -> str:
        return f"{self.lugar} ({self.tipo})"

    def save(self, *args, **kwargs):
        """Valida pelo conteúdo e decide o tipo aqui — a tela não é a única
        porta. Shell, script e qualquer gravação direta passam por este
        `save()`, e um SVG com script que atravessasse só apareceria como
        HTML servido pela origem do painel — tarde demais.

        A recusa sai como `ValidationError` (e não o `ImagemInvalida` cru):
        é o idioma que um formulário do Django traduz para erro de campo,
        em vez de estourar 500 na cara de quem enviou.
        """
        if self.lugar not in LUGARES_DA_IMAGEM:
            raise ValidationError(
                f"lugar de imagem inválido: {self.lugar!r} — use um de "
                f"{', '.join(LUGARES_DA_IMAGEM)}"
            )
        from nucleo.images import ImagemInvalida, validar

        dados = bytes(self.conteudo)
        try:
            imagem = validar(dados)
        except ImagemInvalida as exc:
            raise ValidationError(str(exc)) from exc
        self.conteudo = imagem.data
        self.tipo = imagem.media_type
        super().save(*args, **kwargs)


class AparenciaDaEmpresa(ComGuid):
    """O menu de UMA empresa: logo, fundo e texto (15/09/2026).

    A marca continua sendo da instalação (`Marca`); isto é o que cada cliente
    tem de próprio por cima dela, e é pouco de propósito — é o bastante para
    o cliente se reconhecer no menu, e a forma da tela continua sendo do
    produto. Só a MW5 configura (`mw5.aparencia`), na tela de Empresas.

    Tabela à parte, e não colunas em `Empresa`, porque o logo são bytes: em
    `Empresa`, toda consulta de empresa (e são várias por tela) arrastaria a
    imagem junto.

    Campo em branco herda da instalação — ver
    `plataforma.marca.marca_da_requisicao`.
    """

    empresa = models.OneToOneField(
        "Empresa", verbose_name="empresa", on_delete=models.CASCADE,
        related_name="aparencia")
    #: **O GUID da conta dona, como em toda linha da conta** (16/09/2026).
    #: Derivado da empresa em `save` (`_conta_da_empresa`), nunca gravado à
    #: mão. Nulo só enquanto a empresa não tem titular — empresa nasce antes
    #: dele, e a Matriz nasce junto com ela; quando o titular chega, `Empresa.save`
    #: regrava esta coluna com as de todas as tabelas que têm `empresa` e
    #: `conta`.
    conta = models.ForeignKey(
        "contas.Usuario", verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.PROTECT, null=True,
        blank=True, related_name="+",
        help_text=_("O GUID da conta titular da empresa desta linha."))
    sidebar_bg = models.CharField("fundo do menu", max_length=9, blank=True)
    sidebar_text = models.CharField("texto do menu", max_length=9, blank=True)
    #: Bytes no banco, como `ImagemDaMarca.conteudo` e pelo mesmo motivo: o
    #: backup do banco leva tudo.
    logo = models.BinaryField("logo do menu", null=True, blank=True)
    #: Decidido lendo os bytes na gravação, como `ImagemDaMarca.tipo`. A rota
    #: serve com este valor, então ele é parte da defesa, não uma etiqueta.
    logo_tipo = models.CharField("tipo do logo", max_length=40, blank=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "aparência da empresa"
        verbose_name_plural = "aparências das empresas"

    def __str__(self) -> str:
        return f"Menu de {self.empresa}"

    def clean(self) -> None:
        """A cor é conferida pela MESMA regra do design system
        (`AreaColors.__post_init__`), traduzida para `ValidationError` — como
        `Marca.clean` faz. Cor que não vira token é borda que some ou texto
        invisível, e só apareceria na primeira tela do cliente."""
        super().clean()
        from nucleo.theme.brand import AreaColors

        try:
            AreaColors(sidebar_bg=self.sidebar_bg or None,
                       sidebar_text=self.sidebar_text or None)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def save(self, *args, **kwargs):
        """Valida cor e logo aqui — a tela não é a única porta. O logo passa
        pela mesma peneira de `ImagemDaMarca.save`; vazio quer dizer "sem
        logo", e não arquivo inválido."""
        _conta_da_empresa(self, kwargs)
        self.clean()
        if self.logo:
            from nucleo.images import ImagemInvalida, validar

            from .logo import sem_margem

            try:
                imagem = validar(bytes(self.logo))
            except ImagemInvalida as exc:
                raise ValidationError(str(exc)) from exc
            # Sem a margem em volta do desenho: a barra ajusta o arquivo
            # inteiro à caixa, e borda no arquivo é desenho menor no menu
            # (`plataforma/logo.py`). Depois de validar, para só abrir no
            # Pillow bytes que já se provaram imagem.
            self.logo = sem_margem(imagem.data, imagem.media_type)
            self.logo_tipo = imagem.media_type
        else:
            self.logo, self.logo_tipo = None, ""
        super().save(*args, **kwargs)


class FalhaImutavel(Exception):
    """Tentativa de alterar ou apagar uma linha de `Falha` — o par exato de
    `RegistroImutavel` (auditoria): um teste que capturasse `Exception` cru
    passaria igual contra um erro de digitação, sem provar nada."""


class Falha(ComGuid):
    """Um erro que estourou em produção, gravado dentro da instalação.

    É a metade "quem vê" do item 35: o traceback inteiro vai para o log do
    container (`docker logs`), mas o VPS às vezes é longe — aqui a MW5 abre
    `/mw5/falhas` e vê o que estourou, quando, em que rota, para quem, sem
    SSH. Append-only pelo mesmo motivo da auditoria: registro de passado não
    se edita.

    O limite, nomeado: se o BANCO for o motivo do 500, gravar aqui falha
    também — e é para isso que o middleware engole o erro de gravação em
    silêncio e deixa a exceção original subir (`plataforma.falhas`).
    """

    quando = models.DateTimeField("quando", auto_now_add=True)
    caminho = models.CharField("caminho", max_length=255)
    metodo = models.CharField("método", max_length=10)
    autor_login = models.CharField("login do autor", max_length=150, blank=True)
    autor_nome = models.CharField("nome do autor", max_length=150, blank=True)
    resumo = models.CharField("resumo", max_length=255)
    traceback = models.TextField("traceback")

    class Meta:
        verbose_name = "falha"
        verbose_name_plural = "falhas"
        ordering = ("-quando",)
        indexes = [models.Index(fields=["-quando"], name="idx_falha_quando")]

    def __str__(self) -> str:
        return f"{self.resumo} em {self.caminho}"

    def save(self, *args, **kwargs) -> None:
        if self.pk is not None:
            raise FalhaImutavel(
                "Falha é append-only: uma linha gravada não se altera.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        raise FalhaImutavel(
            "Falha é append-only: nenhuma linha se apaga.")
