"""A documentação que descreve o sistema de HOJE precisa bater com o de hoje.

**Documentação que mente é pior que documentação faltando.** Quem não acha
instrução procura no código; quem acha uma errada roda, toma um erro que não
entende, e conclui que o sistema está quebrado. Foi o caso do bloco "Preparar"
até 10/09/2026: ele mandava definir a senha da MW5 com
`django.contrib.auth.models.User` e `username='mw5'` — de antes de o usuário
virar `contas.models.Usuario` com login por e-mail. O comando levantava
`DoesNotExist` numa instalação recém-subida, que é exatamente o momento em que
a pessoa tem menos como saber que a culpa era do texto.

Documento não roda na suíte, então envelhece sem ninguém ver. Este arquivo
amarra ao código as afirmações que já se soltaram — e só essas: número que
alguém conta à mão, nome de arquivo citado, e estado de uma decisão.

**Não é varredura de tudo que está escrito**, e não deve virar: prender cada
frase de um documento ao código faria a suíte ficar vermelha por redação, e
o efeito seria pararem de escrever documento. O que entra aqui é o que já
mentiu uma vez.

**Um `plan/` ou uma `decisao-*` NÃO entram.** Eles são registros datados, e
descrever o passado é o trabalho deles — o `CLAUDE.md` e o `README.md` são os
que falam no presente.
"""

from __future__ import annotations

import re
from pathlib import Path

from contas.mw5 import EMAIL

README = Path("README.md")
CLAUDE = Path("CLAUDE.md")
TESTES = Path("tests")


def _preparar() -> str:
    """O bloco de código que o roteiro manda rodar antes de tudo."""
    texto = README.read_text(encoding="utf-8")
    depois = texto[texto.index("**Preparar**"):]
    blocos = re.findall(r"```bash\n(.*?)```", depois, re.S)
    assert blocos, "o bloco 'Preparar' do README perdeu o comando de shell"
    return blocos[0]


def test_usa_o_usuario_deste_projeto():
    """`auth.User` não é mais tabela de gente aqui — trocar o `AUTH_USER_MODEL`
    foi decisão de 02/09, e o README ficou para trás por oito dias."""
    comando = _preparar()
    assert "contas.models" in comando
    assert "Usuario" in comando
    assert "django.contrib.auth.models" not in comando, (
        "o README voltou a mandar buscar a MW5 pelo `User` do Django")


def test_procura_a_mw5_pelo_email_que_o_codigo_semeia():
    """O endereço vem de `contas.mw5.EMAIL`, e não de memória: mudá-lo lá sem
    mudar aqui deixaria o roteiro apontando para um usuário que não existe."""
    assert EMAIL in _preparar(), (
        f"o README precisa procurar a MW5 por `{EMAIL}` — é o que "
        f"`garantir_usuario_mw5` semeia")


def test_nao_manda_entrar_com_username():
    """O login é o e-mail. "Entrar como `mw5`" manda a pessoa digitar algo que
    a tela de entrada recusa, e o erro que ela vê é "credenciais inválidas" —
    que não diz nada sobre o texto estar errado."""
    texto = README.read_text(encoding="utf-8")
    assert "username=" not in texto
    assert f"(`{EMAIL}` + a senha de cima)" in texto


def test_destranca_a_mw5():
    """`is_active = True` no comando não é enfeite: desativar este usuário é
    como um cliente trancaria a MW5 do lado de dentro (ver `contas/mw5.py`), e
    o roteiro de primeira entrada é onde isso se desfaz."""
    assert "is_active = True" in _preparar()


class TestOCLAUDEDescreveOSistemaDeHoje:
    """O `CLAUDE.md` é o primeiro arquivo que alguém (ou algum agente) lê.

    Em 10/09/2026 ele dizia três coisas falsas ao mesmo tempo: que a suíte
    tinha 73 arquivos (tinha 103), que havia cinco varreduras (havia doze), e
    — a pior — que a hierarquia de usuários "ainda não está definida",
    mandando conversar com o João antes de mexer. Ela tinha sido desenhada e
    construída oito dias antes. Documento que manda parar na frente de uma
    porta aberta custa mais que documento nenhum.
    """

    def test_toda_contagem_de_testes_bate(self):
        """O número é contado à mão, e por isso envelhece a cada arquivo novo.

        **Procura TODAS as ocorrências**, e não a primeira: o `CLAUDE.md` diz
        o número em dois lugares — na lista de pastas e no bloco "Como rodar"
        do fim —, e corrigir só um deixou o outro mentindo por mais uma
        rodada. Uma varredura que confere a primeira ocorrência ensina que o
        arquivo está certo.
        """
        quantos = len(list(TESTES.glob("test_*.py")))
        escritos = re.findall(r"(\d+) arquivos", CLAUDE.read_text(encoding="utf-8"))
        assert escritos, "o CLAUDE.md perdeu a linha que conta os testes"
        errados = [n for n in escritos if int(n) != quantos]
        assert not errados, (
            f"o CLAUDE.md diz {errados} arquivos de teste e são {quantos}")

    def test_toda_varredura_da_tabela_existe(self):
        """Citar um arquivo que não existe mais manda a pessoa procurar o que
        foi apagado — e esconde que a regra deixou de ser cobrada."""
        citados = set(re.findall(r"`(test_\w+\.py)`",
                                 CLAUDE.read_text(encoding="utf-8")))
        assert citados, "a tabela de varreduras sumiu do CLAUDE.md"
        sumidos = sorted(n for n in citados if not (TESTES / n).exists())
        assert not sumidos, f"o CLAUDE.md cita varreduras que não existem: {sumidos}"

    def test_nao_diz_que_a_hierarquia_esta_por_decidir(self):
        """A frase exata que ficou oito dias mentindo. `contas.models.Nivel`
        existe, `Empresa.dono` e `Usuario.dono` existem: está decidido."""
        from contas.models import Nivel

        assert Nivel.MASTER == 0 and Nivel.TITULAR == 1
        texto = CLAUDE.read_text(encoding="utf-8")
        assert "qual é a nova hierarquia" not in texto
        assert "Empresa é uma por instalação" not in texto, (
            "a empresa deixou de ser uma por instalação em 09/09/2026 — hoje "
            "é uma por CONTA")
