# BoredFy AI - Plataforma de Geração de Roteiros e TTS com IA

![BoredFy AI](https://img.shields.io/badge/BoredFy-AI-6366f1?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)
![Gemini](https://img.shields.io/badge/Gemini-AI-4285F4?style=for-the-badge&logo=google)

## 📋 Descrição

**BoredFy AI** é uma plataforma completa para geração automatizada de roteiros e conversão de texto em áudio (TTS) utilizando inteligência artificial do Google Gemini. A aplicação oferece recursos avançados como:

- ✅ **Geração de roteiros** com IA (Gemini 2.0 Flash)
- ✅ **30 vozes premium** para TTS em múltiplos idiomas
- ✅ **Suporte a 100+ idiomas** com detecção automática
- ✅ **Adaptação cultural** automática de roteiros
- ✅ **Sistema de agentes** personalizáveis
- ✅ **Dashboard de gamificação** (XP, níveis, streaks)
- ✅ **Geração de imagens** com IA (placeholder para Imagen 3)
- ✅ **Fila de jobs** gerenciável com progresso em tempo real
- ✅ **Sistema de arquivos** com deleção manual
- ✅ **Autenticação JWT** segura
- ✅ **API keys criptografadas** no banco de dados

---

## 🚀 Instalação e Configuração

### Pré-requisitos

- Python 3.11+
- pip
- Virtualenv

### Passo 1: Clone o repositório

```bash
git clone https://github.com/secretsducoran333-max/bolt-ia-production.git
cd bolt-ia-production
```

### Passo 2: Crie e ative o ambiente virtual

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### Passo 3: Instale as dependências

```bash
pip install fastapi uvicorn sqlalchemy python-jose python-multipart \
    google-generativeai google-cloud-texttospeech langdetect \
    pydantic pydantic-settings python-dotenv argon2-cffi email-validator
```

### Passo 4: Configure as variáveis de ambiente

Copie o arquivo `.env.example` para `.env` e ajuste as configurações:

```bash
cp .env.example .env
```

Edite o arquivo `.env`:

```env
SECRET_KEY=sua-chave-secreta-super-segura-aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./boredfy_ai.db
```

### Passo 5: Inicie o servidor

```bash
python main.py
```

O servidor estará disponível em: `http://localhost:8000`

---

## 📖 Como Usar

### 1. Acesse a aplicação

Abra o navegador e acesse: `http://localhost:8000`

### 2. Crie uma conta

Na página de login, clique em "Criar conta" e preencha:
- Email
- Senha

### 3. Adicione sua API Key do Gemini

1. Obtenha uma API key gratuita em: https://makersuite.google.com/app/apikey
2. No dashboard, clique em "Configurações" → "API Keys"
3. Cole sua chave e clique em "Adicionar"
4. A chave será validada automaticamente

### 4. Crie um Agente

Um agente define como os roteiros serão gerados:

1. Clique em "Criar Agente"
2. Preencha:
   - **Nome**: Nome do agente
   - **Idioma Principal**: pt-BR, en-US, etc.
   - **Template de Premissa**: Como gerar ideias iniciais
   - **Template de Roteiro**: Regras de formatação e estilo
   - **Estrutura de Blocos**: Organização narrativa
   - **Adaptação Cultural**: Como adaptar para outros idiomas
3. (Opcional) Configure TTS e vozes
4. (Opcional) Ative geração de imagens
5. Salve o agente

### 5. Gere Roteiros

1. Selecione um agente
2. Digite um ou mais títulos/premissas (um por linha)
3. Clique em "Gerar"
4. Acompanhe o progresso na fila de jobs

### 6. Baixe os Arquivos

- Roteiros gerados ficam disponíveis em "Meus Arquivos"
- Áudios (se TTS ativado) também ficam disponíveis
- Arquivos ficam disponíveis por 24 horas

---

## 🎯 Funcionalidades Principais

### Sistema de Agentes

Agentes são templates reutilizáveis que definem:
- Como gerar premissas
- Regras de formatação de roteiros
- Estrutura narrativa
- Adaptação cultural para outros idiomas
- Configurações de TTS (voz por idioma)
- Geração de mídia visual

### Geração de Roteiros

- Usa Gemini 2.0 Flash para geração
- Suporta múltiplos idiomas simultaneamente
- Adaptação cultural automática
- Geração em lote (múltiplos títulos)

### Text-to-Speech (TTS)

- **30 vozes premium** do Google Cloud TTS
- Suporte a idiomas: pt-BR, en-US, es-ES, fr-FR, de-DE, it-IT, ja-JP, ko-KR, zh-CN, ar-XA e mais
- Vozes Neural2 e Wavenet de alta qualidade
- Geração em background com progresso

### Dashboard de Gamificação

- **XP**: Ganhe experiência gerando roteiros e áudios
- **Níveis**: Suba de nível conforme ganha XP
- **Streaks**: Mantenha sequências diárias de uso
- **Estatísticas**: Roteiros hoje/semana/mês, TTS gerados, duração total

### Sistema de Jobs

- Fila gerenciável de jobs
- Progresso em tempo real (0-100%)
- Status: pending, processing, completed, failed, cancelled
- Logs detalhados de cada job
- Cancelamento de jobs em andamento

---

## 🔧 API Endpoints

### Autenticação

- `POST /auth/register` - Registrar novo usuário
- `POST /auth/login` - Login (retorna JWT token)
- `GET /auth/me` - Informações do usuário atual

### API Keys

- `POST /api-keys/validate` - Validar uma API key
- `POST /api-keys/add` - Adicionar API key
- `GET /api-keys` - Listar API keys (mascaradas)
- `DELETE /api-keys/{key_id}` - Remover API key

### Agentes

- `POST /agents` - Criar agente
- `GET /agents` - Listar agentes
- `GET /agents/{agent_id}` - Detalhes de um agente
- `PUT /agents/{agent_id}` - Atualizar agente
- `DELETE /agents/{agent_id}` - Deletar agente

### Vozes

- `GET /voices` - Listar todas as 30 vozes premium
- `GET /voices/{language_code}` - Vozes de um idioma específico

### Jobs

- `POST /jobs/generate` - Criar jobs de geração
- `GET /jobs/queue` - Listar fila de jobs
- `GET /jobs/{job_id}` - Detalhes de um job
- `POST /jobs/{job_id}/cancel` - Cancelar job

### Stats

- `GET /stats/dashboard` - Dashboard de estatísticas e gamificação

### Arquivos

- `GET /files/recent` - Arquivos gerados nas últimas 24h
- `DELETE /files/{file_id}` - Deletar arquivo

### Criação de Agente com IA

- `POST /agents/create-with-ai` - Criar agente analisando roteiros existentes

---

## 🗂️ Estrutura do Projeto

```
boredfy-ai/
├── main.py                 # Backend FastAPI principal
├── models.py               # Modelos do banco de dados (SQLAlchemy)
├── schemas.py              # Schemas Pydantic para validação
├── database.py             # Configuração do banco de dados
├── settings.py             # Configurações da aplicação
├── voices_config.py        # Configuração das 30 vozes premium
├── login.html              # Página de login
├── index.html              # Dashboard principal
├── login_script.js         # JavaScript da página de login
├── script.js               # JavaScript do dashboard
├── test_api.py             # Suite de testes da API
├── .env                    # Variáveis de ambiente
├── .env.example            # Exemplo de variáveis de ambiente
├── requirements.txt        # Dependências Python
└── README.md               # Este arquivo
```

---

## 🧪 Testes

Execute a suite de testes:

```bash
python test_api.py
```

Testes incluídos:
- ✅ Health check
- ✅ Registro de usuário
- ✅ Login e autenticação JWT
- ✅ Validação de API keys
- ✅ Listagem de vozes
- ✅ CRUD de agentes
- ✅ Dashboard de stats
- ✅ Listagem de arquivos

---

## 🔐 Segurança

- **Senhas**: Hash com Argon2 (estado da arte)
- **Autenticação**: JWT com expiração configurável
- **API Keys**: Armazenadas criptografadas no banco
- **CORS**: Configurável para produção
- **Validação**: Pydantic para todos os inputs

---

## 📊 Banco de Dados

O projeto usa **SQLite** por padrão (desenvolvimento). Para produção, recomenda-se PostgreSQL.

### Tabelas:

- `users` - Usuários da plataforma
- `api_keys` - API keys do Gemini (criptografadas)
- `tts_api_keys` - API keys do Google Cloud TTS
- `agents` - Agentes de geração
- `jobs` - Fila de jobs de geração
- `generated_files` - Arquivos gerados (roteiros, áudios, imagens)
- `user_stats` - Estatísticas e gamificação

---

## 🌐 Deploy em Produção

### Recomendações:

1. **Servidor**: Use Gunicorn + Uvicorn workers
2. **Banco de Dados**: PostgreSQL
3. **Reverse Proxy**: Nginx
4. **HTTPS**: Let's Encrypt
5. **Variáveis de Ambiente**: Nunca commite `.env`

### Exemplo com Gunicorn:

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 🎨 Customização

### Adicionar novas vozes:

Edite `voices_config.py` e adicione à lista `PREMIUM_VOICES`:

```python
{
    "voice_id": "pt-BR-Neural2-D",
    "name": "Nova Voz - Português",
    "language_code": "pt-BR",
    "gender": "male",
    "service": "GoogleTTS"
}
```

### Alterar tempo de expiração do token:

Edite `.env`:

```env
ACCESS_TOKEN_EXPIRE_MINUTES=2880  # 48 horas
```

---

## 📝 Changelog

### v2.0.0 (13/11/2025)

- ✅ Sistema de geração de voz com 30 vozes premium
- ✅ Suporte a 100+ idiomas
- ✅ Geração de áudio em segundo plano
- ✅ Geração de imagens com IA (até 20 por roteiro)
- ✅ Upload de imagens de referência
- ✅ Plataforma 30-40% mais rápida
- ✅ Retrys automáticos otimizados
- ✅ Timeouts otimizados
- ✅ Interface simplificada
- ✅ Validação de chaves de API em tempo real
- ✅ Deleção de arquivos pela interface
- ✅ Correção de bugs gerais
- ✅ **SEGURANÇA**: Removidas API keys hardcoded

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto é proprietário. Todos os direitos reservados.

---

## 📧 Suporte

Para dúvidas ou problemas, abra uma issue no GitHub.

---

## 🎉 Agradecimentos

- **Google Gemini** pela API de geração de conteúdo
- **Google Cloud TTS** pelas vozes premium
- **FastAPI** pelo framework incrível
- **Comunidade Python** pelo suporte

---

**Desenvolvido com ❤️ por BoredFy Team**
