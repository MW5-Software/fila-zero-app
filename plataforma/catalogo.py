"""O cruzamento entre o que o código declara e o que o banco liga."""

from __future__ import annotations

from dataclasses import dataclass

from .declaracao import declarados

__all__ = ["ModuloLigado", "modulos_ligados", "semear"]


@dataclass(frozen=True)
class ModuloLigado:
    """Um módulo como ele está **nesta instalação**.

    Os campos já vêm resolvidos: onde a linha do banco preencheu rótulo,
    grupo ou ordem, é o do banco; onde ficou em branco, é o que o código
    declarou. Quem consome não precisa saber de onde veio cada um — e é isso
    que impede a regra de ser reimplementada em cada tela.

    `icone`, `rota` e `permissoes` não têm sobrescrita: vêm sempre do código.
    Ícone e rótulo são aparência, e o cliente pode pedir; rota e permissão
    são contrato, e deixar o banco mexer neles seria deixar o banco redefinir
    o que o código faz.
    """

    chave: str
    rotulo: str
    icone: str
    grupo: str
    rota: str
    permissoes: tuple[str, ...]
    #: Os destinos a mais do módulo. Contrato, como `rota` e `permissoes`:
    #: vem do código e o banco não mexe.
    atalhos: tuple = ()
    ordem: int = 0
    #: Vem do código como `icone`, `rota` e `permissoes`, e pelo mesmo
    #: motivo: é contrato, não aparência. O banco não decide se uma tela é
    #: da MW5.
    so_mw5: bool = False


def semear(apps=None, using=None) -> int:
    """Cria a linha faltante de cada módulo declarado, desligada.

    Roda na migração, então roda em toda instalação que receber a versão. É
    esta função que faz o módulo novo aparecer sozinho nas vinte bases.

    **Não mexe em linha que já existe.** A atualização que traz o módulo novo
    não pode apagar a escolha que a MW5 já fez nos outros.

    `using` repassa o banco que o sinal `post_migrate` entrega — mesmo
    padrão de `django.contrib.auth.management.create_permissions`, que
    também recebe `using` do sinal e repassa para o `Manager`. Sem isto, uma
    instalação com mais de um banco configurado sempre semearia no padrão,
    ignorando qual banco o `migrate` de fato migrou.
    """
    Modulo = apps.get_model("plataforma", "Modulo") if apps else _modulo()
    gerente = Modulo.objects.db_manager(using)
    existentes = set(gerente.values_list("chave", flat=True))
    # `spec.ativo_por_padrao` decide o estado de nascença — e para a imensa
    # maioria dos módulos ele é `False`. Sem essa saída, TODO módulo nasceria
    # desligado, inclusive um da própria plataforma que a tela de Perfis
    # precisa para existir: a instalação subiria com o admin do cliente sem
    # como administrar ninguém até a MW5 lembrar de ligar a chavinha — um
    # perigo na instalação, não uma funcionalidade. Instalação já existente
    # não sente nada disto: a linha `not in existentes` acima nunca mexe no
    # que já está gravado, então desligar depois continua desligado.
    novas = [Modulo(chave=spec.chave, ativo=spec.ativo_por_padrao,
                    ordem=spec.ordem)
             for spec in declarados() if spec.chave not in existentes]
    gerente.bulk_create(novas)
    return len(novas)


def modulos_ligados() -> tuple[ModuloLigado, ...]:
    """Os módulos ligados nesta instalação, já com as sobrescritas aplicadas.

    Linha no banco sem declaração no código é **ignorada**: um módulo removido
    do código deixa a linha para trás, e ela não pode virar item de menu
    apontando para uma rota que não existe mais.

    A mesclagem — banco vence código quando preenchido — mora aqui, e só
    aqui: é a regra de "o que é um módulo nesta instalação", e não uma
    decisão de tela. Se cada tela (menu, tela de Módulos) a reimplementasse,
    passariam a existir duas verdades que divergem no primeiro ajuste feito
    de um lado só.
    """
    ligadas = _modulo().objects.filter(ativo=True).order_by("ordem", "chave")
    por_chave = {spec.chave: spec for spec in declarados()}

    saida = []
    for linha in ligadas:
        spec = por_chave.get(linha.chave)
        if spec is None:
            continue
        saida.append(ModuloLigado(
            chave=spec.chave,
            rotulo=linha.rotulo or spec.rotulo,
            icone=spec.icone,
            grupo=linha.grupo or spec.grupo,
            rota=spec.rota,
            permissoes=spec.permissoes,
            atalhos=spec.atalhos,
            ordem=linha.ordem,
            so_mw5=spec.so_mw5,
        ))
    return tuple(saida)


def _modulo():
    from .models import Modulo

    return Modulo
