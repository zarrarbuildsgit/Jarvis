<!-- JARVIS Dashboard - SvelteKit source version of the Control Center -->
<script>
  import { onMount, onDestroy } from 'svelte';

  const API = 'http://127.0.0.1:8000';
  let active = 'overview';
  let ws;
  let health = {};
  let status = {};
  let resources = null;
  let tasks = [];
  let schedules = [];
  let approvals = [];
  let plugins = [];
  let profiles = [];
  let config = null;
  let audit = [];
  let history = [];
  let trust = {};
  let messages = [];
  let command = '';
  let scheduleCommand = '';
  let scheduleType = 'delay';
  let scheduleValue = '60';
  let error = '';

  async function api(path, options = {}) {
    const r = await fetch(API + path, { headers: { 'Content-Type': 'application/json' }, ...options });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  async function refreshAll() {
    error = '';
    await Promise.allSettled([
      api('/api/health').then(d => health = d),
      api('/api/status').then(d => status = d.status || {}),
      api('/api/resources').then(d => resources = d),
      api('/api/tasks').then(d => tasks = d.tasks || []),
      api('/api/schedules').then(d => schedules = d.schedules || []),
      api('/api/approvals?status=pending').then(d => approvals = d.approvals || []),
      api('/api/plugins').then(d => plugins = d.plugins || []),
      api('/api/config/profiles').then(d => profiles = d.profiles || []),
      api('/api/config').then(d => config = d.config),
      api('/api/audit?limit=50').then(d => audit = d.events || []),
      api('/api/tasks/history?limit=50').then(d => history = d.events || []),
      api('/api/trust').then(d => trust = d.trust || {}).catch(() => trust = {})
    ]);
  }

  function connectWs() {
    ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/client`);
    ws.onopen = () => ws.send(JSON.stringify({ type: 'register_dashboard' }));
    ws.onmessage = e => {
      const data = JSON.parse(e.data);
      if (data.type === 'agent_thought') messages = [...messages, { type: 'thought', text: data.text }];
      if (data.type === 'agent_result') messages = [...messages, { type: 'result', text: data.text }];
      if (['task_update','task_created','task_cancelled','approval_resolved','schedule_created','schedule_cancelled','status_update'].includes(data.type)) refreshAll();
    };
    ws.onclose = () => setTimeout(connectWs, 3000);
  }

  async function sendCommand() {
    if (!command.trim()) return;
    messages = [...messages, { type: 'user', text: command }];
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'user_command', command }));
    else await queueTask(command);
    command = '';
  }
  async function queueTask(cmd = command) { await api('/api/agent/command', { method: 'POST', body: JSON.stringify({ command: cmd }) }); command = ''; refreshAll(); }
  async function taskAction(id, action) { await api(`/api/tasks/${id}${action === 'cancel' ? '' : '/' + action}`, { method: action === 'cancel' ? 'DELETE' : 'POST' }); refreshAll(); }
  async function approval(id, action) { await api(`/api/approvals/${id}/${action}`, { method: 'POST', body: JSON.stringify({ resolved_by: 'dashboard' }) }); refreshAll(); }
  async function enqueueDue() { await api('/api/schedules/enqueue-due', { method: 'POST' }); refreshAll(); }
  async function cancelSchedule(id) { await api(`/api/schedules/${id}`, { method: 'DELETE' }); refreshAll(); }
  async function createSchedule() {
    const body = { command: scheduleCommand, schedule_type: scheduleType, priority: 'normal' };
    if (scheduleType === 'delay') body.delay_seconds = Number(scheduleValue || 0);
    if (scheduleType === 'interval') body.interval_seconds = Number(scheduleValue || 60);
    if (scheduleType === 'daily') body.daily_time = scheduleValue;
    if (scheduleType === 'once') body.run_at = scheduleValue;
    await api('/api/schedules', { method: 'POST', body: JSON.stringify(body) });
    scheduleCommand = ''; refreshAll();
  }

  onMount(() => { connectWs(); refreshAll(); const t = setInterval(refreshAll, 10000); return () => clearInterval(t); });
  onDestroy(() => ws?.close());
</script>

<div class="shell">
  <aside>
    <h1>🤖 JARVIS</h1><p>Control Center</p>
    {#each ['overview','tasks','schedules','approvals','plugins','config','logs'] as tab}
      <button class:active={active === tab} on:click={() => active = tab}>{tab}</button>
    {/each}
  </aside>
  <main>
    <header><b>Agent:</b> {health.agent || 'offline'} <b>Profile:</b> {resources?.profile || config?.system?.profile || '?'} <button on:click={refreshAll}>Refresh</button></header>
    {#if error}<div class="error">{error}</div>{/if}
    {#if active === 'overview'}
      <div class="grid"><section><h2>Health</h2><pre>{JSON.stringify(health,null,2)}</pre></section><section><h2>Resources</h2><pre>{JSON.stringify(resources,null,2)}</pre></section><section><h2>Trust</h2><pre>{JSON.stringify(trust,null,2)}</pre></section></div>
      <section><h2>Chat</h2><div class="row"><input bind:value={command} placeholder="Command"><button on:click={sendCommand}>Send</button><button on:click={() => queueTask()}>Queue</button></div>{#each messages as m}<div class="msg {m.type}"><b>{m.type}</b> {m.text}</div>{/each}</section>
    {/if}
    {#if active === 'tasks'}<section><h2>Tasks</h2>{#each tasks as t}<div class="card"><b>{t.id}</b> {t.status}<p>{t.command}</p><button on:click={() => taskAction(t.id,'pause')}>Pause</button><button on:click={() => taskAction(t.id,'resume')}>Resume</button><button on:click={() => taskAction(t.id,'cancel')}>Cancel</button></div>{/each}</section>{/if}
    {#if active === 'schedules'}<section><h2>Schedules</h2><div class="row"><input bind:value={scheduleCommand} placeholder="Command"><select bind:value={scheduleType}><option>delay</option><option>interval</option><option>daily</option><option>once</option></select><input bind:value={scheduleValue}><button on:click={createSchedule}>Create</button><button on:click={enqueueDue}>Enqueue Due</button></div>{#each schedules as s}<div class="card"><b>{s.id}</b> {s.schedule_type} {s.enabled ? 'enabled':'disabled'}<p>{s.command}</p><button on:click={() => cancelSchedule(s.id)}>Cancel</button></div>{/each}</section>{/if}
    {#if active === 'approvals'}<section><h2>Approvals</h2>{#each approvals as a}<div class="card"><b>{a.id}</b><p>{a.command}</p><p>{a.decision.reason}</p><button on:click={() => approval(a.id,'approve')}>Approve</button><button on:click={() => approval(a.id,'deny')}>Deny</button></div>{/each}</section>{/if}
    {#if active === 'plugins'}<section><h2>Plugins</h2><div class="grid">{#each plugins as p}<div class="card"><h3>{p.name}</h3><p>{p.description}</p><small>{(p.examples||[]).join(' • ')}</small></div>{/each}</div></section>{/if}
    {#if active === 'config'}<section><h2>Profiles</h2>{profiles.join(', ')}<pre>{JSON.stringify(config,null,2)}</pre></section>{/if}
    {#if active === 'logs'}<section><h2>Audit</h2>{#each audit as e}<div class="card"><b>{e.event_type}</b> {e.message}</div>{/each}<h2>Task History</h2>{#each history as h}<div class="card"><b>{h.event_type}</b> {h.message}</div>{/each}</section>{/if}
  </main>
</div>
<style>
  :global(body){margin:0;background:#0b1020;color:#e5e7eb;font-family:Segoe UI,system-ui,sans-serif}.shell{display:grid;grid-template-columns:240px 1fr;min-height:100vh}aside{background:#111827;padding:18px;border-right:1px solid #253047}aside button{display:block;width:100%;margin:7px 0;padding:10px;border-radius:10px;border:1px solid transparent;background:transparent;color:#9ca3af;text-align:left}aside button.active,aside button:hover{background:#172033;color:white;border-color:#253047}main{padding:18px}header,section,.card{background:#111827;border:1px solid #253047;border-radius:14px;padding:14px;margin-bottom:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.row{display:flex;gap:8px}input,select{background:#0f172a;color:white;border:1px solid #253047;border-radius:9px;padding:9px;flex:1}button{background:#2563eb;color:white;border:0;border-radius:9px;padding:9px 11px}pre{white-space:pre-wrap;overflow:auto}.msg{padding:8px;margin:6px 0;border-radius:9px;background:#0f172a}.user{background:#1d4ed8}.thought{background:#422006}.result{background:#14532d}.error{background:#7f1d1d;padding:10px;border-radius:10px}
</style>
