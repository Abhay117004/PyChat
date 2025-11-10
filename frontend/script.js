const CONFIG = {
    API_BASE_URL: window.location.origin,
    MAX_MESSAGE_LENGTH: 8000,
    TOAST_DURATION: 3000,
    STORAGE_KEY: 'python-rag-chat-history',
};

const state = {
    conversationHistory: [],
    currentMode: 'precise', 
    isLoading: false,
    theme: 'dark',
};

let elements = {};

document.addEventListener('DOMContentLoaded', () => {
    elements = {
        sidebar: document.getElementById('sidebar'),
        sidebarToggle: document.getElementById('sidebarToggle'),
        mobileMenuToggle: document.getElementById('mobileMenuToggle'),
        themeToggle: document.getElementById('themeToggle'),
        sourcesToggle: document.getElementById('sourcesToggle'),
        
        mainContent: document.getElementById('mainContent'),
        totalChunks: document.getElementById('totalChunks'),
        uniquePages: document.getElementById('uniquePages'),
        connectionStatus: document.getElementById('connectionStatus'),
        chatMessages: document.getElementById('chatMessages'),
        welcomeScreen: document.getElementById('welcomeScreen'),
        chatForm: document.getElementById('chatForm'),
        messageInput: document.getElementById('messageInput'),
        charCounter: document.getElementById('charCounter'),
        submitBtn: document.getElementById('submitBtn'),
        clearHistoryBtn: document.getElementById('clearHistoryBtn'),
        exportChatBtn: document.getElementById('exportChatBtn'),
        sourcesPanel: document.getElementById('sourcesPanel'),
        closeSourcesBtn: document.getElementById('closeSourcesBtn'),
        sourcesList: document.getElementById('sourcesList'),
        sourcesCount: document.getElementById('sourcesCount'),
        clearModal: document.getElementById('clearModal'),
        cancelClearBtn: document.getElementById('cancelClearBtn'),
        confirmClearBtn: document.getElementById('confirmClearBtn'),
        toast: document.getElementById('toast'),
        toastIcon: document.getElementById('toastIcon'),
        toastMessage: document.getElementById('toastMessage'),
        sidebarOverlay: document.getElementById('sidebarOverlay'),
    };
    
    initializeApp();
});

function initializeApp() {
    console.log('Initializing PyChat...');
    
    loadSavedState();
    
    initializeTheme();
    
    setupEventListeners();
    
    loadConversationHistory();
    
    if (elements.sidebar) {
        elements.sidebar.classList.add('is-collapsed');
    }
    if (elements.sidebarToggle) {
        elements.sidebarToggle.setAttribute('aria-expanded', 'false');
    }
    if (elements.mobileMenuToggle) {
        elements.mobileMenuToggle.setAttribute('aria-expanded', 'false');
    }
    
    console.log('Initial sidebar state: collapsed (overlay style)');
    
    loadSystemStats();

    console.log('App initialized successfully');
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    state.theme = savedTheme;
    document.body.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', state.theme);
    localStorage.setItem('theme', state.theme);
    showToast(
        `Switched to ${state.theme} theme`,
        'info'
    );
}

function setupEventListeners() {
    if (elements.sidebarToggle) {
        elements.sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
    }
    if (elements.mobileMenuToggle) {
        elements.mobileMenuToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
    }
    
    if (elements.themeToggle) {
        elements.themeToggle.addEventListener('click', toggleTheme);
    }
    
    if (elements.sourcesToggle) {
        elements.sourcesToggle.addEventListener('click', toggleSourcesPanel);
    }
    if (elements.closeSourcesBtn) {
        elements.closeSourcesBtn.addEventListener('click', toggleSourcesPanel);
    }
    
    if (elements.chatForm) {
        elements.chatForm.addEventListener('submit', handleSubmit);
    }
    
    if (elements.messageInput) {
        elements.messageInput.addEventListener('input', handleInputChange);
        elements.messageInput.addEventListener('keydown', handleKeyDown);
    }
    
    if (elements.clearHistoryBtn) {
        elements.clearHistoryBtn.addEventListener('click', showClearModal);
    }
    if (elements.exportChatBtn) {
        elements.exportChatBtn.addEventListener('click', exportChat);
    }
    
    if (elements.cancelClearBtn) {
        elements.cancelClearBtn.addEventListener('click', hideClearModal);
    }
    if (elements.confirmClearBtn) {
        elements.confirmClearBtn.addEventListener('click', confirmClearHistory);
    }
    
    const exampleCards = document.querySelectorAll('.example-card');
    exampleCards.forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            if (query && elements.messageInput) {
                elements.messageInput.value = query;
                updateCharCounter();
                elements.messageInput.focus();
            }
        });
    });
    
    if (elements.clearModal) {
        elements.clearModal.addEventListener('click', (e) => {
            if (e.target === elements.clearModal) {
                hideClearModal();
            }
        });
    }

    document.addEventListener('click', (event) => {
        if (elements.sidebar) {
            const isOpen = !elements.sidebar.classList.contains('is-collapsed');
            
            if (isOpen) {
                const clickedInsideSidebar = elements.sidebar.contains(event.target);
                const clickedMenuButton = elements.mobileMenuToggle && 
                                         (elements.mobileMenuToggle === event.target || 
                                          elements.mobileMenuToggle.contains(event.target));
                
                if (!clickedInsideSidebar && !clickedMenuButton) {
                    console.log('Click outside detected - closing sidebar');
                    closeSidebar();
                }
            }
        }
    });
    
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            console.log(`Window resized: ${window.innerWidth}px wide`);
        }, 150);
    });
}

function toggleSidebar() {
    if (!elements.sidebar) return;
    
    elements.sidebar.classList.toggle('is-collapsed');
    const isExpanded = !elements.sidebar.classList.contains('is-collapsed');
    
    if (elements.sidebarToggle) {
        elements.sidebarToggle.setAttribute('aria-expanded', isExpanded);
    }
    if (elements.mobileMenuToggle) {
        elements.mobileMenuToggle.setAttribute('aria-expanded', isExpanded);
    }
    
    if (elements.sidebarOverlay) {
        elements.sidebarOverlay.classList.toggle('is-active', isExpanded);
    }
    
    console.log(`Sidebar ${isExpanded ? 'opened' : 'closed'} (overlay style)`);
}

function toggleSourcesPanel() {
    if (elements.sourcesPanel) {
        elements.sourcesPanel.classList.toggle('is-active');
    }
}

function showSources(sources) {
    if (!elements.sourcesList || !elements.sourcesCount) return;
    
    if (!sources || sources.length === 0) {
        elements.sourcesList.innerHTML = `
            <div class="sources-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
                </svg>
                <p>No sources available</p>
            </div>
        `;
        elements.sourcesCount.textContent = 'No sources';
        return;
    }
    
    elements.sourcesList.innerHTML = sources.map((source, index) => `
        <div class="source-card" onclick="window.open('${escapeHtml(source.url || '#')}', '_blank')">
            <div class="source-card__domain">[${escapeHtml(source.domain || 'Unknown Source')}]</div>
            <div class="source-card__title">${escapeHtml(source.title || 'Untitled')}</div>
            <div class="source-card__snippet">${escapeHtml(source.snippet || source.content || 'No preview available')}</div>
            <div class="source-card__meta">
                <span>Source ${index + 1}</span>
                ${source.score ? `<span>Relevance: ${(source.score * 100).toFixed(0)}%</span>` : ''}
            </div>
        </div>
    `).join('');
    
    elements.sourcesCount.textContent = `${sources.length} source${sources.length !== 1 ? 's' : ''}`;
    
    if (elements.sourcesPanel && !elements.sourcesPanel.classList.contains('is-active')) {
        elements.sourcesPanel.classList.add('is-active');
    }
}

async function handleSubmit(e) {
    e.preventDefault();
    
    const message = elements.messageInput.value.trim();
    
    if (!message || state.isLoading) {
        return;
    }
    
    if (elements.welcomeScreen) {
        elements.welcomeScreen.style.display = 'none';
    }
    
    addMessage(message, 'user');
    
    elements.messageInput.value = '';
    updateCharCounter();
    elements.messageInput.style.height = 'auto';
    
    setLoadingState(true);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: message,
                mode: state.currentMode,
            }),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        addMessage(data.response || data.answer, 'assistant');
        
        if (data.sources && data.sources.length > 0) {
            showSources(data.sources);
        }
        
        saveConversationHistory();
        
    } catch (error) {
        console.error('Error sending message:', error);
        addMessage(
            'Sorry, I encountered an error processing your request. Please make sure the backend server is running on http://localhost:8000.',
            'assistant',
            true
        );
        showToast('Failed to send message. Check backend connection.', 'error');
    } finally {
        setLoadingState(false);
        elements.messageInput.focus();
    }
}

function addMessage(content, sender, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message--${sender}`;
    
    const avatar = sender === 'user' ? 'U' : 'A';
    const senderName = sender === 'user' ? 'You' : 'Assistant';
    
    messageDiv.innerHTML = `
        <div class="message__header">
            <div class="message__avatar">${avatar}</div>
            <span class="message__sender">${senderName}</span>
        </div>
        <div class="message__content ${isError ? 'error-message' : ''}">${formatMessage(content)}</div>
    `;
    
    elements.chatMessages.appendChild(messageDiv);
    
    state.conversationHistory.push({
        role: sender,
        content: content,
        timestamp: new Date().toISOString(),
    });
    
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function formatMessage(text) {
    let formatted = escapeHtml(text);
    
    formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    formatted = formatted.replace(/(?<!<\/pre>)(\r\n|\r|\n)/g, '<br>');
    
    return formatted;
}

function setLoadingState(loading) {
    state.isLoading = loading;
    elements.submitBtn.disabled = loading;
    elements.messageInput.disabled = loading;
    
    if (loading) {
        elements.submitBtn.classList.add('is-loading');
    } else {
        elements.submitBtn.classList.remove('is-loading');
    }
}

function handleInputChange() {
    updateCharCounter();
    autoResizeTextarea();
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        elements.chatForm.dispatchEvent(new Event('submit'));
    }
}

function updateCharCounter() {
    if (elements.messageInput && elements.charCounter) {
        const length = elements.messageInput.value.length;
        elements.charCounter.textContent = `${length}/${CONFIG.MAX_MESSAGE_LENGTH}`;
    }
}

function autoResizeTextarea() {
    if (elements.messageInput) {
        elements.messageInput.style.height = 'auto';
        elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 200) + 'px';
    }
}

function showClearModal() {
    if (elements.clearModal) {
        elements.clearModal.classList.add('is-active');
    }
    closeSidebar();
}

function hideClearModal() {
    if (elements.clearModal) {
        elements.clearModal.classList.remove('is-active');
    }
}

function confirmClearHistory() {
    state.conversationHistory = [];
    
    const messageNodes = elements.chatMessages.querySelectorAll('.message');
    messageNodes.forEach(node => node.remove());
    
    if (elements.welcomeScreen) {
        elements.welcomeScreen.style.display = 'flex';
    } else {
        recreateWelcomeScreen();
    }
    
    saveConversationHistory();
    
    hideClearModal();
    
    showToast('Chat history cleared', 'success');
}

function recreateWelcomeScreen() {
    elements.chatMessages.innerHTML = `
        <div class="welcome" id="welcomeScreen">
            <div class="welcome__content">
                <div class="welcome__icon" aria-hidden="true">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 6v6l4 2"/>
                    </svg>
                </div>
                <h2 class="welcome__title">Welcome to PyChat!</h2>
                <p class="welcome__subtitle">Ask anything about Python, data science, ML, web development, and more</p>
                
                <div class="example-cards">
                    <button class="example-card" data-query="How do I read a CSV file with pandas?">
                        <div class="example-card__header">
                            <span class="example-card__icon" aria-hidden="true">*</span>
                            <h3 class="example-card__title">Data Processing</h3>
                        </div>
                        <p class="example-card__description">How do I read a CSV file with pandas?</p>
                    </button>
                    <button class="example-card" data-query="Explain numpy broadcasting with examples">
                        <div class="example-card__header">
                            <span class="example-card__icon" aria-hidden="true">*</span>
                            <h3 class="example-card__title">NumPy</h3>
                        </div>
                        <p class="example-card__description">Explain numpy broadcasting with examples</p>
                    </button>
                    <button class="example-card" data-query="How to build a REST API with FastAPI?">
                        <div class="example-card__header">
                            <span class="example-card__icon" aria-hidden="true">*</span>
                            <h3 class="example-card__title">Web Development</h3>
                        </div>
                        <p class="example-card__description">How to build a REST API with FastAPI?</p>
                    </button>
                    <button class="example-card" data-query="What are Python decorators and how do they work?">
                        <div class="example-card__header">
                            <span class="example-card__icon" aria-hidden="true">*</span>
                            <h3 class="example-card__title">Core Python</h3>
                        </div>
                        <p class="example-card__description">What are Python decorators?</p>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    const exampleCards = document.querySelectorAll('.example-card');
    exampleCards.forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            if (query) {
                elements.messageInput.value = query;
                updateCharCounter();
                elements.messageInput.focus();
            }
        });
    });
}

function exportChat() {
    if (state.conversationHistory.length === 0) {
        showToast('No conversation to export', 'info');
        return;
    }
    
    const exportData = {
        timestamp: new Date().toISOString(),
        mode: state.currentMode,
        theme: state.theme,
        messages: state.conversationHistory,
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json',
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-export-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Chat exported successfully', 'success');

    closeSidebar();
}

async function loadSystemStats() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/stats`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch stats');
        }
        
        const stats = await response.json();
        
        if (elements.totalChunks) {
            elements.totalChunks.textContent = stats.total_chunks 
                ? stats.total_chunks.toLocaleString() 
                : 'N/A';
        }
        
        if (elements.uniquePages) {
            elements.uniquePages.textContent = stats.unique_pages 
                ? stats.unique_pages.toLocaleString() 
                : 'N/A';
        }
        
        updateConnectionStatus('connected');
        
    } catch (error) {
        console.error('Error loading stats:', error);
        
        if (elements.totalChunks) {
            elements.totalChunks.textContent = 'Offline';
        }
        
        if (elements.uniquePages) {
            elements.uniquePages.textContent = 'Offline';
        }
        
        updateConnectionStatus('disconnected');
    }
}

function updateConnectionStatus(status) {
    const statusBadge = elements.connectionStatus;
    if (!statusBadge) return;
    
    if (status === 'connected') {
        statusBadge.innerHTML = `
            <span class="status-badge__dot"></span>
            <span class="status-badge__text">Ready</span>
        `;
        statusBadge.className = 'status-badge status-badge--success';
    } else {
        statusBadge.innerHTML = `
            <span class="status-badge__dot"></span>
            <span class="status-badge__text">Offline</span>
        `;
        statusBadge.className = 'status-badge status-badge--error';
    }
}

function loadSavedState() {
    try {
        const saved = localStorage.getItem(CONFIG.STORAGE_KEY);
        if (saved) {
            const data = JSON.parse(saved);
            state.conversationHistory = data.messages || [];
            state.currentMode = data.mode || 'balanced';
        }
    } catch (error) {
        console.error('Error loading saved state:', error);
        state.conversationHistory = [];
    }
}

function saveConversationHistory() {
    try {
        const data = {
            messages: state.conversationHistory,
            mode: state.currentMode,
            timestamp: new Date().toISOString(),
        };
        localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(data));
    } catch (error) {
        console.error('Error saving conversation:', error);
    }
}

function loadConversationHistory() {
    if (state.conversationHistory.length > 0) {
        if (elements.welcomeScreen) {
            elements.welcomeScreen.style.display = 'none';
        }
        
        state.conversationHistory.forEach(msg => {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message message--${msg.role}`;
            
            const avatar = msg.role === 'user' ? 'U' : 'A';
            const senderName = msg.role === 'user' ? 'You' : 'Assistant';
            
            messageDiv.innerHTML = `
                <div class="message__header">
                    <div class="message__avatar">${avatar}</div>
                    <span class="message__sender">${senderName}</span>
                </div>
                <div class="message__content">${formatMessage(msg.content)}</div>
            `;
            
            elements.chatMessages.appendChild(messageDiv);
        });
        
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }
}

let toastTimeout;

function showToast(message, type = 'info') {
    const icons = {
        success: '✓',
        error: '✕',
        info: 'ℹ',
        warning: '⚠',
    };
    
    elements.toastIcon.textContent = icons[type] || icons.info;
    elements.toastMessage.textContent = message;
    
    elements.toast.className = `toast toast--${type} is-visible`;
    
    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }
    
    toastTimeout = setTimeout(() => {
        elements.toast.classList.remove('is-visible');
    }, CONFIG.TOAST_DURATION);
}

function escapeHtml(text) {
    if (typeof text !== 'string') {
        return '';
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function closeSidebar() {
    if (!elements.sidebar) return;
    
    if (!elements.sidebar.classList.contains('is-collapsed')) {
        elements.sidebar.classList.add('is-collapsed');
        if (elements.sidebarToggle) {
            elements.sidebarToggle.setAttribute('aria-expanded', 'false');
        }
        if (elements.mobileMenuToggle) {
            elements.mobileMenuToggle.setAttribute('aria-expanded', 'false');
        }
        if (elements.sidebarOverlay) {
            elements.sidebarOverlay.classList.remove('is-active');
        }
        console.log('Sidebar closed');
    }
}

function openSidebar() {
    if (!elements.sidebar) return;
    
    if (elements.sidebar.classList.contains('is-collapsed')) {
        elements.sidebar.classList.remove('is-collapsed');
        if (elements.sidebarToggle) {
            elements.sidebarToggle.setAttribute('aria-expanded', 'true');
        }
        if (elements.mobileMenuToggle) {
            elements.mobileMenuToggle.setAttribute('aria-expanded', 'true');
        }
        if (elements.sidebarOverlay) {
            elements.sidebarOverlay.classList.add('is-active');
        }
        console.log('Sidebar opened');
    }
}

function handleMainContentClick(event) {
    if (window.innerWidth > 1024) return;
    
    if (elements.sidebar && !elements.sidebar.classList.contains('is-collapsed')) {
        if (!elements.sidebar.contains(event.target)) {
            closeSidebar();
        }
    }
}


window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    showToast('An unexpected error occurred.', 'error');
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    showToast('An unhandled promise rejection occurred.', 'error');
});

if (window.location.hostname === 'localhost') {
    window.appDebug = {
        state,
        elements,
        CONFIG,
        showToast,
        loadSystemStats,
    };
}

