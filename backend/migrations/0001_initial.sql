CREATE TABLE grupos (id INTEGER PRIMARY KEY CHECK (id IN (1, 2)));
CREATE TABLE cargos (nome TEXT PRIMARY KEY, peso INTEGER NOT NULL CHECK (peso > 0));
CREATE TABLE pessoas (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL CHECK (length(trim(nome)) > 0),
    grupo_id INTEGER NOT NULL REFERENCES grupos(id),
    cargo TEXT NOT NULL REFERENCES cargos(nome)
);
CREATE TABLE cultos (dia_semana INTEGER PRIMARY KEY CHECK (dia_semana BETWEEN 1 AND 7));
CREATE TABLE funcoes_culto (
    dia_semana INTEGER NOT NULL REFERENCES cultos(dia_semana),
    funcao TEXT NOT NULL CHECK (funcao IN ('palavra', 'louvor')),
    PRIMARY KEY (dia_semana, funcao)
);
CREATE TABLE pesos_grupos_culto (
    dia_semana INTEGER NOT NULL REFERENCES cultos(dia_semana),
    grupo_id INTEGER NOT NULL REFERENCES grupos(id),
    peso INTEGER NOT NULL CHECK (peso > 0), PRIMARY KEY (dia_semana, grupo_id)
);
CREATE TABLE regras (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    maximo_participacoes_semana INTEGER NOT NULL CHECK (maximo_participacoes_semana > 0),
    evitar_semanas_consecutivas BOOLEAN NOT NULL,
    permitir_flexibilizar_consecutivas BOOLEAN NOT NULL
);
CREATE TABLE periodos_culto (
    dia_semana INTEGER PRIMARY KEY REFERENCES cultos(dia_semana),
    periodo TEXT NOT NULL CHECK (periodo IN ('manhã', 'tarde', 'noite', 'não informado'))
);
CREATE TABLE participacoes (
    data DATE NOT NULL, pessoa_id TEXT NOT NULL REFERENCES pessoas(id),
    funcao TEXT NOT NULL CHECK (funcao IN ('palavra', 'louvor')),
    PRIMARY KEY (data, funcao), UNIQUE (data, pessoa_id)
);
CREATE INDEX idx_participacoes_pessoa ON participacoes(pessoa_id);
CREATE TABLE escalas (
    id TEXT PRIMARY KEY,
    inicio_semana DATE NOT NULL CHECK (EXTRACT(ISODOW FROM inicio_semana) = 1),
    versao INTEGER NOT NULL CHECK (versao > 0),
    criada_em TIMESTAMPTZ NOT NULL,
    publicada BOOLEAN NOT NULL DEFAULT FALSE,
    assinatura TEXT NOT NULL UNIQUE,
    semente INTEGER NOT NULL,
    parametros_json JSONB NOT NULL,
    avisos_json JSONB NOT NULL,
    UNIQUE (inicio_semana, versao)
);
CREATE UNIQUE INDEX idx_escala_publicada ON escalas(inicio_semana) WHERE publicada;
CREATE TABLE alocacoes_escala (
    escala_id TEXT NOT NULL REFERENCES escalas(id), vaga_id TEXT NOT NULL,
    data DATE NOT NULL, funcao TEXT NOT NULL CHECK (funcao IN ('palavra', 'louvor')),
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id), nome_pessoa TEXT NOT NULL,
    PRIMARY KEY (escala_id, vaga_id), UNIQUE (escala_id, data, funcao), UNIQUE (escala_id, data, pessoa_id)
);
CREATE INDEX idx_alocacoes_data ON alocacoes_escala(data);
CREATE TABLE geracoes_em_andamento (
    inicio_semana DATE PRIMARY KEY, proprietario TEXT NOT NULL, expira_em DOUBLE PRECISION NOT NULL
);
