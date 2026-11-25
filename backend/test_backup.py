import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from .backup import AgendadorBackups, criar_backup, restaurar_backup, verificar_banco
from .database import BancoIgreja
from .scheduler import AgendadorSemanal, garantir_semana_vigente


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.banco = self.pasta / 'igreja.sqlite3'
        self.backups = self.pasta / 'backups'
        with BancoIgreja(self.banco) as banco:
            banco.inicializar()
            banco.carregar_dados_iniciais()

    def test_backup_online_e_restauracao_preservam_escala_e_dados(self):
        garantir_semana_vigente(self.banco, datetime(2026, 11, 24, tzinfo=timezone.utc))
        with closing(sqlite3.connect(self.banco)) as ativa:
            ativa.execute('PRAGMA journal_mode=WAL')
            ativa.execute("UPDATE pessoas SET nome='Daniel atualizado' WHERE id='daniel'")
            ativa.commit()
            backup = criar_backup(self.banco, self.backups)
            novo = restaurar_backup(backup, self.pasta / 'restaurado.sqlite3')
            verificar_banco(novo)
            with closing(sqlite3.connect(novo)) as restaurada:
                self.assertEqual(restaurada.execute('SELECT count(*) FROM pessoas').fetchone()[0], 10)
                self.assertEqual(restaurada.execute('SELECT count(*) FROM alocacoes_escala').fetchone()[0], 8)
                self.assertEqual(restaurada.execute("SELECT nome FROM pessoas WHERE id='daniel'").fetchone()[0], 'Daniel atualizado')
        with self.assertRaises(ValueError):
            restaurar_backup(backup, self.banco)

    def test_retencao_remove_apenas_backups_proprios(self):
        self.backups.mkdir()
        outro = self.backups / 'arquivo-importante.sqlite3'
        outro.write_text('preservar')
        arquivos = [criar_backup(self.banco, self.backups, reter=2) for _ in range(3)]
        self.assertFalse(arquivos[0].exists())
        self.assertTrue(all(p.exists() for p in arquivos[1:]))
        self.assertTrue(outro.exists())

    def test_falha_nao_remove_backup_anterior_nem_deixa_parcial(self):
        anterior = criar_backup(self.banco, self.backups, reter=1)
        with patch('backend.backup._copiar', side_effect=sqlite3.DatabaseError('erro')):
            with self.assertRaises(sqlite3.DatabaseError):
                criar_backup(self.banco, self.backups, reter=1)
        self.assertTrue(anterior.exists())
        self.assertEqual(list(self.backups.glob('*.partial')), [])

    def test_rejeita_backup_corrompido_e_origem_ausente(self):
        invalido = self.pasta / 'invalido.sqlite3'
        invalido.write_text('não é SQLite')
        destino = self.pasta / 'novo.sqlite3'
        with self.assertRaises(sqlite3.DatabaseError):
            restaurar_backup(invalido, destino)
        self.assertFalse(destino.exists())
        with self.assertRaises(ValueError):
            criar_backup(self.pasta / 'ausente.sqlite3', self.backups)
        with self.assertRaises(ValueError):
            criar_backup(self.banco, self.backups, reter=0)

    def test_intervalo_e_nova_tentativa_depois_de_falha(self):
        agora = [100]
        chamadas = []
        agendador = AgendadorBackups(self.banco, self.backups, intervalo_segundos=300,
            relogio=lambda: agora[0], executar=lambda *args: chamadas.append(args))
        self.assertEqual(agendador.verificar(), 60)
        agora[0] = 200
        agendador.verificar()
        self.assertEqual(len(chamadas), 1)
        agora[0] = 400
        agendador.verificar()
        self.assertEqual(len(chamadas), 2)
        agendador.executar = lambda *_: (_ for _ in ()).throw(OSError('falha'))
        agora[0] = 700
        with self.assertLogs('backend.backup', level='ERROR'):
            self.assertEqual(agendador.verificar(), 60)
        self.assertEqual(agendador.proxima, 760)

    def test_threads_executam_sem_requisicoes_e_encerram(self):
        for classe in (AgendadorSemanal, AgendadorBackups):
            executou = threading.Event()
            kwargs = dict(executar=lambda *_: executou.set())
            worker = classe(self.banco, **kwargs) if classe is AgendadorSemanal else classe(self.banco, self.backups, **kwargs)
            worker.iniciar()
            try:
                self.assertTrue(executou.wait(timeout=5))
            finally:
                worker.encerrar()
            self.assertFalse(worker.thread.is_alive())
