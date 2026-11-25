'use strict';
(() => {
  const clock = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' });
  const weekdays = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
  let services = null;
  let configurationFailed = false;
  const iso = date => date.toISOString().slice(0, 10);
  function todayISO() {
    const p = Object.fromEntries(clock.formatToParts(new Date()).map(part => [part.type, part.value]));
    return `${p.year}-${p.month}-${p.day}`;
  }
  function parse(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Data deve estar no formato AAAA-MM-DD.');
    const result = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(result.getTime()) || iso(result) !== value) throw new Error('Data inválida.');
    return result;
  }
  function plus(date, days) { const result = new Date(date); result.setUTCDate(result.getUTCDate() + days); return result; }
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  let today = todayISO();
  let start = parse(today);
  let entries = new Map();
  function notify() {
    window.dispatchEvent(new CustomEvent('escala:navegar', { detail: { inicio: iso(start), fim: iso(plus(start, 6)), inicioSemana: iso(start) } }));
  }
  function draw() {
    const fragment = document.createDocumentFragment();
    let filled = 0;
    for (let offset = 0; offset < 7; offset++) {
      const date = plus(start, offset), key = iso(date), isToday = key === today;
      const card = el('article', `day${isToday ? ' today' : ''}`);
      if (isToday) card.setAttribute('aria-current', 'date');
      const head = el('div', 'day-head');
      head.append(el('span', 'weekday', weekdays[date.getUTCDay()]));
      const row = el('div', 'date-row'), time = el('time', '', String(date.getUTCDate()).padStart(2, '0'));
      time.dateTime = key; row.append(time);
      if (isToday) row.append(el('span', 'badge', 'Hoje'));
      head.append(row); card.append(head);
      const daily = services?.filter(service => service.diaSemana === (date.getUTCDay() || 7)) || [];
      if (!daily.length) card.append(el('p', 'empty', configurationFailed ? 'Programação indisponível' : services === null ? 'Carregando programação…' : '— Sem culto programado'));
      daily.forEach(service => {
        const box = el('section', 'service'); box.append(el('h3', '', service.titulo));
        const entry = entries.get(`${key}:${service.id}`);
        service.funcoes.forEach(role => {
          const assignment = entry?.atribuicoes.find(a => a && a.funcao === role);
          const name = typeof assignment?.obreiro === 'string' ? assignment.obreiro.trim() : '';
          box.append(el('p', 'role', role === 'louvor' ? 'Louvor' : 'Palavra'), el('p', `person${name ? '' : ' pending'}`, name || 'A definir'));
          if (name) filled++;
        });
        card.append(box);
      });
      fragment.append(card);
    }
    document.getElementById('calendario').replaceChildren(fragment);
    document.getElementById('titulo').textContent = iso(start) === today ? 'Próximos sete dias' : 'Calendário de cultos';
    document.getElementById('status').textContent = filled ? 'Atribuições disponíveis para este período.' : 'Aguardando a publicação da escala.';
    if (configurationFailed) document.getElementById('status').textContent = 'Não foi possível carregar os cultos. Recarregue a página usando um servidor HTTP.';
  }
  function renderizar(data = {}) {
    if (data.cultos !== undefined) {
      if (!Array.isArray(data.cultos)) throw new Error('cultos deve ser uma lista.');
      const next = new Map();
      data.cultos.forEach(entry => {
        if (!entry || typeof entry.id !== 'string' || !Array.isArray(entry.atribuicoes)) throw new Error('Culto inválido.');
        parse(entry.data);
        const key = `${entry.data}:${entry.id}`;
        if (next.has(key)) throw new Error('Culto duplicado na mesma data.');
        const roles = new Set();
        const atribuicoes = entry.atribuicoes.map(assignment => {
          if (!assignment || typeof assignment.funcao !== 'string' || typeof assignment.obreiro !== 'string' || roles.has(assignment.funcao)) throw new Error('Atribuição inválida ou duplicada.');
          roles.add(assignment.funcao);
          return { funcao: assignment.funcao, obreiro: assignment.obreiro };
        });
        next.set(key, { atribuicoes });
      });
      entries = next;
    }
    draw();
  }
  function refreshDay() {
    const next = todayISO();
    if (next === today) return;
    today = next; start = parse(today); draw(); notify();
  }
  function navigate(days) { start = plus(start, days); draw(); notify(); }
  document.getElementById('anterior').addEventListener('click', () => navigate(-7));
  document.getElementById('proxima').addEventListener('click', () => navigate(7));
  document.getElementById('hoje').addEventListener('click', () => { today = todayISO(); start = parse(today); draw(); notify(); });
  setInterval(refreshDay, 1000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshDay(); });
  window.addEventListener('focus', refreshDay);
  window.EscalaUI = Object.freeze({ renderizar, obterInicioPeriodo: () => iso(start), obterInicioSemana: () => iso(start) });
  draw(); notify();
  fetch('cultos.json')
    .then(response => {
      if (!response.ok) throw new Error('Falha ao carregar programação.');
      return response.json();
    })
    .then(data => {
      if (!Array.isArray(data) || !data.every(item => item && typeof item.id === 'string' && Number.isInteger(item.diaSemana) && item.diaSemana >= 1 && item.diaSemana <= 7 && typeof item.titulo === 'string' && Array.isArray(item.funcoes) && item.funcoes.every(role => typeof role === 'string'))) throw new Error('Programação inválida.');
      services = data;
      draw();
    })
    .catch(() => {
      configurationFailed = true;
      draw();
    });
})();
