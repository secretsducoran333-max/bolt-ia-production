│  │    │                                                   │   │  │
│  │    │     # FASE 2: Gerar Roteiro Master                │   │  │
│  │    │     emit_log("Gerando roteiro...")                │   │  │
│  │    │     api_key = get_next_api_key_round_robin()     │   │  │
│  │    │     roteiro = await gemini_generate(              │   │  │
│  │    │       title=job.title,                           │   │  │
│  │    │       agent=job.agent_id,                        │   │  │
│  │    │       api_key=api_key  # Distribuir 5+ APIs      │   │  │
│  │    │     )                                             │   │  │
│  │    │                                                   │   │  │
│  │    │     # FASE 3: Adaptar Culturalmente              │   │  │
│  │    │     emit_log("Adaptando para {language}...")     │   │  │
│  │    │     roteiro_adaptado = await gemini_adapt(       │   │  │
│  │    │       roteiro,                                   │   │  │
│  │    │       language=job.language,                     │   │  │
│  │    │       api_key=api_key  # Mesma API por eficiência│   │  │
│  │    │     )                                             │   │  │
│  │    │                                                   │   │  │
│  │    │     # FASE 4: Gerar TTS COM VOZ SELECIONADA      │   │  │
│  │    │     emit_log(f"Sintetizando voz {job.voice}...")│   │  │
│  │    │     audio_file = await google_tts(               │   │  │
│  │    │       text=roteiro_adaptado,                     │   │  │
│  │    │       language_code=job.language,                │   │  │
│  │    │       voice_name=job.voice,  # ← CRÍTICO!        │   │  │
│  │    │       audio_encoding="MP3",                       │   │  │
│  │    │       speaking_rate=1.0,                         │   │  │
│  │    │       pitch=0.0                                  │   │  │
│  │    │     )                                             │   │  │
│  │    │                                                   │   │  │
│  │    │     # FASE 5: Upload S3 (Paralelo)               │   │  │
│  │    │     emit_log("Fazendo upload para S3...")        │   │  │
│  │    │     [roteiro_url, audio_url] = await asyncio.gather( │ │
│  │    │       s3_upload(roteiro, f"{batch_id}/{job.id}/roteiro.txt"), │
│  │    │       s3_upload(audio_file, f"{batch_id}/{job.id}/audio.mp3") │
│  │    │     )                                             │   │  │
│  │    │                                                   │   │  │
│  │    │     # FASE 6: Cache + DB                          │   │  │
│  │    │     emit_log("Finalizando...")                    │   │  │
│  │    │     cache.setex(cache_key, 30*24*3600, {        │   │  │
│  │    │       roteiro_url, audio_url                      │   │  │
│  │    │     })                                            │   │  │
│  │    │                                                   │   │  │
│  │    │     job.status = "completed"                     │   │  │
│  │    │     job.roteiro_url = roteiro_url                │   │  │
│  │    │     job.audio_url = audio_url                    │   │  │
│  │    │     job.voice_used = job.voice                   │   │  │
│  │    │     job.completed_at = now()                     │   │  │
│  │    │     db.commit()                                  │   │  │
│  │    │                                                   │   │  │
│  │    │     emit_log("✅ Concluído!")                     │   │  │
│  │    │                                                   │   │  │
│  │    │   except Exception as e:                         │   │  │
│  │    │     job.status = "failed"                        │   │  │
│  │    │     job.error = str(e)                           │   │  │
│  │    │     db.commit()                                  │   │  │
│  │    │     emit_log(f"❌ Erro: {e}")                     │   │  │
│  │    │     raise  # Retry automático (3 tentativas)     │   │  │
│  │    │                                                   │   │  │
│  │    └───────────────────────────────────────────────────┘   │  │
│  │                                                             │  │
│  │ 4. AGREGAÇÃO DO BATCH:                                    │  │
│  │    • GET /batches/{batch_id}/status monitora TODOS os jobs │  │
│  │    • Calcula: completed/total, tempo restante estimado     │  │
│  │    • Emite eventos WebSocket de progresso (1x por segundo) │  │
│  │    • Quando: todos_jobs.status == "completed" →            │  │
│  │      batch.status = "done"                                 │  │
│  │      emit_notification(user, "Lote concluído!")            │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
   ↓ Celery Workers (5-10 instâncias)    ↓ External Services
┌────────────────────────────────────┐ ┌──────────────────────────┐
│  WORKER POOL (ESCALÁVEL)           │ │ Google Gemini 2.0 API    │
│ ┌──────────────────────────────┐   │ │ (múltiplas chaves para    │
│ │ Worker 1-10 (concurrency=2)  │   │ │  distribuição paralela)   │
│ │ Max: 20 jobs simultâneos     │   │ └──────────────────────────┘
│ └──────────────────────────────┘   │
│ Processam de forma distribuída     │ ┌──────────────────────────┐
│ Cada worker = 1 job por vez        │ │ Google Cloud Text-to-    │
│ Retry automático em falha (3x)     │ │ Speech API (Chirp3-HD)   │
└────────────────────────────────────┘ │ (todas as 30 vozes)       │
         ↓ Broker                      └──────────────────────────┘
    ┌─────────────────┐
    │ Redis Queue     │ ┌──────────────────────────┐
    │ (Celery)        │ │ AWS S3 (Storage)         │
    │ Max: 100k jobs  │ │ Bucket: bolt-ia-prod     │
    └─────────────────┘ │ /batch_{id}/{job_id}/    │
         ↓              │ /roteiros/               │
    ┌─────────────────┐ │ /audios/                 │
    │ PostgreSQL      │ └──────────────────────────┘
    │ • batches       │
    │ • jobs          │ ┌──────────────────────────┐
    │ • results       │ │ Redis Cache              │
    │ • users         │ │ roteiros:{hash}          │
    │ • agents        │ │ audios:{hash}            │
    │ • apikeys       │ │ TTL: 30 dias             │
    └─────────────────┘ └──────────────────────────┘
```

---

## 💾 BANCO DE DADOS - SCHEMA FINAL

### Tabela: `batches`
```sql
CREATE TABLE batches (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    mode VARCHAR(20),  -- 'expand_languages', 'expand_titles', 'matrix'
    status VARCHAR(20),  -- 'pending', 'processing', 'completed', 'failed', 'paused'
    total_jobs INT,
    completed_jobs INT DEFAULT 0,
    failed_jobs INT DEFAULT 0,
    paused_jobs INT DEFAULT 0,
    estimated_completion_time TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB,  -- guarda config original {titles, languages, variations}
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Tabela: `jobs` (EXPANDIDA)
```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    batch_id UUID NOT NULL,
    user_id UUID NOT NULL,
    agent_id UUID,
    title VARCHAR(1000),
    language_code VARCHAR(10),  -- 'pt-BR', 'en-US', 'ja-JP', etc
    voice_id VARCHAR(100),  -- 'pt-BR-Chirp3-HD-Charon', etc (CRÍTICO!)
    variation_number INT DEFAULT 1,  -- Para A/B testing
    status VARCHAR(20),  -- 'queued', 'running', 'completed', 'failed', 'retrying'
    roteiro TEXT,  -- conteúdo inline (opcional, usar S3 é melhor)
    roteiro_url VARCHAR(500),  -- S3 URL
    audio_url VARCHAR(500),  -- S3 URL
    error_message TEXT,
    retry_count INT DEFAULT 0,
    processing_time_seconds INT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES batches(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
```

### Tabela: `user_voice_preferences` (OPCIONAL)
```sql
CREATE TABLE user_voice_preferences (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    language_code VARCHAR(10),
    preferred_voice_id VARCHAR(100),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
-- Permite que usuários salvem voz favorita por idioma
```

---

## 📊 ROADMAP FASEADO (DEFINITIVO)

### ⚡ FASE 0 - VALIDAÇÃO (3 dias)
- ✅ Criar modelos Pydantic com ALL campos
- ✅ Implementar `POST /batches/create` básico
- ✅ Testar Celery task com 1 título × 3 idiomas (3 jobs)
- ✅ Validar integração Google Cloud TTS com vozes
- ✅ Testar S3 upload
- ✅ Medir tempo total

**Esperado**: 3 roteiros + 3 áudios em <15 minutos

---

### 🟠 FASE 1 - BACKEND COMPLETO (5 dias)
- ✅ Implementar cache Redis (30 dias TTL)
- ✅ Endpoint `GET /tts/voices` com 2250+ combinações
- ✅ Endpoint `GET /tts/languages` com 75+ idiomas
- ✅ WebSocket para `GET /batches/{batch_id}/status`
- ✅ Endpoint `GET /batches/{batch_id}/results`
- ✅ Endpoint `GET /batches/{batch_id}/download` (ZIP)
- ✅ Round-robin inteligente de APIs (5+ chaves)
- ✅ Retry automático (3 tentativas)
- ✅ Logging estruturado cada etapa
- ✅ Testes: 20 títulos × 5 idiomas = 100 jobs em <35 min

**Esperado**: Backend robusto em produção

---

### 🟡 FASE 2 - FRONTEND (4 dias)
- ✅ Componente "Seletor de Modo"
- ✅ MultiSelect de 75+ idiomas com SearchBox
- ✅ Dropdown de 30 vozes por idioma com previews
- ✅ TextArea de títulos (validação + autocomplete)
- ✅ Dashboard progresso real-time
- ✅ Tabela de resultados (paginada, 25/página)
- ✅ Player de áudio integrado
- ✅ Download ZIP
- ✅ Histórico de batches
- ✅ Responsividade completa

**Esperado**: Interface pronta para usuários

---

### 🟢 FASE 3 - OTIMIZAÇÃO (3 dias)
- ✅ Smart API distribution (rotação automática)
- ✅ Monitoramento com Flower
- ✅ Logs estruturados com ELK
- ✅ Webhooks de conclusão
- ✅ Testes de carga (k6)
- ✅ CDN para áudios
- ✅ Rate limiting por usuário

**Esperado**: 100+ títulos × 20 idiomas em <40 minutos

---

## ✅ CHECKLIST FINAL COMPLETO

### Backend
- [ ] Modelos `Batch` + `Job` com novos campos (voice_id, language_code)
- [ ] Endpoint `POST /batches/create` com validação
- [ ] Endpoint `GET /batches/{batch_id}/status` (WebSocket)
- [ ] Endpoint `GET /batches/{batch_id}/results`
- [ ] Endpoint `GET /batches/{batch_id}/download`
- [ ] Endpoint `GET /tts/voices` (2250+ combinações)
- [ ] Endpoint `GET /tts/languages` (75+ idiomas)
- [ ] Task Celery `process_job_optimized()`
- [ ] Integração Google Cloud TTS com seleção de voz
- [ ] Cache Redis (30 dias)
- [ ] Round-robin de 5+ APIs Gemini
- [ ] Retry automático (3 tentativas)
- [ ] Logging estruturado
- [ ] Tratamento erro robusto
- [ ] Testes com 20 títulos × 5 idiomas

### Frontend
- [ ] Componente seletor de modo
- [ ] MultiSelect de idiomas (75+) com SearchBox
- [ ] Dropdown de vozes por idioma (30+)
- [ ] TextArea de títulos com validação
- [ ] Dashboard progresso real-time
- [ ] Tabela resultados paginada
- [ ] Player de áudio
- [ ] Download ZIP
- [ ] Histórico de batches
- [ ] Responsividade total

### DevOps
- [ ] Celery workers configurados
- [ ] Redis instalado
- [ ] AWS S3 bucket
- [ ] PostgreSQL com novas tabelas
- [ ] Environment variables
- [ ] Flower monitoring
- [ ] ELK stack (opcional)

---

## 🎯 RECOMENDAÇÕES FINAIS

1. **Comece pequenininho**: 3 títulos × 3 idiomas (FASE 0)
2. **Expanda gradualmente**: 20 × 5, depois 50 × 10, depois 100 × 20
3. **Cache é OURO**: Reutilizar roteiros = 10x mais rápido
4. **Monitor desde o começo**: Use Flower para ver tudo
5. **Teste vozes diferentes**: Cada idioma soa diferente com vozes diferentes
6. **Documente tudo**: API docs completa com exemplos

---

**Status**: 🚀 PRONTO PARA IMPLEMENTAÇÃO  
**Versão**: 3.0 ULTIMATE SEM LIMITES  
**Data**: 13 de Novembro de 2025  
**Qualidade**: ⭐⭐⭐⭐⭐ PERFECCIONISTA  
**Idiomas**: 75+  
**Vozes**: 2250+ combinações possíveis  
**Escalabilidade**: INFINITA com Celery + Redis
