"""Configuração inicial da igreja compartilhada pelos adaptadores."""


def dados_iniciais():
    pessoas = [
        ('arilson', 'Arilson', 1, 'obreiro'), ('daniel', 'Daniel', 1, 'obreiro'),
        ('mateus-emilio', 'Mateus Emílio', 1, 'obreiro'), ('edimar', 'Edimar', 1, 'obreiro'),
        ('maciel', 'Maciel', 1, 'obreiro'), ('hugo', 'Hugo', 2, 'diácono'),
        ('pr-sebastiao', 'Pr Sebastião', 2, 'pastor'), ('jose-carlos', 'José Carlos', 2, 'diácono'),
        ('juninho', 'Juninho', 2, 'obreiro'), ('deivid', 'Deivid', 2, 'obreiro'),
    ]
    dias = (1, 2, 4, 6, 7)
    funcoes = [(dia, funcao) for dia in dias for funcao in (('louvor', 'palavra') if dia in (2, 6, 7) else ('palavra',))]
    pesos = [(dia, grupo, peso) for dia in dias for grupo, peso in
        (((2, 1),) if dia == 7 else (((1, 2), (2, 1)) if dia in (1, 4) else ((1, 1), (2, 2))))]
    return [
        ('grupos', ('id',), [(1,), (2,)]),
        ('cargos', ('nome', 'peso'), [('obreiro', 1), ('diácono', 2), ('pastor', 3)]),
        ('pessoas', ('id', 'nome', 'grupo_id', 'cargo'), pessoas),
        ('cultos', ('dia_semana',), [(dia,) for dia in dias]),
        ('periodos_culto', ('dia_semana', 'periodo'), [(dia, 'noite' if dia == 7 else 'não informado') for dia in dias]),
        ('funcoes_culto', ('dia_semana', 'funcao'), funcoes),
        ('pesos_grupos_culto', ('dia_semana', 'grupo_id', 'peso'), pesos),
        ('regras', ('id', 'maximo_participacoes_semana', 'evitar_semanas_consecutivas', 'permitir_flexibilizar_consecutivas'), [(1, 1, True, True)]),
    ]
