"""Seleção explícita do armazenamento; DATABASE_URL nunca vira caminho local."""

import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict

ERROS_BANCO = (sqlite3.Error, psycopg.Error)


def postgres(alvo) -> bool:
    return isinstance(alvo, str) and alvo.startswith(('postgresql://', 'postgres://'))


def resolver_banco(alvo=None):
    url = alvo if postgres(alvo) else os.environ.get('DATABASE_URL') if alvo is None else None
    if url is not None or (alvo is None and 'DATABASE_URL' in os.environ):
        if not postgres(url):
            raise ValueError('DATABASE_URL deve ser uma URL PostgreSQL válida.')
        try:
            parametros = conninfo_to_dict(url)
        except psycopg.Error:
            raise ValueError('DATABASE_URL inválida.') from None
        host = parametros.get('host', '')
        if host not in ('localhost', '127.0.0.1', '::1') and parametros.get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError('DATABASE_URL remota deve exigir TLS.')
        return url
    if alvo is not None:
        return alvo
    return Path(os.environ.get('DATABASE_PATH', 'data/igreja.sqlite3')).resolve()


def banco_igreja(alvo):
    if postgres(alvo):
        from .postgres import BancoPostgres
        return BancoPostgres(alvo)
    from .database import BancoIgreja
    return BancoIgreja(alvo)


def repositorio_escalas(alvo):
    if postgres(alvo):
        from .postgres import RepositorioPostgres
        return RepositorioPostgres(alvo)
    from .schedule_repository import RepositorioEscalas
    return RepositorioEscalas(alvo)
