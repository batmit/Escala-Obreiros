import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

from .database import BancoIgreja
from .models import Funcao, Participacao, Pregacao


class BancoTests(unittest.TestCase):
    def test_migracao_com_conflito_reverte_copias_e_preserva_legado(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'conflito.sqlite3'
            with BancoIgreja(path) as banco:
                banco.inicializar()
                banco.carregar_dados_iniciais()
                banco.registrar_pregacao(Pregacao(date(2026, 11, 17), 'hugo'))
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('CREATE TABLE pregacoes (data TEXT PRIMARY KEY, pessoa_id TEXT NOT NULL)')
                connection.executemany('INSERT INTO pregacoes VALUES (?, ?)', [('2026-11-16', 'daniel'), ('2026-11-17', 'daniel')])
                connection.commit()
            with BancoIgreja(path) as banco:
                with self.assertRaises(ValueError):
                    banco.inicializar()
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM pregacoes').fetchone()[0], 2)
                self.assertEqual(connection.execute('SELECT data, pessoa_id FROM participacoes').fetchall(), [('2026-11-17', 'hugo')])

    def test_mesma_pessoa_nao_ocupa_duas_funcoes_no_dia(self):
        with BancoIgreja(':memory:') as banco:
            banco.inicializar()
            banco.carregar_dados_iniciais()
            banco.registrar_participacao(Participacao(date(2026, 11, 17), 'hugo', Funcao.LOUVOR))
            with self.assertRaises(sqlite3.IntegrityError):
                banco.registrar_pregacao(Pregacao(date(2026, 11, 17), 'hugo'))
            with self.assertRaises(ValueError):
                banco.listar_participacoes_ultimas_duas_semanas('2026-11-24')

    def test_migracao_preserva_pregacoes_e_registra_louvor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legado.sqlite3'
            with BancoIgreja(path) as banco:
                banco.inicializar()
                banco.carregar_dados_iniciais()
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('CREATE TABLE pregacoes (data TEXT PRIMARY KEY, pessoa_id TEXT NOT NULL REFERENCES pessoas(id))')
                connection.execute("INSERT INTO pregacoes VALUES ('2026-11-17', 'daniel')")
                connection.commit()
            louvor = Participacao(date(2026, 11, 17), 'hugo', Funcao.LOUVOR)
            with BancoIgreja(path) as banco:
                banco.inicializar()
                banco.inicializar()
                banco.registrar_participacao(louvor)
                banco.registrar_participacao(louvor)
                with self.assertRaises(ValueError):
                    banco.registrar_participacao(Participacao(louvor.data, 'juninho', Funcao.LOUVOR))
                with self.assertRaises(sqlite3.IntegrityError):
                    banco.registrar_participacao(Participacao(date(2026, 11, 22), 'ausente', Funcao.LOUVOR))
                with self.assertRaises(ValueError):
                    banco.registrar_participacao(Participacao(date(2026, 11, 16), 'hugo', Funcao.LOUVOR))
            with BancoIgreja(path) as banco:
                historico = banco.listar_participacoes_ultimas_duas_semanas(date(2026, 11, 24))
                self.assertEqual(historico, [louvor, Participacao(date(2026, 11, 17), 'daniel', Funcao.PALAVRA)])
                self.assertEqual(banco.listar_pregacoes_ultimas_duas_semanas(date(2026, 11, 24)), [Pregacao(date(2026, 11, 17), 'daniel')])

    def test_historico_duas_semanas_e_integridade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'historico.sqlite3'
            with BancoIgreja(path) as banco:
                banco.inicializar()
                banco.carregar_dados_iniciais()
                registros = [Pregacao(date(2026, 11, 8), 'hugo'), Pregacao(date(2026, 11, 9), 'daniel'), Pregacao(date(2026, 11, 22), 'pr-sebastiao'), Pregacao(date(2026, 11, 23), 'arilson')]
                for registro in registros:
                    banco.registrar_pregacao(registro)
                banco.registrar_pregacao(registros[1])
                with self.assertRaises(ValueError):
                    banco.registrar_pregacao(Pregacao(date(2026, 11, 9), 'hugo'))
                with self.assertRaises(ValueError):
                    banco.registrar_pregacao(Pregacao(date(2026, 11, 11), 'daniel'))
                with self.assertRaises(sqlite3.IntegrityError):
                    banco.registrar_pregacao(Pregacao(date(2026, 11, 10), 'desconhecido'))
                self.assertEqual(next(c.periodo for c in banco.listar_cultos() if c.dia_semana == 7), 'noite')
            with BancoIgreja(path) as banco:
                self.assertEqual(banco.listar_pregacoes_ultimas_duas_semanas(date(2026, 11, 24)), registros[1:3])
                self.assertEqual(banco.listar_pregacoes_ultimas_duas_semanas(date(2026, 11, 23)), registros[1:3])

    def test_persistencia_regras_e_carga_repetida(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'igreja.sqlite3'
            with BancoIgreja(path) as banco:
                banco.inicializar()
                banco.carregar_dados_iniciais()
                banco.carregar_dados_iniciais()
            with BancoIgreja(path) as banco:
                pessoas = banco.listar_pessoas()
                self.assertEqual(len(pessoas), 10)
                self.assertEqual(sum(p.grupo == 1 for p in pessoas), 5)
                self.assertEqual(next(p.peso for p in pessoas if p.id == 'pr-sebastiao'), 3)
                self.assertEqual({p.peso for p in pessoas if p.cargo == 'diácono'}, {2})
                cultos = {c.dia_semana: c for c in banco.listar_cultos()}
                self.assertEqual(set(cultos), {1, 2, 4, 6, 7})
                for dia in (2, 6, 7):
                    self.assertEqual(cultos[dia].funcoes, ('louvor', 'palavra'))
                self.assertEqual(cultos[1].pesos_grupos, ((1, 2), (2, 1)))
                self.assertEqual(cultos[4].pesos_grupos, cultos[1].pesos_grupos)
                self.assertEqual(cultos[2].pesos_grupos, ((1, 1), (2, 2)))
                self.assertEqual(cultos[6].pesos_grupos, cultos[2].pesos_grupos)
                self.assertEqual(cultos[7].pesos_grupos, ((2, 1),))
                regras = banco.obter_regras()
                self.assertEqual(regras.maximo_participacoes_semana, 1)
                self.assertTrue(regras.evitar_semanas_consecutivas)
                self.assertTrue(regras.permitir_flexibilizar_consecutivas)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('PRAGMA foreign_keys = ON')
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO pessoas VALUES ('invalida', 'Teste', 3, 'obreiro')")


if __name__ == '__main__':
    unittest.main()
