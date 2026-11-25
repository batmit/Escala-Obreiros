"""Execute: python -m backend [caminho-do-banco]."""

import argparse
import json
from pathlib import Path

from .storage import banco_igreja, resolver_banco, postgres


def main() -> None:
    parser = argparse.ArgumentParser(description='Inicializa os dados da igreja em SQLite.')
    parser.add_argument('banco', nargs='?', default=None)
    parser.add_argument('--exportar-cultos', type=Path, help='Exporta configuração pública do banco para o frontend.')
    args = parser.parse_args()
    alvo = resolver_banco(args.banco)
    if not postgres(alvo):
        Path(alvo).parent.mkdir(parents=True, exist_ok=True)
    with banco_igreja(alvo) as banco:
        banco.inicializar()
        banco.carregar_dados_iniciais()
        print('Banco PostgreSQL inicializado.' if postgres(alvo) else f'Banco: {Path(alvo).resolve()}')
        print(f'{len(banco.listar_pessoas())} pessoas; {len(banco.listar_cultos())} dias de culto.')
        if args.exportar_cultos:
            dados = [{'id': f'culto-{culto.dia_semana}', 'diaSemana': culto.dia_semana, 'titulo': 'Culto' if culto.periodo == 'não informado' else f'Culto · {culto.periodo}', 'funcoes': list(culto.funcoes)} for culto in banco.listar_cultos()]
            args.exportar_cultos.parent.mkdir(parents=True, exist_ok=True)
            args.exportar_cultos.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
