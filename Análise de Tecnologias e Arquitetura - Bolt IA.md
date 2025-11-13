# Análise de Tecnologias e Arquitetura - Bolt IA

## Stack Tecnológico Completo

### Backend

#### Framework Web
- **FastAPI 0.118.0**: Framework assíncrono moderno para APIs REST
  - Suporte nativo a async/await
  - Validação automática com Pydantic
  - Documentação automática (Swagger/OpenAPI)
  - Performance comparável a Node.js e Go

#### Banco de Dados
- **PostgreSQL 13+**: Banco relacional hospedado em AWS RDS
- **SQLAlchemy 1.4.49**: ORM para Python
  - Pool de conexões configurado (5 conexões base, 10 overflow)
  - Suporte a JSON nativo para campos complexos
- **psycopg2-binary 2.9.7**: Driver PostgreSQL

#### Autenticação e Segurança
- **JWT (JSON Web Tokens)**: Autenticação stateless
- **python-jose 3.5.0**: Biblioteca para JWT
- **Argon2**: Hash de senhas (via passlib)
- **passlib 1.7.4**: Framework de hashing de senhas

#### Inteligência Artificial
- **Google Gemini API**: Modelos de linguagem
  - `gemini-2.0-pro`: Qualidade máxima
  - `gemini-2.0-flash`: Velocidade otimizada
  - `gemini-2.5-flash-tts`: Text-to-Speech (experimental)
- **google-generativeai 0.8.5**: SDK oficial do Gemini
- **google-cloud-texttospeech 2.14.0+**: TTS multi-idioma
  - 150+ vozes disponíveis
  - Suporte a 50+ idiomas
  - Controle de velocidade e pitch

#### Servidor de Aplicação
- **Uvicorn 0.37.0**: Servidor ASGI de alta performance
- **Gunicorn 21.2.0**: Process manager para produção
- **Procfile**: Configuração para AWS Elastic Beanstalk

#### Utilitários
- **pydantic 2.11.9**: Validação de dados e schemas
- **pydantic-settings 2.3.2**: Gerenciamento de configurações
- **python-dotenv 1.1.1**: Variáveis de ambiente
- **requests 2.32.5**: Cliente HTTP
- **mutagen 1.47.0**: Metadados de arquivos de áudio

### Frontend

#### Framework e Bibliotecas
- **HTML5 + JavaScript Vanilla**: Sem frameworks pesados
- **Tailwind CSS (CDN)**: Framework CSS utility-first
- **Font Awesome 6.5.1**: Ícones
- **Google Fonts (Inter)**: Tipografia

#### Bibliotecas JavaScript
- **JSZip 3.10.1**: Compressão de arquivos para download em lote

#### Comunicação
- **Fetch API**: Requisições HTTP assíncronas
- **Polling**: Verificação periódica de status de jobs

### Infraestrutura e Deploy

#### Hospedagem
- **AWS Elastic Beanstalk**: Plataforma gerenciada
  - Ambiente: Python 3.11
  - Load balancing automático
  - Auto-scaling configurável
  - Logs centralizados

#### Banco de Dados
- **AWS RDS PostgreSQL**: Banco gerenciado
  - Backups automáticos
  - Multi-AZ para alta disponibilidade
  - Monitoramento via CloudWatch

#### Armazenamento
- **Sistema de arquivos local**: `static/audio/` para MP3s
  - ⚠️ Não escalável (efêmero em ambientes containerizados)
  - Recomendação: Migrar para S3

#### Segurança
- **HTTPS**: AWS Certificate Manager
- **CORS**: Configurado no FastAPI
- **Rate Limiting**: Via AWS WAF (opcional)

## Arquitetura do Sistema

### Camadas da Aplicação

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (SPA)                       │
│  HTML + JavaScript + Tailwind CSS                       │
│  - Autenticação JWT                                     │
│  - Gerenciamento de Agentes                            │
│  - Criação de Jobs                                      │
│  - Polling de Status                                    │
│  - Download de Resultados                               │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  API Layer (26 endpoints)                        │  │
│  │  - /token (login)                                │  │
│  │  - /register                                     │  │
│  │  - /gerar-roteiro                                │  │
│  │  - /status/{job_id}                              │  │
│  │  - /jobs/{job_id}/variacoes                      │  │
│  │  - /me/agents, /me/apikeys, /me/ttskeys          │  │
│  │  - /tts/voices                                   │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                    │
│  ┌──────────────────▼───────────────────────────────┐  │
│  │  Business Logic Layer                            │  │
│  │  - Autenticação JWT                              │  │
│  │  - Validação Pydantic                            │  │
│  │  - Orquestração de Jobs                          │  │
│  │  - Background Tasks                              │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                    │
│  ┌──────────────────▼───────────────────────────────┐  │
│  │  Data Access Layer (SQLAlchemy)                  │  │
│  │  - CRUD Operations                               │  │
│  │  - Session Management                            │  │
│  │  - Connection Pooling                            │  │
│  └──────────────────┬───────────────────────────────┘  │
└────────────────────┬┴───────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ PostgreSQL   │ │ Google       │ │ Google Cloud │
│ (AWS RDS)    │ │ Gemini API   │ │ TTS API      │
│              │ │              │ │              │
│ - Users      │ │ - Geração de │ │ - Síntese de │
│ - Jobs       │ │   Roteiros   │ │   Voz        │
│ - Agents     │ │ - Adaptação  │ │ - 150+ vozes │
│ - API Keys   │ │   Cultural   │ │              │
│ - TTS Keys   │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Modelo de Dados (PostgreSQL)

#### Tabela: `users`
- `id`: Integer (PK)
- `email`: String (unique, indexed)
- `hashed_password`: String (Argon2)
- `created_at`: DateTime

#### Tabela: `jobs`
- `id`: String/UUID (PK)
- `status`: String (queued, running, completed, failed)
- `titulo`: Text
- `log`: Text (JSON array)
- `resultado`: Text
- `owner_email`: String (FK → users.email)
- `created_at`: DateTime
- **Campos Multi-Idioma:**
  - `roteiro_master`: Text
  - `roteiros_adaptados`: JSON
  - `audios_gerados`: JSON
  - `chars_processados_tts`: Integer
  - `duracao_total_segundos`: Integer
- **Campos Múltiplas Variações:**
  - `num_variacoes`: Integer (default 1)
  - `roteiros_por_variacao`: JSON
  - `audios_por_variacao`: JSON

#### Tabela: `agents`
- `id`: Integer (PK)
- `owner_email`: String (FK)
- `name`: String (indexed)
- `idioma`: String
- `premise_prompt`: Text
- `persona_and_global_rules_prompt`: Text
- `block_structure_prompt`: Text
- `cultural_adaptation_prompt`: Text
- `idiomas_alvo`: JSON (array)
- `cultural_configs`: JSON (dict)
- `default_voices`: JSON (dict)
- `created_at`: DateTime

#### Tabela: `api_keys`
- `id`: Integer (PK)
- `owner_email`: String (FK)
- `key`: String (Gemini API Key)
- `created_at`: DateTime

#### Tabela: `tts_api_keys`
- `id`: Integer (PK)
- `owner_email`: String (FK)
- `key`: String (Google Cloud TTS Key)
- `created_at`: DateTime

### Fluxo de Dados

#### 1. Autenticação
```
User → POST /token → Valida credenciais → Gera JWT → Retorna token
```

#### 2. Criação de Job
```
User → POST /gerar-roteiro + JWT
  ↓
Valida token → Cria registro no DB (status: queued)
  ↓
Adiciona task em BackgroundTasks
  ↓
Retorna job_id imediatamente
  ↓
[Background] run_generation_task executa assincronamente
```

#### 3. Processamento de Job (Background)
```
run_generation_task
  ↓
1. Gera Premissa (Gemini API)
  ↓
2. Segmenta Blocos (heurísticas locais)
  ↓
3. Gera Roteiro Bloco a Bloco (Gemini API)
  ↓
4. [Se num_variacoes > 1]
   ├─ Gera N Variações (Gemini API)
   ├─ Para cada variação:
   │   ├─ Adapta para cada idioma (Gemini API)
   │   └─ Gera TTS para cada idioma (Google Cloud TTS)
   └─ Salva roteiros_por_variacao + audios_por_variacao
  ↓
5. [Se num_variacoes == 1]
   ├─ Adapta roteiro_master para cada idioma (Gemini API)
   ├─ Gera TTS para cada idioma (Google Cloud TTS)
   └─ Salva roteiros_adaptados + audios_gerados
  ↓
6. Atualiza status: completed
```

#### 4. Consulta de Resultados
```
User → GET /status/{job_id} + JWT
  ↓
Valida token + ownership
  ↓
Retorna job completo do DB
```

### Padrões de Design Utilizados

#### 1. Repository Pattern
- Funções CRUD isoladas: `get_user_by_email()`, `create_db_job()`, etc.
- Separação entre lógica de negócio e acesso a dados

#### 2. Dependency Injection
- `Depends(get_db)`: Injeção de sessão do banco
- `Depends(get_current_user)`: Injeção de usuário autenticado

#### 3. Background Tasks
- `BackgroundTasks.add_task()`: Processamento assíncrono
- Evita timeout em requisições HTTP longas

#### 4. Schema Validation
- Pydantic schemas para validação automática
- Separação entre modelos ORM e modelos de API

#### 5. Configuration Management
- `pydantic-settings` para variáveis de ambiente
- Centralização em `settings.py`

## Limitações Atuais da Arquitetura

### 1. Processamento Sequencial
- Jobs são processados um por vez dentro do mesmo processo
- Não há fila de jobs distribuída
- Não há workers paralelos

### 2. Armazenamento Local
- Arquivos MP3 salvos em `static/audio/`
- Não escalável em ambientes multi-instância
- Sem CDN para distribuição

### 3. Ausência de Cache
- Sem cache de roteiros ou áudios
- Regeneração completa a cada job

### 4. Monitoramento Limitado
- Logs básicos via `logging`
- Sem métricas de performance
- Sem alertas automatizados

### 5. Resiliência
- Sem retry automático em falhas de API
- Sem circuit breaker para APIs externas
- Sem fallback para modelos alternativos

## Recomendações de Evolução

### Curto Prazo
1. Migrar armazenamento para AWS S3
2. Implementar cache com Redis
3. Adicionar retry com backoff exponencial

### Médio Prazo
1. Implementar fila de jobs com Celery + Redis
2. Adicionar workers paralelos
3. Implementar monitoramento com Prometheus + Grafana

### Longo Prazo
1. Migrar para arquitetura de microserviços
2. Implementar event sourcing para auditoria
3. Adicionar suporte a streaming de áudios
