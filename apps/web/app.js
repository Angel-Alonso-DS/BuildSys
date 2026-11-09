const $ = (selector) => document.querySelector(selector);
const RULE = 'idempotency-by-request-id-v1';
const EVENT = Object.freeze({ request_id: 'return-100', payload: { item: 'book' } });
const buttons = ['learn', 'build', 'first', 'duplicate', 'refresh'].map((id) => document.getElementById(id));
const state = { url: '', connected: false, learned: false, built: false, first: false, busy: false };

function updateButtons() {
  $('#learn').disabled = state.busy || !state.connected;
  $('#build').disabled = state.busy || !state.connected || !state.learned;
  $('#first').disabled = state.busy || !state.connected || !state.built;
  $('#duplicate').disabled = state.busy || !state.connected || !state.first;
  $('#refresh').disabled = state.busy || !state.connected;
}
function markStep(name, done) {
  const step = document.querySelector(`[data-step="${name}"]`);
  step.classList.toggle('done', done);
  step.querySelector('.step-state').textContent = done ? 'COMPLETADO' : 'PENDIENTE';
}
function resetFlow() {
  state.learned = state.built = state.first = false;
  for (const name of ['observation', 'rule', 'build', 'first', 'duplicate']) markStep(name, false);
  $('#rule-badge').textContent = 'ESPERANDO';
  $('#rule-badge').classList.remove('active');
  for (const id of ['inherited', 'first-result', 'duplicate-result']) document.getElementById(id).hidden = true;
  updateButtons();
}
function status(message, kind = '') {
  const element = $('#connection-status');
  element.className = `connection-status ${kind}`;
  element.replaceChildren(Object.assign(document.createElement('span'), { className: 'status-dot' }), ` ${message}`);
}
function showResponse(label, data) {
  $('#response-meta').textContent = label;
  $('#response-body').textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${state.url}${path}`, options);
  } catch (error) {
    throw new Error(`No se pudo conectar con la API. Revisa la URL, la red y la configuración CORS. (${error.message})`);
  }
  const raw = await response.text();
  let data;
  try { data = JSON.parse(raw); } catch { data = raw; }
  showResponse(`${options.method || 'GET'} ${path} · HTTP ${response.status}`, data);
  if (!response.ok) throw new Error(`La API respondió HTTP ${response.status}: ${typeof data === 'object' ? JSON.stringify(data) : data}`);
  return data;
}
function post(path, body) {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}
async function run(action) {
  if (state.busy) return;
  state.busy = true;
  updateButtons();
  const previous = $('#response-meta').textContent;
  $('#response-meta').textContent = 'Cargando…';
  try { await action(); } catch (error) {
    if ($('#response-meta').textContent === 'Cargando…') showResponse('Error de conexión', error.message);
    else $('#response-meta').textContent += ' · Error';
    status(error.message, 'error');
  } finally {
    if ($('#response-meta').textContent === 'Cargando…') $('#response-meta').textContent = previous;
    state.busy = false;
    updateButtons();
  }
}
function renderKnowledge(data) {
  const list = $('#knowledge-list');
  list.replaceChildren();
  if (!Array.isArray(data.items)) throw new Error('La respuesta de /knowledge no contiene una lista items.');
  if (!data.items.length) {
    const empty = document.createElement('div'); empty.className = 'empty';
    const icon = document.createElement('span'); icon.textContent = '◇';
    const title = document.createElement('strong'); title.textContent = 'Aún no hay reglas';
    const copy = document.createElement('small'); copy.textContent = 'Ejecuta el primer paso para aprender una regla.';
    empty.append(icon, title, copy); list.append(empty); return;
  }
  for (const item of data.items) {
    const card = document.createElement('div'); card.className = 'knowledge-item';
    const title = document.createElement('strong'); title.textContent = item.rule_id || 'Regla sin identificador';
    const pattern = document.createElement('p'); pattern.textContent = item.pattern || '';
    const action = document.createElement('p'); action.textContent = item.action || '';
    const meta = document.createElement('small'); meta.textContent = `${item.validated ? '● Validada' : '○ Sin validar'} · Origen: ${item.source_system || 'desconocido'}`;
    card.append(title, pattern, action, meta); list.append(card);
  }
}
async function refreshKnowledge() { renderKnowledge(await request('/knowledge')); }
function result(id, text, success) {
  const element = document.getElementById(id); element.hidden = false;
  element.classList.toggle('error', !success); element.textContent = text;
}
$('#connection-form').addEventListener('submit', (event) => {
  event.preventDefault();
  run(async () => {
    let url;
    try { url = new URL($('#api-url').value.trim()); } catch { throw new Error('Introduce una URL válida para la API.'); }
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Usa una URL HTTP(S) sin credenciales, parámetros ni fragmento.');
    state.url = url.href.replace(/\/$/, ''); state.connected = false; resetFlow();
    try { localStorage.setItem('API_URL', state.url); } catch { /* The demo can still run without storage. */ }
    status('Conectando…');
    const health = await request('/health');
    if (health.status !== 'ok') throw new Error('La API no informó un estado saludable.');
    state.connected = true; status('Conectado', 'connected');
    await refreshKnowledge();
  });
});
$('#refresh').addEventListener('click', () => run(refreshKnowledge));
$('#learn').addEventListener('click', () => run(async () => {
  resetFlow();
  const data = await post('/learning/duplicate-event', { source_system: 'orders' });
  markStep('observation', true);
  state.learned = data.rule_id === RULE && data.validated === true;
  markStep('rule', state.learned);
  $('#rule-badge').textContent = state.learned ? 'VALIDADA' : 'NO CONFIRMADA';
  $('#rule-badge').classList.toggle('active', state.learned);
  if (!state.learned) throw new Error('La respuesta no confirmó la regla esperada.');
  await refreshKnowledge();
}));
$('#build').addEventListener('click', () => run(async () => {
  const data = await post('/systems/returns/build', {});
  state.built = data.system_name === 'returns' && data.inherited_rule_id === RULE;
  state.first = false; markStep('build', state.built); markStep('first', false); markStep('duplicate', false);
  $('#first-result').hidden = $('#duplicate-result').hidden = true;
  result('inherited', state.built ? `✓ returns heredó ${data.inherited_rule_id}` : `No se confirmó la regla heredada: ${data.inherited_rule_id ?? 'ninguna'}`, state.built);
}));
async function sendEvent(isDuplicate) {
  const data = await post('/systems/returns/events', EVENT);
  const expected = isDuplicate ? 'duplicate_ignored' : 'accepted';
  const matches = data.status === expected && data.request_id === EVENT.request_id && data.system_name === 'returns';
  markStep(isDuplicate ? 'duplicate' : 'first', matches);
  result(isDuplicate ? 'duplicate-result' : 'first-result', `${matches ? '✓' : '⚠'} Respuesta: ${data.status ?? 'sin estado'}${matches ? '' : ` · Se esperaba ${expected}`}`, matches);
  if (!isDuplicate) state.first = matches;
}
$('#first').addEventListener('click', () => run(() => sendEvent(false)));
$('#duplicate').addEventListener('click', () => run(() => sendEvent(true)));
try { $('#api-url').value = localStorage.getItem('API_URL') || window.API_URL || 'http://localhost:8000'; } catch { $('#api-url').value = window.API_URL || 'http://localhost:8000'; }
updateButtons();
