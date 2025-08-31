(() => {
  const $ = (id) => document.getElementById(id);

  const canvas = $("playCanvas");
  const ctx = canvas.getContext("2d");
  const modelInput = $("modelInput");
  const tempInput = $("tempInput");
  const boardSelect = $("boardSelect");
  const startBtn = $("startBtn");
  const stepLLMBtn = $("stepLLMBtn");
  const stepHumanBtn = $("stepHumanBtn");
  const actionInput = $("actionInput");
  const autoBtn = $("autoBtn");
  const stopBtn = $("stopBtn");

  const runIdEl = $("runId");
  const movesEl = $("moves");
  const streakEl = $("streak");
  const stateEl = $("state");
  const reasonEl = $("reason");
  const asciiOut = $("asciiOut");
  const chatlog = $("chatlog");

  const replayRunId = $("replayRunId");
  const loadReplayBtn = $("loadReplayBtn");
  const prevStep = $("prevStep");
  const nextStep = $("nextStep");
  const replayIdxEl = $("replayIdx");
  const replayView = $("replayView");

  const CELL = 48;
  const EDGE = 4;

  let currentRunId = null;
  let autoTimer = null;

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function getCss(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  async function loadBoards() {
    try {
      const r = await fetch('/api/boards');
      const j = await r.json();
      const boards = j.boards || [];
      const def = j.default || (boards[0] || 'board.json');
      boardSelect.innerHTML = '';
      for (const name of boards) {
        const opt = document.createElement('option');
        opt.value = name; opt.textContent = name;
        if (name === def) opt.selected = true;
        boardSelect.appendChild(opt);
      }
    } catch (e) {
      // ignore
    }
  }

  function drawBoard(board) {
    if (!board) return;
    canvas.width = Math.max(1, board.cols * CELL);
    canvas.height = Math.max(1, board.rows * CELL);
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0,0,w,h);

    // grid (match editor look)
    ctx.strokeStyle = getCss('--grid') || '#ddd';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let c = 0; c <= board.cols; c++) {
      const x = c * CELL + 0.5; ctx.moveTo(x, 0); ctx.lineTo(x, h);
    }
    for (let r = 0; r <= board.rows; r++) {
      const y = r * CELL + 0.5; ctx.moveTo(0, y); ctx.lineTo(w, y);
    }
    ctx.stroke();

    // walls
    ctx.fillStyle = getCss('--wall') || '#000';
    for (let r = 0; r < board.rows; r++) {
      for (let c = 0; c <= board.cols; c++) if (board.v_walls[r][c]) ctx.fillRect(c*CELL - EDGE/2, r*CELL, EDGE, CELL);
    }
    for (let r = 0; r <= board.rows; r++) {
      for (let c = 0; c < board.cols; c++) if (board.h_walls[r][c]) ctx.fillRect(c*CELL, r*CELL - EDGE/2, CELL, EDGE);
    }

    // gates (draw CLOSED gates only: present && not open)
    ctx.fillStyle = getCss('--gate') || '#0a84ff';
    for (let r = 0; r < board.rows; r++) {
      for (let c = 0; c <= board.cols; c++) {
        const present = board.v_gates && board.v_gates[r][c];
        const open = board.v_gate_open && board.v_gate_open[r] && board.v_gate_open[r][c];
        if (present && !open) ctx.fillRect(c*CELL - EDGE/2, r*CELL, EDGE, CELL);
      }
    }
    for (let r = 0; r <= board.rows; r++) {
      for (let c = 0; c < board.cols; c++) {
        const present = board.h_gates && board.h_gates[r][c];
        const open = board.h_gate_open && board.h_gate_open[r] && board.h_gate_open[r][c];
        if (present && !open) ctx.fillRect(c*CELL, r*CELL - EDGE/2, CELL, EDGE);
      }
    }

    // glyphs
    function square(r, c, bg, fg, text) {
      const pad = Math.max(6, Math.floor(CELL * 0.1));
      ctx.fillStyle = bg; ctx.fillRect(c*CELL + pad, r*CELL + pad, CELL - 2*pad, CELL - 2*pad);
      ctx.fillStyle = fg; ctx.font = `bold ${Math.floor(CELL*0.45)}px sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, c*CELL + CELL/2, r*CELL + CELL/2 + 1);
    }

    // Draw in precedence order: trap < key < scorpion < white < red < exit < player
    for (const rc of (board.traps || [])) square(rc[0], rc[1], getCss('--trap')||'#f5a524', '#000', 'T');
    for (const rc of (board.keys || [])) square(rc[0], rc[1], getCss('--key')||'#ffcc00', '#000', 'K');
    for (const rc of (board.scorpions || [])) square(rc[0], rc[1], getCss('--scorpion')||'#00bcd4', '#000', 'S');
    for (const rc of (board.white_mummies || [])) square(rc[0], rc[1], '#222', getCss('--white')||'#fff', 'W');
    for (const rc of (board.red_mummies || [])) square(rc[0], rc[1], getCss('--red')||'#d12e2e', '#fff', 'R');
    if (Array.isArray(board.exit)) square(board.exit[0], board.exit[1], getCss('--exit')||'#7d5bed', '#fff', 'E');
    if (Array.isArray(board.player)) square(board.player[0], board.player[1], getCss('--player')||'#25a36f', '#fff', 'P');
  }

  function setStatus({run_id, move_count, repeat_count, ended, result, reason}) {
    runIdEl.textContent = run_id || '-';
    movesEl.textContent = (move_count ?? 0).toString();
    streakEl.textContent = (repeat_count ?? 0).toString();
    stateEl.textContent = ended ? (result || 'ended') : 'running';
    reasonEl.textContent = reason ? `(${reason})` : '';
  }

  function addMsg(role, content) {
    const div = document.createElement('div');
    div.className = 'msg';
    const meta = document.createElement('div'); meta.className = 'meta'; meta.textContent = role;
    const body = document.createElement('div'); body.className = 'content'; body.textContent = content;
    div.appendChild(meta); div.appendChild(body); chatlog.appendChild(div); chatlog.scrollTop = chatlog.scrollHeight;
  }

  async function startRun() {
    const model = modelInput.value.trim();
    const temperature = parseFloat(tempInput.value || '0.2') || 0.2;
    const board = (boardSelect.value || '').trim();
    const res = await fetch('/api/run/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model, temperature, board})});
    const j = await res.json();
    if (!res.ok) { alert(j.message || 'start failed'); return; }
    currentRunId = j.run_id;
    runIdEl.textContent = currentRunId;
    asciiOut.textContent = j.ascii || '';
    setStatus({run_id:currentRunId, move_count: j.move_count, repeat_count: j.repeat_count, ended:false});
    chatlog.innerHTML = '';
    addMsg('system', 'Run started');
    if (j.board) drawBoard(j.board);
  }

  async function step(mode, action) {
    if (!currentRunId) { alert('No run'); return; }
    const payload = { run_id: currentRunId, mode };
    if (mode === 'human') payload.action = action;
    const res = await fetch('/api/run/step', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const j = await res.json();
    if (!res.ok) { addMsg('error', j.message || 'step failed'); stopAuto(); return; }
    asciiOut.textContent = j.ascii || '';
    setStatus({run_id:j.run_id, move_count: j.move_count, repeat_count: j.repeat_count, ended:j.done, result: j.won ? 'win':'lose', reason: j.reason});
    if (j.last_reply) addMsg('assistant', String(j.last_reply));
    const evs = (j.events||[]).map(e => JSON.stringify(e)).join(' | ');
    const head = (j.phase && j.phase !== 'turn' && j.phase !== 'player') ? `Phase=${j.phase}` : `Action=${j.action}`;
    addMsg('env', `${head} moves=${j.move_count} 3fold=${j.repeat_count} done=${j.done}${evs? ' events='+evs:''}`);
    if (j.board) drawBoard(j.board);
    if (j.done) stopAuto();
  }

  function stopAuto() { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } }
  function startAuto() { stopAuto(); autoTimer = setInterval(() => step('llm'), 1200); }

  async function stopRun() {
    if (!currentRunId) return;
    await fetch('/api/run/stop', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({run_id: currentRunId})});
    stopAuto();
    addMsg('system', 'Run stopped');
  }

  // Replay
  let replay = { log: [], idx: -1 };
  function showReplayIndex() {
    replayIdxEl.textContent = String(replay.idx);
    if (replay.idx < 0 || replay.idx >= replay.log.length) { replayView.textContent = ''; return; }
    const item = replay.log[replay.idx];
    replayView.textContent = JSON.stringify(item, null, 2);
  }

  async function loadReplay() {
    const id = replayRunId.value.trim() || currentRunId;
    if (!id) { alert('No run id'); return; }
    const r = await fetch(`/api/run/replay?run_id=${id}`);
    const j = await r.json();
    replay.log = j.log || [];
    replay.idx = 0;
    showReplayIndex();
  }

  loadBoards();
  startBtn.addEventListener('click', startRun);
  stepLLMBtn.addEventListener('click', () => step('llm'));
  stepHumanBtn.addEventListener('click', () => step('human', (actionInput.value||'').trim().toUpperCase()));
  autoBtn.addEventListener('click', () => { if (autoTimer) stopAuto(); else startAuto(); });
  stopBtn.addEventListener('click', stopRun);

  loadReplayBtn.addEventListener('click', loadReplay);
  prevStep.addEventListener('click', () => { if (replay.idx>0){replay.idx--; showReplayIndex();} });
  nextStep.addEventListener('click', () => { if (replay.idx<replay.log.length-1){replay.idx++; showReplayIndex();} });
})();

