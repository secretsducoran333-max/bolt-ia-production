document.addEventListener('DOMContentLoaded', () => {
    // Base da API: mesma origem do front-end
    const API_BASE = '';
    // === LISTA DE IDIOMAS PARA SUGESTÃO ===
    const AVAILABLE_LANGUAGES = [
        "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani", "Basque", "Belarusian", "Bengali", "Bosnian",
        "Bulgarian", "Catalan", "Cebuano", "Chichewa", "Chinese (Simplified)", "Chinese (Traditional)", "Corsican", "Croatian",
        "Czech", "Danish", "Dutch", "English (US)", "English (UK)", "Esperanto", "Estonian", "Filipino", "Finnish", "French (France)",
        "Frisian", "Galician", "Georgian", "German", "Greek", "Gujarati", "Haitian Creole", "Hausa", "Hawaiian", "Hebrew",
        "Hindi", "Hmong", "Hungarian", "Icelandic", "Igbo", "Indonesian", "Irish", "Italian", "Japanese", "Javanese", "Kannada",
        "Kazakh", "Khmer", "Khmer", "Kinyarwanda", "Korean", "Kurdish (Kurmanji)", "Kyrgyz", "Lao", "Latin", "Latvian", "Lithuanian",
        "Luxembourgish", "Macedonian", "Malagasy", "Malay", "Malayalam", "Maltese", "Maori", "Marathi", "Mongolian", "Myanmar (Burmese)",
        "Nepali", "Norwegian", "Odia (Oriya)", "Pashto", "Persian", "Polish", "Portuguese (Brazil)", "Portuguese (Portugal)",
        "Punjabi", "Romanian", "Russian", "Samoan", "Scots Gaelic", "Serbian", "Sesotho", "Shona", "Sindhi", "Sinhala", "Slovak",
        "Slovenian", "Somali", "Spanish (Spain)", "Sundanese", "Swahili", "Swedish", "Tajik", "Tamil", "Tatar", "Telugu", "Thai",
        "Turkish", "Turkmen", "Ukrainian", "Urdu", "Uyghur", "Uzbek", "Vietnamese", "Welsh", "Xhosa", "Yiddish", "Yoruba", "Zulu"
    ];

    // === SELETORES DE ELEMENTOS ===
    const apiKeysContainer = document.getElementById("apiKeysContainer");
    const addApiKeyBtn = document.getElementById("addApiKeyBtn");
    const ttsKeysContainer = document.getElementById("ttsKeysContainer");
    const addTtsKeyBtn = document.getElementById("addTtsKeyBtn");
    const jobsContainer = document.getElementById("jobsContainer");
    const addJobBtn = document.getElementById("addJobBtn");
    const manageAgentsBtn = document.getElementById("manageAgentsBtn");
    const generateBtn = document.getElementById("generateBtn");
    const statusContainer = document.getElementById("statusContainer");
    const downloadAllBtn = document.getElementById("downloadAllBtn");
    const agentModal = document.getElementById('agentModal');
    const agentModalTitle = document.getElementById('agentModalTitle');
    const agentModalIcon = document.getElementById('agentModalIcon');
    const agentModalTitleText = document.getElementById('agentModalTitleText');
    const agentModeIndicator = document.getElementById('agentModeIndicator');
    const agentModalClose = document.getElementById('agentModalClose');
    const agentEditSelect = document.getElementById('agentEditSelect');
    const createNewAgentBtn = document.getElementById('createNewAgentBtn');
    const agentModalName = document.getElementById('agentModalName');
    const agentModalIdioma = document.getElementById('agentModalIdioma');
    const agentModalPremise = document.getElementById('agentModalPremise');
    const agentModalPersona = document.getElementById('agentModalPersona');
    const agentModalStructure = document.getElementById('agentModalStructure');
    const agentModalCulturalPrompt = document.getElementById('agentModalCulturalPrompt');
    const agentSaveBtn = document.getElementById('agentSaveBtn');
    const agentSaveBtnText = document.getElementById('agentSaveBtnText');
    const agentCancelBtn = document.getElementById('agentCancelBtn');
    const agentDeleteBtnModal = document.getElementById('agentDeleteBtnModal');
    const unsavedChangesWarning = document.getElementById('unsavedChangesWarning');
    const loginScreen = document.getElementById('loginScreen');
    const appContainer = document.getElementById('appContainer');
    const loginForm = document.getElementById('loginForm');
    const logoutBtn = document.getElementById('logoutBtn');

    // === ESTADO DA APLICAÇÃO ===
    let agents = {}; // mapa: nome -> { id?, idioma, premise_prompt, persona_and_global_rules_prompt, block_structure_prompt }
    let generatedScripts = [];
    
    // === ESTADO DO MODAL DE AGENTES ===
    let currentAgentMode = 'edit'; // 'edit' ou 'create'
    let currentEditingAgent = null;
    let originalAgentData = null;
    let hasUnsavedChanges = false;

    // === FUNÇÃO PARA POPULAR A LISTA DE IDIOMAS ===
    function populateLanguageList() {
        const datalist = document.getElementById('languages-list');
        if (!datalist) return;
        AVAILABLE_LANGUAGES.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            datalist.appendChild(option);
        });
    }

    // === LÓGICA DE AGENTES (Persistência + Local cache) ===
    function getAuthToken() { return localStorage.getItem('authToken'); }
    function authHeaders() {
        const t = getAuthToken();
        return t ? { 'Authorization': `Bearer ${t}` } : {};
    }
    async function fetchAgentsFromBackend() {
        try {
            const res = await fetch(`${API_BASE}/me/agents`, { headers: { ...authHeaders() } });
            if (!res.ok) return;
            const list = await res.json();
            console.log('[FETCH] Agentes recebidos do backend:', list);
            const map = {};
            list.forEach(a => {
                console.log(`[FETCH] Processando agente "${a.name}":`, {
                    idiomas_alvo: a.idiomas_alvo,
                    default_voices: a.default_voices
                });
                map[a.name] = { 
                    id: a.id, 
                    idioma: a.idioma, 
                    premise_prompt: a.premise_prompt, 
                    persona_and_global_rules_prompt: a.persona_and_global_rules_prompt, 
                    block_structure_prompt: a.block_structure_prompt,
                    // Novos campos TTS
                    cultural_adaptation_prompt: a.cultural_adaptation_prompt || '',
                    idiomas_alvo: a.idiomas_alvo || [],
                    default_voices: a.default_voices || {},
                    cultural_configs: a.cultural_configs || {}
                };
            });
            agents = map;
            console.log('[FETCH] Mapa de agentes final:', agents);
            saveAgentsToLocalStorage();
            updateAllAgentDropdowns();
        } catch (e) { console.warn('Falha ao carregar agentes', e); }
    }
    async function saveAgentToBackend(name, data, existingId) {
        const ttsData = getTTSDataForSave();
        console.log('[SAVE] TTS Data obtida:', ttsData);
        console.log('[SAVE] Campo Cultural Prompt:', ttsData.cultural_adaptation_prompt);
        
        const payload = { 
            name, 
            idioma: data.idioma, 
            premise_prompt: data.premise_prompt, 
            persona_and_global_rules_prompt: data.persona_and_global_rules_prompt, 
            block_structure_prompt: data.block_structure_prompt,
            // Novos campos TTS Multi-Idioma
            cultural_adaptation_prompt: ttsData.cultural_adaptation_prompt,
            idiomas_alvo: ttsData.idiomas_alvo,
            default_voices: ttsData.default_voices,
            cultural_configs: ttsData.cultural_configs
        };
        
        console.log('[SAVE] Payload completo sendo enviado:', payload);
        const headers = { 'Content-Type': 'application/json', ...authHeaders() };
        if (existingId) {
            const res = await fetch(`${API_BASE}/me/agents/${existingId}`, { method: 'PUT', headers, body: JSON.stringify(payload) });
            if (!res.ok) throw new Error('Erro ao atualizar agente');
            return await res.json();
        } else {
            const res = await fetch(`${API_BASE}/me/agents`, { method: 'POST', headers, body: JSON.stringify(payload) });
            if (!res.ok) throw new Error('Erro ao criar agente');
            return await res.json();
        }
    }
    async function deleteAgentFromBackend(id) {
        const res = await fetch(`${API_BASE}/me/agents/${id}`, { method: 'DELETE', headers: { ...authHeaders() } });
        if (!res.ok && res.status !== 204) throw new Error('Erro ao deletar agente');
    }
    function saveAgentsToLocalStorage() { localStorage.setItem('scriptGeneratorAgents', JSON.stringify(agents)); }
    
    function loadAgentsFromLocalStorage() {
        const savedAgents = localStorage.getItem('scriptGeneratorAgents');
        if (savedAgents && Object.keys(JSON.parse(savedAgents)).length > 0) {
            agents = JSON.parse(savedAgents);
        } else {
            agents = { "Agente - Exemplo": {
                idioma: "Portuguese (Brazil)",
                premise_prompt: `Defina a tarefa da IA para o primeiro estágio. A missão é receber um TÍTULO e gerar uma PREMISSA detalhada que servirá de guia para o roteiro. É útil pedir que a premissa inclua:

O objetivo principal do vídeo.
O público-alvo.
Uma lista dos pontos-chave a serem abordados.`,
                persona_and_global_rules_prompt: `PERSONA:
Descreva a voz e o tom do narrador. Deve ser formal ou informal? Engraçado ou sério? Didático ou inspirador? Diga se deve falar diretamente com o espectador (usando "você").

REGRAS GLOBAIS:
Defina as regras de formatação para todo o roteiro. Exemplo importante: para um texto fluido, instrua a IA a não usar títulos de seção ou marcadores. Outras regras podem incluir o estilo de escrita ou o ritmo do texto.`,
                block_structure_prompt: `Divida seu roteiro em blocos lógicos usando o formato abaixo. Cada "PARTE" será gerada de forma independente. Este é o esqueleto do seu conteúdo.

FORMATO OBRIGATÓRIO PARA CADA BLOCO:

# PARTE 1: [Título da primeira seção, ex: Introdução e Gancho]
# META: [Metas de tamanho, ex: ~500 palavras | 5-7 parágrafos]
# REGRAS: [Instruções para a IA escrever apenas esta parte. Ex: 'Apresente o problema principal e termine com uma pergunta para prender a atenção.']

# PARTE 2: [Título da segunda seção, ex: Desenvolvimento do Ponto 1]
# META: [...]
# REGRAS: [...]`
            } };
            saveAgentsToLocalStorage();
        }
        updateAllAgentDropdowns();
    }
    
    function updateAllAgentDropdowns() {
        const agentNames = Object.keys(agents);
        
        // Atualizar dropdown do modal (apenas se não estiver em modo de criação)
        if (currentAgentMode !== 'create') {
            agentEditSelect.innerHTML = '';
            if (agentNames.length > 0) {
                agentNames.forEach(name => {
                    const option = document.createElement('option');
                    option.value = name;
                    option.textContent = name;
                    agentEditSelect.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = "Nenhum agente criado";
                agentEditSelect.appendChild(option);
            }
        }

        // Atualizar dropdowns da fila de trabalhos
        document.querySelectorAll('.agent-select-job').forEach(select => {
            const currentSelection = select.value;
            select.innerHTML = '';
            if (agentNames.length > 0) {
                agentNames.forEach(name => {
                    const option = document.createElement('option');
                    option.value = name;
                    option.textContent = name;
                    select.appendChild(option);
                });
                if (currentSelection && agents[currentSelection]) {
                    select.value = currentSelection;
                }
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = "Nenhum agente disponível";
                select.appendChild(option);
            }
        });
    }

    // === LÓGICA DO MODAL DE AGENTES ===
    
    // Função para detectar se há mudanças não salvas
    function detectUnsavedChanges() {
        if (!originalAgentData) return false;
        
        const currentData = {
            name: agentModalName.value.trim(),
            idioma: agentModalIdioma.value.trim(),
            premise_prompt: agentModalPremise.value.trim(),
            persona_and_global_rules_prompt: agentModalPersona.value.trim(),
            block_structure_prompt: agentModalStructure.value.trim()
        };
        
        return JSON.stringify(currentData) !== JSON.stringify(originalAgentData);
    }
    
    // Função para mostrar/esconder aviso de mudanças não salvas
    function updateUnsavedChangesWarning() {
        hasUnsavedChanges = detectUnsavedChanges();
        if (hasUnsavedChanges) {
            unsavedChangesWarning.classList.remove('hidden');
        } else {
            unsavedChangesWarning.classList.add('hidden');
        }
    }
    
    // Função para atualizar a interface visual do modal
    function updateModalInterface() {
        if (currentAgentMode === 'create') {
            agentModalIcon.className = 'fas fa-plus-circle text-green-400';
            agentModalTitleText.textContent = 'Criar Novo Agente';
            agentModeIndicator.className = 'px-2 py-1 rounded-full text-xs font-medium bg-green-900 text-green-200';
            agentModeIndicator.textContent = 'CRIANDO';
            agentSaveBtnText.textContent = 'Criar Agente';
            agentDeleteBtnModal.classList.add('hidden');
        } else {
            agentModalIcon.className = 'fas fa-edit text-blue-400';
            agentModalTitleText.textContent = 'Editar Agente';
            agentModeIndicator.className = 'px-2 py-1 rounded-full text-xs font-medium bg-blue-900 text-blue-200';
            agentModeIndicator.textContent = 'EDITANDO';
            agentSaveBtnText.textContent = 'Salvar Alterações';
            agentDeleteBtnModal.classList.remove('hidden');
        }
    }
    
    // Função para abrir o modal
    function openModal() {
        updateAllAgentDropdowns();
        
        // Se há agentes, abre em modo de edição do primeiro
        const agentNames = Object.keys(agents);
        if (agentNames.length > 0) {
            setEditMode(agentNames[0]);
        } else {
            setCreateMode();
        }
        
        agentModal.classList.remove('hidden');
        agentModal.classList.add('flex');
    }

    // Função para fechar o modal
    function closeModal() {
        if (hasUnsavedChanges) {
            if (!confirm('Você tem alterações não salvas. Tem certeza que deseja fechar sem salvar?')) {
                return;
            }
        }
        
        agentModal.classList.add('hidden');
        agentModal.classList.remove('flex');
        resetModalState();
    }
    
    // Função para resetar o estado do modal
    function resetModalState() {
        currentAgentMode = 'edit';
        currentEditingAgent = null;
        originalAgentData = null;
        hasUnsavedChanges = false;
        unsavedChangesWarning.classList.add('hidden');
    }
    
    // Função para definir modo de criação
    function setCreateMode() {
        currentAgentMode = 'create';
        currentEditingAgent = null;
        
        // Limpar formulário
        agentModalName.value = '';
        agentModalIdioma.value = 'Portuguese (Brazil)';
        agentModalPremise.value = '';
        agentModalPersona.value = '';
        agentModalStructure.value = '';
        
        // Resetar dados de TTS
        resetTTSData();
        
        // Resetar select para mostrar indicação
        agentEditSelect.innerHTML = '<option value="">-- Criando Novo Agente --</option>';
        agentEditSelect.value = '';
        agentEditSelect.disabled = true;
        
        originalAgentData = {
            name: '',
            idioma: 'Portuguese (Brazil)',
            premise_prompt: '',
            persona_and_global_rules_prompt: '',
            block_structure_prompt: ''
        };
        
        updateModalInterface();
        updateUnsavedChangesWarning();
    }
    
    // Função para definir modo de edição
(Content truncated due to size limit. Use page ranges or line ranges to read remaining content)