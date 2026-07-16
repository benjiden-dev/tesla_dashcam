/**
 * Tesla Dashcam Web UI — Frontend Logic
 */
(function () {
  'use strict';

  // ── State ──
  let eventSource = null;
  let isRunning = false;

  // ── DOM Refs ──
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const terminalBody = $('#terminal-body');
  const terminalPlaceholder = $('#terminal-placeholder');
  const statusBadge = $('#status-badge');
  const statusText = $('#status-text');
  const btnGenerate = $('#btn-generate');
  const btnRun = $('#btn-run');
  const btnStop = $('#btn-stop');
  const btnClear = $('#btn-clear');
  const commandPreview = $('#command-preview');
  const commandCode = $('#command-code');
  const eventList = $('#event-list');

  // ── Init ──
  document.addEventListener('DOMContentLoaded', () => {
    initSections();
    initEvents();
    loadEvents();
  });

  // ── Collapsible Sections ──
  function initSections() {
    $$('.section-header').forEach((header) => {
      header.addEventListener('click', () => {
        header.closest('.section').classList.toggle('collapsed');
      });
    });
  }

  // ── Button Events ──
  function initEvents() {
    btnGenerate.addEventListener('click', generateCommand);
    btnRun.addEventListener('click', runProcess);
    btnStop.addEventListener('click', stopProcess);
    btnClear.addEventListener('click', clearTerminal);

    // Copy command button
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('copy-btn')) {
        navigator.clipboard.writeText(commandCode.textContent).then(() => {
          e.target.textContent = 'Copied!';
          setTimeout(() => { e.target.textContent = 'Copy'; }, 1500);
        });
      }
    });

    // Toggle camera checkboxes visual
    $$('.camera-toggle input').forEach((cb) => {
      cb.addEventListener('change', () => {
        cb.closest('.camera-toggle').classList.toggle('excluded', !cb.checked);
      });
    });

    // GPU type visibility
    const gpuToggle = $('#gpu');
    const gpuTypeRow = $('#gpu-type-row');
    gpuToggle.addEventListener('change', () => {
      gpuTypeRow.style.display = gpuToggle.checked ? '' : 'none';
    });
  }

  // ── Collect Form Data ──
  function collectFormData() {
    const data = {};

    data.source = $('#source').value;
    data.output = $('#output').value;

    // Layout
    data.layout = $('#layout').value;
    data.perspective = $('#perspective').checked;
    data.view_mode = document.querySelector('input[name="view_mode"]:checked')?.value || 'mirror';
    data.swap = $('#swap').checked;
    data.background = $('#background').value;

    // Camera exclusions
    data.excluded_cameras = [];
    $$('.camera-toggle input').forEach((cb) => {
      if (!cb.checked) data.excluded_cameras.push(cb.value);
    });

    // Text overlay
    data.no_timestamp = !$('#show_timestamp').checked;
    data.halign = $('#halign').value || null;
    data.valign = $('#valign').value || null;
    data.fontsize = $('#fontsize').value || null;
    data.fontcolor = $('#fontcolor_text').value || 'white';
    data.text_overlay_fmt = $('#text_overlay_fmt').value || null;

    // Video output
    data.motion_only = $('#motion_only').checked;
    data.speedup = $('#speedup').value || null;
    data.slowdown = $('#slowdown').value || null;
    data.merge = $('#merge').checked;

    // Encoding
    data.gpu = $('#gpu').checked;
    data.gpu_type = $('#gpu_type').value;
    data.quality = $('#quality').value;
    data.compression = $('#compression').value;
    data.encoding = $('#encoding').value;
    data.fps = $('#fps').value || 24;
    data.no_faststart = !$('#faststart').checked;

    // Advanced
    data.skip_existing = $('#skip_existing').checked;
    data.delete_source = $('#delete_source').checked;
    data.loglevel = $('#loglevel').value;

    return data;
  }

  // ── Generate Command ──
  async function generateCommand() {
    const data = collectFormData();
    try {
      const resp = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await resp.json();
      commandCode.textContent = result.command;
      commandPreview.classList.add('visible');
    } catch (err) {
      appendLog('error', `Failed to generate command: ${err.message}`);
    }
  }

  // ── Run Process ──
  async function runProcess() {
    if (isRunning) return;

    const data = collectFormData();
    clearTerminal();
    setStatus('starting');
    commandPreview.classList.remove('visible');

    try {
      // First, POST the config and get acknowledgment
      const resp = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (resp.status === 409) {
        appendLog('error', 'A process is already running. Stop it first.');
        setStatus('error');
        return;
      }

      isRunning = true;
      updateButtons();

      // Read the SSE stream
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        let eventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const rawData = line.slice(6);
            try {
              const parsed = JSON.parse(rawData);
              handleSSE(eventType, parsed);
            } catch {
              // ignore parse errors
            }
          }
        }
      }
    } catch (err) {
      appendLog('error', `Connection error: ${err.message}`);
      setStatus('error');
    } finally {
      isRunning = false;
      updateButtons();
    }
  }

  // ── Handle SSE Events ──
  function handleSSE(event, data) {
    switch (event) {
      case 'log':
        appendLog(classifyLog(data), data);
        break;
      case 'status':
        setStatus(data);
        break;
      case 'error':
        appendLog('error', data);
        setStatus('error');
        break;
      case 'done':
        isRunning = false;
        updateButtons();
        if (data === '0') {
          appendLog('success', '\n✓ Processing completed successfully.');
          setStatus('completed');
        } else {
          appendLog('error', `\n✗ Process exited with code ${data}`);
          setStatus('error');
        }
        break;
    }
  }

  // ── Classify Log Lines ──
  function classifyLog(line) {
    const lower = line.toLowerCase();
    if (lower.includes('error') || lower.includes('failed') || lower.includes('traceback')) return 'error';
    if (lower.includes('warning') || lower.includes('warn')) return 'warning';
    if (lower.includes('completed') || lower.includes('done') || lower.includes('finished')) return 'success';
    if (lower.includes('processing') || lower.includes('creating') || lower.includes('merging')) return 'info';
    return '';
  }

  // ── Stop Process ──
  async function stopProcess() {
    try {
      await fetch('/api/stop', { method: 'POST' });
      appendLog('warning', '⚠ Process stopped by user.');
      setStatus('idle');
    } catch (err) {
      appendLog('error', `Failed to stop: ${err.message}`);
    }
  }

  // ── Terminal Helpers ──
  function appendLog(cls, text) {
    if (terminalPlaceholder) {
      terminalPlaceholder.style.display = 'none';
    }
    const line = document.createElement('div');
    line.className = `log-line ${cls}`;
    line.textContent = text;
    terminalBody.appendChild(line);
    terminalBody.scrollTop = terminalBody.scrollHeight;
  }

  function clearTerminal() {
    terminalBody.innerHTML = '';
    if (terminalPlaceholder) {
      const ph = terminalPlaceholder.cloneNode(true);
      terminalBody.appendChild(ph);
    }
    commandPreview.classList.remove('visible');
  }

  function setStatus(status) {
    statusBadge.className = `status-badge ${status}`;
    const labels = {
      idle: 'Idle',
      starting: 'Starting…',
      running: 'Running',
      completed: 'Completed',
      error: 'Error',
    };
    statusText.textContent = labels[status] || status;
  }

  function updateButtons() {
    btnRun.disabled = isRunning;
    btnGenerate.disabled = isRunning;
    btnStop.disabled = !isRunning;
  }

  // ── Load Events ──
  async function loadEvents() {
    const source = $('#source').value;
    try {
      const resp = await fetch(`/api/events?path=${encodeURIComponent(source)}`);
      const events = await resp.json();
      renderEvents(events);
    } catch {
      // Silently fail
    }
  }

  function renderEvents(events) {
    if (!eventList) return;
    if (events.length === 0) {
      eventList.innerHTML = '<div class="event-item"><span class="event-meta">No events found in source directory</span></div>';
      return;
    }
    eventList.innerHTML = events
      .map(
        (e) => `
      <div class="event-item">
        <span class="event-name">${e.name}</span>
        <span class="event-meta">${e.file_count} files · ${e.total_size_mb} MB</span>
      </div>`
      )
      .join('');
  }

  // Reload events when source path changes
  document.addEventListener('DOMContentLoaded', () => {
    const sourceInput = $('#source');
    let debounce;
    sourceInput.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(loadEvents, 500);
    });
  });
})();
