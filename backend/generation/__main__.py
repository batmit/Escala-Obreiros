"""Gera uma proposta sem salvar participações ou publicar a escala."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from ..storage import banco_igreja, repositorio_escalas, resolver_banco, postgres
from .contracts import PedidoGeracao, StatusGeracao
from .cp_sat import gerar_escala
from .slots import criar_vagas_semanais
from .previous_schedule import ler_escala_anterior


def main() -> int:
    parser = argparse.ArgumentParser(description='Gera uma proposta semanal com CP-SAT.')
    parser.add_argument('semana', type=date.fromisoformat, help='Segunda-feira em AAAA-MM-DD')
    parser.add_argument('--banco', default=None)
    parser.add_argument('--semente', type=int, default=0)
    parser.add_argument('--limite-segundos', type=float, default=10)
    parser.add_argument('--escala-anterior', type=Path, help='JSON gerado para a semana imediatamente anterior.')
    parser.add_argument('--saida', type=Path, help='Salva a proposta JSON para uso posterior.')
    parser.add_argument('--salvar-banco', action='store_true', help='Salva e publica a proposta validada no banco.')
    args = parser.parse_args()
    args.banco = resolver_banco(args.banco)
    if not postgres(args.banco) and not Path(args.banco).is_file():
        parser.error('Banco não encontrado; inicialize com python -m backend.')
    try:
        anterior = ler_escala_anterior(json.loads(args.escala_anterior.read_text(encoding='utf-8-sig'))) if args.escala_anterior else None
        if anterior is None and args.salvar_banco:
            anterior = repositorio_escalas(args.banco).obter_anterior(args.semana - timedelta(days=7))
        with banco_igreja(args.banco) as banco:
            cultos = tuple(banco.listar_cultos())
            pedido = PedidoGeracao(
                inicio_semana=args.semana,
                pessoas=tuple(banco.listar_pessoas()),
                cultos=cultos,
                vagas=criar_vagas_semanais(args.semana, cultos),
                regras=banco.obter_regras(),
                historico=tuple(banco.listar_participacoes_ultimas_duas_semanas(args.semana)),
                semente=args.semente,
                limite_segundos=args.limite_segundos,
                escala_anterior=anterior,
            )
    except (ValueError, OSError) as erro:
        parser.error(str(erro))
    resultado = gerar_escala(pedido)
    escala_id = None
    if args.salvar_banco and resultado.status in (StatusGeracao.VIAVEL, StatusGeracao.OTIMA):
        escala_id = repositorio_escalas(args.banco).salvar_e_publicar(pedido, resultado)
    por_id = {v.id: v for v in pedido.vagas}
    texto = json.dumps({
        'inicio_semana': pedido.inicio_semana.isoformat(),
        'escala_id': escala_id,
        'status': resultado.status.value,
        'avisos': resultado.avisos,
        'alocacoes': [{'vaga_id': a.vaga_id, 'data': por_id[a.vaga_id].data.isoformat(), 'funcao': por_id[a.vaga_id].funcao.value, 'pessoa_id': a.pessoa_id} for a in resultado.alocacoes],
    }, ensure_ascii=False, indent=2)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(texto + '\n', encoding='utf-8')
    print(texto)
    return 0 if resultado.status in (StatusGeracao.VIAVEL, StatusGeracao.OTIMA) else 1


if __name__ == '__main__':
    raise SystemExit(main())
