"""Servidor local: frontend e API somente de leitura na mesma origem."""

import argparse
import json
import logging
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .storage import resolver_banco, postgres
from .bootstrap import preparar_banco
from .webapp import consultar_api
from .scheduler import AgendadorSemanal
from .backup import AgendadorBackups

FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'


class CalendarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, banco, **kwargs):
        self.banco = banco
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def _json(self, dados, status=200):
        payload = json.dumps(dados, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        url = urlsplit(self.path)
        workers = {nome: getattr(self.server, nome, None) for nome in ('agendador', 'backups')}
        resposta = consultar_api(url.path, url.query, self.banco, workers)
        if resposta is not None:
            dados, status = resposta
            return self._json(dados, status)
        return super().do_GET()


def main():
    parser = argparse.ArgumentParser(description='Serve o calendário e a API local.')
    parser.add_argument('--banco', default=None)
    parser.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    parser.add_argument('--porta', type=int, default=int(os.environ.get('PORT', '8000')))
    parser.add_argument('--sem-agendamento', action='store_true', help='Desativa a renovação automática neste processo.')
    parser.add_argument('--sem-backup', action='store_true', help='Desativa backups automáticos neste processo.')
    parser.add_argument('--backups', type=Path, default=None, help='Pasta dos backups; padrão: backups ao lado do banco.')
    parser.add_argument('--reter-backups', type=int, default=7)
    args = parser.parse_args()
    args.banco = resolver_banco(args.banco)
    if not postgres(args.banco) and not Path(args.banco).is_file():
        parser.error('Inicialize o banco com python -m backend.')
    if args.reter_backups < 1:
        parser.error('Retenção de backups deve ser positiva.')
    preparar_banco(args.banco)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    servidor = ThreadingHTTPServer((args.host, args.porta), partial(CalendarHandler, banco=args.banco))
    print(f'Calendário: http://localhost:{args.porta}', flush=True)
    agendador = None if args.sem_agendamento else AgendadorSemanal(args.banco)
    pasta_backups = args.backups or (Path(args.banco).parent / 'backups' if not postgres(args.banco) else None)
    backups = None if args.sem_backup or postgres(args.banco) else AgendadorBackups(args.banco, pasta_backups, reter=args.reter_backups)
    servidor.agendador, servidor.backups = agendador, backups
    if agendador:
        agendador.iniciar()
    if backups:
        backups.iniciar()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if agendador:
            agendador.encerrar()
        if backups:
            backups.encerrar()
        servidor.server_close()


if __name__ == '__main__':
    main()
