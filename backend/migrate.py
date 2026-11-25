"""Comando administrativo explícito; nunca recebe segredo por argumento."""

import argparse
import os

from .postgres import BancoPostgres, migrar_schema
from .storage import ERROS_BANCO, postgres, resolver_banco


def main():
    parser = argparse.ArgumentParser(description='Aplicar migrações PostgreSQL versionadas.')
    parser.add_argument('--seed', action='store_true', help='Carrega configuração inicial, somente quando solicitado.')
    args = parser.parse_args()
    try:
        url = os.environ.get('DATABASE_MIGRATION_URL')
        if not url:
            raise ValueError('Defina DATABASE_MIGRATION_URL.')
        url = resolver_banco(url)
        if not postgres(url):
            raise ValueError('O destino deve ser PostgreSQL.')
        migrar_schema(url)
        if args.seed:
            with BancoPostgres(url) as banco:
                banco.carregar_dados_iniciais()
    except (ValueError, *ERROS_BANCO):
        parser.error('Migração não concluída. Verifique a conexão administrativa, permissões e versões; credenciais omitidas.')
    print('Migrações PostgreSQL aplicadas.' + (' Configuração inicial inserida.' if args.seed else ''))


if __name__ == '__main__':
    main()
