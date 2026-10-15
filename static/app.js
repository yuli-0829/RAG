'use strict';

const messagesEl = document.getElementById('messages');
const formEl = document.getElementById('composer');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send');
const strategyEl = document.getElementById('strategy');
const docListEl = document.getElementById('doc-list');
const docCountEl = document.getElementById('doc-count');
const initBtn = document.getElementById('btn-init');
const initHint = document.getElementById('init-hint');

let busy = false;

/* ---------- 工具 ---------- */

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function renderInline(text) {
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function renderMarkdown(text) {
  const lines = escapeHtml(text).split('\n');
  let html = '';
  let listTag = null;
  const closeList = () => {
    if (listTag) {
      html += `</${listTag}>`;
      listTag = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line || /^-{3,}$/.test(line)) {
      closeList();
      continue;
    }
    const ordered = line.match(/^(\d+)[.、)]\s+(.*)$/);
    const bullet = line.match(/^[-*·]\s+(.*)$/);

    if (ordered) {
      if (listTag !== 'ol') { closeList(); html += '<ol>'; listTag = 'ol'; }
      html += `<li>${renderInline(ordered[2])}</li>`;
    } else if (bullet) {
      if (listTag !== 'ul') { closeList(); html += '<ul>'; listTag = 'ul'; }
      html += `<li>${renderInline(bullet[1])}</li>`;
    } else {
      closeList();
      html += `<p>${renderInline(line)}</p>`;
    }
  }
  closeList();
  return html;
}

function splitAnswer(answer) {
  const lines = String(answer).trimEnd().split('\n');
  const last = (lines[lines.length - 1] || '').trim();
  if (last.startsWith('来源：')) {
    return {
      text: lines.slice(0, -1).join('\n').trim(),
      inlineSources: last.slice(3).trim(),
    };
  }
  return { text: String(answer).trim(), inlineSources: '' };
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function clearWelcome() {
  const welcome = messagesEl.querySelector('.welcome');
  if (welcome) welcome.remove();
}

function setBusy(flag) {
  busy = flag;
  sendBtn.disabled = flag;
  initBtn.disabled = flag;
}

/* ---------- 消息渲染 ---------- */

function addUserMessage(text) {
  clearWelcome();
  const row = document.createElement('div');
  row.className = 'row user';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

function addLoading(text) {
  const row = document.createElement('div');
  row.className = 'row bot';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = `
    <div class="loading">
      <span class="dots"><i></i><i></i><i></i></span>
      <span class="loading-text">${escapeHtml(text)}</span>
    </div>`;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();

  const started = Date.now();
  const label = bubble.querySelector('.loading-text');
  const timer = setInterval(() => {
    label.textContent = `${text} ${((Date.now() - started) / 1000).toFixed(0)}s`;
  }, 500);

  return {
    elapsed: () => ((Date.now() - started) / 1000).toFixed(1),
    done: () => {
      clearInterval(timer);
      row.remove();
    },
  };
}

function addErrorMessage(message) {
  clearWelcome();
  const row = document.createElement('div');
  row.className = 'row bot error';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = `<p><strong>请求失败</strong></p><p>${escapeHtml(message)}</p>`;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

function addBotMessage(payload, elapsed) {
  const { text, inlineSources } = splitAnswer(payload.answer);
  const sources = (payload.sources && payload.sources.length)
    ? payload.sources
    : (inlineSources ? inlineSources.split(/[、,，]/).filter(Boolean) : []);

  const row = document.createElement('div');
  row.className = 'row bot';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  const pillStrategy = payload.strategy && payload.strategy !== 'none'
    ? `<span class="pill strategy">${escapeHtml(payload.strategy)}</span>` : '';

  let html = `
    <div class="meta">
      <span class="pill category">${escapeHtml(payload.category || '未知')}</span>
      ${pillStrategy}
      <button class="copy" type="button">复制</button>
      <span class="pill elapsed">${elapsed}s</span>
    </div>
    <div class="body">${renderMarkdown(text)}</div>`;

  if (sources.length) {
    html += `<div class="sources"><span class="sources-label">来源</span>${
      sources.map((s) => `<span class="source">${escapeHtml(s)}</span>`).join('')
    }</div>`;
  }

  const contexts = payload.contexts || [];
  if (contexts.length) {
    html += `<details class="contexts"><summary>查看 ${contexts.length} 条检索片段</summary>${
      contexts.map((c) => `
        <div class="ctx">
          <div class="ctx-head">${escapeHtml(c.doc_name)} · 向量 ${Number(c.score).toFixed(4)} · 重排 ${Number(c.rerank_score).toFixed(4)}</div>
          <div class="ctx-body">${escapeHtml(c.content)}</div>
        </div>`).join('')
    }</details>`;
  }

  bubble.innerHTML = html;

  const copyBtn = bubble.querySelector('.copy');
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(payload.answer);
      copyBtn.textContent = '已复制';
    } catch {
      copyBtn.textContent = '复制失败';
    }
    setTimeout(() => { copyBtn.textContent = '复制'; }, 1600);
  });

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

/* ---------- 接口 ---------- */

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* 非 JSON 响应 */ }

  if (!response.ok) {
    const detail = data && data.detail ? data.detail : (text || `HTTP ${response.status}`);
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

async function askQuestion(question) {
  if (busy || !question.trim()) return;

  addUserMessage(question);
  inputEl.value = '';
  inputEl.style.height = 'auto';
  setBusy(true);

  const loading = addLoading('正在检索知识库…');
  try {
    const payload = await requestJson('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        strategy: strategyEl.value || null,
      }),
    });
    const elapsed = loading.elapsed();
    loading.done();
    addBotMessage(payload, elapsed);
  } catch (error) {
    loading.done();
    addErrorMessage(error.message);
  } finally {
    setBusy(false);
    inputEl.focus();
  }
}

async function loadDocs() {
  try {
    const data = await requestJson('/docs_list');
    const docs = data.documents || [];
    docCountEl.textContent = `${data.total ?? docs.length} 篇`;

    if (!docs.length) {
      docListEl.innerHTML = '<li class="empty">文档库为空</li>';
      return;
    }

    docListEl.innerHTML = docs.map((doc) => `
      <li>
        <span class="dot ${escapeHtml(doc.status)}"></span>
        <span title="${escapeHtml(doc.file_type)} · ${escapeHtml(doc.upload_time)}">${escapeHtml(doc.doc_name)}</span>
      </li>`).join('');
  } catch (error) {
    docListEl.innerHTML = `<li class="empty">${escapeHtml(error.message)}</li>`;
  }
}

async function reloadData() {
  if (busy) return;
  setBusy(true);

  const started = Date.now();
  initHint.textContent = '正在解析并向量化，约需 1~3 分钟…';
  const timer = setInterval(() => {
    initHint.textContent = `正在解析并向量化… ${((Date.now() - started) / 1000).toFixed(0)}s`;
  }, 500);

  try {
    const result = await requestJson('/init_data', { method: 'POST' });
    const s = result.summary || {};
    initHint.textContent = `完成：新增 ${s.success || 0} · 跳过 ${s.skipped || 0} · 失败 ${s.failed || 0}`;
    await loadDocs();
  } catch (error) {
    initHint.textContent = `失败：${error.message}`;
  } finally {
    clearInterval(timer);
    setBusy(false);
  }
}

/* ---------- 事件 ---------- */

formEl.addEventListener('submit', (event) => {
  event.preventDefault();
  askQuestion(inputEl.value.trim());
});

inputEl.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    askQuestion(inputEl.value.trim());
  }
});

inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 160)}px`;
});

initBtn.addEventListener('click', reloadData);

messagesEl.addEventListener('click', (event) => {
  const chip = event.target.closest('.chip');
  if (chip) askQuestion(chip.dataset.q);
});

loadDocs();
inputEl.focus();
