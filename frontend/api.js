'use strict';

// Adaptador HTTP: a renderização continua sem conhecer banco, API ou solver.
(() => {
  let requestId = 0;
  const status = document.getElementById('sincronizacao');
  async function atualizar() {
    const id = ++requestId;
    const inicio = window.EscalaUI.obterInicioPeriodo();
    const fim = new Date(`${inicio}T00:00:00Z`);
    fim.setUTCDate(fim.getUTCDate() + 6);
    status.textContent = 'Consultando escala salva…';
    try {
      const params = new URLSearchParams({ inicio, fim: fim.toISOString().slice(0, 10) });
      const response = await fetch(`/api/escalas?${params}`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Consulta indisponível.');
      const dados = await response.json();
      if (id !== requestId) return;
      if (!Array.isArray(dados.cultos)) throw new Error('Resposta inválida.');
      window.EscalaUI.renderizar({ cultos: dados.cultos });
      status.textContent = dados.atualizada_em
        ? `Escala salva no banco · Atualizada em ${new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo' }).format(new Date(dados.atualizada_em))}`
        : 'Nenhuma escala salva para este período.';
    } catch {
      if (id !== requestId) return;
      status.textContent = 'Não foi possível atualizar a escala. Verifique a conexão e use o servidor da aplicação.';
    }
  }
  window.addEventListener('escala:navegar', () => {
    window.EscalaUI.renderizar({ cultos: [] });
    atualizar();
  });
  window.addEventListener('focus', atualizar);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) atualizar(); });
  setInterval(() => { if (!document.hidden) atualizar(); }, 60000);
  atualizar();
})();
