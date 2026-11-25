"""Persistência e publicação transacional de escalas planejadas."""

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from time import time

from .generation.contracts import Alocacao, EscalaAnterior, PedidoGeracao, ResultadoGeracao, StatusGeracao, Vaga
from .generation.validator import validar_resultado
from .models import Funcao
from .generation.serialization import json_canonico


class RepositorioEscalas:
    def __init__(self, caminho: str | Path):
        self.caminho = caminho

    def _conectar(self):
        connection = sqlite3.connect(self.caminho, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        return connection

    def salvar_e_publicar(self, pedido: PedidoGeracao, resultado: ResultadoGeracao, *, somente_se_ausente: bool = False) -> str:
        if resultado.status not in (StatusGeracao.VIAVEL, StatusGeracao.OTIMA):
            raise ValueError('Somente uma escala viável pode ser salva e publicada.')
        erros = validar_resultado(pedido, resultado)
        if erros:
            raise ValueError('; '.join(erros))
        parametros = json_canonico(asdict(pedido))
        assinatura = hashlib.sha256((parametros + json_canonico(asdict(resultado))).encode('utf-8')).hexdigest()
        vagas = {v.id: v for v in pedido.vagas}
        pessoas = {p.id: p for p in pedido.pessoas}
        with closing(self._conectar()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            if somente_se_ausente:
                publicada = connection.execute('SELECT id FROM escalas WHERE inicio_semana = ? AND publicada = 1', (pedido.inicio_semana.isoformat(),)).fetchone()
                if publicada:
                    return publicada['id']
            existente = connection.execute('SELECT id FROM escalas WHERE assinatura = ?', (assinatura,)).fetchone()
            if existente:
                return existente['id']
            identificador = str(uuid4())
            semana = pedido.inicio_semana.isoformat()
            versao = connection.execute('SELECT COALESCE(MAX(versao), 0) + 1 FROM escalas WHERE inicio_semana = ?', (semana,)).fetchone()[0]
            connection.execute('INSERT INTO escalas VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)', (
                identificador, semana, versao, datetime.now(timezone.utc).isoformat(), assinatura,
                pedido.semente, parametros, json_canonico(resultado.avisos),
            ))
            connection.executemany('INSERT INTO alocacoes_escala VALUES (?, ?, ?, ?, ?, ?)', [
                (identificador, a.vaga_id, vagas[a.vaga_id].data.isoformat(), vagas[a.vaga_id].funcao.value, a.pessoa_id, pessoas[a.pessoa_id].nome)
                for a in resultado.alocacoes
            ])
            connection.execute('UPDATE escalas SET publicada = 0 WHERE inicio_semana = ? AND publicada = 1', (semana,))
            connection.execute('UPDATE escalas SET publicada = 1 WHERE id = ?', (identificador,))
            return identificador

    def adquirir_geracao(self, inicio_semana: date, proprietario: str, agora: float | None = None) -> bool:
        instante = time() if agora is None else agora
        with closing(self._conectar()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('DELETE FROM geracoes_em_andamento WHERE expira_em <= ?', (instante,))
            cursor = connection.execute('INSERT INTO geracoes_em_andamento VALUES (?, ?, ?) ON CONFLICT DO NOTHING',
                (inicio_semana.isoformat(), proprietario, instante + 120))
            return cursor.rowcount == 1

    def liberar_geracao(self, inicio_semana: date, proprietario: str) -> None:
        with closing(self._conectar()) as connection, connection:
            connection.execute('DELETE FROM geracoes_em_andamento WHERE inicio_semana = ? AND proprietario = ?',
                (inicio_semana.isoformat(), proprietario))

    def obter_anterior(self, inicio_semana: date) -> EscalaAnterior | None:
        with closing(self._conectar()) as connection:
            escala = connection.execute('SELECT id FROM escalas WHERE inicio_semana = ? AND publicada = 1', (inicio_semana.isoformat(),)).fetchone()
            if escala is None:
                return None
            rows = connection.execute('SELECT * FROM alocacoes_escala WHERE escala_id = ? ORDER BY data, funcao', (escala['id'],)).fetchall()
            return EscalaAnterior(inicio_semana,
                tuple(Vaga(r['vaga_id'], date.fromisoformat(r['data']), Funcao(r['funcao'])) for r in rows),
                tuple(Alocacao(r['vaga_id'], r['pessoa_id']) for r in rows))

    def consultar_periodo(self, inicio: date, fim: date) -> dict:
        if type(inicio) is not date or type(fim) is not date or not 0 <= (fim - inicio).days <= 30:
            raise ValueError('Informe um intervalo de até 31 dias, com início anterior ou igual ao fim.')
        with closing(self._conectar()) as connection:
            rows = connection.execute('''
                SELECT a.*, e.versao, e.criada_em FROM alocacoes_escala a
                JOIN escalas e ON e.id = a.escala_id
                WHERE e.publicada = 1 AND a.data BETWEEN ? AND ? ORDER BY a.data, a.funcao
            ''', (inicio.isoformat(), fim.isoformat())).fetchall()
        cultos = {}
        for row in rows:
            data = row['data']
            culto = cultos.setdefault(data, {'id': f'culto-{date.fromisoformat(data).isoweekday()}', 'data': data, 'atribuicoes': [], 'versao': row['versao']})
            culto['atribuicoes'].append({'funcao': row['funcao'], 'obreiro': row['nome_pessoa']})
        return {'cultos': list(cultos.values()), 'atualizada_em': max((r['criada_em'] for r in rows), default=None)}
