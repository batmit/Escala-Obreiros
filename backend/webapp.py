"""API e aplicação WSGI sem dependência do servidor de execução."""

import json
import mimetypes
import logging
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from .storage import banco_igreja, postgres, ERROS_BANCO
from .storage import repositorio_escalas

FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'
ARQUIVOS_PUBLICOS = {'/': 'index.html', '/index.html': 'index.html', '/styles.css': 'styles.css',
    '/calendar.js': 'calendar.js', '/api.js': 'api.js'}


def consultar_api(path, query, banco, workers=None):
    try:
        if path in ('/healthz', '/readyz'):
            if path == '/readyz' or not postgres(banco):
                with banco_igreja(banco) as dados:
                    dados.obter_regras()
            estados = {nome: 'desativado' if worker is None else 'ativo' if worker.thread.is_alive() else 'parado'
                for nome, worker in (workers or {}).items()}
            saudavel = 'parado' not in estados.values()
            return {'status': 'ok' if saudavel else 'degradado', 'workers': estados}, 200 if saudavel else 503
        if path == '/api/escalas':
            params = parse_qs(query, keep_blank_values=True)
            if set(params) != {'inicio', 'fim'} or any(len(v) != 1 for v in params.values()):
                raise ValueError('Informe inicio e fim uma única vez.')
            inicio, fim = (date.fromisoformat(params[k][0]) for k in ('inicio', 'fim'))
            return repositorio_escalas(banco).consultar_periodo(inicio, fim), 200
        if path == '/cultos.json':
            with banco_igreja(banco) as dados:
                cultos = dados.listar_cultos()
            return [{'id': f'culto-{c.dia_semana}', 'diaSemana': c.dia_semana,
                'titulo': 'Culto' if c.periodo == 'não informado' else f'Culto · {c.periodo}', 'funcoes': c.funcoes} for c in cultos], 200
    except ValueError as erro:
        if path in ('/healthz', '/readyz'):
            return {'erro': 'Configuração do banco indisponível.'}, 503
        return {'erro': str(erro)}, 400
    except ERROS_BANCO:
        return {'erro': 'Não foi possível consultar a escala.'}, 503
    if path.startswith('/api/'):
        return {'erro': 'Recurso não encontrado.'}, 404
    return None


def criar_aplicacao(banco, workers=None, *, ao_consultar=None):
    def application(environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        extras = []
        if method not in ('GET', 'HEAD'):
            dados, status = {'erro': 'Método não permitido.'}, 405
            extras.append(('Allow', 'GET, HEAD'))
            resposta = dados, status
        else:
            resposta = None
            # Somente GET de consulta válida dispara manutenção; healthcheck/HEAD não geram.
            if method == 'GET' and path == '/api/escalas' and ao_consultar is not None:
                params = parse_qs(environ.get('QUERY_STRING', ''), keep_blank_values=True)
                valido = set(params) == {'inicio', 'fim'} and all(len(v) == 1 for v in params.values())
                try:
                    inicio, fim = (date.fromisoformat(params[k][0]) for k in ('inicio', 'fim')) if valido else (None, None)
                    valido = valido and 0 <= (fim - inicio).days <= 30
                except (ValueError, TypeError):
                    valido = False
                if valido:
                    try:
                        ao_consultar()
                    except Exception:
                        logging.getLogger(__name__).exception('Falha ao preparar a escala no acesso.')
                        resposta = {'erro': 'A escala semanal ainda não está disponível. Tente novamente em instantes.'}, 503
            if resposta is None:
                resposta = consultar_api(path, environ.get('QUERY_STRING', ''), banco, workers)
        if resposta is not None:
            dados, status = resposta
            payload = json.dumps(dados, ensure_ascii=False).encode('utf-8')
            content_type = 'application/json; charset=utf-8'
        elif path in ARQUIVOS_PUBLICOS:
            arquivo = FRONTEND / ARQUIVOS_PUBLICOS[path]
            payload = arquivo.read_bytes()
            status = 200
            content_type = (mimetypes.guess_type(arquivo.name)[0] or 'application/octet-stream') + '; charset=utf-8'
        else:
            payload, status, content_type = b'Not found', 404, 'text/plain; charset=utf-8'
        textos = {200: 'OK', 400: 'Bad Request', 404: 'Not Found', 405: 'Method Not Allowed', 503: 'Service Unavailable'}
        start_response(f'{status} {textos[status]}', [('Content-Type', content_type), ('Content-Length', str(len(payload))),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'DENY')] + extras)
        return [] if method == 'HEAD' else [payload]
    return application
