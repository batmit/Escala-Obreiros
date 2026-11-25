"""Manutenção síncrona no primeiro acesso, sem agendadores em background."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from time import time

from .backup import PADRAO, criar_backup
from .storage import repositorio_escalas, postgres
from .scheduler import garantir_semana_vigente, limites_semana

logger = logging.getLogger(__name__)


class RenovacaoPorAcesso:
    def __init__(self, banco, backups, *, relogio=None, gerar=None, copiar=None):
        self.banco = banco
        self.backups = None if postgres(banco) else Path(backups)
        self.relogio = relogio or (lambda: datetime.now(timezone.utc))
        self.gerar = gerar or garantir_semana_vigente
        self.copiar = copiar or criar_backup

    def __call__(self):
        agora = self.relogio()
        semana, _ = limites_semana(agora)
        repo = repositorio_escalas(self.banco)
        # A checagem persistente evita inclusive chamar o algoritmo em outros acessos.
        if repo.obter_anterior(semana) is None:
            self.gerar(self.banco, agora)
        if repo.obter_anterior(semana) is None:
            raise RuntimeError('A escala semanal está sendo preparada; tente novamente em instantes.')
        if self.backups is None:
            return  # PostgreSQL: backup externo pelo comando dedicado, nunca em disco efêmero.
        try:
            # Em hospedagem sem workers, o primeiro acesso após 24h faz o backup.
            existentes = [p for p in self.backups.glob('igreja-backup-*.sqlite3') if PADRAO.fullmatch(p.name) and p.is_file() and not p.is_symlink()]
            recente = max((p.stat().st_mtime for p in existentes), default=0)
            if time() - recente >= 86400:
                self.copiar(self.banco, self.backups, reter=3)
        except Exception:
            logger.exception('Backup por acesso falhou; a escala publicada permanece disponível.')
