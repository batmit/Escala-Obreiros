"""Factory para hospedagem WSGI gratuita; não cria threads nem servidor próprio."""

from pathlib import Path

from .bootstrap import preparar_banco
from .on_access import RenovacaoPorAcesso
from .webapp import criar_aplicacao
from .storage import resolver_banco, postgres


def criar_wsgi(banco: str | Path, backups: str | Path | None = None):
    caminho = resolver_banco(banco)
    preparar_banco(caminho)
    manter = RenovacaoPorAcesso(caminho, None if postgres(caminho) else backups or Path(caminho).parent / 'backups')
    return criar_aplicacao(caminho, ao_consultar=manter)
