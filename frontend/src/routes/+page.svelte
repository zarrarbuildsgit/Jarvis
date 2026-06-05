<!-- JARVIS Dashboard - SvelteKit -->
<script>
  import { onMount, onDestroy } from 'svelte';
  
  let ws = null;
  let agentStatus = 'offline';
  let messages = [];
  let inputText = '';
  let tasks = [];
  let screenPreview = '';
  let currentAction = '';
  let trustLevel = 1;

  onMount(() => {
    connectWebSocket();
    fetchInitialData();
  });

  function connectWebSocket() {
    ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/client`);
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'register_dashboard' }));
    };
    ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
    ws.onclose = () => {
      agentStatus = 'offline';
      setTimeout(connectWebSocket, 3000);
    };
  }

  function handleMessage(data) {
    switch (data.type) {
      case 'agent_connected':
        agentStatus = data.status;
        break;
      case 'agent_thought':
        messages.push({ type: 'thought', text: data.text, time: new Date().toLocaleTimeString() });
        currentAction = data.text;
        break;
      case 'agent_result':
        messages.push({ type: 'result', text: data.text, time: new Date().toLocaleTimeString() });
        currentAction = '';
        break;
      case 'task_update':
        const idx = tasks.findIndex(t => t.id === data.taskId);
        if (idx >= 0) tasks[idx] = { ...tasks[idx], ...data };
        else tasks.push(data);
        break;
    }
    setTimeout(() => {
      const c = document.getElementById('msg-container');
      if (c) c.scrollTop = c.scrollHeight;
    }, 50);
  }

  function sendCommand() {
    if (!inputText.trim() || !ws) return;
    messages.push({ type: 'user', text: inputText, time: new Date().toLocaleTimeString() });
    ws.send(JSON.stringify({ type: 'user_command', command: inputText }));
    inputText = '';
  }

  async function createTask() {
    if (!inputText.trim()) return;
    const r = await fetch('http://localhost:8000/api/agent/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: inputText })
    });
    if (r.ok) {
      const task = await r.json();
      tasks.push(task);
      inputText = '';
    }
  }

  async function fetchInitialData() {
    try {
      const r = await fetch('http://localhost:8000/api/health');
      const d = await r.json();
      agentStatus = d.agent;
    } catch (e) { console.error(e); }
  }

  onDestroy(() => ws?.close());

  function trustColor(l) {
    return {1:'text-red-400',2:'text-yellow-400',3:'text-blue-400',4:'text-green-400'}[l]||'text-gray-400';
  }
  function trustLabel(l) {
    return {1:'New (Read-only)',2:'Proven (Basic)',3:'Trusted (System)',4:'Full Access'}[l]||'Unknown';
  }
</script>

<div class="min-h-screen bg-gray-900 text-gray-100 flex flex-col">
  <header class="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="text-2xl">🤖</div>
      <div>
        <h1 class="text-xl font-bold text-white">J.A.R.V.I.S.</h1>
        <p class="text-xs text-gray-400">Just A Rather Very Intelligent System</p>
      </div>
    </div>
    <div class="flex items-center gap-4">
      <div class="flex items-center gap-2">
        <span class="text-sm text-gray-400">Trust:</span>
        <span class="text-sm font-semibold {trustColor(trustLevel)}">{trustLevel} - {trustLabel(trustLevel)}</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 rounded-full {agentStatus==='online'?'bg-green-500':'bg-red-500'}"></div>
        <span class="text-sm">{agentStatus==='online'?'Online':'Offline'}</span>
      </div>
    </div>
  </header>

  <main class="flex-1 flex overflow-hidden">
    <div class="w-1/2 flex flex-col border-r border-gray-700">
      <div class="flex border-b border-gray-700">
        <button class="px-4 py-2 text-sm font-medium text-white bg-gray-700">Chat</button>
        <button class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Tasks ({tasks.length})</button>
        <button class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Memory</button>
      </div>

      <div id="msg-container" class="flex-1 overflow-y-auto p-4 space-y-3">
        {#each messages as msg}
          <div class="flex {msg.type==='user'?'justify-end':'justify-start'}">
            <div class="max-w-[80%] rounded-lg px-4 py-2 {
              msg.type==='user'?'bg-blue-600 text-white':
              msg.type==='thought'?'bg-gray-700 text-yellow-300':
              msg.type==='action'?'bg-gray-700 text-blue-300':
              'bg-gray-700 text-green-300'
            }">
              <div class="text-xs opacity-70 mb-1">{msg.time}</div>
              <div class="text-sm">{msg.text}</div>
            </div>
          </div>
        {/each}
        {#if currentAction}
          <div class="flex justify-start">
            <div class="max-w-[80%] rounded-lg px-4 py-2 bg-gray-700 text-blue-300 animate-pulse">
              <div class="text-xs opacity-70 mb-1">Working...</div>
              <div class="text-sm">{currentAction}</div>
            </div>
          </div>
        {/if}
      </div>

      <div class="border-t border-gray-700 p-4">
        <form on:submit|preventDefault={sendCommand} class="flex gap-2">
          <input type="text" bind:value={inputText} placeholder="Type a command..."
            class="flex-1 bg-gray-800 text-white px-4 py-2 rounded-lg border border-gray-600 focus:border-blue-500"/>
          <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium">Send</button>
          <button type="button" on:click={createTask} class="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg">Task</button>
        </form>
      </div>
    </div>

    <div class="w-1/2 flex flex-col">
      <div class="flex-1 bg-gray-800 m-4 rounded-lg overflow-hidden border border-gray-700">
        <div class="bg-gray-700 px-4 py-2 text-sm font-medium">🖥️ Screen Preview</div>
        <div class="h-full flex items-center justify-center text-gray-500">
          {#if screenPreview}
            <img src={screenPreview} alt="Screen preview" class="w-full h-full object-contain"/>
          {:else}
            <div class="text-center">
              <div class="text-4xl mb-2">🖥️</div>
              <p>Screen preview will appear here</p>
              <p class="text-xs mt-1">when agent is analyzing your desktop</p>
            </div>
          {/if}
        </div>
      </div>

      {#if tasks.length > 0}
        <div class="bg-gray-800 mx-4 mb-4 rounded-lg border border-gray-700 overflow-hidden">
          <div class="bg-gray-700 px-4 py-2 text-sm font-medium">📋 Active Tasks</div>
          <div class="p-4 space-y-2">
            {#each tasks as task}
              <div class="flex items-center gap-3">
                <div class="flex-1">
                  <div class="text-sm">{task.command}</div>
                  <div class="w-full bg-gray-700 rounded-full h-1.5 mt-1">
                    <div class="bg-blue-500 h-1.5 rounded-full" style="width: {task.progress || 0}%"></div>
                  </div>
                </div>
                <span class="text-xs px-2 py-1 rounded bg-gray-700 {
                  task.status==='completed'?'text-green-400':
                  task.status==='failed'?'text-red-400':
                  'text-yellow-400'
                }">{task.status}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </main>
</div>

<style>
  :global(body) { margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
</style>
