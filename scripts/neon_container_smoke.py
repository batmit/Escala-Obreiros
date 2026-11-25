"""Ensaio Render/Neon usando somente Docker e PostgreSQL de teste locais."""

import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg import sql

from backend.postgres import BancoPostgres, conectar, migrar_schema


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def main():
    base = os.environ['TEST_DATABASE_URL']
    partes = urlsplit(base)
    if partes.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Este ensaio exige PostgreSQL local isolado, nunca Neon.')
    pg_container = os.environ['POSTGRES_TEST_CONTAINER']
    schema = 'smoke_' + uuid4().hex
    nome = 'escala-neon-smoke-' + uuid4().hex[:12]
    query = dict(parse_qsl(partes.query))
    query['options'] = '-csearch_path=' + schema
    url_host = urlunsplit(partes._replace(query=urlencode(query)))
    credenciais = partes.netloc.rsplit('@', 1)[0]
    url_container = urlunsplit(partes._replace(netloc=credenciais + '@127.0.0.1:5432', query=urlencode(query)))
    criado = False
    with conectar(base) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        migrar_schema(url_host)
        with BancoPostgres(url_host) as banco:
            banco.carregar_dados_iniciais()
        docker('run', '--detach', '--name', nome, '--network', 'container:' + pg_container,
            '--env', 'DATABASE_URL=' + url_container, '--env', 'GENERATION_MODE=on-access',
            '--env', 'RENDER=true', '--env', 'PORT=18080', os.environ.get('NEON_SMOKE_IMAGE', 'escala-obreiros:local'))
        criado = True

        def http(path):
            codigo = "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18080'+" + repr(path) + ",timeout=15).read().decode())"
            return json.loads(docker('exec', nome, 'python', '-c', codigo))

        def aguardar():
            prazo = time.monotonic() + 60
            while True:
                try:
                    return http('/healthz')
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    if time.monotonic() >= prazo:
                        raise
                    time.sleep(0.5)

        assert aguardar()['status'] == 'ok'
        hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        inicio = hoje - timedelta(days=hoje.weekday())
        caminho = f'/api/escalas?inicio={inicio}&fim={inicio+timedelta(days=6)}'
        assert sum(len(c['atribuicoes']) for c in http(caminho)['cultos']) == 8
        with conectar(url_host) as connection:
            antes = connection.execute('SELECT id FROM escalas WHERE publicada').fetchone()['id']
        docker('restart', nome)
        assert aguardar()['status'] == 'ok'
        assert sum(len(c['atribuicoes']) for c in http(caminho)['cultos']) == 8
        with conectar(url_host) as connection:
            rows = connection.execute('SELECT id FROM escalas').fetchall()
            assert rows == [{'id': antes}], rows
        print('OK: container sem volume local, PostgreSQL externo, geração por acesso e persistência após reinício.')
    finally:
        if criado:
            docker('rm', '--force', nome)
        with conectar(base) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__ == '__main__':
    main()
