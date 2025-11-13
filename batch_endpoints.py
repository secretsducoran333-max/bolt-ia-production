# batch_endpoints.py
"""
Endpoints para processamento em lote.
Separado do main.py para melhor organização.
"""
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Annotated, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func

import models
import models_batch
import schemas_batch
from database import SessionLocal
from fastapi.security import OAuth2PasswordBearer

# OAuth2 scheme local
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Função de autenticação local
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Placeholder para autenticação"""
    return {"username": "admin", "email": "admin@boltia.com"}

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(prefix="/batches", tags=["batches"])

# Dependência para obter sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Carregar catálogo de vozes
try:
    with open('tts_voices_catalog.json', 'r', encoding='utf-8') as f:
        TTS_VOICES_CATALOG = json.load(f)
except FileNotFoundError:
    logger.warning("tts_voices_catalog.json não encontrado, usando catálogo vazio")
    TTS_VOICES_CATALOG = {}

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def validate_voice_for_language(language_code: str, voice_id: str) -> bool:
    """Valida se a voz existe para o idioma especificado."""
    if language_code not in TTS_VOICES_CATALOG:
        return False
    return voice_id in TTS_VOICES_CATALOG[language_code]


def estimate_job_cost(num_jobs: int) -> Dict[str, Any]:
    """
    Estima custo e tempo para processamento de jobs.
    
    Custos estimados:
    - Gemini API: $0.002 por roteiro
    - TTS API: $0.016 por 1000 caracteres (média 8000 chars = $0.128)
    - Total por job: ~$0.13
    
    Tempo estimado:
    - Geração de roteiro: ~60s
    - Adaptação cultural: ~30s
    - TTS: ~45s
    - Total por job: ~135s = 2.25 min
    """
    cost_per_job = 0.13  # USD
    time_per_job = 2.25  # minutos
    
    # Com paralelização (assumindo 10 workers)
    parallel_factor = min(num_jobs, 10)
    estimated_time = (num_jobs / parallel_factor) * time_per_job
    
    return {
        "total_jobs": num_jobs,
        "estimated_cost_usd": round(num_jobs * cost_per_job, 2),
        "estimated_time_minutes": int(estimated_time),
        "cost_per_job": cost_per_job,
        "time_per_job": time_per_job,
        "parallel_workers": parallel_factor
    }


def create_batch_jobs(
    db: Session,
    batch_id: str,
    owner_email: str,
    agent_id: int,
    titles: List[str],
    language_voices: List[schemas_batch.LanguageVoiceConfig],
    num_variations: int = 1
) -> List[models_batch.BatchJob]:
    """
    Cria jobs individuais para um batch.
    
    Args:
        db: Sessão do banco
        batch_id: ID do batch
        owner_email: Email do dono
        agent_id: ID do agente
        titles: Lista de títulos
        language_voices: Lista de configurações idioma+voz
        num_variations: Número de variações por título
    
    Returns:
        Lista de BatchJob criados
    """
    jobs = []
    
    for title in titles:
        for lang_voice in language_voices:
            for variation_num in range(1, num_variations + 1):
                job_id = str(uuid.uuid4())
                
                # Criar cache key
                import hashlib
                cache_data = f"{title}|{agent_id}|{lang_voice.code}|{lang_voice.voice}|{variation_num}"
                cache_key = hashlib.sha256(cache_data.encode()).hexdigest()
                
                job = models_batch.BatchJob(
                    id=job_id,
                    batch_id=batch_id,
                    owner_email=owner_email,
                    agent_id=agent_id,
                    title=title,
                    language_code=lang_voice.code,
                    voice_id=lang_voice.voice,
                    variation_number=variation_num,
                    status="queued",
                    cache_key=cache_key
                )
                
                db.add(job)
                jobs.append(job)
    
    db.commit()
    return jobs


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/create", response_model=schemas_batch.BatchCreationResponse)
async def create_batch(
    request: schemas_batch.BatchCreateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Cria um novo batch de processamento.
    
    Suporta três modos:
    1. expand_languages: 1 título × N idiomas
    2. expand_titles: N títulos × 1 idioma
    3. matrix: N títulos × M idiomas
    """
    try:
        # Validar agente
        agent = db.query(models.Agent).filter(
            models.Agent.id == request.agent_id,
            models.Agent.owner_email == current_user.email
        ).first()
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        
        # Processar conforme o modo
        titles = []
        language_voices = []
        
        if request.mode == "expand_languages":
            if not request.title or not request.language_voices:
                raise HTTPException(status_code=400, detail="Modo expand_languages requer 'title' e 'language_voices'")
            titles = [request.title]
            language_voices = request.language_voices
            
        elif request.mode == "expand_titles":
            if not request.titles or not request.language_voice:
                raise HTTPException(status_code=400, detail="Modo expand_titles requer 'titles' e 'language_voice'")
            titles = request.titles
            language_voices = [request.language_voice]
            
        elif request.mode == "matrix":
            if not request.batch_config:
                raise HTTPException(status_code=400, detail="Modo matrix requer 'batch_config'")
            titles = request.batch_config.get("titles", [])
            language_voices = [
                schemas_batch.LanguageVoiceConfig(**lv)
                for lv in request.batch_config.get("language_voices", [])
            ]
        
        # Validar vozes
        for lv in language_voices:
            if not validate_voice_for_language(lv.code, lv.voice):
                raise HTTPException(
                    status_code=400,
                    detail=f"Voz '{lv.voice}' não disponível para idioma '{lv.code}'"
                )
        
        # Calcular total de jobs
        total_jobs = len(titles) * len(language_voices) * request.num_variations
        
        # Verificar limite de jobs
        if total_jobs > 1000:
            raise HTTPException(
                status_code=400,
                detail=f"Limite excedido: {total_jobs} jobs (máximo 1000)"
            )
        
        # Estimar custo e tempo
        estimate = estimate_job_cost(total_jobs)
        
        # Criar batch
        batch_id = str(uuid.uuid4())
        batch = models_batch.Batch(
            id=batch_id,
            owner_email=current_user.email,
            mode=request.mode,
            status="pending",
            total_jobs=total_jobs,
            estimated_cost_usd=estimate["estimated_cost_usd"],
            metadata_config={
                "titles": titles,
                "language_voices": [lv.dict() for lv in language_voices],
                "agent_id": request.agent_id,
                "num_variations": request.num_variations,
                "priority": request.priority
            }
        )
        
        db.add(batch)
        db.commit()
        db.refresh(batch)
        
        # Criar jobs individuais
        jobs = create_batch_jobs(
            db=db,
            batch_id=batch_id,
            owner_email=current_user.email,
            agent_id=request.agent_id,
            titles=titles,
            language_voices=language_voices,
            num_variations=request.num_variations
        )
        
        logger.info(f"[BATCH {batch_id}] Criado com {len(jobs)} jobs")
        
        # Enfileirar jobs no Celery (será implementado na próxima fase)
        # for job in jobs:
        #     process_job_task.delay(job.id)
        
        return schemas_batch.BatchCreationResponse(
            batch_id=batch_id,
            total_jobs=total_jobs,
            estimated_time_minutes=estimate["estimated_time_minutes"],
            estimated_cost_usd=estimate["estimated_cost_usd"],
            message=f"Batch criado com sucesso! {total_jobs} jobs enfileirados."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar batch: {str(e)}")


@router.get("/{batch_id}/status", response_model=schemas_batch.BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    include_jobs: bool = False
):
    """
    Retorna o status de um batch.
    
    Args:
        batch_id: ID do batch
        include_jobs: Se True, inclui lista de jobs individuais
    """
    batch = db.query(models_batch.Batch).filter(
        models_batch.Batch.id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch não encontrado")
    
    if batch.owner_email != current_user.email:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    # Atualizar estatísticas
    jobs_stats = db.query(
        models_batch.BatchJob.status,
        func.count(models_batch.BatchJob.id)
    ).filter(
        models_batch.BatchJob.batch_id == batch_id
    ).group_by(models_batch.BatchJob.status).all()
    
    stats = {status: count for status, count in jobs_stats}
    
    batch.completed_jobs = stats.get("completed", 0)
    batch.failed_jobs = stats.get("failed", 0)
    batch.running_jobs = stats.get("running", 0)
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
    
    # Buscar jobs se solicitado
    jobs_info = []
    if include_jobs:
        jobs = db.query(models_batch.BatchJob).filter(
            models_batch.BatchJob.batch_id == batch_id
        ).limit(100).all()  # Limitar a 100 para performance
        
        jobs_info = [
            schemas_batch.BatchJobInfo(
                job_id=job.id,
                title=job.title,
                language_code=job.language_code,
                voice_id=job.voice_id,
                status=job.status,
                roteiro_url=job.roteiro_url,
                audio_url=job.audio_url,
                error_message=job.error_message,
                processing_time_seconds=job.processing_time_seconds,
                created_at=job.created_at,
                completed_at=job.completed_at
            )
            for job in jobs
        ]
    
    return schemas_batch.BatchStatusResponse(
        batch_id=batch.id,
        mode=batch.mode,
        status=batch.status,
        total_jobs=batch.total_jobs,
        completed_jobs=batch.completed_jobs,
        failed_jobs=batch.failed_jobs,
        running_jobs=batch.running_jobs,
        progress_percentage=batch.progress_percentage,
        estimated_completion_time=batch.estimated_completion_time,
        created_at=batch.created_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        jobs=jobs_info
    )


@router.get("/{batch_id}/results", response_model=schemas_batch.BatchResultsResponse)
async def get_batch_results(
    batch_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Retorna os resultados completos de um batch.
    Apenas disponível quando o batch está completo.
    """
    batch = db.query(models_batch.Batch).filter(
        models_batch.Batch.id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch não encontrado")
    
    if batch.owner_email != current_user.email:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    if batch.status not in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Batch ainda em processamento")
    
    # Buscar todos os jobs completados
    jobs = db.query(models_batch.BatchJob).filter(
        models_batch.BatchJob.batch_id == batch_id,
        models_batch.BatchJob.status == "completed"
    ).all()
    
    results = [
        {
            "job_id": job.id,
            "title": job.title,
            "language": job.language_code,
            "voice": job.voice_id,
            "roteiro_url": job.roteiro_url,
            "audio_url": job.audio_url,
            "duration_seconds": job.audio_duration_seconds,
            "char_count": job.roteiro_char_count
        }
        for job in jobs
    ]
    
    return schemas_batch.BatchResultsResponse(
        batch_id=batch.id,
        status=batch.status,
        total_jobs=batch.total_jobs,
        completed_jobs=batch.completed_jobs,
        failed_jobs=batch.failed_jobs,
        results=results,
        metadata=batch.metadata_config or {}
    )


@router.get("/list", response_model=schemas_batch.BatchListResponse)
async def list_user_batches(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """
    Lista todos os batches do usuário.
    """
    batches = db.query(models_batch.Batch).filter(
        models_batch.Batch.owner_email == current_user.email
    ).order_by(models_batch.Batch.created_at.desc()).limit(limit).offset(offset).all()
    
    total = db.query(func.count(models_batch.Batch.id)).filter(
        models_batch.Batch.owner_email == current_user.email
    ).scalar()
    
    batches_data = [
        {
            "batch_id": b.id,
            "mode": b.mode,
            "status": b.status,
            "total_jobs": b.total_jobs,
            "completed_jobs": b.completed_jobs,
            "failed_jobs": b.failed_jobs,
            "progress_percentage": b.progress_percentage,
            "created_at": b.created_at.isoformat(),
            "completed_at": b.completed_at.isoformat() if b.completed_at else None
        }
        for b in batches
    ]
    
    return schemas_batch.BatchListResponse(
        total=total,
        batches=batches_data
    )


@router.get("/voices", response_model=schemas_batch.VoicesResponse)
async def list_available_voices():
    """
    Lista todas as vozes disponíveis por idioma.
    """
    total_voices = sum(len(voices) for voices in TTS_VOICES_CATALOG.values())
    
    return schemas_batch.VoicesResponse(
        total_voices=total_voices,
        voices_by_language=TTS_VOICES_CATALOG
    )


@router.get("/languages", response_model=schemas_batch.LanguagesResponse)
async def list_available_languages():
    """
    Lista todos os idiomas suportados.
    """
    languages = [
        {
            "code": lang_code,
            "name": lang_code,  # TODO: Adicionar nomes completos
            "voice_count": len(voices)
        }
        for lang_code, voices in TTS_VOICES_CATALOG.items()
    ]
    
    return schemas_batch.LanguagesResponse(
        total_languages=len(languages),
        languages=languages
    )


@router.post("/estimate", response_model=schemas_batch.EstimateResponse)
async def estimate_batch_cost(
    request: schemas_batch.EstimateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    """
    Estima custo e tempo de um batch antes de criá-lo.
    """
    total_jobs = request.num_titles * request.num_languages * request.num_variations
    estimate = estimate_job_cost(total_jobs)
    
    return schemas_batch.EstimateResponse(
        total_jobs=total_jobs,
        estimated_time_minutes=estimate["estimated_time_minutes"],
        estimated_cost_usd=estimate["estimated_cost_usd"],
        breakdown=estimate
    )
