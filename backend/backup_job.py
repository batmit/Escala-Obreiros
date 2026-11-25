"""Backup PostgreSQL cifrado para GitHub Actions; nenhum segredo vai aos argumentos."""

import os
import subprocess
from pathlib import Path

from .storage import resolver_banco
from .transfer import exportar


def executar_backup(diretorio: Path):
    url = os.environ.get('DATABASE_BACKUP_URL')
    senha = os.environ.get('BACKUP_PASSPHRASE', '')
    if not url or len(senha) < 20 or '\n' in senha or '\r' in senha:
        raise ValueError('Configure DATABASE_BACKUP_URL e BACKUP_PASSPHRASE com ao menos 20 caracteres, sem quebras de linha.')
    diretorio.mkdir(parents=True, exist_ok=True)
    claro = diretorio / 'snapshot.json.gz'
    cifrado = diretorio / 'snapshot.json.gz.gpg'
    if claro.exists() or cifrado.exists():
        raise ValueError('Diretório de saída já contém um snapshot.')
    produzido = False
    try:
        contagens = exportar(resolver_banco(url), claro)
        produzido = True
        subprocess.run(['gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase-fd', '0',
            '--symmetric', '--cipher-algo', 'AES256', '--output', str(cifrado), str(claro)],
            input=senha + '\n', text=True, check=True, capture_output=True)
    finally:
        if produzido:
            claro.unlink(missing_ok=True)
    print('Backup cifrado criado. Registros:', sum(contagens.values()))
    return cifrado


if __name__ == '__main__':
    executar_backup(Path('data/backup-job'))
