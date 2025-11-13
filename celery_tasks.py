# celery_tasks.py
"""
Tasks do Celery para processamento distribuído de jobs.
"""
import os
import time
import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from celery import Task

from celery_app import celery_app
from database import SessionLocal
import models_batch
import models

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_api_key_round_robin(db, service: str = "gemini") -> Optional[str]:
    """
    Obtém uma API key usando round-robin com circuit breaker.
    
    Args:
        db: Sessão do banco
        service: Serviço ('gemini' ou 'tts')
    
    Returns:
        API key ou None se nenhuma disponível
    """
    now = datetime.utcnow()
    
    # Buscar keys ativas (circuit breaker fechado)
    keys = db.query(models_batch.ApiKeyPool).filter(
        models_batch.ApiKeyPool.service == service,
        models_batch.ApiKeyPool.is_active == 1,
        (models_batch.ApiKeyPool.circuit_open_until == None) | 
        (models_batch.ApiKeyPool.circuit_open_until < now)
    ).order_by(models_batch.ApiKeyPool.last_used_at.asc()).all()
    
    if not keys:
        logger.warning(f"Nenhuma API key disponível para {service}")
        return None
    
    # Selecionar a menos usada recentemente
    selected_key = keys[0]
    
    # Atualizar estatísticas
    selected_key.last_used_at = now
    selected_key.total_requests += 1
    db.commit()
    
    return selected_key.api_key


def emit_log(db, job_id: str, message: str, level: str = "info"):
    """
    Emite um log para o job.
    Atualiza o campo de logs no banco (se existir) ou loga no console.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level.upper()}] {message}"
    logger.info(f"[JOB {job_id}] {message}")
    
    # TODO: Adicionar campo de logs no modelo BatchJob se necessário
    # job = db.query(models_batch.BatchJob).filter(models_batch.BatchJob.id == job_id).first()
    # if job:
    #     if not job.logs:
    #         job.logs = []
    #     job.logs.append(log_entry)
    #     db.commit()


async def generate_roteiro_gemini(title: str, agent_prompts: Dict[str, str], api_key: str) -> str:
    """
    Gera roteiro usando API Gemini.
    
    Args:
        title: Título do roteiro
        agent_prompts: Dicionário com prompts do agente
        api_key: API key do Gemini
    
    Returns:
        Texto do roteiro gerado
    """
    # Simulação (em produção, usar a API real)
    logger.info(f"Gerando roteiro para: {title}")
    await asyncio.sleep(2)  # Simula tempo de API
    
    # TODO: Implementar chamada real à API Gemini
    # import google.generativeai as genai
    # genai.configure(api_key=api_key)
    # model = genai.GenerativeModel('gemini-2.0-pro')
    # response = model.generate_content(f"{agent_prompts['premise']}\n\nTítulo: {title}")
    # return response.text
    
    return f"Roteiro gerado para: {title}\n\nConteúdo simulado do roteiro..."


async def adapt_roteiro_culturally(roteiro: str, language_code: str, api_key: str) -> str:
    """
    Adapta roteiro culturalmente para um idioma.
    
    Args:
        roteiro: Texto do roteiro original
        language_code: Código do idioma alvo
        api_key: API key do Gemini
    
    Returns:
        Roteiro adaptado
    """
    logger.info(f"Adaptando roteiro para: {language_code}")
    await asyncio.sleep(1)  # Simula tempo de API
    
    # TODO: Implementar adaptação real
    return f"[{language_code}] {roteiro}"


async def generate_tts_audio(text: str, language_code: str, voice_id: str, api_key: str) -> bytes:
    """
    Gera áudio TTS usando Google Cloud TTS.
    
    Args:
        text: Texto para sintetizar
        language_code: Código do idioma
        voice_id: ID da voz
        api_key: API key do TTS
    
    Returns:
        Bytes do arquivo de áudio MP3
    """
    logger.info(f"Gerando TTS: {voice_id}")
    await asyncio.sleep(1.5)  # Simula tempo de API
    
    # TODO: Implementar TTS real
    # from google.cloud import texttospeech
    # client = texttospeech.TextToSpeechClient()
    # synthesis_input = texttospeech.SynthesisInput(text=text)
    # voice = texttospeech.VoiceSelectionParams(
    #     language_code=language_code,
    #     name=voice_id
    # )
    # audio_config = texttospeech.AudioConfig(
    #     audio_encoding=texttospeech.AudioEncoding.MP3
    # )
    # response = client.synthesize_speech(
    #     input=synthesis_input,
    #     voice=voice,
    #     audio_config=audio_config
    # )
    # return response.audio_content
    
    return b"fake_audio_data"


async def upload_to_s3(content: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """
    Faz upload de conteúdo para S3.
    
    Args:
        content: Bytes do conteúdo
        key: Chave (caminho) no S3
        content_type: Tipo MIME do conteúdo
    
    Returns:
        URL pública do arquivo
    """
    logger.info(f"Uploading to S3: {key}")
    await asyncio.sleep(0.5)  # Simula tempo de upload
    
    # TODO: Implementar upload real para S3
    # import boto3
    # s3_client = boto3.client('s3')
    # bucket_name = os.getenv('AWS_S3_BUCKET', 'bolt-ia-prod')
    # s3_client.put_object(
    #     Bucket=bucket_name,
    #     Key=key,
    #     Body=content,
    #     ContentType=content_type
    # )
    # return f"https://{bucket_name}.s3.amazonaws.com/{key}"
    
    return f"https://fake-s3-url.com/{key}"


def check_cache(db, cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Verifica se existe resultado em cache.
    
    Args:
        db: Sessão do banco
        cache_key: Chave do cache
    
    Returns:
        Dicionário com roteiro_url e audio_url ou None
    """
    # Buscar job anterior com mesma cache_key
    cached_job = db.query(models_batch.BatchJob).filter(
        models_batch.BatchJob.cache_key == cache_key,
        models_batch.BatchJob.status == "completed",
        models_batch.BatchJob.roteiro_url != None,
        models_batch.BatchJob.audio_url != None
    ).first()
    
    if cached_job:
        logger.info(f"Cache HIT para key: {cache_key}")
        return {
            "roteiro_url": cached_job.roteiro_url,
            "audio_url": cached_job.audio_url,
            "roteiro_text": cached_job.roteiro_text
        }
    
    logger.info(f"Cache MISS para key: {cache_key}")
    return None


# ============================================================================
# CELERY TASKS
# ============================================================================

class JobTask(Task):
    """Base task com retry automático."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(base=JobTask, bind=True, name='celery_tasks.process_job_task')
def process_job_task(self, job_id: str):
    """
    Processa um job individual.
    
    Fluxo:
    1. Verificar cache
    2. Gerar roteiro (Gemini)
    3. Adaptar culturalmente (Gemini)
    4. Gerar TTS (Google Cloud TTS)
    5. Upload para S3
    6. Atualizar banco
    
    Args:
        job_id: ID do job a processar
    """
    db = SessionLocal()
    start_time = time.time()
    
    try:
        # Buscar job
        job = db.query(models_batch.BatchJob).filter(
            models_batch.BatchJob.id == job_id
        ).first()
        
        if not job:
            logger.error(f"Job {job_id} não encontrado")
            return
        
        # Atualizar status
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.retry_count = self.request.retries
        db.commit()
        
        emit_log(db, job_id, f"Iniciando processamento (tentativa {self.request.retries + 1}/3)")
        
        # Verificar cache
        cached_result = check_cache(db, job.cache_key)
        if cached_result:
            emit_log(db, job_id, "Resultado encontrado em cache!")
            job.roteiro_url = cached_result["roteiro_url"]
            job.audio_url = cached_result["audio_url"]
            job.roteiro_text = cached_result.get("roteiro_text")
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.processing_time_seconds = int(time.time() - start_time)
            db.commit()
            return
        
        # Buscar agente
        agent = db.query(models.Agent).filter(
            models.Agent.id == job.agent_id
        ).first()
        
        if not agent:
            raise Exception(f"Agente {job.agent_id} não encontrado")
        
        # Obter API keys
        gemini_key = get_api_key_round_robin(db, "gemini")
        tts_key = get_api_key_round_robin(db, "tts")
        
        if not gemini_key or not tts_key:
            raise Exception("API keys não disponíveis")
        
        # Executar pipeline assíncrono
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            process_job_pipeline(
                db=db,
                job=job,
                agent=agent,
                gemini_key=gemini_key,
                tts_key=tts_key
            )
        )
        
        # Atualizar job com resultados
        job.roteiro_text = result["roteiro_text"]
        job.roteiro_url = result["roteiro_url"]
        job.audio_url = result["audio_url"]
        job.roteiro_char_count = len(result["roteiro_text"])
        job.audio_duration_seconds = result.get("audio_duration", 0)
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.processing_time_seconds = int(time.time() - start_time)
        db.commit()
        
        emit_log(db, job_id, f"✅ Concluído em {job.processing_time_seconds}s")
        
        # Atualizar estatísticas do batch
        update_batch_stats(db, job.batch_id)
        
    except Exception as e:
        logger.error(f"Erro ao processar job {job_id}: {str(e)}")
        
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            job.processing_time_seconds = int(time.time() - start_time)
            db.commit()
            
            emit_log(db, job_id, f"❌ Erro: {str(e)}", level="error")
            
            # Atualizar estatísticas do batch
            update_batch_stats(db, job.batch_id)
        
        # Re-raise para o Celery fazer retry
        raise
        
    finally:
        db.close()


async def process_job_pipeline(db, job, agent, gemini_key: str, tts_key: str) -> Dict[str, Any]:
    """
    Pipeline de processamento do job com paralelização.
    
    Args:
        db: Sessão do banco
        job: Objeto BatchJob
        agent: Objeto Agent
        gemini_key: API key do Gemini
        tts_key: API key do TTS
    
    Returns:
        Dicionário com resultados
    """
    emit_log(db, job.id, "Fase 1: Gerando roteiro master...")
    
    # Gerar roteiro master
    agent_prompts = {
        "premise": agent.premise_prompt or "",
        "block_structure": agent.block_structure_prompt or ""
    }
    
    roteiro_master = await generate_roteiro_gemini(
        title=job.title,
        agent_prompts=agent_prompts,
        api_key=gemini_key
    )
    
    emit_log(db, job.id, f"Fase 2: Adaptando para {job.language_code}...")
    
    # Adaptar culturalmente
    roteiro_adaptado = await adapt_roteiro_culturally(
        roteiro=roteiro_master,
        language_code=job.language_code,
        api_key=gemini_key
    )
    
    emit_log(db, job.id, f"Fase 3: Sintetizando voz {job.voice_id}...")
    
    # Gerar TTS
    audio_data = await generate_tts_audio(
        text=roteiro_adaptado,
        language_code=job.language_code,
        voice_id=job.voice_id,
        api_key=tts_key
    )
    
    emit_log(db, job.id, "Fase 4: Fazendo upload para S3...")
    
    # Upload para S3 (paralelo)
    roteiro_key = f"batches/{job.batch_id}/{job.id}/roteiro.txt"
    audio_key = f"batches/{job.batch_id}/{job.id}/audio.mp3"
    
    roteiro_url, audio_url = await asyncio.gather(
        upload_to_s3(roteiro_adaptado.encode('utf-8'), roteiro_key, "text/plain"),
        upload_to_s3(audio_data, audio_key, "audio/mpeg")
    )
    
    return {
        "roteiro_text": roteiro_adaptado,
        "roteiro_url": roteiro_url,
        "audio_url": audio_url,
        "audio_duration": 120  # TODO: Calcular duração real
    }


def update_batch_stats(db, batch_id: str):
    """
    Atualiza estatísticas do batch.
    
    Args:
        db: Sessão do banco
        batch_id: ID do batch
    """
    from sqlalchemy import func
    
    batch = db.query(models_batch.Batch).filter(
        models_batch.Batch.id == batch_id
    ).first()
    
    if not batch:
        return
    
    # Contar jobs por status
    stats = db.query(
        models_batch.BatchJob.status,
        func.count(models_batch.BatchJob.id)
    ).filter(
        models_batch.BatchJob.batch_id == batch_id
    ).group_by(models_batch.BatchJob.status).all()
    
    status_counts = {status: count for status, count in stats}
    
    batch.completed_jobs = status_counts.get("completed", 0)
    batch.failed_jobs = status_counts.get("failed", 0)
    batch.running_jobs = status_counts.get("running", 0)
    batch.progress_percentage = (batch.completed_jobs / batch.total_jobs * 100) if batch.total_jobs > 0 else 0
    
    # Atualizar status do batch
    if batch.completed_jobs + batch.failed_jobs == batch.total_jobs:
        batch.status = "completed" if batch.failed_jobs == 0 else "failed"
        if not batch.completed_at:
            batch.completed_at = datetime.utcnow()
    elif batch.running_jobs > 0:
        batch.status = "processing"
        if not batch.started_at:
            batch.started_at = datetime.utcnow()
    
    db.commit()
    logger.info(f"[BATCH {batch_id}] Stats: {batch.completed_jobs}/{batch.total_jobs} completed, {batch.failed_jobs} failed")
