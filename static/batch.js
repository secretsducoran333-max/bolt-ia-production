// batch.js
// Frontend para processamento em lote do Bolt IA

const API_BASE = window.location.origin;
let token = localStorage.getItem('token');
let availableVoices = {};
let selectedLanguages = new Set();
let agents = [];

// ============================================================================
// INICIALIZAÇÃO
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    if (!token) {
        window.location.href = '/';
        return;
    }

    // Carregar dados iniciais
    await Promise.all([
        loadUserInfo(),
        loadAgents(),
        loadAvailableVoices(),
        loadBatches()
    ]);

    // Setup event listeners
    setupEventListeners();
});

function setupEventListeners() {
    // Modo de processamento
    document.querySelectorAll('input[name="mode"]').forEach(radio => {
        radio.addEventListener('change', onModeChange);
    });

    // Títulos múltiplos
    document.getElementById('multipleTitles')?.addEventListener('input', updateTitleCount);

    // Busca de idiomas
    document.getElementById('languageSearch')?.addEventListener('input', filterLanguages);

    // Atualizar estimativa em tempo real
    document.getElementById('singleTitle')?.addEventListener('input', updateEstimate);
    document.getElementById('multipleTitles')?.addEventListener('input', updateEstimate);
}

// ============================================================================
// CARREGAMENTO DE DADOS
// ============================================================================

async function loadUserInfo() {
    try {
        const response = await fetch(`${API_BASE}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        document.getElementById('userEmail').textContent = data.email;
    } catch (error) {
        console.error('Erro ao carregar usuário:', error);
    }
}

async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE}/me/agents`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        agents = await response.json();
        
        const select = document.getElementById('agentSelect');
        select.innerHTML = '<option value="">Selecione um agente</option>';
        
        agents.forEach(agent => {
            const option = document.createElement('option');
            option.value = agent.id;
            option.textContent = agent.name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Erro ao carregar agentes:', error);
    }
}

async function loadAvailableVoices() {
    try {
        const response = await fetch(`${API_BASE}/batches/voices`);
        const data = await response.json();
        availableVoices = data.voices_by_language;
        
        renderLanguageList();
    } catch (error) {
        console.error('Erro ao carregar vozes:', error);
    }
}

async function loadBatches() {
    try {
        const response = await fetch(`${API_BASE}/batches/list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        
        renderBatchList(data.batches);
    } catch (error) {
        console.error('Erro ao carregar batches:', error);
        document.getElementById('batchList').innerHTML = 
            '<p class="text-red-500 text-center">Erro ao carregar batches</p>';
    }
}

// ============================================================================
// RENDERIZAÇÃO
// ============================================================================

function renderLanguageList() {
    const container = document.getElementById('languageList');
    container.innerHTML = '';
    
    const languages = Object.keys(availableVoices).sort();
    
    languages.forEach(langCode => {
        const voiceCount = availableVoices[langCode].length;
        
        const div = document.createElement('div');
        div.className = 'flex items-center space-x-2 p-2 hover:bg-gray-50 rounded';
        div.innerHTML = `
            <input type="checkbox" id="lang_${langCode}" value="${langCode}" 
                   class="language-checkbox" onchange="onLanguageToggle('${langCode}')">
            <label for="lang_${langCode}" class="flex-1 cursor-pointer">
                <span class="font-medium">${langCode}</span>
                <span class="text-sm text-gray-500">(${voiceCount} vozes)</span>
            </label>
        `;
        container.appendChild(div);
    });
}

function renderVoiceSelectors() {
    const container = document.getElementById('voiceSelectionContainer');
    container.innerHTML = '';
    
    if (selectedLanguages.size === 0) {
        document.getElementById('selectedLanguagesVoices').classList.add('hidden');
        return;
    }
    
    document.getElementById('selectedLanguagesVoices').classList.remove('hidden');
    
    selectedLanguages.forEach(langCode => {
        const voices = availableVoices[langCode] || [];
        
        const div = document.createElement('div');
        div.className = 'border border-gray-300 rounded-lg p-3';
        div.innerHTML = `
            <label class="block text-sm font-medium text-gray-700 mb-2">
                ${langCode}
            </label>
            <select id="voice_${langCode}" class="w-full border border-gray-300 rounded px-3 py-2">
                ${voices.map(voice => `<option value="${voice}">${voice}</option>`).join('')}
            </select>
        `;
        container.appendChild(div);
    });
    
    updateEstimate();
}

function renderBatchList(batches) {
    const container = document.getElementById('batchList');
    
    if (batches.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-center py-8">Nenhum lote criado ainda</p>';
        return;
    }
    
    container.innerHTML = batches.map(batch => `
        <div class="border border-gray-300 rounded-lg p-4 mb-3 hover:shadow-md transition">
            <div class="flex justify-between items-start mb-2">
                <div>
                    <h3 class="font-bold text-lg">${batch.batch_id.substring(0, 8)}...</h3>
                    <p class="text-sm text-gray-600">Modo: ${batch.mode}</p>
                </div>
                <span class="px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(batch.status)}">
                    ${batch.status}
                </span>
            </div>
            
            <div class="mb-3">
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div class="bg-blue-600 h-2 rounded-full" style="width: ${batch.progress_percentage}%"></div>
                </div>
                <p class="text-sm text-gray-600 mt-1">
                    ${batch.completed_jobs}/${batch.total_jobs} jobs completados 
                    ${batch.failed_jobs > 0 ? `(${batch.failed_jobs} falharam)` : ''}
                </p>
            </div>
            
            <div class="flex space-x-2">
                <button onclick="viewBatchDetails('${batch.batch_id}')" 
                        class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 text-sm">
                    Ver Detalhes
                </button>
                ${batch.status === 'completed' ? `
                    <button onclick="downloadBatchResults('${batch.batch_id}')" 
                            class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 text-sm">
                        Download Resultados
                    </button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function getStatusColor(status) {
    const colors = {
        'pending': 'bg-yellow-100 text-yellow-800',
        'processing': 'bg-blue-100 text-blue-800',
        'completed': 'bg-green-100 text-green-800',
        'failed': 'bg-red-100 text-red-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
}

// ============================================================================
// EVENTOS
// ============================================================================

function onModeChange(event) {
    const mode = event.target.value;
    
    const titleInput = document.getElementById('titleInput');
    const titlesInput = document.getElementById('titlesInput');
    
    if (mode === 'expand_languages') {
        titleInput.classList.remove('hidden');
        titlesInput.classList.add('hidden');
    } else if (mode === 'expand_titles') {
        titleInput.classList.add('hidden');
        titlesInput.classList.remove('hidden');
    } else if (mode === 'matrix') {
        titleInput.classList.add('hidden');
        titlesInput.classList.remove('hidden');
    }
    
    updateEstimate();
}

function onLanguageToggle(langCode) {
    const checkbox = document.getElementById(`lang_${langCode}`);
    
    if (checkbox.checked) {
        selectedLanguages.add(langCode);
    } else {
        selectedLanguages.delete(langCode);
    }
    
    document.getElementById('languageCount').textContent = selectedLanguages.size;
    renderVoiceSelectors();
}

function selectAllLanguages() {
    document.querySelectorAll('.language-checkbox').forEach(checkbox => {
        checkbox.checked = true;
        selectedLanguages.add(checkbox.value);
    });
    document.getElementById('languageCount').textContent = selectedLanguages.size;
    renderVoiceSelectors();
}

function clearAllLanguages() {
    document.querySelectorAll('.language-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    selectedLanguages.clear();
    document.getElementById('languageCount').textContent = 0;
    renderVoiceSelectors();
}

function filterLanguages() {
    const search = document.getElementById('languageSearch').value.toLowerCase();
    const checkboxes = document.querySelectorAll('.language-checkbox');
    
    checkboxes.forEach(checkbox => {
        const parent = checkbox.closest('div');
        const langCode = checkbox.value.toLowerCase();
        
        if (langCode.includes(search)) {
            parent.style.display = 'flex';
        } else {
            parent.style.display = 'none';
        }
    });
}

function updateTitleCount() {
    const text = document.getElementById('multipleTitles').value;
    const lines = text.split('\n').filter(line => line.trim().length >= 3);
    document.getElementById('titleCount').textContent = lines.length;
    updateEstimate();
}

function updateEstimate() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    
    let numTitles = 0;
    let numLanguages = selectedLanguages.size;
    
    if (mode === 'expand_languages') {
        const title = document.getElementById('singleTitle').value;
        numTitles = title.trim().length >= 3 ? 1 : 0;
    } else {
        const text = document.getElementById('multipleTitles').value;
        const lines = text.split('\n').filter(line => line.trim().length >= 3);
        numTitles = lines.length;
    }
    
    const totalJobs = numTitles * numLanguages;
    const estimatedTime = Math.ceil((totalJobs / 10) * 2.25); // 10 workers paralelos, 2.25 min por job
    const estimatedCost = (totalJobs * 0.13).toFixed(2);
    
    document.getElementById('estimatedJobs').textContent = totalJobs;
    document.getElementById('estimatedTime').textContent = estimatedTime;
    document.getElementById('estimatedCost').textContent = `$${estimatedCost}`;
}

// ============================================================================
// AÇÕES
// ============================================================================

async function createBatch() {
    try {
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const agentId = parseInt(document.getElementById('agentSelect').value);
        
        if (!agentId) {
            alert('Por favor, selecione um agente');
            return;
        }
        
        if (selectedLanguages.size === 0) {
            alert('Por favor, selecione pelo menos um idioma');
            return;
        }
        
        // Montar configuração de idiomas + vozes
        const languageVoices = Array.from(selectedLanguages).map(langCode => ({
            code: langCode,
            voice: document.getElementById(`voice_${langCode}`).value
        }));
        
        let requestBody = {
            mode: mode,
            agent_id: agentId,
            num_variations: 1
        };
        
        if (mode === 'expand_languages') {
            const title = document.getElementById('singleTitle').value.trim();
            if (title.length < 3) {
                alert('Título deve ter pelo menos 3 caracteres');
                return;
            }
            requestBody.title = title;
            requestBody.language_voices = languageVoices;
            
        } else if (mode === 'expand_titles') {
            const text = document.getElementById('multipleTitles').value;
            const titles = text.split('\n').filter(line => line.trim().length >= 3);
            
            if (titles.length === 0) {
                alert('Insira pelo menos um título válido');
                return;
            }
            
            requestBody.titles = titles;
            requestBody.language_voice = languageVoices[0]; // Apenas 1 idioma neste modo
            
        } else if (mode === 'matrix') {
            const text = document.getElementById('multipleTitles').value;
            const titles = text.split('\n').filter(line => line.trim().length >= 3);
            
            if (titles.length === 0) {
                alert('Insira pelo menos um título válido');
                return;
            }
            
            requestBody.batch_config = {
                titles: titles,
                language_voices: languageVoices
            };
        }
        
        // Criar batch
        const response = await fetch(`${API_BASE}/batches/create`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao criar batch');
        }
        
        const data = await response.json();
        
        alert(`✅ Batch criado com sucesso!\n\n` +
              `ID: ${data.batch_id}\n` +
              `Jobs: ${data.total_jobs}\n` +
              `Tempo estimado: ${data.estimated_time_minutes} minutos\n` +
              `Custo estimado: $${data.estimated_cost_usd}`);
        
        // Recarregar lista de batches
        await loadBatches();
        
        // Iniciar polling para atualizar status
        startBatchPolling(data.batch_id);
        
    } catch (error) {
        console.error('Erro ao criar batch:', error);
        alert(`❌ Erro ao criar batch: ${error.message}`);
    }
}

async function viewBatchDetails(batchId) {
    try {
        const response = await fetch(`${API_BASE}/batches/${batchId}/status?include_jobs=true`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        const data = await response.json();
        
        // TODO: Criar modal ou página de detalhes
        console.log('Batch details:', data);
        alert(`Batch ${batchId}\n\nStatus: ${data.status}\nProgresso: ${data.progress_percentage.toFixed(1)}%\nJobs: ${data.completed_jobs}/${data.total_jobs}`);
        
    } catch (error) {
        console.error('Erro ao buscar detalhes:', error);
        alert('Erro ao buscar detalhes do batch');
    }
}

async function downloadBatchResults(batchId) {
    try {
        const response = await fetch(`${API_BASE}/batches/${batchId}/results`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        const data = await response.json();
        
        // Criar CSV dos resultados
        const csv = convertToCSV(data.results);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch_${batchId}_results.csv`;
        a.click();
        
    } catch (error) {
        console.error('Erro ao baixar resultados:', error);
        alert('Erro ao baixar resultados');
    }
}

function convertToCSV(results) {
    const headers = ['Job ID', 'Título', 'Idioma', 'Voz', 'Roteiro URL', 'Áudio URL'];
    const rows = results.map(r => [
        r.job_id,
        r.title,
        r.language,
        r.voice,
        r.roteiro_url,
        r.audio_url
    ]);
    
    return [headers, ...rows].map(row => row.join(',')).join('\n');
}

function startBatchPolling(batchId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/batches/${batchId}/status`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(interval);
                await loadBatches(); // Recarregar lista
            }
        } catch (error) {
            console.error('Erro no polling:', error);
        }
    }, 5000); // A cada 5 segundos
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/';
}
