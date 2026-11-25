"""Processo contínuo de produção: Waitress, geração semanal e backups."""

import logging
import os
import signal
from pathlib import Path
from threading import Event, Thread

from waitress import create_server

from .backup import AgendadorBackups
from .bootstrap import preparar_banco
from .scheduler import AgendadorSemanal
from .webapp import criar_aplicacao
from .on_access import RenovacaoPorAcesso
from .storage import resolver_banco, postgres

logger = logging.getLogger(__name__)


def executar(caminho, host, porta, backups, *, parar=None, modo='continuous'):
    if modo not in ('continuous', 'on-access'):
        raise ValueError('GENERATION_MODE deve ser continuous ou on-access.')
    preparar_banco(caminho)
    parada = parar or Event()
    workers = {'agendador': AgendadorSemanal(caminho)} if modo == 'continuous' else {}
    if modo == 'continuous' and not postgres(caminho):
        workers['backups'] = AgendadorBackups(caminho, backups)
    renovar = RenovacaoPorAcesso(caminho, backups) if modo == 'on-access' else None
    servidor = create_server(criar_aplicacao(caminho, workers, ao_consultar=renovar), host=host, port=porta, threads=4,
        channel_timeout=30, max_request_body_size=65536)
    http = Thread(target=servidor.run, name='waitress', daemon=True)
    iniciados = []
    try:
        for worker in workers.values():
            worker.iniciar()
            iniciados.append(worker)
        http.start()
        logger.info('Aplicação contínua iniciada em %s:%s', host, servidor.effective_port)
        while not parada.wait(1):
            if not http.is_alive() or any(not w.thread.is_alive() for w in workers.values()):
                raise RuntimeError('Componente essencial parou; processo encerrado para reinício pelo supervisor.')
    finally:
        for worker in iniciados:
            worker.encerrar()
        servidor.close()
        servidor.task_dispatcher.shutdown(timeout=5)
        if http.is_alive():
            http.join(timeout=5)
        logger.info('Aplicação encerrada.')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    parada = Event()
    for nome in ('SIGINT', 'SIGTERM'):
        signal.signal(getattr(signal, nome), lambda *_: parada.set())
    caminho = resolver_banco()
    if os.environ.get('RENDER') and not postgres(caminho):
        raise ValueError('A hospedagem Render exige DATABASE_URL PostgreSQL; fallback SQLite desativado.')
    executar(caminho, os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8000')),
        None if postgres(caminho) else Path(os.environ.get('BACKUP_DIR', str(caminho.parent / 'backups'))), parar=parada,
        modo=os.environ.get('GENERATION_MODE', 'on-access' if postgres(caminho) else 'continuous'))


if __name__ == '__main__':
    main()
