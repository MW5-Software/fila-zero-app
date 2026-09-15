"""A trava do condomínio: toda tabela de negócio carrega a empresa, e a
consulta que esquece do contexto vem VAZIA — nunca cheia.

Este é o arquivo mais importante do produto, e o motivo cabe numa frase: um
`.filter()` esquecido numa consulta mostra a tabela de preços de um cliente
para o concorrente dele, e ninguém percebe.

**O modo de falha é escolhido, não herdado.** Um manager comum devolve tudo
por padrão, então esquecer o filtro vaza — e o sintoma é invisível, porque a
tela funciona. Aqui `objects` nasce VAZIO sem contexto: esquecer produz uma
tela em branco, que alguém reclama no mesmo dia. Trocar um defeito invisível
por um barulhento é a coisa mais valiosa que se pode fazer com isolamento.

**Por que existem dois managers.** `irrestritos` é o padrão do Django
(`default_manager_name`), e não é descuido: `dumpdata`, o comando de backup,
as migrações e o acesso por relação (`empresa.produtos`) usam o
`_default_manager`. Se ele viesse vazio, o backup desta instalação
exportaria zero linhas — em silêncio, e só se descobriria no dia de
restaurar. Quem escreve tela usa `objects`; quem precisa do irrestrito
escreve o nome por extenso, e o nome é a bandeira na revisão.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from comum.guid import ComGuid

__all__ = ["GerenteDaEmpresa", "ModeloDaEmpresa"]


class GerenteDaEmpresa(models.Manager):
    """Vazio por padrão; cheio só depois de dizer de quem é a consulta."""

    def get_queryset(self):
        """**Nada**, de propósito.

        `Produto.objects.all()` numa tela é um esquecimento, e aqui ele
        aparece como lista vazia. A alternativa — devolver tudo — é a mesma
        linha de código com um vazamento dentro.
        """
        return super().get_queryset().none()

    def da_empresa(self, empresa):
        """As linhas de UMA empresa."""
        if empresa is None or empresa.conta_id is None:
            return super().get_queryset().none()
        return super().get_queryset().filter(
            empresa=empresa, conta_id=empresa.conta_id)

    def da_conta(self, conta):
        """As linhas de UMA conta, relacionadas pelo GUID dela."""
        if conta is None:
            return super().get_queryset().none()
        return super().get_queryset().filter(conta=conta)

    def de(self, usuario):
        """As linhas das empresas que `usuario` alcança.

        É a mesma `empresas_alcancadas` que o cabeçalho e a tela de usuários
        usam — não uma segunda regra de visibilidade. Duas regras divergem no
        primeiro ajuste feito de um lado só, e a que divergir para mais é o
        vazamento.
        """
        from .alcance import empresas_alcancadas

        return super().get_queryset().filter(empresa__in=empresas_alcancadas(usuario))

    def do_contexto(self, request):
        """As linhas da empresa escolhida no cabeçalho desta sessão.

        É o caminho normal de uma tela: o que se vê é o que pertence à
        empresa em que a pessoa está trabalhando agora.
        """
        from plataforma.contexto import empresa_atual

        return self.da_empresa(empresa_atual(request))


class ModeloDaEmpresa(ComGuid):
    """A base de toda tabela de dado de negócio deste portal.

    Herdar disto dá três coisas de uma vez: a coluna do inquilino, o manager
    que falha vazio, e a passagem pela varredura
    (`tests/test_regra_do_inquilino.py`), que recusa model de negócio sem
    ela. Model novo que esqueça não vai para produção — fica vermelho na
    suíte.
    """

    empresa = models.ForeignKey(
        "plataforma.Empresa", verbose_name="empresa",
        on_delete=models.PROTECT, related_name="+")

    #: A fronteira estável do cliente. A coluna física guarda o GUID da conta,
    #: não o id sequencial desta instalação. Cada linha continua tendo o seu
    #: próprio `guid`; `conta_guid` é o GUID compartilhado por todas as linhas
    #: pertencentes à mesma conta.
    conta = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.PROTECT, related_name="+",
        help_text="A conta dona desta linha, identificada pelo GUID.")

    #: **A ORDEM AQUI CARREGA PESO.** O primeiro manager declarado é o
    #: `_default_manager` do Django, e é ele que `dumpdata`, o comando de
    #: backup, as migrações e o acesso por relação usam. Com o vazio nessa
    #: posição, o backup desta instalação exportaria zero linhas — em
    #: silêncio, e só se descobriria no dia de restaurar.
    #:
    #: A `Meta` abaixo diz o mesmo por nome, mas **não dá para confiar só
    #: nela**: um model filho que declare a própria `Meta` sem herdar desta
    #: perde `base_manager_name` e `default_manager_name` — e é o que
    #: qualquer pessoa escreve ao precisar de um `app_label` ou de um
    #: `ordering`. A ordem sobrevive a esse esquecimento; o nome não.
    #: `tests/test_regra_do_inquilino.py` prova as duas pontas.
    irrestritos = models.Manager()

    #: O que as telas usam. Vazio sem contexto.
    objects = GerenteDaEmpresa()

    class Meta:
        abstract = True
        base_manager_name = "irrestritos"
        default_manager_name = "irrestritos"

    def save(self, *args, **kwargs):
        """Valida ANTES de gravar — a mesma porta que `Empresa` e `Marca` já
        tinham, agora para toda tabela de negócio.

        **Existe porque um texto colado devolvia HTTP 500.** O Django só
        confere `max_length` em `full_clean()`, que ninguém chama sozinho: um
        nome de produto com 300 caracteres ia inteiro para o Postgres, que
        recusava com `value too long for type character varying(180)`, e a
        pessoa via "Algo inesperado aconteceu". Os campos nem `maxlength` no
        HTML tinham — bastava colar uma descrição no campo errado.

        O lugar é aqui e não em cada view: são dezenas de campos (código,
        nome, marca, unidade, modelo, código OEM…) e a lista cresce a cada
        tabela nova. Uma checagem por view seria uma lista para esquecer;
        aqui a tabela nova nasce protegida.

        `validate_unique=False`: a unicidade continua sendo do BANCO, que é
        quem decide sem corrida entre duas requisições simultâneas. Conferir
        aqui gastaria uma consulta por gravação para dar a mesma resposta com
        menos garantia. As telas que precisam da frase amigável (o código
        repetido do produto) já perguntam antes, de propósito.

        Quem chama continua responsável por capturar `ValidationError` e
        virar frase na tela.
        """
        # A empresa continua presente durante a transição, mas já não decide
        # sozinha a fronteira: a conta é materializada em cada linha. Fazer a
        # derivação aqui mantém as duas colunas coerentes para todas as portas
        # normais do ORM. `bulk_create` deve preencher `conta` explicitamente.
        empresa = self.empresa
        if empresa.conta_id is None:
            raise ValidationError({
                "empresa": "A empresa precisa ter uma conta titular antes "
                           "de receber dados de negócio."
            })

        conta_guid = empresa.conta_id
        if self.conta_id is not None and self.conta_id != conta_guid:
            raise ValidationError({
                "conta": "A conta informada não é a titular desta empresa."
            })
        self.conta_id = conta_guid

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "empresa" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"conta"}

        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)
