# Análise do Fluxo de Processamento - Bolt IA

## Fluxo de Geração de Roteiros (Pipeline Completo)

### 1. Entrada do Usuário (Frontend → Backend)
- **Endpoint**: `POST /gerar-roteiro`
- **Dados enviados**:
  - `titulo`: Título do vídeo/roteiro
  - `num_variacoes`: Número de variações (1-5)
  - `modelo_ia`: Modelo Gemini (gemini-2.0-pro, gemini-2.0-flash)
  - `agente_config`: Configuração completa do agente
    - `idioma`: Idioma primário
    - `premise_prompt`: Prompt para premissa
    - `persona_and_global_rules_prompt`: Tom e regras globais
    - `block_structure_prompt`: Estrutura de blocos
    - `idiomas_alvo`: Lista de idiomas para adaptação
    - `cultural_configs`: Configurações por idioma
    - `default_voices`: Vozes TTS por idioma

### 2. Criação do Job
- Gera UUID único para o job
- Cria registro no banco PostgreSQL (tabela `jobs`)
- Status inicial: `queued`
- Adiciona task em background (`BackgroundTasks`)
- Retorna `job_id` imediatamente ao cliente

### 3. Processamento em Background (`run_generation_task`)

#### ESTÁGIO 1: Geração da Premissa
- Usa o `premise_prompt` do agente
- Chama API Gemini com temperatura 0.8
- Gera briefing estratégico detalhado
- Atualiza status: "Estágio 1/3: Gerando Premissa Estratégica..."

#### ESTÁGIO 2: Segmentação de Blocos
- Função: `segmentar_narrativa_em_blocos()`
- **Detecção automática**:
  - Se contém marcadores `# PARTE / # META / # REGRAS` → parsing manual
  - Caso contrário → segmentação automática por heurísticas
- Divide estrutura em blocos numerados
- Cada bloco tem: número, título, conteúdo, tipo (manual/auto)

#### ESTÁGIO 3: Geração Bloco a Bloco
- Itera sobre cada bloco sequencialmente
- Mantém contexto acumulativo (últimos 2000 chars)
- Para cada bloco:
  - Monta prompt específico com contexto
  - Chama API Gemini
  - Acumula resultado no roteiro final
- Resultado: `roteiro_master` completo

### 4. Fluxo de Múltiplas Variações (se `num_variacoes > 1`)

#### ESTÁGIO 2.3: Geração de Variações
- Função: `gerar_variacoes_roteiro()`
- Define aspectos diferentes para cada variação:
  1. Emocional e psicológico
  2. Espiritual e filosófico
  3. Prático e acional
  4. Histórico e narrativo
  5. Científico e analítico
- Gera N roteiros GENUINAMENTE DIFERENTES
- Usa temperatura 0.95 (alta criatividade)
- Parser extrai cada variação por marcadores regex
- Resultado: Dict `{"variacao_1": "roteiro...", "variacao_2": "roteiro..."}`

#### Para cada variação:

##### 4.1. Adaptação Cultural Multi-Idioma
- Para cada idioma em `idiomas_alvo`:
  - Função: `adaptar_culturalmente()`
  - Traduz + adapta culturalmente o roteiro
  - Aplica configurações específicas do idioma
  - Armazena em `roteiros_por_variacao[var_key][idioma]`

##### 4.2. Geração de Áudios (TTS)
- Para cada idioma da variação:
  - Função: `gerar_audio_google_tts()`
  - Divide texto em chunks de 4000 chars
  - Chama Google Cloud Text-to-Speech API
  - Parâmetros: `voice_id`, `speaking_rate`, `pitch`
  - Salva MP3 em `static/audio/{titulo}_{variacao}_{idioma}.mp3`
  - Calcula duração do áudio
  - Armazena caminho em `audios_por_variacao[var_key][idioma]`

#### 4.3. Salvamento Final
- Salva no banco:
  - `num_variacoes`: Quantidade gerada
  - `roteiros_por_variacao`: JSON com todos os roteiros
  - `audios_por_variacao`: JSON com todos os caminhos de áudio
- Status final: `completed`

### 5. Fluxo de Variação Única (se `num_variacoes == 1`)

#### ESTÁGIO 2.5: Adaptação Cultural
- Usa o `roteiro_master` gerado no Estágio 3
- Para cada idioma em `idiomas_alvo`:
  - Adapta culturalmente
  - Salva em `roteiros_adaptados[idioma]`

#### ESTÁGIO 3: TTS Multi-Idioma
- Para cada roteiro adaptado:
  - Gera áudio via Google Cloud TTS
  - Salva em `static/audio/`
  - Calcula duração
  - Acumula chars processados
- Salva no banco:
  - `roteiros_adaptados`: JSON
  - `audios_gerados`: JSON
  - `chars_processados_tts`: Total
  - `duracao_total_segundos`: Soma

### 6. Consulta de Resultados (Frontend)

#### Polling de Status
- **Endpoint**: `GET /status/{job_id}`
- Retorna:
  - `status`: queued, running, completed, failed
  - `log`: Array de mensagens
  - `roteiro_master`, `roteiros_adaptados`, `audios_gerados`

#### Buscar Variações
- **Endpoint**: `GET /jobs/{job_id}/variacoes`
- Retorna estrutura completa:
  - `num_variacoes`
  - `roteiros_por_variacao`
  - `audios_por_variacao`

#### Download de Áudio
- **Endpoint**: `GET /jobs/{job_id}/audio/{language}`
- Retorna arquivo MP3 para download

## Pontos Críticos do Fluxo

### 1. Processamento Síncrono
- Cada job é processado sequencialmente em background
- Múltiplas variações são geradas uma após a outra
- Adaptações culturais são sequenciais
- TTS é gerado um idioma por vez

### 2. Dependências em Cadeia
```
Premissa → Blocos → Roteiro Master → Variações → Adaptações → TTS
```

### 3. Tempo de Processamento Estimado
- 1 variação × 3 idiomas: ~3-5 min
- 3 variações × 3 idiomas: ~10-15 min
- 5 variações × 3 idiomas: ~20-30 min

### 4. Gargalos Identificados
1. **Geração de variações**: Chamada única à API Gemini (não paralelizável)
2. **Adaptação cultural**: Loop sequencial por idioma
3. **TTS**: Loop sequencial por idioma/variação
4. **Armazenamento**: Arquivos salvos localmente em `static/audio/`

## Oportunidades para Processamento em Lote

### Cenário Atual
- 1 job = 1 título = N variações × M idiomas
- Processamento: sequencial dentro do job

### Cenário Desejado (Lote)
- 1 lote = K títulos × N variações × M idiomas
- Processamento: paralelo entre títulos

### Estrutura Necessária
1. **Endpoint de lote**: `POST /jobs/generate-batch`
2. **Modelo de dados**: Tabela `batches` + relação com `jobs`
3. **Orquestração**: Fila de jobs (Celery + Redis)
4. **Paralelização**: Workers processando jobs simultaneamente
5. **Agregação**: Dashboard de progresso do lote
