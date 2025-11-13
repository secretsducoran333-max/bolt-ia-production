'''
# Bolt IA - Sistema de Processamento em Lote (V3)

**Versão**: 3.0 ULTIMATE  
**Data**: 13 de Novembro de 2025

Este documento descreve a implementação completa do sistema de processamento em lote para o Bolt IA, transformando-o em uma plataforma escalável para geração massiva e multilíngue de roteiros e áudios.

---

## 🚀 Visão Geral da Implementação

A implementação seguiu o plano definido no `MEGA-PROMPT-BOLT-IA-V3-ULTIMATE.md`, com as seguintes correções e otimizações:

1.  **Validação de Vozes**: O sistema agora utiliza um catálogo realista de vozes do Google Cloud TTS, obtido através do script `validate_tts_voices.py`. As premissas de 30+ vozes por idioma foram corrigidas para a quantidade real (média de 5-10).
2.  **Arquitetura Distribuída com Celery**: Toda a lógica de processamento de jobs foi migrada para tasks assíncronas do Celery, permitindo o processamento paralelo e distribuído por múltiplos workers.
3.  **Banco de Dados Escalável**: Foram introduzidos novos modelos (`Batch`, `BatchJob`, `ApiKeyPool`) para gerenciar lotes, jobs individuais e um pool de chaves de API com circuit breaker.
4.  **Frontend Avançado**: Uma nova interface (`batch.html`) foi criada para permitir a criação de lotes nos três modos operacionais (Expandir Idiomas, Expandir Títulos, Matriz Completa), com seletores dinâmicos e estimativas em tempo real.
5.  **Otimizações e Confiabilidade**: Foram implementados mecanismos de cache com Redis, rate limiting para proteger as APIs externas e um sistema de circuit breaker para as chaves de API, garantindo maior robustez.

---

## 🛠️ Como Configurar e Executar

Siga os passos abaixo para configurar o ambiente e executar o novo sistema.

### 1. Instalar Dependências

As novas dependências foram adicionadas ao `requirements.txt`. Instale todas com o comando:

```bash
# Certifique-se de que o ambiente virtual está ativado
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

O sistema agora depende de uma instância Redis. Adicione a seguinte variável ao seu ambiente:

```bash
export REDIS_URL="redis://localhost:6379/0"
export REDIS_BACKEND="redis://localhost:6379/1"

# Configure também as variáveis de banco de dados e AWS S3
export DATABASE_URL="postgresql://user:password@host/dbname"
export AWS_ACCESS_KEY_ID="YOUR_KEY"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET"
export AWS_S3_BUCKET="bolt-ia-prod"
```

### 3. Migrar o Banco de Dados

Execute o script de migração para criar as novas tabelas (`batches`, `batch_jobs`, `api_key_pool`, etc.).

```bash
python3.11 migrate_database.py migrate
```

### 4. Popular o Pool de API Keys

Adicione suas chaves de API do Google Gemini e Google Cloud TTS ao pool. Execute o comando abaixo para cada chave que deseja adicionar:

```bash
# Adicionar uma chave Gemini
python3.11 setup_api_keys.py add --email "seu-email@dominio.com" --service "gemini" --key "SUA_API_KEY_GEMINI"

# Adicionar uma chave TTS
python3.11 setup_api_keys.py add --email "seu-email@dominio.com" --service "tts" --key "SUA_API_KEY_TTS"
```

Para listar as chaves existentes, use `python3.11 setup_api_keys.py list`.

### 5. Iniciar os Serviços

Para executar o sistema completo, você precisa de três processos rodando em terminais separados:

**Terminal 1: Servidor Web (FastAPI)**

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

**Terminal 2: Worker do Celery**

```bash
celery -A celery_app.celery_app worker --loglevel=info -c 4
```

**Terminal 3: Monitoramento com Flower (Opcional)**

```bash
celery -A celery_app.celery_app flower --port=5555
```

### 6. Acessar a Nova Interface

Após iniciar os serviços, acesse a nova interface de processamento em lote em:

[http://localhost:8000/batch.html](http://localhost:8000/batch.html)

---

## 📂 Arquivos Implementados

A lista abaixo detalha todos os arquivos novos e modificados nesta implementação:

| Arquivo | Descrição |
| :--- | :--- |
| **`README_LOTE.md`** | **(Novo)** Este documento. |
| **`batch_endpoints.py`** | **(Novo)** Contém todos os endpoints FastAPI para gerenciar lotes. |
| **`celery_app.py`** | **(Novo)** Arquivo de configuração da aplicação Celery. |
| **`celery_tasks.py`** | **(Novo)** Contém a lógica de processamento dos jobs que é executada pelos workers. |
| **`models_batch.py`** | **(Novo)** Define os novos modelos SQLAlchemy (`Batch`, `BatchJob`, `ApiKeyPool`). |
| **`schemas_batch.py`** | **(Novo)** Define os novos schemas Pydantic para validação de dados da API. |
| **`cache_utils.py`** | **(Novo)** Utilitários para cache, rate limiting e circuit breaker com Redis. |
| **`migrate_database.py`** | **(Novo)** Script para criar e gerenciar as tabelas do banco de dados. |
| **`setup_api_keys.py`** | **(Novo)** Ferramenta de linha de comando para gerenciar o pool de API keys. |
| **`validate_tts_voices.py`**| **(Novo)** Script para gerar o catálogo de vozes realistas do Google TTS. |
| **`tts_voices_catalog.json`**| **(Novo)** Catálogo de vozes gerado para ser usado pela aplicação. |
| **`test_batch_system.py`** | **(Novo)** Script de testes automatizados para validar a implementação. |
| **`static/batch.html`** | **(Novo)** A interface de usuário para o sistema de lote. |
| **`static/js/batch.js`** | **(Novo)** A lógica do frontend para a nova interface. |
| **`requirements.txt`** | **(Modificado)** Adicionadas novas dependências (Celery, Redis, Boto3, etc.). |
| **`main.py`** | **(Modificado)** Adicionado o router dos endpoints de lote. |

---

## ✅ Conclusão

A implementação está completa e funcional, seguindo as especificações e incorporando as melhorias necessárias. O sistema agora é uma plataforma robusta e escalável, pronta para processamento massivo de roteiros e áudios.
'''
