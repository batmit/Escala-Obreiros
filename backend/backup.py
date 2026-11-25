"""Backup consistente do SQLite e restauração para um novo arquivo."""

import argparse
import logging
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from uuid import uuid4

logger = logging.getLogger(__name__)
PADRAO = re.compile(r'igreja-backup-\d{8}T\d{12}Z-[0-9a-f]{32}\.sqlite3')


def verificar_banco(caminho: Path) -> None:
    with closing(sqlite3.connect(caminho.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Banco não passou na verificação de integridade.')
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Banco contém referências inválidas.')


def _copiar(origem: Path, destino: Path) -> None:
    if not origem.is_file():
        raise ValueError('Banco de origem não encontrado.')
    with closing(sqlite3.connect(origem.resolve().as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(destino)) as target:
            prazo = monotonic() + 30
            def progresso(*_):
                if monotonic() > prazo:
                    raise TimeoutError('Tempo limite excedido durante a cópia do banco.')
            source.backup(target, pages=256, sleep=0.05, progress=progresso)
    verificar_banco(destino)


def criar_backup(banco: str | Path, diretorio: str | Path, reter: int = 7) -> Path:
    if type(reter) is not int or reter < 1:
        raise ValueError('Retenção deve ser um inteiro positivo.')
    origem, pasta = Path(banco).resolve(), Path(diretorio).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    instante = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destino = pasta / f'igreja-backup-{instante}-{uuid4().hex}.sqlite3'
    parcial = destino.with_suffix('.partial')
    try:
        _copiar(origem, parcial)
        parcial.replace(destino)
    finally:
        if parcial.is_file():
            parcial.unlink()
    # Remove somente backups próprios, diretamente na pasta resolvida, após validar o novo.
    arquivos = sorted((p for p in pasta.iterdir() if PADRAO.fullmatch(p.name) and p.is_file() and not p.is_symlink() and p.resolve().parent == pasta and p.resolve() != origem), key=lambda p: p.name, reverse=True)
    for antigo in arquivos[reter:]:
        antigo.unlink()
    logger.info('Backup validado: arquivo=%s retenção=%s', destino.name, reter)
    return destino


def restaurar_backup(backup: str | Path, destino: str | Path) -> Path:
    """Nunca sobrescreve o banco ativo: restaura exclusivamente para caminho novo."""
    origem, novo = Path(backup).resolve(), Path(destino).absolute()
    if novo.exists() or novo.is_symlink():
        raise ValueError('O destino de restauração já existe; escolha um novo arquivo.')
    verificar_banco(origem)
    novo.parent.mkdir(parents=True, exist_ok=True)
    # Reserva exclusiva evita sobrescrever arquivo criado entre verificação e cópia.
    with novo.open('xb'):
        pass
    try:
        _copiar(origem, novo)
    except Exception:
        novo.unlink(missing_ok=True)
        raise
    logger.info('Restauração validada em novo arquivo: %s', novo)
    return novo


class AgendadorBackups:
    def __init__(self, banco, diretorio, *, reter=7, intervalo_segundos=86400, executar=None, relogio=None):
        if type(reter) is not int or reter < 1 or intervalo_segundos <= 0:
            raise ValueError('Retenção e intervalo devem ser positivos.')
        self.banco, self.diretorio, self.reter = banco, diretorio, reter
        self.intervalo = intervalo_segundos
        self.executar = executar or criar_backup
        self.relogio = relogio or monotonic
        self.proxima = 0
        self.parada = Event()
        self.thread = Thread(target=self._rodar, name='backup-sqlite', daemon=True)

    def verificar(self):
        if self.relogio() >= self.proxima:
            try:
                self.executar(self.banco, self.diretorio, self.reter)
                self.proxima = self.relogio() + self.intervalo
            except Exception:
                logger.exception('Falha no backup; nova tentativa em 60 segundos.')
                self.proxima = self.relogio() + 60
        return min(60, max(0.01, self.proxima - self.relogio()))

    def iniciar(self):
        self.thread.start()

    def encerrar(self):
        self.parada.set()
        self.thread.join(timeout=35)

    def _rodar(self):
        while not self.parada.is_set():
            self.parada.wait(self.verificar())


def main():
    parser = argparse.ArgumentParser(description='Backup e restauração segura do SQLite.')
    comandos = parser.add_subparsers(dest='comando', required=True)
    criar = comandos.add_parser('criar')
    criar.add_argument('--banco', type=Path, default=Path('data/igreja.sqlite3'))
    criar.add_argument('--diretorio', type=Path, default=Path('data/backups'))
    criar.add_argument('--reter', type=int, default=7)
    restaurar = comandos.add_parser('restaurar')
    restaurar.add_argument('backup', type=Path)
    restaurar.add_argument('destino', type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        resultado = criar_backup(args.banco, args.diretorio, args.reter) if args.comando == 'criar' else restaurar_backup(args.backup, args.destino)
    except (ValueError, OSError, sqlite3.Error) as erro:
        parser.error(str(erro))
    print(resultado)


if __name__ == '__main__':
    main()
