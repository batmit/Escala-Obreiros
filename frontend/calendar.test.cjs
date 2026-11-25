// Testes de comportamento com DOM mínimo; não substituem verificação visual no navegador.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(fragment) { this.children = fragment.children; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
}

async function setup(fail = false) {
  let now = '2026-11-25T02:59:59Z', tick;
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])); } }
  const nodes = new Map();
  const document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Element(id)); return nodes.get(id); },
    createElement: tag => new Element(tag), createDocumentFragment: () => new Element('fragment'), addEventListener() {}
  };
  const context = {
    Date: Clock, Intl, document,
    window: { dispatchEvent() {}, addEventListener() {} }, CustomEvent: class {},
    setInterval(callback) { tick = callback; },
    fetch: async () => {
      if (fail) throw new Error('Rede indisponível');
      return { ok: true, json: async () => JSON.parse(fs.readFileSync(`${__dirname}/cultos.json`, 'utf8')) };
    }
  };
  vm.runInNewContext(fs.readFileSync(`${__dirname}/calendar.js`, 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  return { ui: context.window.EscalaUI, nodes, midnight() { now = '2026-11-25T03:00:00Z'; tick(); } };
}

function text(node) { return [node.textContent || '', ...node.children.map(text)].join(' '); }

test('janela móvel, domingo único à noite e virada no horário de Brasília', async () => {
  const app = await setup();
  assert.equal(app.ui.obterInicioPeriodo(), '2026-11-24');
  const days = app.nodes.get('calendario').children;
  assert.equal(days.length, 7);
  const sunday = days.find(day => day.children[0].children[1].children[0].dateTime === '2026-11-29');
  assert.equal(sunday.children.length, 2);
  assert.match(text(sunday), /Culto · noite/);
  assert.match(text(sunday), /Louvor/);
  assert.match(text(sunday), /Palavra/);
  app.nodes.get('proxima').listeners.click();
  assert.equal(app.ui.obterInicioPeriodo(), '2026-12-01');
  app.nodes.get('anterior').listeners.click();
  app.midnight();
  assert.equal(app.ui.obterInicioPeriodo(), '2026-11-25');
  assert.match(text(app.nodes.get('calendario').children[0]), /Sem culto programado/);
});

test('dados externos não podem alterar atribuições já recebidas', async () => {
  const app = await setup();
  const data = { cultos: [{ id: 'culto-2', data: '2026-11-24', atribuicoes: [{ funcao: 'palavra', obreiro: 'Daniel' }] }] };
  app.ui.renderizar(data);
  data.cultos[0].atribuicoes[0].obreiro = 'Alterado';
  app.ui.renderizar();
  assert.match(text(app.nodes.get('calendario')), /Daniel/);
  assert.doesNotMatch(text(app.nodes.get('calendario')), /Alterado/);
  assert.throws(() => app.ui.renderizar({ cultos: [{ id: 'x', data: '2026-02-30', atribuicoes: [] }] }));
  assert.match(text(app.nodes.get('calendario')), /Daniel/);
});

test('falha na configuração permanece visível ao navegar', async () => {
  const app = await setup(true);
  assert.match(app.nodes.get('status').textContent, /Não foi possível/);
  app.nodes.get('proxima').listeners.click();
  assert.match(app.nodes.get('status').textContent, /Não foi possível/);
  assert.doesNotMatch(text(app.nodes.get('calendario')), /Sem culto programado/);
});
