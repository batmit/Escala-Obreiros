PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS grupos (
    id INTEGER PRIMARY KEY CHECK (id IN (1, 2))
);
CREATE TABLE IF NOT EXISTS cargos (
    nome TEXT PRIMARY KEY,
    peso INTEGER NOT NULL CHECK (peso > 0)
);
CREATE TABLE IF NOT EXISTS pessoas (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL CHECK (length(trim(nome)) > 0),
    grupo_id INTEGER NOT NULL REFERENCES grupos(id),
    cargo TEXT NOT NULL REFERENCES cargos(nome)
);
CREATE TABLE IF NOT EXISTS cultos (
    dia_semana INTEGER PRIMARY KEY CHECK (dia_semana BETWEEN 1 AND 7)
);
CREATE TABLE IF NOT EXISTS funcoes_culto (
    dia_semana INTEGER NOT NULL REFERENCES cultos(dia_semana),
    funcao TEXT NOT NULL CHECK (funcao IN ('palavra', 'louvor')),
    PRIMARY KEY (dia_semana, funcao)
);
-- Peso relativo do grupo, aplicado antes da escolha ponderada da pessoa.
-- Ausência de associação significa que o grupo não participa nesse dia.
CREATE TABLE IF NOT EXISTS pesos_grupos_culto (
    dia_semana INTEGER NOT NULL REFERENCES cultos(dia_semana),
    grupo_id INTEGER NOT NULL REFERENCES grupos(id),
    peso INTEGER NOT NULL CHECK (peso > 0),
    PRIMARY KEY (dia_semana, grupo_id)
);
CREATE TABLE IF NOT EXISTS regras (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    maximo_participacoes_semana INTEGER NOT NULL CHECK (maximo_participacoes_semana > 0),
    evitar_semanas_consecutivas INTEGER NOT NULL CHECK (evitar_semanas_consecutivas IN (0, 1)),
    permitir_flexibilizar_consecutivas INTEGER NOT NULL CHECK (permitir_flexibilizar_consecutivas IN (0, 1))
);

CREATE TABLE IF NOT EXISTS periodos_culto (
    dia_semana INTEGER PRIMARY KEY REFERENCES cultos(dia_semana),
    periodo TEXT NOT NULL CHECK (periodo IN ('manhã', 'tarde', 'noite', 'não informado'))
);

-- Histórico realizado, não é uma escala planejada.
CREATE TABLE IF NOT EXISTS participacoes (
    data TEXT NOT NULL CHECK (length(data) = 10 AND date(data, '+0 days') IS NOT NULL AND date(data, '+0 days') = data),
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id),
    funcao TEXT NOT NULL CHECK (funcao IN ('palavra', 'louvor')),
    PRIMARY KEY (data, funcao),
    UNIQUE (data, pessoa_id)
);
CREATE INDEX IF NOT EXISTS idx_participacoes_pessoa ON participacoes(pessoa_id);

CREATE TABLE IF NOT EXISTS escalas (
    id TEXT PRIMARY KEY,
    inicio_semana TEXT NOT NULL,
    versao INTEGER NOT NULL CHECK (versao > 0),
    criada_em TEXT NOT NULL,
    publicada INTEGER NOT NULL DEFAULT 0 CHECK (publicada IN (0, 1)),
    assinatura TEXT NOT NULL UNIQUE,
    semente INTEGER NOT NULL,
    parametros_json TEXT NOT NULL,
    avisos_json TEXT NOT NULL,
    UNIQUE (inicio_semana, versao)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_escala_publicada ON escalas(inicio_semana) WHERE publicada = 1;
CREATE TABLE IF NOT EXISTS alocacoes_escala (
    escala_id TEXT NOT NULL REFERENCES escalas(id),
    vaga_id TEXT NOT NULL,
    data TEXT NOT NULL CHECK (length(data) = 10 AND date(data, '+0 days') = data),
    funcao TEXT NOT NULL CHECK (funcao IN ('palavra', 'louvor')),
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id),
    nome_pessoa TEXT NOT NULL,
    PRIMARY KEY (escala_id, vaga_id),
    UNIQUE (escala_id, data, funcao),
    UNIQUE (escala_id, data, pessoa_id)
);
CREATE INDEX IF NOT EXISTS idx_alocacoes_data ON alocacoes_escala(data);

CREATE TABLE IF NOT EXISTS geracoes_em_andamento (
    inicio_semana TEXT PRIMARY KEY,
    proprietario TEXT NOT NULL,
    expira_em REAL NOT NULL
);
