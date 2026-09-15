"""Máscaras de campo — CPF, CNPJ, telefone, CEP.

**Visuais.** O valor gravado sai com a pontuação, que é como os sistemas
legados normalmente já guardam. Nada é validado nem normalizado no servidor: a
máscara ajuda quem digita, e não decide o formato do dado.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import nucleo
from nucleo.campos import Campo, MASCARAS, campos_de_json


def _html(campos):
    from nucleo.campos import montar_campos
    from nucleo.rendering import render_all

    return render_all(montar_campos(campos))


class TestOVocabulario:
    def test_as_mascaras_que_existem(self):
        assert set(MASCARAS) == {"cpf", "cnpj", "cpf_cnpj", "telefone", "cep"}

    def test_o_campo_guarda_a_mascara(self):
        campo = Campo(rotulo="CPF", mascara="cpf")
        assert campo.mascara == "cpf"

    def test_mascara_desconhecida_e_ignorada(self):
        """Leitura tolerante: um `menu_json` editado a mao com uma mascara que
        nao existe nao pode derrubar a previa, que roda a cada tecla."""
        campos = campos_de_json([{"rotulo": "X", "mascara": "inventada"}])
        assert campos[0].mascara == ""

    def test_mascara_so_vale_em_campo_de_texto(self):
        """Numa data ou num checkbox ela nao tem o que formatar, e guardada ali
        viraria uma segunda verdade sobre o tipo."""
        campos = campos_de_json([{"rotulo": "X", "tipo": "data",
                                  "mascara": "cpf"}])
        assert campos[0].mascara == ""


class TestNoHTML:
    def test_o_campo_leva_a_mascara_num_atributo(self):
        html = _html([Campo(rotulo="CPF", mascara="cpf")])
        assert 'data-mascara="cpf"' in html

    def test_o_campo_sem_mascara_nao_leva_atributo(self):
        assert "data-mascara" not in _html([Campo(rotulo="Nome")])

    def test_o_teclado_do_celular_e_numerico(self):
        """Todas as cinco sao so digitos. Sem isto, quem preenche no celular
        recebe o teclado de letras."""
        for mascara in MASCARAS:
            html = _html([Campo(rotulo="X", mascara=mascara)])
            assert 'inputmode="numeric"' in html, mascara

    def test_continua_sendo_um_input_de_texto(self):
        """`type="number"` recusaria ponto e barra — e a mascara os poe."""
        html = _html([Campo(rotulo="CPF", mascara="cpf")])
        assert 'type="text"' in html


class TestOFormatador:
    """O formatador roda no navegador, no `mw5.js` que vai em todo projeto."""

    def _formatar(self, mascara, digitado):
        node = shutil.which("node")
        if not node:
            pytest.skip("sem node: esta garantia fica sem guarda")
        js = (Path(nucleo.__file__).parent / "static" / "nucleo"
              / "mw5.js").read_text(encoding="utf-8")
        achado = re.search(r"\n  var PADROES = \{.*?\n  \};\n", js, re.S)
        assert achado, "`PADROES` sumiu do mw5.js"
        formatar = re.search(r"\n  function aplicarMascara\(.*?\n  \}\n", js, re.S)
        assert formatar, "`aplicarMascara` sumiu do mw5.js"
        programa = achado.group(0) + formatar.group(0) + (
            "console.log(JSON.stringify(aplicarMascara(%s, %s)));"
            % (json.dumps(mascara), json.dumps(digitado)))
        return json.loads(subprocess.run([node, "-e", programa],
                                         capture_output=True, text=True,
                                         check=True).stdout)

    @pytest.mark.parametrize("mascara,digitado,esperado", [
        ("cpf", "12345678900", "123.456.789-00"),
        ("cnpj", "12345678000100", "12.345.678/0001-00"),
        ("cep", "80000000", "80000-000"),
        ("telefone", "41999998888", "(41) 99999-8888"),
        # Fixo, oito digitos: o quinto nao vira o comeco do sufixo.
        ("telefone", "4133334444", "(41) 3333-4444"),
    ])
    def test_formata_o_completo(self, mascara, digitado, esperado):
        assert self._formatar(mascara, digitado) == esperado

    def test_formata_enquanto_se_digita(self):
        """Meio caminho tem que sair legivel — senao a pontuacao so aparece no
        ultimo digito e a pessoa acha que a mascara nao funciona."""
        assert self._formatar("cpf", "123456") == "123.456"

    def test_ignora_o_que_nao_e_digito(self):
        """Colar um CPF ja formatado nao pode virar lixo."""
        assert self._formatar("cpf", "123.456.789-00") == "123.456.789-00"

    def test_nao_deixa_passar_do_tamanho(self):
        assert self._formatar("cpf", "123456789001234") == "123.456.789-00"

    def test_cpf_cnpj_troca_de_forma_pelo_tamanho(self):
        """O caso mais comum do Brasil: um campo so para pessoa fisica e
        juridica."""
        assert self._formatar("cpf_cnpj", "12345678900") == "123.456.789-00"
        assert self._formatar("cpf_cnpj", "12345678000100") == "12.345.678/0001-00"

    def test_mascara_desconhecida_devolve_o_que_veio(self):
        assert self._formatar("inventada", "abc123") == "abc123"


def test_o_contrato_entre_o_python_e_o_js():
    """A lista que o painel oferece e os padroes que o navegador aplica moram
    em arquivos diferentes — um em Python, outro em JS, e nao ha como o JS ler
    o Python. Divergindo, o painel oferece uma mascara que nao formata nada."""
    js = (Path(nucleo.__file__).parent / "static" / "nucleo"
          / "mw5.js").read_text(encoding="utf-8")
    trecho = re.search(r"\n  var PADROES = \{(.*?)\n  \};", js, re.S).group(1)
    no_js = set(re.findall(r'"([a-z_]+)":', trecho))
    assert no_js == set(MASCARAS), (
        f"so no JS: {no_js - set(MASCARAS)} | so no Python: {set(MASCARAS) - no_js}")


def test_o_ouvinte_da_mascara_e_registrado_UMA_vez():
    """Aninhado dentro de outro ouvinte, `addEventListener` roda a cada evento
    dele — e depois de cinquenta cliques haveria cinquenta ouvintes de `input`,
    todos formatando o mesmo campo.

    Aconteceu: o bloco caiu dentro do ouvinte de clique, o `node --check`
    passou, e os testes do formatador nao viram porque extraem a funcao
    isolada. O que se mede aqui e a PROFUNDIDADE de chaves — zero aninhamento
    alem da IIFE do arquivo.
    """
    linhas = (Path(nucleo.__file__).parent / "static" / "nucleo"
              / "mw5.js").read_text(encoding="utf-8").split("\n")
    alvo = next((n for n, l in enumerate(linhas)
                 if 'addEventListener("input"' in l and "mascara" in "".join(
                     linhas[n:n + 4])), None)
    assert alvo is not None, "ninguem escuta o `input` para formatar"
    profundidade = sum(l.count("{") - l.count("}") for l in linhas[:alvo])
    assert profundidade == 1, (
        f"o ouvinte da mascara esta aninhado (profundidade {profundidade}): "
        f"ele seria registrado de novo a cada evento externo")
