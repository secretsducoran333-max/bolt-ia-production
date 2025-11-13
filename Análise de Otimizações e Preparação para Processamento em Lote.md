# Análise de Otimizações e Preparação para Processamento em Lote

## Pontos de Otimização Identificados

### 1. Gargalos de Performance

#### 1.1. Geração de Variações (Crítico)
**Problema**: Geração de múltiplas variações em uma única chamada à API Gemini.

**Impacto**:
- Tempo de resposta aumenta linearmente com número de variações
- Timeout risk para 5+ variações
- Não há paralelização possível dentro do job

**Solução Proposta**:
- Separar geração de cada variação em chamadas independentes
- Permitir processamento paralelo via workers
- Implementar timeout configurável por variação

**Código Atual** (linha 874-882 em main.py):
```python
response = await model.generate_content_async(
    prompt_variacoes,
    generation_config=genai.types.GenerationConfig(
        temperature=temperature,
        max_output_tokens=100000,  # Espaço para múltiplos roteiros
        top_p=0.95,
        top_k=40
    )
)
```

**Código Otimizado**:
```python
# Gerar cada variação independentemente
tasks = []
for aspecto in aspectos_selecionados:
    task = gerar_variacao_individual(titulo, aspecto, agente_config, api_key)
    tasks.append(task)

# Executar em paralelo com asyncio.gather
variacoes = await asyncio.gather(*tasks)
```

#### 1.2. Adaptação Cultural Sequencial (Alto)
**Problema**: Loop sequencial para adaptar cada idioma.

**Impacto**:
- Tempo total = soma de todos os idiomas
- 3 idiomas × 2 min/idioma = 6 minutos desperdiçados

**Solução Proposta**:
```python
# Atual (sequencial)
for idioma in idiomas_alvo:
    roteiro_adaptado = await adaptar_culturalmente(...)
    roteiros_adaptados[idioma] = roteiro_adaptado

# Otimizado (paralelo)
tasks = [
    adaptar_culturalmente(roteiro_master, idioma_master, idioma, ...)
    for idioma in idiomas_alvo
]
roteiros_adaptados = dict(zip(idiomas_alvo, await asyncio.gather(*tasks)))
```

**Ganho Estimado**: 60-70% de redução no tempo de adaptação.

#### 1.3. Geração de TTS Sequencial (Alto)
**Problema**: Áudios gerados um por vez para cada idioma/variação.

**Impacto**:
- 3 variações × 3 idiomas = 9 áudios sequenciais
- Tempo total: ~15-20 minutos

**Solução Proposta**:
```python
# Criar lista de tarefas TTS
tts_tasks = []
for var_key, roteiros_var in roteiros_por_variacao.items():
    for idioma, roteiro in roteiros_var.items():
        task = gerar_audio_google_tts(roteiro, idioma, voice_id, ...)
        tts_tasks.append((var_key, idioma, task))

# Executar em paralelo com limite de concorrência
from asyncio import Semaphore
semaphore = Semaphore(3)  # Máximo 3 TTS simultâneos

async def tts_with_limit(var_key, idioma, task):
    async with semaphore:
        return var_key, idioma, await task

results = await asyncio.gather(*[
    tts_with_limit(var, lang, task) 
    for var, lang, task in tts_tasks
])
```

**Ganho Estimado**: 70-80% de redução no tempo de TTS.

#### 1.4. Armazenamento de Arquivos (Médio)
**Problema**: Arquivos MP3 salvos localmente em `static/audio/`.

**Impactos**:
- Não escalável em multi-instância
- Sem CDN para distribuição
- Backup manual necessário

**Solução Proposta**:
```python
import boto3

s3_client = boto3.client('s3')

def salvar_audio_s3(audio_bytes, bucket, key):
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=audio_bytes,
        ContentType='audio/mpeg',
        ACL='public-read'  # ou usar CloudFront
    )
    return f"https://{bucket}.s3.amazonaws.com/{key}"

# Uso
audio_url = salvar_audio_s3(
    audio_bytes, 
    'bolt-ia-audios', 
    f'jobs/{job_id}/{variacao}_{idioma}.mp3'
)
```

**Benefícios**:
- Escalabilidade infinita
- Integração com CloudFront CDN
- Backup automático
- Versionamento

#### 1.5. Ausência de Cache (Médio)
**Problema**: Sem cache de roteiros ou áudios reutilizáveis.

**Impacto**:
- Regeneração completa a cada job idêntico
- Custos de API duplicados

**Solução Proposta**:
```python
import redis
import hashlib

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_key(titulo, aspecto, idioma):
    data = f"{titulo}|{aspecto}|{idioma}"
    return hashlib.sha256(data.encode()).hexdigest()

async def gerar_variacao_com_cache(titulo, aspecto, idioma, ...):
    key = cache_key(titulo, aspecto, idioma)
    
    # Tentar buscar do cache
    cached = redis_client.get(key)
    if cached:
        logger.info(f"[CACHE HIT] {key}")
        return cached.decode()
    
    # Gerar novo
    roteiro = await gerar_variacao_individual(...)
    
    # Salvar no cache (TTL 7 dias)
    redis_client.setex(key, 604800, roteiro)
    
    return roteiro
```

### 2. Problemas de Escalabilidade

#### 2.1. Background Tasks Limitados
**Problema**: FastAPI `BackgroundTasks` não é distribuído.

**Limitações**:
- Apenas 1 worker por instância
- Sem persistência de fila
- Sem retry automático

**Solução**: Migrar para Celery + Redis.

#### 2.2. Conexões de Banco
**Problema**: Pool de conexões fixo (5 base + 10 overflow).

**Impacto**:
- Limite de 15 jobs simultâneos por instância
- Contenção em alta carga

**Solução**:
```python
# database.py
engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=20,        # Aumentar para 20
    max_overflow=30,     # Aumentar para 30
    pool_recycle=3600    # Reciclar conexões a cada hora
)
```

#### 2.3. Timeout de Requisições
**Problema**: Sem timeout configurado para APIs externas.

**Risco**:
- Hang indefinido em falhas de rede
- Recursos bloqueados

**Solução**:
```python
import httpx

async def chamar_gemini_com_timeout(prompt, timeout=60):
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/...",
            json={"prompt": prompt},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return response.json()
```

### 3. Qualidade de Código

#### 3.1. Função `run_generation_task` Muito Grande
**Problema**: 500+ linhas, múltiplas responsabilidades.

**Impacto**:
- Difícil manutenção
- Difícil testar
- Difícil paralelizar

**Solução**: Refatorar em funções menores.

```python
async def run_generation_task(job_id, request, api_key):
    db = SessionLocal()
    try:
        # 1. Preparação
        config = await preparar_configuracao(job_id, request, api_key, db)
        
        # 2. Geração de roteiro base
        roteiro_master = await gerar_roteiro_master(config)
        await salvar_roteiro_master(job_id, roteiro_master, db)
        
        # 3. Processamento de variações
        if config.num_variacoes > 1:
            await processar_multiplas_variacoes(job_id, config, db)
        else:
            await processar_variacao_unica(job_id, config, db)
        
        # 4. Finalização
        await finalizar_job(job_id, db)
        
    except Exception as e:
        await tratar_erro_job(job_id, e, db)
    finally:
        db.close()
```

#### 3.2. Logging Inconsistente
**Problema**: Mix de `logger.info()`, `logger.warning()`, `logger.error()`.

**Solução**: Padronizar com structured logging.

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "variacao_gerada",
    job_id=job_id,
    variacao=var_key,
    chars=len(roteiro),
    idioma=idioma
)
```

#### 3.3. Tratamento de Erros Genérico
**Problema**: `except Exception as e` captura tudo.

**Solução**: Capturar exceções específicas.

```python
from google.api_core.exceptions import GoogleAPIError
from sqlalchemy.exc import SQLAlchemyError

try:
    response = await model.generate_content_async(...)
except GoogleAPIError as e:
    logger.error("gemini_api_error", error=str(e), job_id=job_id)
    raise
except SQLAlchemyError as e:
    logger.error("database_error", error=str(e), job_id=job_id)
    db.rollback()
    raise
```

## Preparação para Processamento em Lote

### Arquitetura Proposta para Lote

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND                             │
│  POST /batches/generate                                 │
│  {                                                      │
│    "titulos": ["Título 1", "Título 2", ...],           │
│    "num_variacoes": 3,                                  │
│    "agente_config": {...}                               │
│  }                                                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                      │
│  POST /batches/generate                                 │
│    ↓                                                    │
│  1. Cria registro de Batch no DB                        │
│  2. Para cada título:                                   │
│     - Cria Job individual                               │
│     - Enfileira no Celery                               │
│  3. Retorna batch_id                                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  CELERY + REDIS                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Fila: bolt_ia_jobs                              │  │
│  │  - job_1 (Título 1)                              │  │
│  │  - job_2 (Título 2)                              │  │
│  │  - job_3 (Título 3)                              │  │
│  │  ...                                             │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        ▼            ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ Worker 1│  │ Worker 2│  │ Worker 3│  │ Worker 4│
   │         │  │         │  │         │  │         │
   │ Job 1   │  │ Job 2   │  │ Job 3   │  │ Job 4   │
   └─────────┘  └─────────┘  └─────────┘  └─────────┘
        │            │            │            │
        └────────────┴────────────┴────────────┘
                     │
                     ▼
            ┌──────────────────┐
            │   PostgreSQL     │
            │   - Batches      │
            │   - Jobs         │
            │   - Status       │
            └──────────────────┘
```

### Modelo de Dados para Lote

#### Nova Tabela: `batches`
```python
class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(String, primary_key=True)  # UUID
    owner_email = Column(String, index=True)
    status = Column(String, default="queued")  # queued, running, completed, failed
    total_jobs = Column(Integer)
    completed_jobs = Column(Integer, default=0)
    failed_jobs = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    # Configuração do lote
    num_variacoes = Column(Integer)
    idiomas_alvo = Column(JSON)
    agente_config = Column(JSON)
```

#### Relacionamento: `jobs.batch_id`
```python
class Job(Base):
    # ... campos existentes ...
    
    batch_id = Column(String, ForeignKey('batches.id'), nullable=True, index=True)
```

### Endpoint de Lote

```python
@app.post("/batches/generate", response_model=schemas.BatchCreationResponse)
async def gerar_lote_endpoint(
    request: schemas.BatchGenerationRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    api_key: str | None = Header(None, alias="X-API-Key")
):
    """
    Gera múltiplos roteiros em lote.
    
    Request:
    {
        "titulos": ["Título 1", "Título 2", ...],
        "num_variacoes": 3,
        "agente_config": {...}
    }
    
    Response:
    {
        "batch_id": "uuid",
        "total_jobs": 10,
        "job_ids": ["job1", "job2", ...]
    }
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key do Gemini não fornecida")
    
    # 1. Criar batch
    batch_id = str(uuid.uuid4())
    batch = models.Batch(
        id=batch_id,
        owner_email=current_user.email,
        total_jobs=len(request.titulos),
        num_variacoes=request.num_variacoes,
        idiomas_alvo=request.agente_config.idiomas_alvo,
        agente_config=request.agente_config.dict()
    )
    db.add(batch)
    db.commit()
    
    # 2. Criar jobs individuais
    job_ids = []
    for titulo in request.titulos:
        job_id = str(uuid.uuid4())
        job = create_db_job(db, job_id, current_user.email, titulo)
        job.batch_id = batch_id
        db.commit()
        
        # 3. Enfileirar no Celery
        process_job_task.delay(
            job_id=job_id,
            request_dict=request.dict(),
            api_key=api_key
        )
        
        job_ids.append(job_id)
    
    return schemas.BatchCreationResponse(
        batch_id=batch_id,
        total_jobs=len(job_ids),
        job_ids=job_ids
    )
```

### Configuração do Celery

```python
# celery_app.py
from celery import Celery

celery_app = Celery(
    'bolt_ia',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='America/Sao_Paulo',
    enable_utc=True,
    
    # Configurações de workers
    worker_prefetch_multiplier=1,  # 1 task por vez
    worker_max_tasks_per_child=10,  # Restart após 10 tasks
    
    # Configurações de retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Timeout
    task_soft_time_limit=3600,  # 1 hora
    task_time_limit=3900,  # 1h 5min (hard limit)
)

@celery_app.task(bind=True, max_retries=3)
def process_job_task(self, job_id, request_dict, api_key):
    """
    Task Celery para processar um job.
    """
    try:
        # Executar geração
        asyncio.run(run_generation_task(job_id, request_dict, api_key))
        
        # Atualizar contador do batch
        update_batch_progress(job_id)
        
    except Exception as e:
        logger.error(f"Job {job_id} falhou: {e}")
        
        # Retry com backoff exponencial
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

### Comando para Iniciar Workers

```bash
# Iniciar 4 workers paralelos
celery -A celery_app worker --loglevel=info --concurrency=4

# Ou com autoscaling
celery -A celery_app worker --autoscale=10,3
```

### Endpoint de Status do Lote

```python
@app.get("/batches/{batch_id}/status", response_model=schemas.BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Retorna status agregado do lote.
    
    Response:
    {
        "batch_id": "uuid",
        "status": "running",
        "total_jobs": 10,
        "completed_jobs": 7,
        "failed_jobs": 1,
        "running_jobs": 2,
        "progress_percentage": 70.0,
        "jobs": [
            {"job_id": "...", "titulo": "...", "status": "completed"},
            ...
        ]
    }
    """
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch não encontrado")
    
    if batch.owner_email != current_user.email:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    # Buscar jobs do batch
    jobs = db.query(models.Job).filter(models.Job.batch_id == batch_id).all()
    
    # Calcular estatísticas
    completed = sum(1 for j in jobs if j.status == 'completed')
    failed = sum(1 for j in jobs if j.status == 'failed')
    running = sum(1 for j in jobs if j.status == 'running')
    
    progress = (completed / batch.total_jobs * 100) if batch.total_jobs > 0 else 0
    
    return schemas.BatchStatusResponse(
        batch_id=batch_id,
        status=batch.status,
        total_jobs=batch.total_jobs,
        completed_jobs=completed,
        failed_jobs=failed,
        running_jobs=running,
        progress_percentage=progress,
        jobs=[
            {"job_id": j.id, "titulo": j.titulo, "status": j.status}
            for j in jobs
        ]
    )
```

### Estimativa de Ganho de Performance

#### Cenário: 10 títulos × 3 variações × 3 idiomas

**Atual (Sequencial)**:
- 1 título: ~10 min
- 10 títulos: ~100 min (1h 40min)

**Com Lote + 4 Workers**:
- 4 títulos em paralelo
- 10 títulos: ~30 min (70% mais rápido)

**Com Lote + 10 Workers**:
- 10 títulos em paralelo
- 10 títulos: ~12 min (88% mais rápido)

### Custos de Implementação

#### Infraestrutura Adicional
- **Redis**: $10-30/mês (AWS ElastiCache)
- **Workers**: 2-4 instâncias EC2 t3.medium ($30-60/mês cada)

#### Desenvolvimento
- Implementação do Celery: 2-3 dias
- Endpoints de lote: 1-2 dias
- Testes e ajustes: 2-3 dias
- **Total**: 5-8 dias de desenvolvimento

### Checklist de Implementação

#### Fase 1: Otimizações Básicas (1-2 dias)
- [ ] Paralelizar adaptação cultural com `asyncio.gather()`
- [ ] Paralelizar geração de TTS com semáforo
- [ ] Aumentar pool de conexões do banco
- [ ] Adicionar timeouts em chamadas de API

#### Fase 2: Infraestrutura (2-3 dias)
- [ ] Instalar e configurar Redis
- [ ] Configurar Celery
- [ ] Criar modelo `Batch` no banco
- [ ] Adicionar campo `batch_id` em `Job`
- [ ] Executar migrations

#### Fase 3: Endpoints de Lote (2-3 dias)
- [ ] Implementar `POST /batches/generate`
- [ ] Implementar `GET /batches/{batch_id}/status`
- [ ] Implementar `GET /batches/{batch_id}/download-all`
- [ ] Criar schemas Pydantic para lote

#### Fase 4: Workers (1-2 dias)
- [ ] Refatorar `run_generation_task` para Celery
- [ ] Implementar retry com backoff
- [ ] Configurar logging distribuído
- [ ] Testar com 10+ jobs simultâneos

#### Fase 5: Frontend (2-3 dias)
- [ ] Adicionar interface de criação de lote
- [ ] Adicionar dashboard de progresso de lote
- [ ] Adicionar download em massa (ZIP)
- [ ] Adicionar filtros e busca de lotes

#### Fase 6: Monitoramento (1-2 dias)
- [ ] Configurar Flower (UI do Celery)
- [ ] Adicionar métricas de performance
- [ ] Configurar alertas de falha
- [ ] Dashboard de estatísticas

**Total Estimado**: 9-15 dias de desenvolvimento
