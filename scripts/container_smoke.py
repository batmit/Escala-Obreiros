"""Smoke test executado pelo CI com Docker Engine Linux ativo."""

import json
import subprocess
import time
from datetime import date, timedelta
from urllib.request import urlopen


def compose(*args):
    return subprocess.check_output(['docker', 'compose', *args], text=True).strip()


def obter_escala():
    codigo = "import json,sqlite3,os; c=sqlite3.connect(os.environ['DATABASE_PATH']); print(json.dumps(c.execute('SELECT id, inicio_semana FROM escalas WHERE publicada=1').fetchall()))"
    return json.loads(compose('exec', '-T', 'app', 'python', '-c', codigo))


def main():
    compose('up', '--detach', '--wait', '--wait-timeout', '120')
    prazo = time.monotonic() + 30
    escalas = obter_escala()
    while not escalas and time.monotonic() < prazo:
        time.sleep(0.1)
        escalas = obter_escala()
    assert len(escalas) == 1, escalas
    inicio = date.fromisoformat(escalas[0][1])
    fim = inicio + timedelta(days=6)
    with urlopen(f'http://127.0.0.1:8080/api/escalas?inicio={inicio}&fim={fim}', timeout=5) as response:
        dados = json.load(response)
        assert sum(len(c['atribuicoes']) for c in dados['cultos']) == 8
    compose('restart')
    compose('up', '--detach', '--wait', '--wait-timeout', '120')
    assert obter_escala() == escalas, 'A escala mudou após reiniciar o serviço.'
    with urlopen('http://127.0.0.1:8080/healthz', timeout=5) as response:
        assert json.load(response)['workers'] == {'agendador': 'ativo', 'backups': 'ativo'}
    print('OK: API, workers, volume e escala preservados após reinício.')


if __name__ == '__main__':
    main()
