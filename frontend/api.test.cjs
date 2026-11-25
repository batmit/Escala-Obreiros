const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  let inicio = '2026-11-24';
  const listeners = {}, pending = [], rendered = [], status = {};
  const context = {
    URLSearchParams, Date, Intl,
    window: { EscalaUI: { obterInicioPeriodo: () => inicio, renderizar: data => rendered.push(data) }, addEventListener: (name, fn) => { listeners[name] = fn; } },
    document: { getElementById: () => status, addEventListener() {}, hidden: false },
    setInterval() {},
    fetch: url => new Promise(resolve => pending.push({ url, resolve }))
  };
  vm.runInNewContext(fs.readFileSync(`${__dirname}/api.js`, 'utf8'), context);
  return { listeners, pending, rendered, status, navigate() { inicio = '2026-12-01'; listeners['escala:navegar'](); } };
}

const flush = () => new Promise(resolve => setImmediate(resolve));
const ok = cultos => ({ ok: true, json: async () => ({ cultos, atualizada_em: null }) });

test('carrega período inicial e ignora resposta antiga após navegação', async () => {
  const app = setup();
  assert.match(app.pending[0].url, /inicio=2026-11-24.*fim=2026-11-30/);
  app.navigate();
  app.pending[1].resolve(ok([{ id: 'nova' }]));
  await flush();
  app.pending[0].resolve(ok([{ id: 'antiga' }]));
  await flush();
  assert.equal(app.rendered.at(-1).cultos[0].id, 'nova');
});

test('erro da API é informado sem apagar dados já exibidos', async () => {
  const app = setup();
  app.pending[0].resolve(ok([{ id: 'salva' }]));
  await flush();
  app.listeners.focus();
  app.pending[1].resolve({ ok: false });
  await flush();
  assert.match(app.status.textContent, /Não foi possível/);
  assert.equal(app.rendered.at(-1).cultos[0].id, 'salva');
});
