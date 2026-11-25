-- Executar como proprietário após criar escala_runtime e escala_backup
-- pelo painel do Neon. Senhas não devem ser adicionadas a este arquivo.
GRANT USAGE ON SCHEMA public TO escala_runtime, escala_backup;
GRANT SELECT ON grupos, cargos, pessoas, cultos, funcoes_culto,
    pesos_grupos_culto, regras, periodos_culto, participacoes,
    escalas, alocacoes_escala, geracoes_em_andamento TO escala_runtime;
GRANT INSERT, UPDATE ON escalas TO escala_runtime;
GRANT INSERT ON alocacoes_escala TO escala_runtime;
GRANT INSERT, UPDATE, DELETE ON geracoes_em_andamento TO escala_runtime;
GRANT SELECT ON grupos, cargos, pessoas, cultos, funcoes_culto,
    pesos_grupos_culto, regras, periodos_culto, participacoes,
    escalas, alocacoes_escala TO escala_backup;
