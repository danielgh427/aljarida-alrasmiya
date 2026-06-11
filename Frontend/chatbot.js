// Chatbot JavaScript with semantic features and context memory
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
const exportBtn = document.getElementById('export-chat');
const clearBtn = document.getElementById('clear-chat');
const toggleSidebar = document.getElementById('toggle-sidebar');
const closePanel = document.getElementById('close-panel');

// State
let currentLang = 'ar';
let currentCategory = 'all';
let chatHistory = [];
let currentSources = [];
let lastSources = []; // Store sources for multi-turn conversations

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Event Listeners
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Category buttons
    categoryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            categoryBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.category;
            updateChatTitle();

            // Hide sidebar on mobile once a category is selected
            if (window.innerWidth <= 768) {
                document.querySelector('.sidebar').classList.add('hidden');
            }
        });
    });

    // Language toggle
    langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            langButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentLang = btn.id.includes('ar') ? 'ar' : 'en';
            updateLanguage();
        });
    });

    // Suggestion buttons
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            userInput.value = btn.dataset.query;
            sendMessage();
        });
    });

    // Export chat
    exportBtn.addEventListener('click', exportChat);

    // Clear chat
    clearBtn.addEventListener('click', clearChat);

    // Toggle sidebar
    toggleSidebar.addEventListener('click', () => {
        document.querySelector('.sidebar').classList.toggle('hidden');
    });

    // Close source panel
    closePanel.addEventListener('click', () => {
        sourcePanel.classList.add('hidden');
    });

    // Initialize health check
    checkHealth();
});

// Helper function to detect follow-up questions
function isFollowupQuestion(message) {
    const followupPatterns = [
        'أخبر',      // tell
        'أعطني',     // give me
        'هل هناك',   // are there
        'ما هو',     // what is
        'ما هي',     // what are
        'تفاصيل',    // details
        'معلومات',   // information
        'المزيد',    // more
        'أيضا',      // also
        'كذلك',      // also
        'متعلق',     // related
        'مثل',       // like
        'tell',      // tell me
        'give me',   // give me
        'do you have', // do you have
        'show me',   // show me
        'what is',   // what is
        'what are',  // what are
        'details',   // details
        'information', // information
        'more',      // more
        'also',      // also
        'related',   // related
        'similar',   // similar
        'about',     // about
        'any other', // any other
    ];

    const msgLower = message.toLowerCase();
    for (let pattern of followupPatterns) {
        if (msgLower.includes(pattern)) {
            return true;
        }
    }

    // Single keyword questions are new queries
    if (message.split(' ').length <= 2 && !message.includes('ما') && !message.includes('هل')) {
        return false;
    }

    return false;
}

// Send Message Function
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message
    addMessage(message, 'user');
    userInput.value = '';
    sendBtn.disabled = true;

    // Show typing indicator
    showTyping();

    try {
        // Add to chat history
        const timestamp = new Date().toISOString();
        chatHistory.push({
            role: 'user',
            content: message,
            timestamp: timestamp
        });

        const response = await fetch(`${API_URL}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: message,
                category: currentCategory,
                include_sources: true,
                max_results: 5,
                chat_history: chatHistory.slice(-8),
                // Only send previous sources for genuine follow-up questions
                previous_sources: (chatHistory.length > 0 &&
                    !/\d+/.test(message) &&           // No numbers (exact search)
                    !/(آخر|احدث|أحدث|latest|newest|recent)/i.test(message) &&  // No latest keywords
                    isFollowupQuestion(message))      // Is genuine follow-up
                    ? lastSources : null
            })
        });

        const data = await response.json();

        // Hide typing indicator
        hideTyping();

        // Add bot response
        addMessage(data.answer, 'assistant', {
            sources: data.sources,
            type: data.detected_category
        });

        // Update sources panel
        if (data.sources && data.sources.length > 0) {
            updateSourcesPanel(data.sources);
            lastSources = data.sources; // Store for multi-turn conversations
        }

        // Add to chat history
        chatHistory.push({
            role: 'assistant',
            content: data.answer,
            timestamp: new Date().toISOString(),
            sources: data.sources
        });

    } catch (error) {
        hideTyping();
        addMessage('عذراً، حدث خطأ في الاتصال. يرجى المحاولة مرة أخرى.', 'assistant');
        console.error('Error:', error);
    } finally {
        sendBtn.disabled = false;
    }
}

// Add Message to Chat
function addMessage(text, sender, metadata = null) {
    // Remove welcome message if exists
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Format message with markdown-like syntax
    contentDiv.innerHTML = formatMessage(text);

    messageDiv.appendChild(contentDiv);

    // Add metadata for assistant messages
    if (sender === 'assistant' && metadata) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';

        // Message type badge
        const typeSpan = document.createElement('span');
        typeSpan.className = `message-type ${metadata.type}`;
        if (metadata.type === 'law') {
            typeSpan.textContent = 'قانون';
        } else if (metadata.type === 'tender') {
            typeSpan.textContent = 'مناقصة';
        } else {
            typeSpan.textContent = 'مصدر';
        }
        metaDiv.appendChild(typeSpan);

        // Timestamp
        const timeSpan = document.createElement('span');
        timeSpan.textContent = new Date().toLocaleTimeString(currentLang === 'ar' ? 'ar-SA' : 'en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
        metaDiv.appendChild(timeSpan);

        // Sources button
        if (metadata.sources && metadata.sources.length > 0) {
            const sourcesBtn = document.createElement('button');
            sourcesBtn.className = 'sources-btn';
            sourcesBtn.innerHTML = `<i class="fas fa-book"></i> ${metadata.sources.length} مصادر`;
            sourcesBtn.addEventListener('click', () => {
                updateSourcesPanel(metadata.sources);
                sourcePanel.classList.remove('hidden');
            });
            metaDiv.appendChild(sourcesBtn);
        }

        messageDiv.appendChild(metaDiv);
    }

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Format Message with markdown-like syntax
function formatMessage(text) {
    // Convert markdown-like syntax to HTML
    let formatted = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>')
        .replace(/- (.*?)(<br>|$)/g, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        .replace(/<\/ul><ul>/g, '');

    return formatted;
}

// Update Sources Panel
// تحديث لوحة المصادر لإضافة رابط المصدر
function updateSourcesPanel(sources) {
    currentSources = sources;
    sourcesList.innerHTML = '';

    sources.forEach((source, index) => {
        const card = document.createElement('div');
        card.className = 'source-card';

        let metaHTML = '';

        if (source.source_type === 'tender') {
            metaHTML = `
                <strong>العنوان:</strong> ${source.tender_title || '-'}<br>
                <strong>الوصف:</strong> ${source.description || '-'}<br>
                <strong>الموقع:</strong> ${source.location || '-'}<br>
                <strong>الموعد النهائي:</strong> ${source.deadline || '-'}
            `;
        } else {
            metaHTML = `
                <strong>العنوان:</strong> ${source.law_title || '-'}<br>
                <strong>الرقم:</strong> ${source.law_number || '-'}<br>
                <strong>النوع:</strong> ${source.law_type || '-'}<br>
                <strong>التاريخ:</strong> ${source.law_date || '-'}
            `;
        }

        card.innerHTML = `
            <div class="source-header">
                <span class="source-type ${source.source_type}">
                    ${source.source_type === 'tender' ? 'مناقصة' : source.law_type || 'قانون'}
                </span>
                <span class="source-score">${source.percentage}%</span>
            </div>

            <div class="source-meta">
                ${metaHTML}
            </div>

            <div class="source-excerpt">
                ${source.excerpt || ''}
            </div>

            <div class="source-footer">
                <span>المصدر ${index + 1}</span>

                <div class="source-actions">

                    ${source.link ? `<a href="${source.link}" target="_blank" class="link-btn" onclick="event.stopPropagation();">
                        <i class="fas fa-external-link-alt"></i>
                    </a>` : ''}

                    <button class="copy-btn" onclick="event.stopPropagation(); copySource(${index})">
                        <i class="fas fa-copy"></i>
                    </button>

                </div>
            </div>
        `;

        card.addEventListener('click', () => {
            showFullSource(source);
        });

        sourcesList.appendChild(card);
    });
}
// Copy source to clipboard
function copySource(index) {
    const source = currentSources[index];
    navigator.clipboard.writeText(source.excerpt)
        .then(() => {
            // Show copied notification
            showNotification('تم نسخ المصدر');
        })
        .catch(err => {
            console.error('Failed to copy:', err);
        });
}

// Show full source in modal
// تحديث النافذة المنبثقة لإظهار رابط المصدر
function showFullSource(source) {
    const modal = document.createElement('div');
    modal.className = 'modal';

    let bodyHTML = '';

    if (source.source_type === 'tender') {
        bodyHTML = `
            <p><strong>العنوان:</strong> ${source.tender_title || '-'}</p>
            <p><strong>الوصف:</strong> ${source.description || '-'}</p>
            <p><strong>الموقع:</strong> ${source.location || '-'}</p>
            <p><strong>الموعد النهائي:</strong> ${source.deadline || '-'}</p>
        `;
    } else {
        bodyHTML = `
            <p><strong>العنوان:</strong> ${source.law_title || '-'}</p>
            <p><strong>رقم القانون:</strong> ${source.law_number || '-'}</p>
            <p><strong>نوع القانون:</strong> ${source.law_type || '-'}</p>
            <p><strong>تاريخ القانون:</strong> ${source.law_date || '-'}</p>
        `;
    }

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <button class="modal-close">&times;</button>
            </div>

            <div class="modal-body">
                ${bodyHTML}

                <hr>

                <pre style="white-space: pre-wrap;">
${source.excerpt || ''}
                </pre>

                ${source.link ? `<a href="${source.link}" target="_blank">فتح المصدر الرسمي</a>` : ''}
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector('.modal-close').onclick = () => modal.remove();
    modal.onclick = e => {
        if (e.target === modal) modal.remove();
    };
}
// Show typing indicator
function showTyping() {
    typingIndicator.classList.add('visible');
}

// Hide typing indicator
function hideTyping() {
    typingIndicator.classList.remove('visible');
}

// Update chat title based on category
function updateChatTitle() {
    const title = document.getElementById('chat-title');
    const titles = {
        all: 'المحادثة العامة',
        law: 'المحادثة القانونية',
        tender: 'محادثة المناقصات'
    };
    title.textContent = titles[currentCategory] || titles.all;
}

// Update language
function updateLanguage() {
    const isArabic = currentLang === 'ar';
    document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
    document.documentElement.lang = isArabic ? 'ar' : 'en';

    // Update placeholders
    userInput.placeholder = isArabic ? 'اكتب سؤالك هنا...' : 'Type your question here...';

    // Update UI elements
    document.querySelectorAll('.category-btn').forEach(btn => {
        const text = btn.textContent.trim();
        if (isArabic) {
            if (text.includes('All Documents')) btn.innerHTML = '<i class="fas fa-layer-group"></i> جميع المستندات';
            if (text.includes('Laws')) btn.innerHTML = '<i class="fas fa-gavel"></i> القوانين';
            if (text.includes('Tenders')) btn.innerHTML = '<i class="fas fa-file-contract"></i> المناقصات';
        } else {
            if (text.includes('جميع المستندات')) btn.innerHTML = '<i class="fas fa-layer-group"></i> All Documents';
            if (text.includes('القوانين')) btn.innerHTML = '<i class="fas fa-gavel"></i> Laws';
            if (text.includes('المناقصات')) btn.innerHTML = '<i class="fas fa-file-contract"></i> Tenders';
        }
    });
}

// Export chat history
function exportChat() {
    if (chatHistory.length === 0) {
        showNotification('لا توجد محادثة للتصدير');
        return;
    }

    let exportText = 'Al Jarida AI - Chat History\n';
    exportText += '================================\n\n';

    chatHistory.forEach(msg => {
        const timestamp = new Date(msg.timestamp).toLocaleString();
        exportText += `[${timestamp}] ${msg.role === 'user' ? 'المستخدم' : 'المساعد'}:\n`;
        exportText += `${msg.content}\n\n`;
    });

    const blob = new Blob([exportText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-history-${new Date().toISOString().split('T')[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    showNotification('تم تصدير المحادثة بنجاح');
}

// Clear chat
function clearChat() {
    if (confirm('هل أنت متأكد من مسح المحادثة؟')) {
        chatHistory = [];
        currentSources = [];
        lastSources = []; // Clear stored sources for new conversation
        sourcesList.innerHTML = '';

        // Show welcome message again
        messagesContainer.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">
                    <i class="fas fa-robot"></i>
                </div>
                <h2>مرحباً بك في Al Jarida AI</h2>
                <p>اسأل أي سؤال حول القوانين والمناقصات اللبنانية</p>
                <div class="suggestions">
                    <button class="suggestion-btn" data-query="ما هي آخر القوانين الصادرة؟">
                        <i class="fas fa-lightbulb"></i>
                        آخر القوانين
                    </button>
                    <button class="suggestion-btn" data-query="المناقصات الصحية المتاحة">
                        <i class="fas fa-lightbulb"></i>
                        المناقصات الصحية
                    </button>
                    <button class="suggestion-btn" data-query="قوانين البناء في لبنان">
                        <i class="fas fa-lightbulb"></i>
                        قوانين البناء
                    </button>
                    <button class="suggestion-btn" data-query="مناقصات البناء والتشييد">
                        <i class="fas fa-lightbulb"></i>
                        مناقصات البناء
                    </button>
                </div>
            </div>
        `;

        // Reattach event listeners to new suggestion buttons
        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                userInput.value = btn.dataset.query;
                sendMessage();
            });
        });

        showNotification('تم مسح المحادثة');
    }
}

// Show notification
function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Check API health
async function checkHealth() {
    try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();
        console.log('API Health:', data);
    } catch (error) {
        console.error('API Health Check Failed:', error);
    }
}

// Function to copy source (global for onclick)
window.copySource = copySource;