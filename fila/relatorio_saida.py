"""O relatório no papel e na planilha (28/09/2026).

Os dois leem o MESMO `fila.relatorio.Relatorio`. O Excel grava NÚMERO nas
colunas de número (somável, filtrável), com o formato de moeda e de
porcentagem na célula; o papel escreve o texto com `relatorio.formatar`.
"""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _

from comum.exportacao import CONTENT_TYPE_XLSX

from .graficos import dinheiro_curto, escala
from .relatorio import Relatorio, formatar

__all__ = ["em_impressao", "em_xlsx"]

_FORMATO = {"dinheiro": 'R$ #,##0.00', "porcento": "0.0%", "inteiro": "0",
            "minutos": "0"}


def _celula(valor, tipo):
    """O valor que a célula GRAVA. Porcentagem vai como fração (12,5% é
    0,125), que é o que o formato `0.0%` do Excel espera."""
    if valor is None or valor == "":
        return None
    if tipo == "dinheiro":
        return float(Decimal(valor))
    if tipo == "porcento":
        return float(valor) / 100
    if tipo == "minutos":
        return int(valor.total_seconds() // 60) if isinstance(valor, timedelta) else int(valor)
    if tipo == "inteiro":
        return int(valor)
    return str(valor)


def _nada_e_formula(livro) -> None:
    """O relatório não escreve fórmula nenhuma, e o openpyxl grava como
    FÓRMULA todo texto que começa com "=". A observação da não venda é o
    vendedor quem digita, e o nome de loja, de pessoa e de cadastro é dado do
    cliente: um `=HYPERLINK(...)` ali viraria link vivo na planilha do gerente
    (revisão final de 28/09/2026). Forçar o tipo texto guarda o que foi
    digitado, letra por letra, sem o Excel interpretar."""
    for folha in livro.worksheets:
        for linha in folha.iter_rows():
            for celula in linha:
                if celula.data_type == "f":
                    celula.data_type = "s"


def em_xlsx(relatorio: Relatorio) -> HttpResponse:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    livro = Workbook()
    capa = livro.active
    capa.title = _("Relatório")
    for rotulo, valor in (
            (_("Relatório"), relatorio.titulo), (_("Empresa"), relatorio.empresa),
            (_("Lojas"), relatorio.lojas), (_("Período"), relatorio.periodo),
            (_("Gerado por"), relatorio.gerado_por),
            (_("Gerado em"), timezone.localtime(relatorio.gerado_em).strftime("%d/%m/%Y %H:%M"))):
        capa.append([rotulo, valor])
    for secao in relatorio.secoes:
        # O formato limita o nome da aba a 31 caracteres.
        folha = livro.create_sheet(secao.titulo[:31])
        folha.append([c.rotulo for c in secao.colunas])
        for celula in folha[1]:
            celula.font = Font(bold=True)
        for linha in secao.linhas:
            folha.append([_celula(c.valor(linha), c.tipo) for c in secao.colunas])
        for indice, coluna in enumerate(secao.colunas, start=1):
            formato = _FORMATO.get(coluna.tipo)
            if formato:
                for (celula,) in folha.iter_rows(min_row=2, min_col=indice, max_col=indice):
                    celula.number_format = formato
    _nada_e_formula(livro)
    resposta = HttpResponse(content_type=CONTENT_TYPE_XLSX)
    resposta["Content-Disposition"] = f'attachment; filename="{relatorio.nome_do_arquivo}.xlsx"'
    livro.save(resposta)
    return resposta


def _papel(relatorio: Relatorio) -> dict:
    """O que o papel desenha, arrumado a partir do MESMO relatório da
    planilha (28/09/2026). Não há conta aqui: só ordem, fatias para as barras
    e o texto de cada linha."""
    from .relatorio import (PERIODOS, chamada_do_periodo, grupos_do_lancamento,
                            motivo_do_lancamento, placar)

    secoes = {s.chave: s for s in relatorio.secoes}
    total = relatorio.total
    n_lojas = len(relatorio.nomes_das_lojas)
    resumo = secoes["resumo"].linhas

    def fatia(parte, todo):
        return float(parte) * 100 / float(todo) if todo else 0.0

    # A rosca das lojas: cada pedaço começa onde o anterior terminou, na cor
    # de série do tema (as oito `--chart-N`, repetidas depois da oitava).
    lojas, inicio = [], 0.0
    for i, l in enumerate(resumo[1:1 + n_lojas]):
        parte = fatia(l.numeros.vendido, total.vendido)
        lojas.append({"nome": l.rotulo, "n": l.numeros, "fatia": parte,
                      "inicio": inicio, "cor": f"var(--chart-{i % 8 + 1})"})
        inicio += parte
    empresas = [{"nome": l.rotulo, "n": l.numeros,
                 "fatia": fatia(l.numeros.vendido, total.vendido)}
                for l in resumo[1 + n_lojas:]]

    # Um ranking só, pelo vendido, com a loja ao lado: é a pergunta "quem
    # vendeu", e a numeração é posição de verdade.
    vendedores = sorted(secoes["vendedores"].linhas,
                        key=lambda l: (-float(l["vendido"] or 0), l["nome"]))
    maior = max((float(l["vendido"] or 0) for l in vendedores), default=0) or 1
    com_meta = any(c.rotulo == _("% da meta") for c in secoes["vendedores"].colunas)
    ranking = [{"posicao": i, "nome": l["nome"], "loja": l["loja_nome"],
                "vendido": formatar(l["vendido"], "dinheiro"),
                "barra": float(l["vendido"] or 0) * 100 / maior,
                "vendas": l["vendas"], "atendimentos": l["atendimentos"],
                "conversao": formatar(l["conversao"], "porcento"),
                "meta": l.get("pct_meta") if com_meta else None}
               for i, l in enumerate(vendedores, start=1)]

    def lista(chave, valor, texto):
        linhas = secoes[chave].linhas
        maior = max((float(valor(l)) for l in linhas), default=0) or 1
        return [{"nome": l[0], "texto": texto(l), "barra": float(valor(l)) * 100 / maior}
                for l in linhas]

    listas = [
        (_("Motivos de não venda"), lista("motivos", lambda l: l[1],
                                          lambda l: str(l[1])), "perda"),
        (_("Mídias"), lista("midias", lambda l: l[1],
                            lambda l: _("%(v)s de %(n)s (%(c)s)") % {
                                "v": l[2], "n": l[1],
                                "c": formatar(100 * l[2] / l[1] if l[1] else None,
                                              "porcento")}), "venda"),
        (_("Grupos de item"), lista("grupos", lambda l: l[1],
                                    lambda l: formatar(l[1], "dinheiro")), "venda"),
        (_("Pausas"), lista("pausas", lambda l: l[1],
                            lambda l: formatar(l[1], "minutos")), "neutra"),
    ]

    lancamentos = [{
        "quando": timezone.localtime(a.fim).strftime("%d/%m %H:%M"),
        "loja": str(a.filial), "vendedor": a.vendedor.nome or a.vendedor.email,
        "vendeu": a.resultado == "vendeu",
        "valor": formatar(a.total, "dinheiro") if a.resultado == "vendeu" else "",
        "detalhe": (grupos_do_lancamento(a) if a.resultado == "vendeu"
                    else " — ".join(t for t in (motivo_do_lancamento(a), a.observacao) if t)),
        "midia": a.midia.nome if a.midia_id else "",
    } for a in secoes["lancamentos"].linhas]

    # O gráfico do período: a altura é a fatia do topo da ESCALA, e não do
    # maior dia, para as linhas de referência caírem em número redondo. O
    # rótulo de baixo sai a cada tantos dias, senão os 31 de um mês se atropelam
    # na largura do A4 (medido: com 16 rótulos, "05/09" encostava no "07/09").
    serie = relatorio.serie
    maior_dia = max((f.vendido for f in serie), default=0)
    topo, passo = escala(maior_dia)
    a_cada = max(1, math.ceil(len(serie) / 10))
    dias = [{"rotulo": f.rotulo, "altura": float(f.vendido) * 100 / topo,
             "valor": formatar(f.vendido, "dinheiro"), "vendas": f.vendas,
             "maior": bool(maior_dia) and f.vendido == maior_dia,
             "com_rotulo": i % a_cada == 0}
            for i, f in enumerate(serie)]
    # Sem venda nenhuma a escala é de mentira (R$ 1 a R$ 4): sem marcas, o
    # gráfico vazio diz só que não houve venda.
    marcas = [{"altura": k * passo * 100 / topo, "texto": dinheiro_curto(k * passo)}
              for k in range(1, round(topo / passo) + 1)] if maior_dia else []

    return {"chamada": chamada_do_periodo(relatorio),
            "tipo": dict(PERIODOS).get(relatorio.chave, ""), "placar": placar(relatorio),
            "dias": dias, "marcas": marcas,
            "conversao": float(total.conversao) if total.conversao is not None else None,
            "podio": ranking[:3], "resto": ranking[3:],
            "pedacos_das_lojas": [(l["cor"], l["fatia"], l["inicio"]) for l in lojas],
            "lojas": lojas, "empresas": empresas, "ranking": ranking,
            "com_meta": com_meta, "listas": listas, "lancamentos": lancamentos}


def em_impressao(relatorio: Relatorio, *, com_logo: bool = False) -> HttpResponse:
    """`com_logo` diz se a empresa tem logo: sem ele, `/marca/empresa/menu`
    responde 404 e o papel sairia com o ícone de imagem quebrada na capa."""
    from django.utils.translation import get_language

    from comum.estaticos import versionado

    from .ambiente import ambiente_da_fila

    html = ambiente_da_fila().get_template("fila/relatorio.html").render(
        r=relatorio, p=_papel(relatorio), formatar=formatar, com_logo=com_logo,
        idioma=get_language() or "pt-BR",
        gerado_em=_("%(data)s às %(hora)s") % {
            "data": timezone.localtime(relatorio.gerado_em).strftime("%d/%m/%Y"),
            "hora": timezone.localtime(relatorio.gerado_em).strftime("%H:%M")},
        folha_do_sistema=versionado("/static/nucleo/mw5.css"),
        folha_da_impressao=versionado("/static/plataforma/impressao.css"),
        folha_do_relatorio=versionado("/static/fila/relatorio.css"))
    return HttpResponse(html)
