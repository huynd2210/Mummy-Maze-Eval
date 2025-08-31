(() => {
  const $ = (id) => document.getElementById(id);
  const canvas = $("boardCanvas");
  const ctx = canvas.getContext("2d");
  const rowsInput = $("rowsInput");
  const colsInput = $("colsInput");
  const newBtn = $("newBtn");
  const loadBtn = $("loadBtn");
  const saveBtn = $("saveBtn");
  const clearBtn = $("clearBtn");
  const clearEntitiesBtn = $("clearEntitiesBtn");
  const exportJsonBtn = $("exportJsonBtn");
  const exportPairsBtn = $("exportPairsBtn");
  const copyExportBtn = $("copyExportBtn");
  const exportText = $("exportText");
  const exportPanel = $("exportPanel");
  const indexBaseSel = $("indexBase");
  const statusEl = $("status");
  const toolRadios = () => Array.from(document.querySelectorAll('input[name="tool"]'));

  const CELL = 48;            // pixels per cell
  const EDGE = 4;             // edge thickness
  const CLICK_TOL = 8;        // click tolerance to a grid line

  // board = { rows, cols, v_walls, h_walls, v_gates, h_gates, player, white_mummies, red_mummies, traps, keys }
  let board = null;

  function getTool() {
    const r = toolRadios().find(x => x.checked);
    return r ? r.value : 'wall';
  }

  function setStatus(msg, timeoutMs = 2000) {
    statusEl.textContent = msg || "";
    if (timeoutMs) {
      setTimeout(() => { if (statusEl.textContent === msg) statusEl.textContent = ""; }, timeoutMs);
    }
  }

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function ensureFields(b) {
    // Back-compat: if gates/entities are missing, add them.
    if (!b.v_gates) b.v_gates = Array.from({ length: b.rows }, () => Array(b.cols + 1).fill(false));
    if (!b.h_gates) b.h_gates = Array.from({ length: b.rows + 1 }, () => Array(b.cols).fill(false));
    b.player = Array.isArray(b.player) && b.player.length === 2 ? [b.player[0], b.player[1]] : null;
    b.exit = Array.isArray(b.exit) && b.exit.length === 2 ? [b.exit[0], b.exit[1]] : null;
    for (const k of ['white_mummies','red_mummies','traps','keys']) {
      if (!Array.isArray(b[k])) b[k] = [];
    }
  }

  function resizeCanvasToBoard() {
    if (!board) return;
    canvas.width = Math.max(1, board.cols * CELL);
    canvas.height = Math.max(1, board.rows * CELL);
  }

  function drawGrid() {
    const w = canvas.width, h = canvas.height;
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let c = 0; c <= board.cols; c++) {
      const x = c * CELL + 0.5;
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
    }
    for (let r = 0; r <= board.rows; r++) {
      const y = r * CELL + 0.5;
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();
  }

  function drawEdges() {
    // walls in black
    ctx.fillStyle = getCss('--wall');
    for (let r = 0; r < board.rows; r++) {
      for (let c = 0; c <= board.cols; c++) {
        if (board.v_walls[r][c]) {
          const x = c * CELL - EDGE / 2;
          const y = r * CELL;
          ctx.fillRect(x, y, EDGE, CELL);
        }
      }
    }
    for (let r = 0; r <= board.rows; r++) {
      for (let c = 0; c < board.cols; c++) {
        if (board.h_walls[r][c]) {
          const x = c * CELL;
          const y = r * CELL - EDGE / 2;
          ctx.fillRect(x, y, CELL, EDGE);
        }
      }
    }

    // gates in blue on top
    ctx.fillStyle = getCss('--gate');
    for (let r = 0; r < board.rows; r++) {
      for (let c = 0; c <= board.cols; c++) {
        if (board.v_gates[r][c]) {
          const x = c * CELL - EDGE / 2;
          const y = r * CELL;
          ctx.fillRect(x, y, EDGE, CELL);
        }
      }
    }
    for (let r = 0; r <= board.rows; r++) {
      for (let c = 0; c < board.cols; c++) {
        if (board.h_gates[r][c]) {
          const x = c * CELL;
          const y = r * CELL - EDGE / 2;
          ctx.fillRect(x, y, CELL, EDGE);
        }
      }
    }
  }

  function drawEntities() {
    const cx = (c) => c * CELL + CELL / 2;
    const cy = (r) => r * CELL + CELL / 2;

    function drawGlyph(r, c, bg, fg, text) {
      const pad = Math.max(6, Math.floor(CELL * 0.1));
      ctx.fillStyle = bg;
      ctx.fillRect(c * CELL + pad, r * CELL + pad, CELL - 2 * pad, CELL - 2 * pad);
      ctx.fillStyle = fg;
      ctx.font = `bold ${Math.floor(CELL * 0.45)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, cx(c), cy(r) + 1);
    }

    if (Array.isArray(board.player)) {
      const [r,c] = board.player; drawGlyph(r, c, getCss('--player'), '#ffffff', 'P');
    }
    if (Array.isArray(board.exit)) {
      const [r,c] = board.exit; drawGlyph(r, c, getCss('--exit'), '#ffffff', 'E');
    }
    for (const [r,c] of board.white_mummies) drawGlyph(r, c, '#222', getCss('--white'), 'W');
    for (const [r,c] of board.red_mummies) drawGlyph(r, c, getCss('--red'), '#ffffff', 'R');
    for (const [r,c] of board.traps) drawGlyph(r, c, getCss('--trap'), '#000000', 'T');
    for (const [r,c] of board.keys) drawGlyph(r, c, getCss('--key'), '#000000', 'K');
  }

  function draw() {
    if (!board) return;
    ctx.clearRect(0,0,canvas.width,canvas.height);
    drawGrid();
    drawEdges();
    drawEntities();
  }

  function getCss(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || '#000';
  }

  function hitTest(evt) {
    const rect = canvas.getBoundingClientRect();
    const x = evt.clientX - rect.left;
    const y = evt.clientY - rect.top;
    const col = clamp(Math.floor(x / CELL), 0, board.cols - 1);
    const row = clamp(Math.floor(y / CELL), 0, board.rows - 1);
    const nearCol = Math.round(x / CELL);
    const distV = Math.abs(x - nearCol * CELL);
    const nearRow = Math.round(y / CELL);
    const distH = Math.abs(y - nearRow * CELL);
    return { x, y, row, col, nearRow, nearCol, distH, distV };
  }

  function toggleEdge(evt) {
    const { row, col, nearRow, nearCol, distH, distV } = hitTest(evt);
    if (distV > CLICK_TOL && distH > CLICK_TOL) return false; // not near any grid line

    const tool = getTool();
    const isGate = tool === 'gate';

    if (distV <= distH) {
      // vertical edge: (r in [0..rows-1], c in [0..cols])
      const r = clamp(row, 0, board.rows - 1);
      const c = clamp(nearCol, 0, board.cols);
      if (isGate) {
        // internal only; clear wall if gate set
        if (c > 0 && c < board.cols) {
          board.v_gates[r][c] = !board.v_gates[r][c];
          if (board.v_gates[r][c]) board.v_walls[r][c] = false;
        }
      } else {
        board.v_walls[r][c] = !board.v_walls[r][c];
        if (c > 0 && c < board.cols && board.v_walls[r][c]) board.v_gates[r][c] = false;
      }
    } else {
      // horizontal edge: (r in [0..rows], c in [0..cols-1])
      const r = clamp(nearRow, 0, board.rows);
      const c = clamp(col, 0, board.cols - 1);
      if (isGate) {
        if (r > 0 && r < board.rows) {
          board.h_gates[r][c] = !board.h_gates[r][c];
          if (board.h_gates[r][c]) board.h_walls[r][c] = false;
        }
      } else {
        board.h_walls[r][c] = !board.h_walls[r][c];
        if (r > 0 && r < board.rows && board.h_walls[r][c]) board.h_gates[r][c] = false;
      }
    }
    return true;
  }

  function coordEquals(a, b) { return a && b && a[0] === b[0] && a[1] === b[1]; }
  function listToggle(list, r, c) {
    const idx = list.findIndex(([rr,cc]) => rr === r && cc === c);
    if (idx >= 0) list.splice(idx, 1); else list.push([r,c]);
  }

  function toggleCell(evt) {
    const { row, col } = hitTest(evt);
    const tool = getTool();
    if (tool === 'player') {
      if (Array.isArray(board.player) && coordEquals(board.player, [row,col])) board.player = null;
      else board.player = [row, col];
      return true;
    }
    if (tool === 'white') { listToggle(board.white_mummies, row, col); return true; }
    if (tool === 'red') { listToggle(board.red_mummies, row, col); return true; }
    if (tool === 'trap') { listToggle(board.traps, row, col); return true; }
    if (tool === 'key') { listToggle(board.keys, row, col); return true; }
    if (tool === 'exit') {
      if (Array.isArray(board.exit) && coordEquals(board.exit, [row,col])) board.exit = null;
      else board.exit = [row, col];
      return true;
    }
    return false;
  }

  function onCanvasClick(evt) {
    const tool = getTool();
    const isEdgeTool = tool === 'wall' || tool === 'gate';
    const changed = isEdgeTool ? toggleEdge(evt) : toggleCell(evt);
    if (changed) draw();
  }

  function clearInnerWallsAndGates() {
    if (!board) return;
    // clear internal vertical
    for (let r = 0; r < board.rows; r++) {
      for (let c = 1; c < board.cols; c++) {
        board.v_walls[r][c] = false;
        board.v_gates[r][c] = false;
      }
    }
    // clear internal horizontal
    for (let r = 1; r < board.rows; r++) {
      for (let c = 0; c < board.cols; c++) {
        board.h_walls[r][c] = false;
        board.h_gates[r][c] = false;
      }
    }
    draw();
  }

  function clearEntities() {
    if (!board) return;
    board.player = null;
    board.white_mummies = [];
    board.red_mummies = [];
    board.traps = [];
    board.keys = [];
    board.exit = null;
    draw();
  }

  async function loadBoard() {
    const res = await fetch('/api/board');
    board = await res.json();
    ensureFields(board);
    rowsInput.value = board.rows;
    colsInput.value = board.cols;
    resizeCanvasToBoard();
    draw();
    setStatus('Loaded board.json');
  }

  async function newBoard() {
    const rows = Math.max(1, parseInt(rowsInput.value || '8', 10));
    const cols = Math.max(1, parseInt(colsInput.value || '8', 10));
    const res = await fetch('/api/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows, cols })
    });
    board = await res.json();
    ensureFields(board);
    rowsInput.value = board.rows;
    colsInput.value = board.cols;
    resizeCanvasToBoard();
    draw();
    setStatus(`New ${rows}x${cols} board created`);
  }

  async function saveBoard() {
    if (!board) return;
    const res = await fetch('/api/board', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(board)
    });
    const j = await res.json();
    if (j.status === 'ok') setStatus('Saved to data/board.json');
    else setStatus('Save failed: ' + (j.message || 'unknown'));
  }

  function exportJSON() {
    if (!board) return;
    const data = JSON.stringify(board, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'board.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setStatus('Exported JSON');
  }

  function exportPairs() {
    if (!board) return;
    const base = parseInt(indexBaseSel.value || '0', 10);
    const lines = [];

    // walls
    lines.push('# walls');
    for (let r = 0; r < board.rows; r++) {
      for (let c = 1; c < board.cols; c++) {
        if (board.v_walls[r][c]) {
          const r1 = r + base, c1 = (c - 1) + base; const r2 = r + base, c2 = c + base;
          lines.push(`${r1},${c1} ${r2},${c2}`);
        }
      }
    }
    for (let r = 1; r < board.rows; r++) {
      for (let c = 0; c < board.cols; c++) {
        if (board.h_walls[r][c]) {
          const r1 = (r - 1) + base, c1 = c + base; const r2 = r + base, c2 = c + base;
          lines.push(`${r1},${c1} ${r2},${c2}`);
        }
      }
    }

    // gates
    lines.push('# gates');
    for (let r = 0; r < board.rows; r++) {
      for (let c = 1; c < board.cols; c++) {
        if (board.v_gates[r][c]) {
          const r1 = r + base, c1 = (c - 1) + base; const r2 = r + base, c2 = c + base;
          lines.push(`${r1},${c1} ${r2},${c2}`);
        }
      }
    }
    for (let r = 1; r < board.rows; r++) {
      for (let c = 0; c < board.cols; c++) {
        if (board.h_gates[r][c]) {
          const r1 = (r - 1) + base, c1 = c + base; const r2 = r + base, c2 = c + base;
          lines.push(`${r1},${c1} ${r2},${c2}`);
        }
      }
    }

    // entities & tiles
    lines.push('# entities');
    const emitRC = (tag, r, c) => lines.push(`${tag} ${r + base},${c + base}`);
    if (Array.isArray(board.player)) emitRC('player', board.player[0], board.player[1]);
    if (Array.isArray(board.exit)) emitRC('exit', board.exit[0], board.exit[1]);
    for (const [r,c] of board.white_mummies) emitRC('white', r, c);
    for (const [r,c] of board.red_mummies) emitRC('red', r, c);
    for (const [r,c] of board.traps) emitRC('trap', r, c);
    for (const [r,c] of board.keys) emitRC('key', r, c);

    exportText.value = lines.join('\n');
    exportPanel.open = true;
    setStatus('Exported walls, gates, and entities');
  }

  async function copyExport() {
    if (!exportText.value) return;
    await navigator.clipboard.writeText(exportText.value);
    setStatus('Copied to clipboard');
  }

  // Event bindings
  canvas.addEventListener('mousedown', onCanvasClick);
  clearBtn.addEventListener('click', clearInnerWallsAndGates);
  clearEntitiesBtn.addEventListener('click', clearEntities);
  loadBtn.addEventListener('click', loadBoard);
  newBtn.addEventListener('click', newBoard);
  saveBtn.addEventListener('click', saveBoard);
  exportJsonBtn.addEventListener('click', exportJSON);
  exportPairsBtn.addEventListener('click', exportPairs);
  copyExportBtn.addEventListener('click', copyExport);

  // Init
  loadBoard();
})();
