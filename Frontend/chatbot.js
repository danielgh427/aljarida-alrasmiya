const API_BASE = '';

const messagesEl   = document.getElementById('messages');
const sourcesEl    = document.getElementById('sources-panel');
const form         = document.getElementById('chat-form');
const inputEl      = document.getElementById('user-input');

let chatHistory    = [];
let lastSources    = [];

function addMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showSources(sources) {
  if (!sources || sources.length === 0) {
    sourcesEl.classList.add('hidden');
    sourcesEl.innerHTML = '';
    return;
  }

  sourcesEl.classList.remove('hidden');
  const html = sources.map((s, i) => {
    if (s.source_type === 'tender') {
      return `<div class="source-card">
        <span class="badge tender">مناقصة</span>
        <strong>${escHtml(s.tender_title)}</strong>
        <p>${escHtml(s.description || '')}</p>
        ${s.deadline ? `<small>⚠️ Deadline: ${s.deadline}</small>` : ''}
        ${s.location ? `<small>📍 ${s.location}</small>` : ''}
        <small>${s.percentage ?? ''}%</small>
      </div>`;
    }
    return `<div class="source-card">
      <span class="badge law">قانون</span>
      <strong>${escHtml(s.law_title)}</strong>
      <p>${escHtml(s.excerpt || '')}</p>
      ${s.law_number ? `<small>رقم ${escHtml(s.law_number)}</small>` : ''}
      ${s.law_date ? `<small>📅 ${s.law_date}</small>` : ''}
      <small>${s.percentage ?? ''}%</small>
    </div>`;
  }).join('');

  sourcesEl.innerHTML = `<h3>المصادر</h3>${html}`;
}

function escHtml(text) {
  const d = document.createElement('div');
  d.textContent = text || '';
  return d.innerHTML;
}

async function sendMessage(question) {
  addMessage('user', escHtml(question));

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        category: 'all',
        max_results: 8,
        include_sources: true,
        chat_history: chatHistory,
        previous_sources: lastSources,
      }),
    });

    const data = await res.json();
    lastSources = data.sources || [];
    chatHistory.push({ role: 'user', content: question });
    chatHistory.push({ role: 'assistant', content: data.answer });

    addMessage('assistant', escHtml(data.answer));
    showSources(lastSources);
  } catch (err) {
    addMessage('assistant', '⚠️ خطأ في الاتصال بالخادم.');
  }
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = inputEl.value.trim();
  if (!q) return;
  inputEl.value = '';
  sendMessage(q);
});

// Health check on load
fetch(`${API_BASE}/health`)
  .then(r => r.json())
  .then(d => console.log('Health:', d))
  .catch(() => console.warn('Server not reachable'));
