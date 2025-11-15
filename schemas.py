# schemas.py - Schemas Pydantic para validação de dados

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from datetime import datetime

# ===== User Schemas =====
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: int
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# ===== API Key Schemas =====
class ApiKeyValidate(BaseModel):
    api_key: str

class ApiKeyAdd(BaseModel):
    api_key: str
    service: str = "Gemini"

class ApiKeyResponse(BaseModel):
    id: int
    service: str
    key_masked: str
    is_valid: bool
    last_validated: Optional[datetime]
    created_at: datetime

# ===== Agent Schemas =====
class AgentCreate(BaseModel):
    name: str
    agent_type: str = "premissa"
    idioma_principal: str
    premise_prompt: str
    script_prompt: str
    block_structure: str
    cultural_adaptation_prompt: Optional[str] = None
    idiomas_adicionais: List[str] = []
    tts_enabled: bool = False
    tts_voices: Dict[str, str] = {}
    visual_media_enabled: bool = False
    visual_media_type: Optional[str] = None
    visual_media_config: Dict = {}

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    premise_prompt: Optional[str] = None
    script_prompt: Optional[str] = None
    block_structure: Optional[str] = None
    cultural_adaptation_prompt: Optional[str] = None
    idiomas_adicionais: Optional[List[str]] = None
    tts_enabled: Optional[bool] = None
    tts_voices: Optional[Dict[str, str]] = None
    visual_media_enabled: Optional[bool] = None
    visual_media_type: Optional[str] = None
    visual_media_config: Optional[Dict] = None

class AgentResponse(BaseModel):
    id: int
    name: str
    agent_type: str
    idioma_principal: str
    premise_prompt: str
    script_prompt: str
    block_structure: str
    cultural_adaptation_prompt: Optional[str]
    idiomas_adicionais: List[str]
    tts_enabled: bool
    tts_voices: Dict[str, str]
    visual_media_enabled: bool
    visual_media_type: Optional[str]
    visual_media_config: Dict
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===== Job Schemas =====
class JobCreate(BaseModel):
    agent_id: int
    titulos: List[str]  # Lista de títulos para gerar

class JobResponse(BaseModel):
    id: str
    status: str
    progress: int
    titulo: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class JobDetailResponse(BaseModel):
    id: str
    status: str
    progress: int
    titulo: Optional[str]
    log: List[str]
    roteiro_master: Optional[str]
    roteiros_adaptados: Optional[Dict[str, str]]
    audios_gerados: Optional[Dict[str, str]]
    imagens_geradas: Optional[List[str]]
    video_gerado: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ===== Stats Schemas =====
class UserStatsResponse(BaseModel):
    scripts_today: int
    scripts_week: int
    scripts_month: int
    scripts_total: int
    tts_today: int
    tts_week: int
    tts_month: int
    tts_total: int
    total_audio_duration: int
    days_active: int
    streak_count: int
    level: int
    xp: int
    
    class Config:
        from_attributes = True

# ===== File Schemas =====
class GeneratedFileResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: Optional[int]
    download_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===== AI Agent Creation Schemas =====
class AIAgentCreateRequest(BaseModel):
    agent_name: str
    # Os arquivos serão enviados via FormData/multipart

class AIAgentPreview(BaseModel):
    agent_name: str
    premise_template: str
    script_template: str
    block_structure: str
    cultural_adaptation_template: str
