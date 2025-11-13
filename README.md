# 🎬 BOLT IA - Gerador de VSL com IA

Sistema de geração automática de **Video Sales Letter (VSL)** usando IA generativa, com suporte a **múltiplas variações**, adaptação cultural e síntese de voz em vários idiomas.

---

## 🚀 Funcionalidades

### ✨ Core Features
- ✅ Geração de roteiros VSL usando **Google Gemini 2.0**
- ✅ **Múltiplas variações** genuinamente diferentes (1-5 por job)
- ✅ Adaptação cultural multi-idioma (pt-BR, fr-FR, es-ES, en-US, ar-XA)
- ✅ Síntese de voz (TTS) com **Google Cloud Text-to-Speech**
- ✅ 150+ vozes disponíveis
- ✅ Autenticação JWT com Argon2
- ✅ 26 endpoints REST API

### 🎯 Feature: Múltiplas Variações
Gere múltiplas versões do mesmo roteiro com ângulos completamente diferentes:
- **Emocional e psicológico:** Foca em sentimentos e conexões
- **Espiritual e filosófico:** Aborda transcendência e significado
- **Prático e acional:** Passos concretos e resultados
- **Histórico e narrativo:** Storytelling e contexto
- **Científico e analítico:** Dados, pesquisas e lógica

---

## 📋 Requisitos

- **Python:** 3.11+
- **PostgreSQL:** 13+ (AWS RDS)
- **APIs:**
  - Google Gemini API Key
  - Google Cloud TTS API Key (opcional, 4M chars/mês grátis)

---

## 🛠️ Instalação Local

```bash
# 1. Clonar repositório
git clone <repo-url>
cd bolt-ia

# 2. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais

# 5. Executar migration
python migrate_add_variacoes.py

# 6. Rodar servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Servidor rodando em:** http://localhost:8000

---

## 🧪 Testes

```bash
# Executar suite completa de testes
python test_variacoes.py

# Executar verificações pré-deploy
python pre_deploy_check.py
```

**Resultado esperado:** 12/12 testes passando ✅

---

## 📦 Deploy em Produção

### Deploy Automático
```bash
python deploy.py
```

### Deploy Manual
```bash
# 1. Verificar ambiente
python pre_deploy_check.py

# 2. Executar migration no banco de produção
python migrate_add_variacoes.py

# 3. Deploy via EB CLI
eb deploy Bolt-env

# 4. Monitorar
eb logs --stream
```

**Documentação completa:** Ver [`GUIA_DEPLOY.md`](GUIA_DEPLOY.md)

---

## 📚 API Endpoints

### Autenticação
```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=senha
```

### Geração de Roteiros (Variação Única)
```http
POST /jobs/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "titulo": "Como Superar a Procrastinação",
  "num_variacoes": 1,
  "modelo_ia": "gemini-2.0-pro",
  "agente_config": {
    "idioma": "pt-BR",
    "idiomas_alvo": ["fr-FR", "es-ES"],
    "premise_prompt": "...",
    "persona_and_global_rules_prompt": "...",
    "block_structure_prompt": "..."
  }
}
```

### Geração de Roteiros (Múltiplas Variações) ⭐ NOVO
```http
POST /jobs/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "titulo": "Como Superar a Procrastinação",
  "num_variacoes": 3,  # 👈 Gera 3 variações diferentes!
  "modelo_ia": "gemini-2.0-pro",
  "agente_config": {...}
}
```

### Buscar Variações ⭐ NOVO
```http
GET /jobs/{job_id}/variacoes
Authorization: Bearer {token}
```

**Resposta:**
```json
{
  "job_id": "abc-123",
  "num_variacoes": 3,
  "roteiros_por_variacao": {
    "variacao_1": {
      "pt-BR": "Roteiro com foco emocional...",
      "fr-FR": "Script avec approche émotionnelle..."
    },
    "variacao_2": {
      "pt-BR": "Roteiro com foco prático...",
      "fr-FR": "Script avec approche pratique..."
    },
    "variacao_3": {
      "pt-BR": "Roteiro com foco científico...",
      "fr-FR": "Script avec approche scientifique..."
    }
  },
  "audios_por_variacao": {
    "variacao_1": {
      "pt-BR": "/static/audio/abc_variacao_1_pt_BR.mp3",
      "fr-FR": "/static/audio/abc_variacao_1_fr_FR.mp3"
    },
    ...
  }
}
```

---

## 🏗️ Arquitetura

```
┌─────────────────┐
│   Frontend      │
│  (Cliente API)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│   FastAPI       │──────▶│  Google Gemini   │
│   Backend       │      │  2.0 API         │
└────────┬────────┘      └──────────────────┘
         │
         ├──────▶ ┌──────────────────┐
         │        │  PostgreSQL      │
         │        │  (AWS RDS)       │
         │        └──────────────────┘
         │
         └──────▶ ┌──────────────────┐
                  │  Google Cloud    │
                  │  TTS API         │
                  └──────────────────┘
```

---

## 📊 Estrutura do Projeto

```
bolt-ia/
├── main.py                          # FastAPI app principal
├── models.py                        # SQLAlchemy models
├── schemas.py                       # Pydantic schemas
├── database.py                      # Conexão PostgreSQL
├── settings.py                      # Configurações
├── migrate_add_variacoes.py         # Migration para variações
├── test_variacoes.py                # Suite de testes
├── pre_deploy_check.py              # Verificações pré-deploy
├── deploy.py                        # Script de deploy automático
├── requirements.txt                 # Dependências Python
│
├── .ebextensions/                   # Configs AWS EB
│   ├── 01_packages.config
│   ├── 02_python.config
│   └── 03_static.config
│
├── static/                          # Arquivos estáticos
│   └── audio/                       # Áudios gerados (TTS)
│
├── cache_jobs/                      # Cache de jobs (JSON)
│
└── docs/                            # Documentação
    ├── GUIA_DEPLOY.md               # Guia de deploy
    ├── SUMARIO_EXECUTIVO.md         # Sumário executivo
    ├── RELATORIO_REVISAO.md         # Relatório de revisão
    ├── FEATURE_MULTIPLAS_VARIACOES.md  # Doc técnica da feature
    └── CODIGO_COMPLETO_VARIACOES.py    # Código de referência
```

---

## 🧩 Modelos de Dados

### Job (Banco de Dados)
```python
{
  "id": "uuid",
  "status": "completed",
  "roteiro_master": "...",
  "num_variacoes": 3,                    # NOVO
  "roteiros_por_variacao": {             # NOVO
    "variacao_1": {"pt-BR": "...", "fr-FR": "..."},
    "variacao_2": {"pt-BR": "...", "fr-FR": "..."},
    "variacao_3": {"pt-BR": "...", "fr-FR": "..."}
  },
  "audios_por_variacao": {               # NOVO
    "variacao_1": {"pt-BR": "/path...", "fr-FR": "/path..."},
    "variacao_2": {...},
    "variacao_3": {...}
  }
}
```

---

## 📈 Performance

| Configuração | Tempo Estimado | Custos API |
|--------------|----------------|------------|
| 1 variação × 3 idiomas | ~3-5 min | $0.001 |
| 3 variações × 3 idiomas | ~10-15 min | $0.005 |
| 5 variações × 3 idiomas | ~20-30 min | $0.01 |

---

## 🔐 Segurança

- ✅ Autenticação JWT (Bearer tokens)
- ✅ Senhas hasheadas com Argon2
- ✅ HTTPS em produção (AWS Certificate Manager)
- ✅ Validação Pydantic em todos os endpoints
- ✅ Rate limiting (via AWS WAF)

---

## 📝 Logs

Logs estruturados com emojis para fácil identificação:

```
[VARIAÇÕES] 🎬 Gerando 3 variações para 'Título'
[VARIAÇÕES] ✅ Variação 1 extraída: 8542 chars
[VARIAÇÕES] ✅ Variação 2 extraída: 7891 chars
[VARIAÇÕES] ✅ Variação 3 extraída: 9103 chars
[VARIAÇÕES] 📊 Estatísticas:
[VARIAÇÕES]    - Variações geradas: 3/3
[VARIAÇÕES]    - Tamanho médio: 8512 chars
[VARIAÇÕES]    - Modelo usado: gemini-2.0-pro
[VARIAÇÕES]    - Temperature: 0.95
```

---

## 🐛 Troubleshooting

### Erro: "Coluna num_variacoes não existe"
**Solução:** Execute a migration
```bash
python migrate_add_variacoes.py
```

### Erro: "Função gerar_variacoes_roteiro não encontrada"
**Solução:** Verifique que main.py está atualizado
```bash
grep -n "async def gerar_variacoes_roteiro" main.py
# Deve retornar: main.py:760
```

### Testes falhando
**Solução:** Execute verificações
```bash
python pre_deploy_check.py
```

---

## 📞 Suporte

- **Documentação Técnica:** Ver pasta `/docs`
- **Testes:** `python test_variacoes.py`
- **Logs em Produção:** `eb logs --stream`

---

## 🎯 Roadmap

### ✅ Concluído
- [x] Geração de roteiros com IA
- [x] Adaptação cultural multi-idioma
- [x] Síntese de voz (TTS)
- [x] Múltiplas variações (Feature Novembro/2025)
- [x] Testes automatizados
- [x] Deploy AWS Elastic Beanstalk

### 🔜 Próximas Features
- [ ] Fila assíncrona (Celery + Redis)
- [ ] Dashboard de analytics
- [ ] A/B testing de variações
- [ ] API de votação (melhor variação)
- [ ] Cache inteligente
- [ ] S3 para armazenamento de áudios

---

## 📜 Licença

Proprietary - Todos os direitos reservados

---

## 👨‍💻 Desenvolvido por

**Bolt IA Team**  
Data: Novembro 2025  
Versão: 4.0 (com Múltiplas Variações)

---

## 🙏 Tecnologias Utilizadas

- **Backend:** FastAPI 0.118.0
- **IA:** Google Gemini 2.0 (Pro & Flash)
- **TTS:** Google Cloud Text-to-Speech
- **Banco:** PostgreSQL 13 (AWS RDS)
- **Deploy:** AWS Elastic Beanstalk
- **Auth:** JWT + Argon2
- **Testes:** Pytest

---

**🚀 Ready to ship! Deploy with confidence!**
#   b o l t - i a - p r o d u c t i o n 
 
 