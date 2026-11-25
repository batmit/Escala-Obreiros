"""Exportação verificada e restauração de dados em PostgreSQL vazio.

Usado para migrar SQLite e para backups portáveis do banco PostgreSQL.
Não inclui travas temporárias de execução nem credenciais.
"""

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from psycopg import sql
from psycopg.types.json import Jsonb

from .postgres import conectar, migrar_schema, trava_transacao
from .seed import dados_iniciais
from .storage import ERROS_BANCO, postgres, resolver_banco

TABELAS = {t: c for t, c, _ in dados_iniciais()}
TABELAS.update({
    'participacoes': ('data', 'pessoa_id', 'funcao'),
    'escalas': ('id', 'inicio_semana', 'versao', 'criada_em', 'publicada', 'assinatura', 'semente', 'parametros_json', 'avisos_json'),
    'alocacoes_escala': ('escala_id', 'vaga_id', 'data', 'funcao', 'pessoa_id', 'nome_pessoa'),
})
BOOLEANOS = {'publicada', 'evitar_semanas_consecutivas', 'permitir_flexibilizar_consecutivas'}
JSONS = {'parametros_json', 'avisos_json'}


def canonico(dados):
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def normalizar(linha):
    resultado = {}
    for chave, valor in dict(linha).items():
        if chave in BOOLEANOS:
            if valor not in (0, 1, False, True):
                raise ValueError('Indicador booleano inválido na origem.')
            valor = bool(valor)
        elif chave in JSONS and isinstance(valor, str):
            valor = json.loads(valor)
        elif chave == 'criada_em':
            instante = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
            if instante.tzinfo is None:
                raise ValueError('Timestamp sem fuso na origem.')
            valor = instante.astimezone(timezone.utc).isoformat()
        elif isinstance(valor, date):
            valor = valor.isoformat()
        resultado[chave] = valor
    return resultado


def ler_tabelas(connection, pg):
    dados = {}
    for tabela, colunas in TABELAS.items():
        if pg:
            comando = sql.SQL('SELECT {} FROM {}').format(sql.SQL(',').join(map(sql.Identifier, colunas)), sql.Identifier(tabela))
        else:
            comando = f"SELECT {','.join(colunas)} FROM {tabela}"
        linhas = connection.execute(comando).fetchall()
        dados[tabela] = sorted((normalizar(linha) for linha in linhas), key=canonico)
    return dados


def exportar(origem, arquivo):
    pg = postgres(origem)
    if pg:
        with conectar(origem) as connection, connection.transaction():
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            tabelas = ler_tabelas(connection, True)
    else:
        caminho = Path(origem).resolve()
        if not caminho.is_file():
            raise ValueError('Banco de origem não encontrado.')
        with closing(sqlite3.connect(caminho.as_uri() + '?mode=ro', uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN')
            tabelas = ler_tabelas(connection, False)
    payload = {'formato': 1, 'tabelas': tabelas, 'sha256': hashlib.sha256(canonico(tabelas).encode()).hexdigest()}
    destino = Path(arquivo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open('xb') as raw:
        try:
            with gzip.GzipFile(fileobj=raw, mode='wb') as compactado:
                compactado.write(canonico(payload).encode('utf-8'))
        except Exception:
            raw.close()
            destino.unlink(missing_ok=True)
            raise
    return {t: len(linhas) for t, linhas in tabelas.items()}


def restaurar_postgres(arquivo, destino):
    if not postgres(destino):
        raise ValueError('O destino deve ser PostgreSQL.')
    with gzip.open(arquivo, 'rt', encoding='utf-8') as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict) or payload.get('formato') != 1 or not isinstance(payload.get('tabelas'), dict) or set(payload['tabelas']) != set(TABELAS):
        raise ValueError('Formato de exportação incompatível.')
    tabelas = payload['tabelas']
    if hashlib.sha256(canonico(tabelas).encode()).hexdigest() != payload.get('sha256'):
        raise ValueError('Checksum do arquivo inválido.')
    for tabela, colunas in TABELAS.items():
        if not isinstance(tabelas[tabela], list) or any(not isinstance(r, dict) or set(r) != set(colunas) for r in tabelas[tabela]):
            raise ValueError('Colunas de exportação inválidas.')
    migrar_schema(destino)
    with conectar(destino) as connection, connection.transaction():
        trava_transacao(connection, 'restaurar-dados')
        for tabela in TABELAS:
            if connection.execute(sql.SQL('SELECT 1 FROM {} LIMIT 1').format(sql.Identifier(tabela))).fetchone():
                raise ValueError('Destino contém dados; restauração exige banco vazio.')
        for tabela, colunas in TABELAS.items():
            comando = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(tabela),
                sql.SQL(',').join(map(sql.Identifier, colunas)), sql.SQL(',').join(sql.Placeholder() for _ in colunas))
            valores = [tuple(Jsonb(r[c]) if c in JSONS else r[c] for c in colunas) for r in tabelas[tabela]]
            with connection.cursor() as cursor:
                cursor.executemany(comando, valores)
        if ler_tabelas(connection, True) != tabelas:
            raise ValueError('Verificação pós-importação falhou; a transação foi revertida.')
    return {t: len(linhas) for t, linhas in tabelas.items()}


def main():
    parser = argparse.ArgumentParser(description='Exportar dados ou restaurar em PostgreSQL vazio.')
    sub = parser.add_subparsers(dest='comando', required=True)
    saida = sub.add_parser('exportar')
    saida.add_argument('--origem', default=None, help='Caminho SQLite; omitir para usar DATABASE_URL.')
    saida.add_argument('--arquivo', type=Path, required=True)
    entrada = sub.add_parser('restaurar')
    entrada.add_argument('--arquivo', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.comando == 'exportar':
            contagens = exportar(resolver_banco(args.origem), args.arquivo)
        else:
            # Conexão direta e administrativa distinta da usada pela aplicação.
            url = os.environ.get('DATABASE_MIGRATION_URL')
            if not url:
                raise ValueError('Defina DATABASE_MIGRATION_URL para o destino vazio.')
            contagens = restaurar_postgres(args.arquivo, resolver_banco(url))
    except (ValueError, OSError, *ERROS_BANCO):
        parser.error('Operação não concluída. Verifique origem, destino vazio, migrações e arquivo; credenciais omitidas.')
    print(json.dumps(contagens, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
