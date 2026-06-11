// Dynamic API URL for Railway or Localhost
const API_URL = window.location.origin;

// DOM Elements
const messagesContainer = document.getElementById('messages-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const typingIndicator = document.getElementById('typing-indicator');
const sourcePanel = document.getElementById('source-panel');
const sourcesList = document.getElementById('sources-list');
const categoryBtns = document.querySelectorAll('.category-btn');
const langButtons = document.querySelectorAll('.language-toggle button');
const clearBtn = document.getElementById('clear-chat');
const toggleSidebar = document.getElementById('toggle-sidebar');
const closePanel = document.getElementById('close-panel');

// State
let currentLang = 'ar';
let currentCategory = 'all';
let chatHistory = []; // Stores cleaned objects {role, content}
let lastSources = []; // Multi-turn memory

document.addEventListener('DOMContentLoaded', () => {
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Sidebar Category Logic
    categoryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            categoryBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.category;
            if (window.innerWidth <= 1024) document.querySelector('.sidebar').classList.remove('active');
        });
    });

    // Mobile Sidebar Toggle
    if (toggleSidebar) {
        toggleSidebar.addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('active');
        });
    }

    // Close Source Panel
    if (closePanel) {
        closePanel.addEventListener('click', () => {
            sourcePanel.classList.remove('active');
            sourcePanel.classList.add('hidden');
        });
    }

    checkHealth();
});

// Detect follow-up questions for Multi-Turn Logic
function isFollowup(msg) {
    const keywords = ['أخبر', 'أعطني', 'تفاصيل', 'أيضا', 'more', 'details', 'tell me'];
    return keywords.some(k => msg.toLowerCase().includes(k)) && chatHistory.length > 0;
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // 1. UI: Add User Message
    addMessage(message, 'user');
    userInput.value = '';
    sendBtn.disabled = true;
    showTyping();

    try {
        // 2. Prepare Multi-Turn Payload
        const payload = {
            question: message,
            category: currentCategory,
            include_sources: true,
            max_results: 5,
            chat_history: chatHistory.slice(-6), // Send last 3 turns
            previous_sources: (isFollowup(message) && !/\d+/.test(message)) ? lastSources : null
        };

        const response = await fetch(`${API_URL}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        hideTyping();

        // 3. UI: Add Assistant Message
        addMessage(data.answer, 'assistant', {
            sources: data.sources,
            type: data.detected_category
        });

        // 4. Update Memory
        if (data.sources && data.sources.length > 0) {
            updateSourcesPanel(data.sources);
            lastSources = data.sources;
        }

        chatHistory.push({ role: 'user', content: message });
        chatHistory.push({ role: 'assistant', content: data.answer });

    } catch (error) {
        hideTyping();
        addMessage('عذراً، حدث خطأ فني. يرجى المحاولة لاحقاً.', 'assistant');
        console.error('Fetch Error:', error);
    } finally {
        sendBtn.disabled = false;
    }
}

function addMessage(text, sender, metadata = null) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    
    let metaHTML = '';
    if (metadata && metadata.sources) {
        metaHTML = `<div class="message-meta">
            <span class="message-type ${metadata.type}">${metadata.type === 'law' ? 'قانون' : 'مناقصة'}</span>
            <button class="sources-btn" onclick="openSources()"><i class="fas fa-book"></i> المصادر</button>
        </div>`;
    }

    div.innerHTML = `<div class="message-content">${text.replace(/\n/g, '<br>')}</div>${metaHTML}`;
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

window.openSources = () => {
    sourcePanel.classList.add('active');
    sourcePanel.classList.remove('hidden');
};

function updateSourcesPanel(sources) {
    sourcesList.innerHTML = '';
    sources.forEach((s, idx) => {
        const card = document.createElement('div');
        card.className = 'source-card';
        card.innerHTML = `
            <div class="source-header">
                <span class="source-type ${s.source_type}">${s.source_type}</span>
                <span class="source-score">${s.percentage}%</span>
            </div>
            <div class="source-excerpt">${s.excerpt}</div>
            <div class="source-footer">
                <strong>${s.law_title || s.tender_title || 'مصدر'}</strong>
                ${s.link ? `<a href="${s.link}" target="_blank" class="link-btn"><i class="fas fa-external-link-alt"></i></a>` : ''}
            </div>
        `;
        sourcesList.appendChild(card);
    });
}

async function checkHealth() {
    try { await fetch(`${API_URL}/health`); } catch (e) { console.log("Offline"); }
}

function showTyping() { typingIndicator.classList.add('visible'); }
function hideTyping() { typingIndicator.classList.remove('visible'); }

function clearChat() {
    if(confirm('مسح المحادثة؟')) {
        messagesContainer.innerHTML = '';
        chatHistory = [];
        lastSources = [];
        sourcesList.innerHTML = '';
    }
}