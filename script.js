// script.js - Integração Frontend com Backend BoredFy AI

// ===== CONFIGURAÇÃO =====
const API_BASE_URL = window.location.origin;
let authToken = null;
let currentUser = null;

// ===== FUNÇÕES AUXILIARES =====

function getAuthHeaders() {
    if (!authToken) {
        return {};
    }
    return {
        'Authorization': `Bearer ${authToken}`
    };
}

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
        ...options.headers
    };
    
    const response = await fetch(url, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        // Token expirado, redirecionar para login
        sessionStorage.removeItem('boredfy_logged_in');
        sessionStorage.removeItem('boredfy_auth_token');
        window.location.href = 'login.html';
        throw new Error('Sessão expirada');
    }
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
        throw new Error(error.detail || 'Erro na requisição');
    }
    
    return response.json();
}

function showNotification(message, type = 'info') {
    // Criar notificação toast
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        'bg-blue-500'
    } text-white`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ===== AUTENTICAÇÃO =====

async function checkAuth() {
    const token = sessionStorage.getItem('boredfy_auth_token');
    if (!token) {
        return false;
    }
    
    authToken = token;
    
    try {
        currentUser = await apiRequest('/auth/me');
        return true;
    } catch (error) {
        console.error('Erro ao verificar autenticação:', error);
        return false;
    }
}

async function login(email, password) {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        throw new Error('Email ou senha incorretos');
    }
    
    const data = await response.json();
    authToken = data.access_token;
    sessionStorage.setItem('boredfy_auth_token', authToken);
    sessionStorage.setItem('boredfy_logged_in', 'true');
    
    return data;
}

async function register(email, password) {
    return await apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password })
    });
}

// ===== API KEYS =====

async function validateApiKey(apiKey) {
    return await apiRequest('/api-keys/validate', {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey })
    });
}

async function addApiKey(apiKey, service = 'Gemini') {
    return await apiRequest('/api-keys/add', {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey, service })
    });
}

async function getApiKeys() {
    return await apiRequest('/api-keys');
}

async function deleteApiKey(keyId) {
    return await apiRequest(`/api-keys/${keyId}`, {
        method: 'DELETE'
    });
}

// ===== AGENTES =====

async function createAgent(agentData) {
    return await apiRequest('/agents', {
        method: 'POST',
        body: JSON.stringify(agentData)
    });
}

async function getAgents() {
    return await apiRequest('/agents');
}

async function getAgent(agentId) {
    return await apiRequest(`/agents/${agentId}`);
}

async function updateAgent(agentId, agentData) {
    return await apiRequest(`/agents/${agentId}`, {
        method: 'PUT',
        body: JSON.stringify(agentData)
    });
}

async function deleteAgent(agentId) {
    return await apiRequest(`/agents/${agentId}`, {
        method: 'DELETE'
    });
}

// ===== CRIAÇÃO DE AGENTE COM IA =====

async function createAgentWithAI(agentName, files) {
    const formData = new FormData();
    formData.append('agent_name', agentName);
    
    for (let file of files) {
        formData.append('files', file);
    }
    
    const response = await fetch(`${API_BASE_URL}/agents/create-with-ai`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Erro ao criar agente com IA');
    }
    
    return response.json();
}

// ===== VOZES =====

async function getVoices() {
    return await apiRequest('/voices');
}

async function getVoicesByLanguage(languageCode) {
    return await apiRequest(`/voices/${languageCode}`);
}

// ===== JOBS =====

async function createGenerationJobs(agentId, titulos) {
    return await apiRequest('/jobs/generate', {
        method: 'POST',
        body: JSON.stringify({ agent_id: agentId, titulos })
    });
}

async function getJobQueue() {
    return await apiRequest('/jobs/queue');
}

async function getJobDetail(jobId) {
    return await apiRequest(`/jobs/${jobId}`);
}

async function cancelJob(jobId) {
    return await apiRequest(`/jobs/${jobId}/cancel`, {
        method: 'POST'
    });
}

// ===== STATS =====

async function getUserStats() {
    return await apiRequest('/stats/dashboard');
}

// ===== ARQUIVOS =====

async function getRecentFiles() {
    return await apiRequest('/files/recent');
}

async function deleteFile(fileId) {
    return await apiRequest(`/files/${fileId}`, {
        method: 'DELETE'
    });
}

// ===== INICIALIZAÇÃO =====

document.addEventListener('DOMContentLoaded', async function() {
    // Verificar se estamos na página de login
    if (window.location.pathname.includes('login.html')) {
        return; // Não fazer nada na página de login
    }
    
    // Verificar autenticação
    const isAuthenticated = await checkAuth();
    
    if (!isAuthenticated) {
        window.location.href = 'login.html';
        return;
    }
    
    // Inicializar a aplicação
    await initializeApp();
});

async function initializeApp() {
    console.log('✅ Usuário autenticado:', currentUser);
    
    // Carregar API keys
    await loadApiKeys();
    
    // Carregar agentes
    await loadAgents();
    
    // Carregar vozes
    await loadVoices();
    
    // Configurar event listeners
    setupEventListeners();
    
    // Iniciar polling de jobs
    startJobPolling();
}

async function loadApiKeys() {
    try {
        const keys = await getApiKeys();
        const container = document.getElementById('api-keys-list');
        
        if (!container) return;
        
        if (keys.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">Nenhuma chave adicionada</p>';
            return;
        }
        
        container.innerHTML = keys.map(key => `
            <div class="flex items-center justify-between p-2 bg-gray-700 rounded">
                <div>
                    <span class="text-sm text-white">${key.key_masked}</span>
                    <span class="text-xs text-gray-400 ml-2">${key.service}</span>
                </div>
                <button onclick="removeApiKey(${key.id})" class="text-red-400 hover:text-red-300">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Erro ao carregar API keys:', error);
    }
}

async function loadAgents() {
    try {
        const agents = await getAgents();
        const select = document.getElementById('agent-select');
        
        if (!select) return;
        
        select.innerHTML = '<option value="">Selecione um agente</option>' +
            agents.map(agent => `
                <option value="${agent.id}">${agent.name}</option>
            `).join('');
    } catch (error) {
        console.error('Erro ao carregar agentes:', error);
    }
}

async function loadVoices() {
    try {
        const data = await getVoices();
        window.availableVoices = data.voices;
        console.log('✅ Vozes carregadas:', data.voices.length);
    } catch (error) {
        console.error('Erro ao carregar vozes:', error);
    }
}

function setupEventListeners() {
    // Botão de adicionar API key
    const addKeyBtn = document.getElementById('add-api-key-btn');
    if (addKeyBtn) {
        addKeyBtn.addEventListener('click', handleAddApiKey);
    }
    
    // Botão de gerar roteiros
    const generateBtn = document.getElementById('generate-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', handleGenerate);
    }
    
    // Botão de criar agente
    const createAgentBtn = document.getElementById('create-agent-btn');
    if (createAgentBtn) {
        createAgentBtn.addEventListener('click', () => {
            document.getElementById('agent-modal').classList.remove('hidden');
        });
    }
    
    // Botão de stats
    const statsBtn = document.getElementById('stats-btn');
    if (statsBtn) {
        statsBtn.addEventListener('click', handleShowStats);
    }
    
    // Botão de arquivos
    const filesBtn = document.getElementById('files-btn');
    if (filesBtn) {
        filesBtn.addEventListener('click', handleShowFiles);
    }
}

async function handleAddApiKey() {
    const input = document.getElementById('api-key-input');
    if (!input) return;
    
    const apiKey = input.value.trim();
    if (!apiKey) {
        showNotification('Digite uma API key', 'error');
        return;
    }
    
    try {
        input.disabled = true;
        showNotification('Validando chave...', 'info');
        
        await addApiKey(apiKey);
        
        showNotification('Chave adicionada com sucesso!', 'success');
        input.value = '';
        await loadApiKeys();
    } catch (error) {
        showNotification(error.message, 'error');
    } finally {
        input.disabled = false;
    }
}

async function removeApiKey(keyId) {
    if (!confirm('Deseja remover esta chave?')) return;
    
    try {
        await deleteApiKey(keyId);
        showNotification('Chave removida', 'success');
        await loadApiKeys();
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

async function handleGenerate() {
    const agentSelect = document.getElementById('agent-select');
    const titulosInput = document.getElementById('titulos-input');
    
    if (!agentSelect || !titulosInput) return;
    
    const agentId = parseInt(agentSelect.value);
    const titulos = titulosInput.value.split('\n').filter(t => t.trim());
    
    if (!agentId) {
        showNotification('Selecione um agente', 'error');
        return;
    }
    
    if (titulos.length === 0) {
        showNotification('Digite pelo menos um título', 'error');
        return;
    }
    
    try {
        const jobs = await createGenerationJobs(agentId, titulos);
        showNotification(`${jobs.length} job(s) criado(s)!`, 'success');
        titulosInput.value = '';
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

async function handleShowStats() {
    try {
        const stats = await getUserStats();
        const modal = document.getElementById('stats-modal');
        
        if (!modal) return;
        
        // Atualizar conteúdo do modal
        document.getElementById('scripts-today').textContent = stats.scripts_today;
        document.getElementById('tts-today').textContent = stats.tts_today;
        document.getElementById('level-display').textContent = stats.level;
        document.getElementById('xp-display').textContent = stats.xp;
        document.getElementById('streak-display').textContent = stats.streak_count;
        
        modal.classList.remove('hidden');
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

async function handleShowFiles() {
    try {
        const files = await getRecentFiles();
        const modal = document.getElementById('user-files-modal');
        const list = document.getElementById('files-list');
        
        if (!modal || !list) return;
        
        if (files.length === 0) {
            list.innerHTML = '<p class="text-gray-400">Nenhum arquivo nas últimas 24h</p>';
        } else {
            list.innerHTML = files.map(file => `
                <div class="flex items-center justify-between p-2 bg-gray-700 rounded">
                    <div>
                        <a href="${file.download_url}" class="text-blue-400 hover:underline" download>
                            ${file.filename}
                        </a>
                        <span class="text-xs text-gray-400 ml-2">${file.file_type}</span>
                    </div>
                    <button onclick="removeFile(${file.id})" class="text-red-400 hover:text-red-300">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `).join('');
        }
        
        modal.classList.remove('hidden');
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

async function removeFile(fileId) {
    if (!confirm('Deseja deletar este arquivo?')) return;
    
    try {
        await deleteFile(fileId);
        showNotification('Arquivo deletado', 'success');
        await handleShowFiles();
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

let jobPollingInterval = null;

function startJobPolling() {
    // Atualizar fila de jobs a cada 5 segundos
    jobPollingInterval = setInterval(async () => {
        try {
            const jobs = await getJobQueue();
            updateJobsDisplay(jobs);
        } catch (error) {
            console.error('Erro ao atualizar jobs:', error);
        }
    }, 5000);
}

function updateJobsDisplay(jobs) {
    const container = document.getElementById('jobs-queue');
    if (!container) return;
    
    if (jobs.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-sm">Nenhum job na fila</p>';
        return;
    }
    
    container.innerHTML = jobs.slice(0, 10).map(job => `
        <div class="p-3 bg-gray-700 rounded-lg mb-2">
            <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-white">${job.titulo || 'Sem título'}</span>
                <span class="text-xs px-2 py-1 rounded ${
                    job.status === 'completed' ? 'bg-green-600' :
                    job.status === 'processing' ? 'bg-blue-600' :
                    job.status === 'failed' ? 'bg-red-600' :
                    job.status === 'cancelled' ? 'bg-gray-600' :
                    'bg-yellow-600'
                }">${job.status}</span>
            </div>
            <div class="w-full bg-gray-600 rounded-full h-2">
                <div class="bg-indigo-600 h-2 rounded-full" style="width: ${job.progress}%"></div>
            </div>
        </div>
    `).join('');
}

// Exportar funções globais
window.removeApiKey = removeApiKey;
window.removeFile = removeFile;
