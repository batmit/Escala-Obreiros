"""Representação estável das entradas/resultados, independente do armazenamento."""

import json


def json_canonico(dados):
    return json.dumps(dados, ensure_ascii=False, sort_keys=True,
        default=lambda value: value.isoformat(), separators=(',', ':'))
