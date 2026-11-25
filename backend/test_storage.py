import unittest
from pathlib import Path
from unittest.mock import patch

from .storage import banco_igreja, postgres, repositorio_escalas, resolver_banco


class StorageTests(unittest.TestCase):
    def test_variavel_invalida_nao_faz_fallback_para_sqlite(self):
        for url in ('', 'sqlite:///arquivo', 'postgresql://usuario:senha@remote/db'):
            with patch.dict('os.environ', {'DATABASE_URL': url}), self.assertRaises(ValueError):
                resolver_banco()

    def test_postgres_remoto_exige_tls_e_seleciona_adaptadores(self):
        url = 'postgresql://usuario:segredo@host.neon.tech/db?sslmode=require'
        with patch.dict('os.environ', {'DATABASE_URL': url}):
            self.assertEqual(resolver_banco(), url)
        self.assertTrue(postgres(url))
        self.assertEqual(type(banco_igreja(url)).__name__, 'BancoPostgres')
        self.assertEqual(type(repositorio_escalas(url)).__name__, 'RepositorioPostgres')
        self.assertIsInstance(resolver_banco(Path('data/igreja.sqlite3')), Path)
