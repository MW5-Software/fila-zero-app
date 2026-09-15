"""O identificador que atravessa a fronteira do sistema.

Toda tabela nossa carrega um GUID. Não é a chave primária, e a diferença é
deliberada: como chave, ele seria impossível de aplicar "em todas as tabelas"
— as do Django continuariam `bigint`, e o banco ficaria metade em UUID e
metade em inteiro, que é justo a falta de uniformidade que o pedido quer
evitar. Como coluna, toda linha nossa tem um, sem exceção.

O custo do outro caminho cai no lugar mais quente: `empresa_id` está em quase
todo índice do sistema, e trocá-la por UUID multiplica por quatro o tamanho
dela em cada um.

`uuid4` (aleatório) e não `uuid7` (ordenado no tempo): o ordenado existe para
não fragmentar o índice a cada inserção, e isso pesa quando o UUID é a CHAVE.
Aqui ele é um índice secundário. `uuidv7` também é nativo só no Postgres 18, e
este roda em 16.

Ver `docs/superpowers/specs/2026-09-02-saas-identidade-e-acesso-design.md`.
"""

from __future__ import annotations

from uuid import uuid4

from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = ["ComGuid"]


class ComGuid(models.Model):
    guid = models.UUIDField(
        "GUID", unique=True, default=uuid4, editable=False,
        help_text=_("Identificador estável desta linha para fora do sistema."),
    )

    class Meta:
        abstract = True
