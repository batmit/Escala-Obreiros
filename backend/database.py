"""Adaptador SQLite: criação, carga inicial e leitura dos dados."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .models import Culto, Funcao, Participacao, Pessoa, Pregacao, Regras
from .seed import dados_iniciais


class BancoIgreja:
    def __init__(self, caminho: str | Path):
        self._connection = sqlite3.connect(caminho)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute('PRAGMA foreign_keys = ON')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._connection.close()

    def inicializar(self) -> None:
        self._connection.executescript(
            Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
        )
        # Migração transacional do formato anterior; conflito interrompe sem perder o legado.
        with self._connection:
            legado = self._connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'pregacoes'").fetchone()
            if legado:
                for row in self._connection.execute('SELECT data, pessoa_id FROM pregacoes').fetchall():
                    existente = self._connection.execute("SELECT pessoa_id FROM participacoes WHERE data = ? AND funcao = 'palavra'", (row[0],)).fetchone()
                    if existente and existente[0] != row[1]:
                        raise ValueError('Conflito na migração do histórico de pregações.')
                    if not existente:
                        self._connection.execute("INSERT INTO participacoes VALUES (?, ?, 'palavra')", tuple(row))
                self._connection.execute('DROP TABLE pregacoes')

    def carregar_dados_iniciais(self) -> None:
        """Insere dados ausentes sem sobrescrever alterações existentes."""
        with self._connection:
            for tabela, colunas, linhas in dados_iniciais():
                comando = f"INSERT INTO {tabela} ({','.join(colunas)}) VALUES ({','.join('?' for _ in colunas)}) ON CONFLICT DO NOTHING"
                self._connection.executemany(comando, linhas)

    def listar_pessoas(self) -> list[Pessoa]:
        rows = self._connection.execute('SELECT p.id, p.nome, p.grupo_id, p.cargo, c.peso FROM pessoas p JOIN cargos c ON c.nome = p.cargo ORDER BY p.grupo_id, p.id')
        return [Pessoa(*row) for row in rows]

    def listar_cultos(self) -> list[Culto]:
        result = []
        for row in self._connection.execute('SELECT dia_semana FROM cultos ORDER BY dia_semana'):
            dia = row[0]
            funcoes = tuple(r[0] for r in self._connection.execute('SELECT funcao FROM funcoes_culto WHERE dia_semana = ? ORDER BY funcao', (dia,)))
            pesos = tuple(tuple(r) for r in self._connection.execute('SELECT grupo_id, peso FROM pesos_grupos_culto WHERE dia_semana = ? ORDER BY grupo_id', (dia,)))
            periodo = self._connection.execute('SELECT periodo FROM periodos_culto WHERE dia_semana = ?', (dia,)).fetchone()
            result.append(Culto(dia, funcoes, pesos, periodo[0] if periodo else 'não informado'))
        return result

    def registrar_pregacao(self, pregacao: Pregacao) -> None:
        """Compatibilidade: palavra é uma participação."""
        self.registrar_participacao(Participacao(pregacao.data, pregacao.pessoa_id, Funcao.PALAVRA))

    def registrar_participacao(self, participacao: Participacao) -> None:
        """Registra fatos sem sobrescrever conflitos nem aplicar regras do gerador."""
        with self._connection:
            if not self._connection.execute('SELECT 1 FROM funcoes_culto WHERE dia_semana = ? AND funcao = ?', (participacao.data.isoweekday(), participacao.funcao.value)).fetchone():
                raise ValueError('Não há essa função de culto configurada nesse dia.')
            existente = self._connection.execute('SELECT pessoa_id FROM participacoes WHERE data = ? AND funcao = ?', (participacao.data.isoformat(), participacao.funcao.value)).fetchone()
            if existente:
                if existente[0] != participacao.pessoa_id:
                    raise ValueError('Já existe outra pessoa nessa data e função.')
                return
            self._connection.execute('INSERT INTO participacoes VALUES (?, ?, ?)', (participacao.data.isoformat(), participacao.pessoa_id, participacao.funcao.value))

    def listar_pregacoes_ultimas_duas_semanas(self, referencia: date) -> list[Pregacao]:
        return [Pregacao(p.data, p.pessoa_id) for p in self.listar_participacoes_ultimas_duas_semanas(referencia) if p.funcao == Funcao.PALAVRA]

    def listar_participacoes_ultimas_duas_semanas(self, referencia: date) -> list[Participacao]:
        """Duas semanas completas anteriores à semana da referência (segunda a domingo)."""
        if type(referencia) is not date:
            raise ValueError('Referência deve ser datetime.date.')
        fim = referencia - timedelta(days=referencia.weekday())
        inicio = fim - timedelta(days=14)
        rows = self._connection.execute('SELECT data, pessoa_id, funcao FROM participacoes WHERE data >= ? AND data < ? ORDER BY data, funcao', (inicio.isoformat(), fim.isoformat()))
        return [Participacao(date.fromisoformat(row[0]), row[1], Funcao(row[2])) for row in rows]

    def obter_regras(self) -> Regras:
        row = self._connection.execute('SELECT maximo_participacoes_semana, evitar_semanas_consecutivas, permitir_flexibilizar_consecutivas FROM regras WHERE id = 1').fetchone()
        if row is None:
            raise ValueError('Regras ainda não cadastradas; execute a carga inicial.')
        return Regras(row[0], bool(row[1]), bool(row[2]))
