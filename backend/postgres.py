"""Adaptadores PostgreSQL com transações curtas compatíveis com o pool do Neon."""

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .generation.contracts import Alocacao, EscalaAnterior, StatusGeracao, Vaga
from .generation.validator import validar_resultado
from .models import Culto, Funcao, Participacao, Pessoa, Pregacao, Regras
from .generation.serialization import json_canonico
from .seed import dados_iniciais


def conectar(url):
    return psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=10, prepare_threshold=None)


def trava_transacao(connection, chave):
    numero = int.from_bytes(hashlib.sha256(chave.encode()).digest()[:8], 'big', signed=True)
    connection.execute("SET LOCAL lock_timeout = '10s'")
    connection.execute("SET LOCAL statement_timeout = '20s'")
    connection.execute('SELECT pg_advisory_xact_lock(%s)', (numero,))


def migrar_schema(url):
    with conectar(url) as connection, connection.transaction():
        trava_transacao(connection, 'schema-migrations')
        connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations (versao TEXT PRIMARY KEY, checksum TEXT NOT NULL, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        for arquivo in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
            texto = arquivo.read_text(encoding='utf-8')
            checksum = hashlib.sha256(texto.encode()).hexdigest()
            row = connection.execute('SELECT checksum FROM schema_migrations WHERE versao=%s', (arquivo.stem,)).fetchone()
            if row:
                if row['checksum'] != checksum:
                    raise ValueError('Uma migração já aplicada foi alterada.')
                continue
            connection.execute(texto, prepare=False)
            connection.execute('INSERT INTO schema_migrations (versao, checksum) VALUES (%s, %s)', (arquivo.stem, checksum))


class BancoPostgres:
    def __init__(self, url):
        self.url = url

    def __enter__(self):
        self.connection = conectar(self.url)
        return self

    def __exit__(self, *_):
        self.connection.close()

    def inicializar(self):
        migrar_schema(self.url)

    def carregar_dados_iniciais(self):
        with self.connection.transaction():
            for tabela, colunas, linhas in dados_iniciais():
                comando = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING').format(
                    sql.Identifier(tabela), sql.SQL(',').join(map(sql.Identifier, colunas)),
                    sql.SQL(',').join(sql.Placeholder() for _ in colunas))
                with self.connection.cursor() as cursor:
                    cursor.executemany(comando, linhas)

    def listar_pessoas(self):
        rows = self.connection.execute('SELECT p.id,p.nome,p.grupo_id,p.cargo,c.peso FROM pessoas p JOIN cargos c ON c.nome=p.cargo ORDER BY p.grupo_id,p.id').fetchall()
        return [Pessoa(r['id'], r['nome'], r['grupo_id'], r['cargo'], r['peso']) for r in rows]

    def listar_cultos(self):
        result = []
        for row in self.connection.execute('SELECT c.dia_semana, p.periodo FROM cultos c LEFT JOIN periodos_culto p USING (dia_semana) ORDER BY c.dia_semana').fetchall():
            dia = row['dia_semana']
            funcoes = tuple(r['funcao'] for r in self.connection.execute('SELECT funcao FROM funcoes_culto WHERE dia_semana=%s ORDER BY funcao', (dia,)))
            pesos = tuple((r['grupo_id'], r['peso']) for r in self.connection.execute('SELECT grupo_id,peso FROM pesos_grupos_culto WHERE dia_semana=%s ORDER BY grupo_id', (dia,)))
            result.append(Culto(dia, funcoes, pesos, row['periodo'] or 'não informado'))
        return result

    def obter_regras(self):
        r = self.connection.execute('SELECT * FROM regras WHERE id=1').fetchone()
        if r is None:
            raise ValueError('Regras ainda não cadastradas.')
        return Regras(r['maximo_participacoes_semana'], r['evitar_semanas_consecutivas'], r['permitir_flexibilizar_consecutivas'])

    def registrar_participacao(self, p):
        with self.connection.transaction():
            if not self.connection.execute('SELECT 1 FROM funcoes_culto WHERE dia_semana=%s AND funcao=%s', (p.data.isoweekday(), p.funcao.value)).fetchone():
                raise ValueError('Função não configurada para o dia.')
            self.connection.execute('INSERT INTO participacoes VALUES (%s,%s,%s) ON CONFLICT (data,funcao) DO NOTHING', (p.data, p.pessoa_id, p.funcao.value))
            r = self.connection.execute('SELECT pessoa_id FROM participacoes WHERE data=%s AND funcao=%s', (p.data, p.funcao.value)).fetchone()
            if r['pessoa_id'] != p.pessoa_id:
                raise ValueError('Já existe outra pessoa nessa data e função.')

    def registrar_pregacao(self, p):
        self.registrar_participacao(Participacao(p.data, p.pessoa_id, Funcao.PALAVRA))

    def listar_participacoes_ultimas_duas_semanas(self, referencia):
        if type(referencia) is not date:
            raise ValueError('Referência deve ser datetime.date.')
        fim = referencia - timedelta(days=referencia.weekday())
        rows = self.connection.execute('SELECT * FROM participacoes WHERE data >= %s AND data < %s ORDER BY data,funcao', (fim - timedelta(days=14), fim))
        return [Participacao(r['data'], r['pessoa_id'], Funcao(r['funcao'])) for r in rows]

    def listar_pregacoes_ultimas_duas_semanas(self, referencia):
        return [Pregacao(p.data, p.pessoa_id) for p in self.listar_participacoes_ultimas_duas_semanas(referencia) if p.funcao == Funcao.PALAVRA]


class RepositorioPostgres:
    def __init__(self, url):
        self.url = url

    def salvar_e_publicar(self, pedido, resultado, *, somente_se_ausente=False):
        if resultado.status not in (StatusGeracao.VIAVEL, StatusGeracao.OTIMA):
            raise ValueError('Somente uma escala viável pode ser publicada.')
        erros = validar_resultado(pedido, resultado)
        if erros:
            raise ValueError('; '.join(erros))
        parametros = json_canonico(asdict(pedido))
        assinatura = hashlib.sha256((parametros + json_canonico(asdict(resultado))).encode()).hexdigest()
        with conectar(self.url) as connection, connection.transaction():
            trava_transacao(connection, 'publicar:' + pedido.inicio_semana.isoformat())
            if somente_se_ausente:
                row = connection.execute('SELECT id FROM escalas WHERE inicio_semana=%s AND publicada', (pedido.inicio_semana,)).fetchone()
                if row:
                    return row['id']
            existente = connection.execute('SELECT id FROM escalas WHERE assinatura=%s', (assinatura,)).fetchone()
            if existente:
                return existente['id']
            versao = connection.execute('SELECT COALESCE(MAX(versao),0)+1 AS numero FROM escalas WHERE inicio_semana=%s', (pedido.inicio_semana,)).fetchone()['numero']
            identificador = str(uuid4())
            connection.execute('INSERT INTO escalas VALUES (%s,%s,%s,%s,FALSE,%s,%s,%s,%s)', (
                identificador, pedido.inicio_semana, versao, datetime.now(timezone.utc), assinatura, pedido.semente,
                Jsonb(json.loads(parametros)), Jsonb(list(resultado.avisos))))
            vagas, pessoas = {v.id: v for v in pedido.vagas}, {p.id: p for p in pedido.pessoas}
            with connection.cursor() as cursor:
                cursor.executemany('INSERT INTO alocacoes_escala VALUES (%s,%s,%s,%s,%s,%s)', [
                    (identificador, a.vaga_id, vagas[a.vaga_id].data, vagas[a.vaga_id].funcao.value, a.pessoa_id, pessoas[a.pessoa_id].nome)
                    for a in resultado.alocacoes])
            connection.execute('UPDATE escalas SET publicada=FALSE WHERE inicio_semana=%s AND publicada', (pedido.inicio_semana,))
            connection.execute('UPDATE escalas SET publicada=TRUE WHERE id=%s', (identificador,))
            return identificador

    def obter_anterior(self, inicio_semana):
        with conectar(self.url) as connection:
            rows = connection.execute('SELECT a.* FROM alocacoes_escala a JOIN escalas e ON e.id=a.escala_id WHERE e.inicio_semana=%s AND e.publicada ORDER BY a.data,a.funcao', (inicio_semana,)).fetchall()
            # Uma semana configurada vazia também pode ter publicação.
            if not rows and not connection.execute('SELECT 1 FROM escalas WHERE inicio_semana=%s AND publicada', (inicio_semana,)).fetchone():
                return None
            return EscalaAnterior(inicio_semana, tuple(Vaga(r['vaga_id'], r['data'], Funcao(r['funcao'])) for r in rows), tuple(Alocacao(r['vaga_id'], r['pessoa_id']) for r in rows))

    def adquirir_geracao(self, inicio_semana, proprietario, agora=None):
        with conectar(self.url) as connection:
            row = connection.execute('''INSERT INTO geracoes_em_andamento VALUES (%s,%s,COALESCE(%s::double precision,EXTRACT(EPOCH FROM clock_timestamp()))+120)
                ON CONFLICT (inicio_semana) DO UPDATE SET proprietario=EXCLUDED.proprietario, expira_em=EXCLUDED.expira_em
                WHERE geracoes_em_andamento.expira_em <= EXCLUDED.expira_em-120 RETURNING proprietario''', (inicio_semana, proprietario, agora)).fetchone()
            return row is not None

    def liberar_geracao(self, inicio_semana, proprietario):
        with conectar(self.url) as connection:
            connection.execute('DELETE FROM geracoes_em_andamento WHERE inicio_semana=%s AND proprietario=%s', (inicio_semana, proprietario))

    def consultar_periodo(self, inicio, fim):
        if type(inicio) is not date or type(fim) is not date or not 0 <= (fim-inicio).days <= 30:
            raise ValueError('Informe um intervalo de até 31 dias.')
        with conectar(self.url) as connection:
            rows = connection.execute('SELECT a.*,e.versao,e.criada_em FROM alocacoes_escala a JOIN escalas e ON e.id=a.escala_id WHERE e.publicada AND a.data BETWEEN %s AND %s ORDER BY a.data,a.funcao', (inicio, fim)).fetchall()
        cultos = {}
        for r in rows:
            chave = r['data'].isoformat()
            culto = cultos.setdefault(chave, {'id': f"culto-{r['data'].isoweekday()}", 'data': chave, 'atribuicoes': [], 'versao': r['versao']})
            culto['atribuicoes'].append({'funcao': r['funcao'], 'obreiro': r['nome_pessoa']})
        atualizada = max((r['criada_em'] for r in rows), default=None)
        return {'cultos': list(cultos.values()), 'atualizada_em': atualizada.isoformat() if atualizada else None}
