"""Um model de negócio de mentira, para provar a trava do inquilino.

**App próprio, carregado só por `config/settings_test.py`.** A primeira
tentativa foi declarar este model dentro do app `acesso`, e ela contaminou a
suíte inteira: o pytest importa todos os módulos de teste na coleta, então o
model ficava registrado no catálogo do Django desde o começo — e a partir
daí QUALQUER `Empresa.delete()` da suíte consultava a tabela dele para checar
a FK `PROTECT`, quebrando testes que não têm nada a ver com isolamento.

Num app próprio com migração própria, o banco de teste cria a tabela como
cria qualquer outra, e nada disso acontece.

Existe porque a trava precisa ser provada ANTES da primeira tabela de negócio
de verdade: se ela só fosse testável depois, a primeira tabela já nasceria
sem rede.
"""

from __future__ import annotations

from django.db import models

from contas.inquilino import ModeloDaEmpresa


class ProdutoDeTeste(ModeloDaEmpresa):
    #: `Meta` própria de propósito: é o que qualquer model real faz ao
    #: precisar de `ordering` ou `app_label`, e é justamente o caso em que
    #: `base_manager_name`/`default_manager_name` do model abstrato se
    #: perdem. Provar a trava AQUI é provar que ela sobrevive ao
    #: esquecimento mais comum — ver `tests/test_regra_do_inquilino.py`.
    nome = models.CharField("nome", max_length=60)

    class Meta:
        verbose_name = "produto de teste"
        ordering = ("nome",)
