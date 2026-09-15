"""A senha do Oracle, cifrada em repouso.

O cadastro de empresa guarda a credencial de acesso ao banco do CLIENTE.
Guardá-la em texto claro faria de um dump do nosso banco — um backup mal
guardado, um `SELECT` de alguém com acesso de leitura — a chave do ERP dele.

Mesmo mecanismo do painel de versões, que cifra a chave SSH privada de cada
instalação: Fernet, com a chave vindo do ambiente. E o mesmo contrato: a
senha em claro só existe pelo tempo de uma chamada, nunca em disco e nunca
numa coluna.

**Falha no USO, não na subida.** As outras variáveis obrigatórias do projeto
(`DJANGO_SECRET_KEY`, `KRONOS_BANCO`) travam o processo quando faltam, e o
raciocínio é o mesmo aqui — mas este módulo é OPCIONAL: a maioria das
instalações não vai ler do Kronos legado, e exigir a chave de todas seria
cobrar de quem não usa. Então a exigência mora no ponto exato em que uma
credencial seria escrita, com a mensagem dizendo o que fazer.
"""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

__all__ = ["VARIAVEL", "chave_de_cifragem", "cifrar", "decifrar", "gerar_chave"]

#: De onde a chave vem. Nunca do `settings` versionado: uma chave commitada
#: seria a mesma nas sessenta instalações, e um dump de qualquer uma abriria
#: o Oracle de todas.
VARIAVEL = "PORTAL_CHAVE_DE_CIFRAGEM"


def gerar_chave() -> str:
    """Uma chave Fernet nova, para quem está configurando uma instalação."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def chave_de_cifragem(valor: "str | None" = None) -> bytes:
    """A chave desta instalação, ou a recusa explicando o que falta.

    Recebe `valor` para poder ser testada sem mexer no ambiente do processo
    — mesma razão de `exigir_chave_de_cifragem` existir como função pura no
    painel: recarregar `settings` no meio da suíte deixa o processo com
    metade da configuração antiga.
    """
    bruto = valor if valor is not None else os.environ.get(VARIAVEL, "")
    if not bruto:
        raise ImproperlyConfigured(
            f"{VARIAVEL} é obrigatória para cadastrar uma empresa: a senha "
            f"do banco do cliente é guardada cifrada, e sem a chave ela "
            f"ficaria em texto claro no nosso banco. Gere uma com "
            f"`python -c \"from plataforma.cifra import gerar_chave; "
            f"print(gerar_chave())\"` e exporte antes de subir."
        )
    return bruto.encode()


def cifrar(claro: str, chave: "str | None" = None) -> str:
    """O texto cifrado, pronto para a coluna. Vazio continua vazio — não se
    cifra ausência de senha, e um Fernet de string vazia seria indistinguível
    de uma senha de verdade para quem lê a coluna."""
    from cryptography.fernet import Fernet

    claro = (claro or "").strip()
    if not claro:
        return ""
    return Fernet(chave_de_cifragem(chave)).encrypt(claro.encode()).decode()


def decifrar(cifrado: str, chave: "str | None" = None) -> str:
    """A senha em claro, para o tempo de uma conexão. Vazio continua vazio."""
    from cryptography.fernet import Fernet

    if not cifrado:
        return ""
    return Fernet(chave_de_cifragem(chave)).decrypt(cifrado.encode()).decode()
