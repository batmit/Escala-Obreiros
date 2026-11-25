# Frontend

O visual segue o projeto `Cronometro_Cultos_ICM`: Segoe UI, fundo cinza-claro, painéis brancos, vermelho institucional e azul-escuro. A logo centralizada e o favicon usam o mesmo SVG oficial remoto do cronômetro; o carregamento da imagem depende de acesso ao site da igreja. As cores ficam centralizadas em variáveis CSS.

Calendário móvel de sete dias em HTML, CSS e JavaScript, no horário `America/Sao_Paulo`.

## Executar

Na raiz do projeto:

```sh
python -m backend
python -m backend.server --porta 8000
```

Abra http://localhost:8000. É necessário servir via HTTP para carregar a configuração JSON; abrir o HTML diretamente não é mais suportado.

`cultos.json` é exportado do banco, sem pessoas ou pesos individuais. Não editar manualmente: altere o banco e exporte novamente. Não há configuração de cultos no JavaScript. Domingo possui apenas um culto à noite, com louvor e palavra. Esse arquivo estático é apenas uma exportação. No servidor backend.server, a rota /cultos.json consulta diretamente o banco. O adaptador api.js consulta /api/escalas para preencher o calendário.

## Atribuições

```javascript
window.EscalaUI.renderizar({
  cultos: [{
    id: 'culto-7',
    data: '2026-11-29',
    atribuicoes: [
      { funcao: 'palavra', obreiro: 'Hugo' },
      { funcao: 'louvor', obreiro: 'Juninho' }
    ]
  }]
});
```

Os IDs vêm do JSON. Os antigos `domingo_manha` e `domingo_noite` foram substituídos por `culto-7`. Cada chamada substitui as atribuições disponíveis. O evento `escala:navegar` informa `{ inicio, fim }`; `obterInicioPeriodo()` retorna o primeiro dia exibido. Os aliases `inicioSemana` e `obterInicioSemana()` permanecem por compatibilidade. O consumidor deve consultar o período inicial após instalar seu listener.

## Escalas salvas

Siga [persistência e integração](../docs/persistence.md) para gerar e salvar as escalas. Use backend.server: o servidor genérico http.server não fornece a API. Os dados são atualizados na navegação, no retorno à aba e a cada minuto enquanto visível.
