# schemas_batch.py
"""
Schemas Pydantic para validação de requisições de batch.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

# ============================================================================
# SCHEMAS DE ENTRADA (Requisições)
# ============================================================================

class LanguageVoiceConfig(BaseModel):
    """Configuração de idioma + voz."""
    code: str = Field(..., description="Código do idioma (ex: pt-BR, en-US)")
    voice: str = Field(..., description="ID da voz (ex: pt-BR-Neural2-A)")
    
    @validator('code')
    def validate_language_code(cls, v):
        if len(v) < 2 or len(v) > 10:
            raise ValueError("Código de idioma inválido")
        return v


class BatchCreateRequest(BaseModel):
    """Requisição para criar um batch."""
    mode: str = Field(..., description="Modo: expand_languages, expand_titles, matrix")
    agent_id: int = Field(..., description="ID do agente a ser usado")
    
    # Modo expand_languages: 1 título × N idiomas
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    language_voices: Optional[List[LanguageVoiceConfig]] = None
    
    # Modo expand_titles: N títulos × 1 idioma
    titles: Optional[List[str]] = None
    language_voice: Optional[LanguageVoiceConfig] = None
    
    # Modo matrix: N títulos × M idiomas
    batch_config: Optional[Dict[str, Any]] = None
    
    # Opcional
    num_variations: int = Field(1, ge=1, le=5, description="Número de variações por roteiro")
    priority: str = Field("normal", description="Prioridade: low, normal, high")
    
    @validator('mode')
    def validate_mode(cls, v):
        if v not in ['expand_languages', 'expand_titles', 'matrix']:
            raise ValueError("Modo inválido. Use: expand_languages, expand_titles ou matrix")
        return v
    
    @validator('titles')
    def validate_titles(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError("Lista de títulos não pode estar vazia")
            if len(v) > 1000:
                raise ValueError("Máximo de 1000 títulos por batch")
            for title in v:
                if len(title) < 3 or len(title) > 500:
                    raise ValueError(f"Título inválido: {title}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "mode": "expand_languages",
                "agent_id": 1,
                "title": "O Segredo da Riqueza",
                "language_voices": [
                    {"code": "pt-BR", "voice": "pt-BR-Neural2-A"},
                    {"code": "en-US", "voice": "en-US-Neural2-C"},
                    {"code": "es-ES", "voice": "es-ES-Neural2-B"}
                ],
                "num_variations": 1,
                "priority": "normal"
            }
        }


# ============================================================================
# SCHEMAS DE SAÍDA (Respostas)
# ============================================================================

class BatchCreationResponse(BaseModel):
    """Resposta da criação de batch."""
    batch_id: str
    total_jobs: int
    estimated_time_minutes: int
    estimated_cost_usd: float
    message: str


class BatchJobInfo(BaseModel):
    """Informações de um job dentro do batch."""
    job_id: str
    title: str
    language_code: str
    voice_id: str
    status: str
    roteiro_url: Optional[str] = None
    audio_url: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_seconds: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class BatchStatusResponse(BaseModel):
    """Status detalhado de um batch."""
    batch_id: str
    mode: str
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    running_jobs: int
    progress_percentage: float
    estimated_completion_time: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    jobs: List[BatchJobInfo] = []


class BatchResultsResponse(BaseModel):
    """Resultados completos de um batch."""
    batch_id: str
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    results: List[Dict[str, Any]]  # Lista de {title, language, roteiro_url, audio_url}
    metadata: Dict[str, Any]


class VoiceInfo(BaseModel):
    """Informações de uma voz TTS."""
    voice_id: str
    language_code: str
    gender: Optional[str] = None
    description: Optional[str] = None


class LanguagesResponse(BaseModel):
    """Lista de idiomas suportados."""
    total_languages: int
    languages: List[Dict[str, Any]]  # [{code, name, voice_count}]


class VoicesResponse(BaseModel):
    """Lista de vozes disponíveis."""
    total_voices: int
    voices_by_language: Dict[str, List[str]]  # {language_code: [voice_ids]}


class BatchListResponse(BaseModel):
    """Lista de batches do usuário."""
    total: int
    batches: List[Dict[str, Any]]


# ============================================================================
# SCHEMAS AUXILIARES
# ============================================================================

class EstimateRequest(BaseModel):
    """Requisição para estimar custo/tempo de um batch."""
    mode: str
    num_titles: int
    num_languages: int
    num_variations: int = 1


class EstimateResponse(BaseModel):
    """Resposta de estimativa."""
    total_jobs: int
    estimated_time_minutes: int
    estimated_cost_usd: float
    breakdown: Dict[str, Any]  # Detalhamento dos custos
