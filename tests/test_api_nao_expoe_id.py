"""A API fala em GUID, nunca no id sequencial desta instalação.

Id sequencial numa URL de app deixa enumerar ("orçamento 41, 42, 43") e amarra
o app a um número que não é a identidade estável de nada. Toda tabela da casa
já tem `guid` (`tests/test_regra_guid.py`).
"""

from config.openapi import esquema

PROIBIDOS = {"id", "pk"}


def _campos():
    for nome, definicao in esquema()["components"]["schemas"].items():
        for campo in definicao.get("properties", {}):
            yield nome, campo


def _proibido(campo: str) -> bool:
    return campo in PROIBIDOS or campo.endswith("_id")


def test_nenhum_esquema_expoe_id():
    problemas = [f"{nome}.{campo}" for nome, campo in _campos() if _proibido(campo)]
    assert not problemas, f"campos de id sequencial na API: {problemas}. Use `guid`."


def test_nenhum_parametro_de_caminho_e_inteiro():
    problemas = []
    for caminho, metodos in esquema()["paths"].items():
        for metodo, operacao in metodos.items():
            for parametro in operacao.get("parameters", []):
                if parametro.get("in") == "path" and \
                        parametro.get("schema", {}).get("type") == "integer":
                    problemas.append(f"{metodo.upper()} {caminho}: {parametro['name']}")
    assert not problemas, problemas


def test_a_varredura_olha_algo():
    assert list(_campos()), "nenhum campo nos esquemas — a varredura olharia o vazio"
