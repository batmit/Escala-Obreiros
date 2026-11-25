import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .backup_job import executar_backup


class BackupJobTests(unittest.TestCase):
    def test_cifra_sem_colocar_senha_nos_argumentos_e_remove_arquivo_claro(self):
        senha = 'chave-longa-apenas-para-o-teste'
        with tempfile.TemporaryDirectory() as pasta:
            diretorio = Path(pasta)
            def exportar(_, arquivo):
                arquivo.write_bytes(b'conteudo-do-banco')
                return {'pessoas': 10}
            def gpg(args, **kwargs):
                self.assertNotIn(senha, ' '.join(args))
                self.assertEqual(kwargs['input'], senha + '\n')
                Path(args[args.index('--output')+1]).write_bytes(b'cifrado')
            with patch.dict(os.environ, {'DATABASE_BACKUP_URL': 'postgresql://user:pass@localhost/db', 'BACKUP_PASSPHRASE': senha}), patch('backend.backup_job.exportar', side_effect=exportar), patch('backend.backup_job.subprocess.run', side_effect=gpg):
                resultado = executar_backup(diretorio)
            self.assertTrue(resultado.is_file())
            self.assertFalse((diretorio / 'snapshot.json.gz').exists())

    def test_nao_remove_snapshot_preexistente(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'snapshot.json.gz'
            arquivo.write_bytes(b'preservar')
            with patch.dict(os.environ, {'DATABASE_BACKUP_URL': 'postgresql://user:pass@localhost/db', 'BACKUP_PASSPHRASE': 'chave-com-mais-de-vinte-caracteres'}), self.assertRaises(ValueError):
                executar_backup(Path(pasta))
            self.assertEqual(arquivo.read_bytes(), b'preservar')
