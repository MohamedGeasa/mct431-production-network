const $ = id => document.getElementById(id);
let first = true, lastStatus = null, pending = false, online = false;
function refreshButtons() {
  const s = lastStatus;
  document.querySelectorAll('[data-action]').forEach(b => {
    const action = b.dataset.action;
    b.disabled = !online || !s || pending || s.stopping ||
      (action === 'start' && (s.state !== 'Idle' || !s.station_a || !s.station_b)) ||
      (action === 'pause' && s.state !== 'Running') ||
      (action === 'resume' && s.state !== 'Paused');
  });
}
function render(s, events) {
  lastStatus = s;
  $('state').textContent = s.state;
  $('mode').textContent = s.simulation ? 'SIMULATION · software stations' : 'HARDWARE · physical stations';
  $('a').textContent = `Production ${s.station_a ? 'online' : 'offline'}`;
  $('b').textContent = `Inspection ${s.station_b ? 'online' : 'offline'}`;
  if (first) { Object.entries(s.config).forEach(([key,value]) => document.forms.settings.elements[key].value = value); first = false; }
  document.querySelectorAll('input').forEach(input => input.disabled = s.state !== 'Idle' || pending);
  ['produced','accepted','rejected'].forEach(key => $(key).textContent = s[key]);
  $('batch').textContent = s.batch_id ? `#${s.batch_id}` : '';
  $('progress').max = s.config.target_parts; $('progress').value = s.accepted + s.rejected;
  $('summary').textContent = s.fault || (s.stopping ? 'Stopping: waiting for current work…' :
    s.outcome === 'completed' ? 'Batch completed: every target part has a verdict.' :
    s.outcome === 'stopped' ? `Batch stopped. ${s.discarded} produced parts have no verdict.` :
    `${s.accepted + s.rejected} of ${s.config.target_parts} parts inspected.`);
  $('capacity').textContent = `${s.queued.length} / ${s.config.queue_capacity}`;
  $('queue').replaceChildren(...(s.queued.length ? s.queued : ['No waiting parts']).map(part => {
    const span = document.createElement('span'); span.textContent = typeof part === 'number' ? `Part ${part}` : part; return span;
  }));
  $('active').textContent = `Producing: ${s.producing ?? '—'} · Inspecting: ${s.inspecting ?? '—'}${s.blocked ? ' · Production blocked: queue full' : ''}`;
  $('events').textContent = events.map(e => `${e.utc.slice(11,23)}  ${e.event}  ${JSON.stringify(Object.fromEntries(Object.entries(e).filter(([k]) => !['utc','monotonic_s','simulation','event','hex'].includes(k))))}`).join('\n');
  refreshButtons();
}
function connect() {
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws.onopen = () => { online = true; $('connection').textContent = 'Live status connected'; refreshButtons(); };
  ws.onmessage = event => { const data = JSON.parse(event.data); render(data.status, data.events); };
  ws.onclose = () => { online = false; $('connection').textContent = 'Status disconnected · reconnecting'; refreshButtons(); setTimeout(connect, 1000); };
  ws.onerror = () => ws.close();
}
function commandId() {
  // crypto.randomUUID is unavailable on plain HTTP LAN addresses. getRandomValues works there.
  const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(x => x.toString(16).padStart(2,'0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', async () => {
  const action = button.dataset.action;
  if (action === 'start' && !document.forms.settings.reportValidity()) return;
  const body = {cmd_id: commandId(), action};
  if (action === 'start') body.config = Object.fromEntries([...new FormData(document.forms.settings).entries()].map(([k,v]) => [k,Number(v)]));
  pending = true; refreshButtons(); $('alert').textContent = `${action}: sending…`;
  try {
    // Retry the same identifier if the HTTP response is lost.
    let response;
    for (let attempt=0; attempt<3; attempt++) {
      try { response = await fetch('/api/commands', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(5000)}); break; }
      catch(error) { if (attempt === 2) throw error; }
    }
    let record = await response.json();
    if (!response.ok) throw new Error(record.error || 'Command rejected');
    const deadline = Date.now() + 240000;
    while (record.phase === 'accepted' && Date.now() < deadline) {
      $('alert').textContent = `${action}: accepted; waiting for completion…`;
      await new Promise(resolve => setTimeout(resolve, 350));
      const poll = await fetch(`/api/commands/${body.cmd_id}`, {signal:AbortSignal.timeout(5000)});
      if (!poll.ok) throw new Error('Command status unavailable'); record = await poll.json();
    }
    if (record.phase !== 'completed') throw new Error(record.error || 'Completion deadline expired');
    $('alert').textContent = `${action}: completed.`;
  } catch(error) { $('alert').textContent = error.message; }
  finally { pending = false; refreshButtons(); }
}));
refreshButtons(); connect();
