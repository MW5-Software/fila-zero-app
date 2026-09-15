"""Onde moram os módulos de negócio da matriz.

Cada subpasta é um app Django independente, que se declara à plataforma
(`plataforma.declaracao.registrar`) no `ready()` do próprio `AppConfig` — ver
`modulos/exemplo/apps.py`. Este pacote em si não tem código: só agrupa.
"""
