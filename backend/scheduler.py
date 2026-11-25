"""Renovação semanal no fuso da igreja; independente da interface HTTP."""

import logging
import secrets
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4
from zoneinfo import ZoneInfo

from .storage import banco_igreja
from .generation.contracts import PedidoGeracao
from .generation.cp_sat import gerar_escala
from .generation.slots import criar_vagas_semanais
from .storage import repositorio_escalas

FUSO_IGREJA = ZoneInfo('America/Sao_Paulo')
logger = logging.getLogger(__name__)


def limites_semana(agora: datetime):
    if agora.tzinfo is None:
        raise ValueError('O relógio deve informar um fuso horário.')
    local = agora.astimezone(FUSO_IGREJA)
    inicio = local.date() - timedelta(days=local.weekday())
    proxima = datetime.combine(inicio + timedelta(days=7), time.min, tzinfo=FUSO_IGREJA)
    return inicio, proxima


def garantir_semana_vigente(caminho: str | Path, agora: datetime) -> bool:
    """Gera somente a semana vigente ausente. Retorna se publicou uma geração."""
    inicio, _ = limites_semana(agora)
    repo = repositorio_escalas(caminho)
    if repo.obter_anterior(inicio) is not None:
        return False
    proprietario = str(uuid4())
    if not repo.adquirir_geracao(inicio, proprietario):
        return False
    try:
        if repo.obter_anterior(inicio) is not None:
            return False
        anterior = repo.obter_anterior(inicio - timedelta(days=7))
        with banco_igreja(caminho) as banco:
            cultos = tuple(banco.listar_cultos())
            pedido = PedidoGeracao(
                inicio_semana=inicio, pessoas=tuple(banco.listar_pessoas()), cultos=cultos,
                vagas=criar_vagas_semanais(inicio, cultos), regras=banco.obter_regras(),
                historico=tuple(banco.listar_participacoes_ultimas_duas_semanas(inicio)),
                escala_anterior=anterior, semente=secrets.randbelow(2**31), limite_segundos=10,
            )
        resultado = gerar_escala(pedido)
        repo.salvar_e_publicar(pedido, resultado, somente_se_ausente=True)
        logger.info('Escala semanal disponível: semana=%s', inicio)
        return True
    finally:
        repo.liberar_geracao(inicio, proprietario)


class AgendadorSemanal:
    def __init__(self, caminho: str | Path, *, relogio=None, executar=None):
        self.caminho = caminho
        self.relogio = relogio or (lambda: datetime.now(timezone.utc))
        self.executar = executar or garantir_semana_vigente
        self.parada = Event()
        self.thread = Thread(target=self._rodar, name='geracao-semanal', daemon=True)

    def iniciar(self):
        _, proxima = limites_semana(self.relogio())
        logger.info('Agendamento ativo; próxima virada semanal=%s; verificação inicial imediata.', proxima.isoformat())
        self.thread.start()

    def encerrar(self):
        self.parada.set()
        self.thread.join(timeout=15)

    def verificar(self) -> float:
        try:
            self.executar(self.caminho, self.relogio())
        except Exception:
            logger.exception('Falha ao renovar escala; nova tentativa em até 60 segundos.')
        agora = self.relogio()
        _, proxima = limites_semana(agora)
        segundos = (proxima.astimezone(timezone.utc) - agora.astimezone(timezone.utc)).total_seconds()
        return max(0.01, min(60.0, segundos))

    def _rodar(self):
        while not self.parada.is_set():
            self.parada.wait(self.verificar())
