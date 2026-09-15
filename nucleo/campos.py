"""Os campos de um formulário: o que a pessoa declara e o que isso vira.

Mora em `nucleo`, não em `mw5_generator`: quem desenha formulário de
verdade em tempo de execução — o `Resource` — só tem acesso ao que o projeto
gerado empacota, e o projeto gerado só empacota `nucleo`. Guardar o modelo
do campo no gerador exigiria um segundo modelo, mais pobre, aqui dentro — e
esta branch já gastou duas rodadas matando esse tipo de duplicação.

[`mw5_generator` e `corpo.py` são vocabulário da fonte: não existem no
KRONOS.net, que não gera projeto por cliente — os dois parágrafos abaixo
descrevem a arquitetura de origem, não algo presente aqui.]

Como nos blocos de `corpo.py`, cada tipo tem **uma** descrição — em
`_DESCRICOES` —, e `chamadas_dos_campos` é quem a expõe para os dois lados
que precisam dela: `montar_campos`, aqui, a instancia para quem desenha de
verdade (o `Resource`, o bloco Formulário da prévia); o bloco Formulário do
gerador (`corpo.py`) embute a mesma `chamadas_dos_campos` na própria árvore
que escreve. `codigo_dos_campos`, em `mw5_generator.campos`, escreve essa
descrição como texto Python isolada — é o caminho que o cadastro CRUD usava
antes de declarar o próprio `Campo` em vez do widget (veja
`mw5_generator.campos.codigo_da_lista_de_campos`, o caminho atual). Só o
gerador escreve texto Python — é por isso que `codigo_dos_campos` e
`imports_dos_campos` **não** moraram para cá: o framework nunca escreve
arquivo.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from . import icons as icones
from .descricao import Chamada, instanciar

__all__ = ["Campo", "LARGURAS", "TIPOS_DE_CAMPO", "campos_de_json",
           "MASCARAS", "chamadas_dos_campos", "montar_campos", "nome_do_campo",
           "rotulo_do_registro"]

#: Os nove tipos e o rótulo que o painel mostra.
TIPOS_DE_CAMPO: dict[str, str] = {
    "texto": "Texto",
    "area": "Área de texto",
    "numero": "Número",
    "moeda": "Moeda",
    "data": "Data",
    "selecao": "Seleção",
    "sim_nao": "Sim/Não",
    "arquivo": "Arquivo",
    #: Aponta para outro cadastro. O que se guarda é o id dele, e o `alvo` diz
    #: qual — muitos-para-um: muitos Pedidos para um Cliente.
    "relacao": "Relação",
}

#: As máscaras que um campo de texto pode vestir, e o rótulo do seletor.
#:
#: **Visuais.** O valor gravado sai com a pontuação — que é como os sistemas
#: legados normalmente já guardam —, e nada aqui valida nem normaliza: a
#: máscara ajuda quem digita, não decide o formato do dado.
#:
#: Os padrões de fato moram no `mw5.js`, porque é lá que se digita. Esta lista
#: é o que o painel oferece, e um teste de contrato compara as duas.
MASCARAS: dict[str, str] = {
    "cpf": "CPF",
    "cnpj": "CNPJ",
    #: Um campo só para pessoa física e jurídica — o caso mais comum aqui.
    "cpf_cnpj": "CPF ou CNPJ",
    "telefone": "Telefone",
    "cep": "CEP",
}

#: As larguras que a grade de 12 divide sem sobra. Um campo de 5 colunas deixa
#: um buraco de 2 na linha, e a tela fica torta sem ninguém entender por quê.
LARGURAS: dict[int, str] = {12: "Inteira", 6: "Metade", 4: "Um terço",
                            3: "Um quarto"}


@dataclass
class Campo:
    rotulo: str
    tipo: str = "texto"
    largura: int = 6
    obrigatorio: bool = False
    ajuda: str = ""
    opcoes: list[str] = field(default_factory=list)
    #: Só `tipo="texto"` usa. Visual: ver `MASCARAS`.
    mascara: str = ""
    #: Só `tipo="relacao"` usa: a **rota** do cadastro apontado (`/clientes`).
    #: Rota, e não rótulo, porque é o que o `Resource` do outro lado conhece de
    #: si mesmo — e é a chave do catálogo.
    alvo: str = ""
    #: O ícone à esquerda do campo. Nome do catálogo do design system, como o
    #: dos itens de menu — nunca um caminho de arquivo, para que trocar o jogo
    #: de ícones não quebre formulário nenhum.
    icone: str = ""
    #: A unidade à direita: `kg`, `%`, `R$`. Texto curto e fixo, e não um
    #: segundo campo — quem preenche não escolhe a unidade, ela é do campo.
    sufixo: str = ""
    #: O exemplo que aparece DENTRO da caixa enquanto ela está vazia — "Seu
    #: e-mail", "0,00", "Selecione a filial".
    #:
    #: Diferente de `ajuda`, que fica embaixo do campo e continua lá depois de
    #: preenchido. A dica some assim que se digita: ela mostra o FORMATO
    #: esperado, e por isso nunca substitui o rótulo — um campo preenchido cuja
    #: única identificação era a dica não diz mais o que ele é.
    dica: str = ""
    #: O campo já vem preenchido com isto.
    #:
    #: Sozinho é valor inicial: quem preenche pode trocar. Junto com
    #: `somente_leitura` vira dado fixo — que era o par que faltava, porque um
    #: campo só-leitura sem valor é uma caixa cinza vazia.
    #:
    #: No cadastro CRUD ele só vale na tela de criar: ao editar, o que está
    #: gravado no registro é que manda (ver `Resource._formulario`).
    valor: str = ""
    #: Mostra e não deixa mexer. É o dado que a tela apresenta como contexto —
    #: a origem fixa de uma operação, o CNPJ de quem já está logado. Continua
    #: sendo enviado: `readonly`, e não `disabled`, porque um campo desligado
    #: some do envio e o back-end receberia um formulário incompleto.
    somente_leitura: bool = False
    #: Começa uma fileira nova da grade, sem mudar de largura.
    #:
    #: A largura sozinha não responde "ao lado ou embaixo": dois campos de meia
    #: largura SEMPRE emparelham. Para pôr o segundo embaixo do primeiro só
    #: havia alargar um dos dois — o layout ficava refém do tamanho.
    quebra_linha: bool = False

    @property
    def nome(self) -> str:
        """O `name` do HTML, que é também o nome da coluna.

        Um lugar só, de propósito. Com duas derivações — uma para o formulário
        e outra para o banco — uma relação gravaria em `cliente` e o banco
        leria `cliente_id`: sem erro nenhum, com o campo sempre vazio.

        A relação ganha `_id` porque é isso que ela guarda, e é o nome que
        alguém escreveria à mão. O sufixo não dobra num rótulo que já termina
        em "id".
        """
        base = nome_do_campo(self.rotulo)
        if self.tipo != "relacao":
            return base
        return base if base.endswith("_id") or base == "id" else base + "_id"


def _largura(valor) -> int:
    """A largura permitida mais próxima. Ajustada, não recusada."""
    try:
        pedida = int(valor)
    except (TypeError, ValueError):
        return 6
    return min(LARGURAS, key=lambda l: (abs(l - pedida), l))


#: Os tipos que têm uma caixa de digitar onde encostar ícone e sufixo. Fora
#: deles — Sim/Não, Arquivo, Seleção — não há onde pôr, e um ajuste que a tela
#: ignora é o pior tipo de ajuste: ele não dá erro.
COM_ADORNO: tuple[str, ...] = ("texto", "numero", "moeda", "data", "relacao")

#: Os tipos onde a dica tem onde aparecer. Nos quatro primeiros ela é o
#: `placeholder` da caixa; na Seleção é a primeira opção, a que hoje diz
#: "Selecione…" — é a mesma pergunta ("o que aparece enquanto está vazio"),
#: só que respondida com o elemento que cada tipo tem.
#:
#: Fora daqui não há onde escrevê-la, e o ajuste seria daqueles que a tela
#: ignora sem dar erro: num `<input type="date">` o navegador desenha o próprio
#: formato e descarta o `placeholder`; num Sim/Não e num Arquivo não existe
#: caixa em branco. A Relação fica de fora porque a primeira opção dela já
#: carrega um recado do sistema — "Cadastro não encontrado", quando o alvo
#: sumiu —, e uma dica escrita à mão o apagaria justo quando ele importa.
COM_DICA: tuple[str, ...] = ("texto", "area", "numero", "moeda", "selecao")

#: Os tipos que aceitam vir preenchidos. Um Arquivo não aceita — o navegador
#: proíbe, por segurança, que uma página escolha arquivo por quem usa. Um
#: Sim/Não guarda marcação, não texto. Uma Relação guarda o id de outro
#: registro, e digitar id à mão é o tipo de ajuste que só erra.
COM_VALOR: tuple[str, ...] = ("texto", "area", "numero", "moeda", "data",
                              "selecao")


def campos_de_json(cru: Any) -> "list[Campo]":
    """A lista do painel em `Campo`, tolerando o que vier torto.

    Uma string vale como campo de texto: é assim que `fields` sempre foi, e é o
    que mantém o catálogo embutido e todo projeto já gerado funcionando. Um
    `Campo` já pronto passa direto: `MenuItem` e `ModuleSpec` copiam `fields`
    um do outro, e cada cópia normaliza de novo — sem isso, o segundo passo
    veria só objetos que não são nem string nem dicionário, e derrubaria a
    lista inteira.
    """
    if isinstance(cru, (str, bytes)) or cru is None:
        try:
            cru = json.loads(cru or "[]")
        except (ValueError, TypeError):
            return []
    if not isinstance(cru, list):
        return []

    saida: list[Campo] = []
    for item in cru:
        if isinstance(item, Campo):
            saida.append(item)
            continue
        if isinstance(item, str):
            saida.append(Campo(rotulo=item.strip() or "Campo"))
            continue
        if not isinstance(item, dict):
            continue
        tipo = str(item.get("tipo") or "texto")
        if tipo not in TIPOS_DE_CAMPO:
            tipo = "texto"
        alvo = str(item.get("alvo") or "").strip()
        # Relação sem alvo vira texto: um select que não sabe para onde aponta
        # não tem opção nenhuma, e seria um campo permanentemente vazio sem
        # ninguém entender por quê. E `alvo` só sobrevive na relação — guardado
        # num campo de texto, ele viraria uma segunda verdade sobre o tipo.
        if tipo == "relacao" and not alvo:
            tipo = "texto"
        if tipo != "relacao":
            alvo = ""
        mascara = str(item.get("mascara") or "").strip()
        # Só em texto, e só se existir. Numa data ou num checkbox ela não tem o
        # que formatar, e guardada ali viraria uma segunda verdade sobre o tipo.
        if tipo != "texto" or mascara not in MASCARAS:
            mascara = ""
        # Ícone e sufixo são adornos de um campo de digitar. Num checkbox ou num
        # arquivo não há caixa onde encostá-los, e guardá-los ali seria um
        # ajuste que a tela ignora — o pior tipo, porque não dá erro.
        icone = str(item.get("icone") or "").strip()
        sufixo = str(item.get("sufixo") or "").strip()
        if tipo not in COM_ADORNO:
            icone = sufixo = ""
        # Nome que o catálogo não conhece vira nenhum ícone, e não uma tela
        # derrubada: isto roda a cada tecla digitada no construtor, e quem
        # digita "ma" mirando "map-pin" passa por aqui a caminho do nome certo.
        # Mesma decisão que o ícone do item de menu já toma.
        if icone and not icones.existe(icone):
            icone = ""
        # Mesma disciplina do adorno: guardadas num tipo que não as desenha,
        # dica e valor virariam uma segunda verdade sobre o campo — o painel
        # mostraria os dois preenchidos e a tela não mostraria nada.
        dica = str(item.get("dica") or "").strip()
        valor = str(item.get("valor") or "").strip()
        if tipo not in COM_DICA:
            dica = ""
        if tipo not in COM_VALOR:
            valor = ""
        saida.append(Campo(
            rotulo=str(item.get("rotulo") or "").strip() or "Campo",
            tipo=tipo,
            largura=_largura(item.get("largura")),
            obrigatorio=bool(item.get("obrigatorio")),
            ajuda=str(item.get("ajuda") or "").strip(),
            opcoes=[str(o).strip() for o in (item.get("opcoes") or [])
                    if str(o).strip()],
            alvo=alvo,
            mascara=mascara,
            icone=icone,
            sufixo=sufixo,
            dica=dica,
            valor=valor,
            somente_leitura=bool(item.get("somente_leitura")),
            quebra_linha=bool(item.get("quebra_linha")),
        ))
    return saida


_NAO_IDENTIFICADOR = re.compile(r"[^a-z0-9]+")


def nome_do_campo(rotulo: str) -> str:
    """O `name` do HTML a partir do rótulo, sem acento e sem espaço.

    Começa com `n` quando o rótulo começa com dígito: o `name` vira nome de
    coluna e de atributo no código gerado, e identificador não abre com número.
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", rotulo)
        if not unicodedata.combining(c)
    )
    limpo = _NAO_IDENTIFICADOR.sub("_", sem_acento.lower()).strip("_")
    if not limpo:
        return "campo"
    return f"n{limpo}" if limpo[0].isdigit() else limpo


def _comuns(campo: "Campo") -> dict:
    kwargs: dict = {"name": campo.nome, "label": campo.rotulo,
                    "span": campo.largura}
    if campo.obrigatorio:
        kwargs["required"] = True
    if campo.ajuda:
        kwargs["help"] = campo.ajuda
    # `readonly`, e não `disabled`: um campo desligado some do envio, e o
    # back-end receberia um formulário sem a origem que a tela mostrava.
    if campo.somente_leitura:
        kwargs["readonly"] = True
    if campo.quebra_linha:
        kwargs["quebra_linha"] = True
    if campo.icone:
        kwargs["icon"] = campo.icone
    if campo.sufixo:
        kwargs["suffix"] = campo.sufixo
    # A Seleção não passa por aqui com a dica: nela a dica é a primeira opção,
    # e `_selecao` a coloca em `empty_label`. Um `placeholder` num `<select>`
    # é atributo que o navegador ignora — o pior desfecho, porque não dá erro.
    if campo.dica and campo.tipo != "selecao":
        kwargs["placeholder"] = campo.dica
    if campo.valor:
        kwargs["value"] = campo.valor
    return kwargs


def _texto(campo):
    kwargs = _comuns(campo)
    if campo.mascara:
        # `type="text"` continua: `number` recusaria ponto e barra, que é
        # justamente o que a máscara põe. `inputmode` dá o teclado numérico no
        # celular — as cinco máscaras são só dígitos.
        kwargs["attrs"] = {"data-mascara": campo.mascara, "inputmode": "numeric"}
    return Chamada("TextInput", kwargs=kwargs)
def _area(campo): return Chamada("Textarea", kwargs={**_comuns(campo), "rows": 3})
def _numero(campo): return Chamada("TextInput", kwargs={**_comuns(campo), "type": "number"})
def _data(campo): return Chamada("TextInput", kwargs={**_comuns(campo), "type": "date"})
def _sim_nao(campo): return Chamada("Checkbox", kwargs=_comuns(campo))
def _arquivo(campo): return Chamada("FileInput", kwargs=_comuns(campo))


def _moeda(campo):
    # Texto e não `number`: `number` recusa vírgula, que é como se escreve
    # dinheiro aqui. `inputmode` dá o teclado numérico no celular sem uma linha
    # de JavaScript, e a máscara fica fora de propósito.
    # `_comuns` DEPOIS do padrão, e não antes: escrito na outra ordem, o
    # "0,00" sobrescreveria a dica que a pessoa acabou de digitar, e o campo
    # de moeda seria o único onde esse ajuste não pega.
    return Chamada("TextInput", kwargs={
        "placeholder": "0,00", **_comuns(campo),
        "attrs": {"inputmode": "decimal"}})


def _selecao(campo):
    return Chamada("Select", kwargs={
        **_comuns(campo),
        "empty_label": campo.dica or "Selecione…",
        "options": [Chamada("Option", args=[o, o]) for o in campo.opcoes],
    })


def rotulo_do_registro(registro: Any, campos: "list[Campo]") -> str:
    """Como um registro se apresenta numa lista de escolha.

    O **primeiro campo de texto**, e não o primeiro campo: com uma data na
    frente, a data viraria o nome do cliente no select e ninguém acharia quem
    procura. Sem campo de texto nenhum, `#12` — melhor do que uma opção em
    branco, que faz a lista parecer ter registros vazios.
    """
    for campo in campos:
        if campo.tipo not in ("texto", "area", "selecao"):
            continue
        valor = str(getattr(registro, campo.nome, "") or "").strip()
        if valor:
            return valor
    return f"#{getattr(registro, 'id', '?')}"


def _opcoes_da_relacao(campo: "Campo") -> "tuple[list, bool]":
    """As opções de um campo de relação, e se ele está utilizável.

    Alvo que não existe no catálogo devolve lista vazia e `False` — o select
    sai desabilitado em vez de levantar. Um cadastro pode ter sido removido do
    menu depois de outro passar a apontar para ele, e isto roda no sistema do
    cliente: derrubar a tela de Pedidos porque alguém apagou Clientes é pior do
    que mostrar um campo que não dá para preencher.
    """
    from . import catalogo

    alvo = catalogo.procurar(campo.alvo)
    if alvo is None:
        return [], False

    # Sem paginação: um select com mil opções já é a tela errada, e resolver
    # isso é busca com autocompletar — outro assunto, e não este.
    pagina = alvo.repositorio.listar(por_pagina=1000)
    return [Chamada("Option", args=[str(r.id),
                                    rotulo_do_registro(r, alvo.campos)])
            for r in pagina.itens], True


def _relacao(campo):
    opcoes, existe = _opcoes_da_relacao(campo)
    kwargs = {
        **_comuns(campo),
        "empty_label": "Selecione…" if existe else "Cadastro não encontrado",
        "options": opcoes,
    }
    if not existe:
        kwargs["attrs"] = {"disabled": True}
    return Chamada("Select", kwargs=kwargs)


_DESCRICOES = {"texto": _texto, "area": _area, "numero": _numero,
               "moeda": _moeda, "data": _data, "selecao": _selecao,
               "sim_nao": _sim_nao, "arquivo": _arquivo, "relacao": _relacao}


def chamadas_dos_campos(campos: "list[Campo]") -> list:
    """A descrição de cada campo — o que `montar_campos` instancia e
    `codigo_dos_campos` (em `mw5_generator.campos`) escreve, e o que o bloco
    Formulário usa para montar a grade dentro do próprio `Card`. Pública
    porque outros módulos também precisam dela: `corpo.py`, no gerador, não
    instancia nem escreve campo nenhum sozinho, ele delega — e delegar num
    nome privado acopla os módulos pela porta dos fundos.

    [`mw5_generator` e `corpo.py` são vocabulário da fonte: não existem no
    KRONOS.net, que não gera projeto por cliente.]"""
    return [_DESCRICOES[c.tipo](c) for c in campos]


def montar_campos(campos: "list[Campo]") -> list:
    return [instanciar(c) for c in chamadas_dos_campos(campos)]
