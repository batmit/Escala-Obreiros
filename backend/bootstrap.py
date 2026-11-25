"""Inicialização: SQLite local; PostgreSQL migrado por comando administrativo."""
from pathlib import Path
from .storage import banco_igreja, postgres


def preparar_banco(alvo):
    if postgres(alvo):
        with banco_igreja(alvo) as banco:
            banco.obter_regras()
        return
    caminho = Path(alvo)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo = not caminho.exists()
    with banco_igreja(caminho) as banco:
        banco.inicializar()
        if novo:
            banco.carregar_dados_iniciais()
        banco.obter_regras()
