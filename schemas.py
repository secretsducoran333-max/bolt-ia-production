from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# =================================================================
# == Modelos de API (Pydantic) - Para validação de requisições   ==
# =================================================================

# --- Modelos para Adaptação Cultural e TTS ---

class CulturalConfig(BaseModel):
    """Configuração de adaptação cultural para um idioma"""
    adaptacao_prompt: Optional[str] = None
    sensibilidade: Optional[str] = None
    formato: Optional[str] = None
    voice_id: str
    speaking_rate: float = 0.95
    pitch: int = 0

# --- Modelos para a Geração de Roteiros ---

class AgenteConfig(BaseModel):
    premise_prompt: str
    idioma: str
    persona_and_global_rules_prompt: str
    block_structure_prompt: str
    
    # Novos campos para adaptação cultural e TTS
    cultural_adaptation_prompt: Optional[str] = None
    idiomas_alvo: List[str] = ["fr-FR"]
    cultural_configs: Dict[str, Any] = {}
    default_voices: Dict[str, Any] = {}

class GenerationRequest(BaseModel):
    modelo_ia: str
    agente_config: AgenteConfig
    titulo: str
    num_variacoes: int = 1  # NOVO: quantas variações gerar (default 1 para retrocompatibilidade)
    
    class Config:
        json_schema_extra = {
            "example": {
                "modelo_ia": "gemini-1.5-pro",
                "titulo": "A Força da Persistência",
                "num_variacoes": 3,
                "agente_config": {
                    "premise_prompt": "Roteiro motivacional...",
                    "idioma": "pt-BR",
                    "persona_and_global_rules_prompt": "Tom inspirador...",
                    "block_structure_prompt": "3 blocos...",
                    "idiomas_alvo": ["pt-BR", "fr-FR", "es-ES"]
                }
            }
        }

# --- Modelos para o Sistema de Jobs ---

class JobResponse(BaseModel):
    id: str
    status: str
    titulo: Optional[str] = None  # NOVO: título do job para interface
    log: List[str] = []
    resultado: Optional[str] = None
    
    # Novos campos para multi-idioma e TTS
    roteiro_master: Optional[str] = None
    roteiros_adaptados: Optional[Dict[str, str]] = None
    audios_gerados: Optional[Dict[str, str]] = None
    chars_processados_tts: int = 0
    duracao_total_segundos: Optional[int] = None

class JobResponseVariacoes(BaseModel):
    """Resposta de job com suporte a múltiplas variações"""
    id: str
    status: str
    titulo: Optional[str] = None  # NOVO: título do job para interface
    num_variacoes: int
    roteiros_por_variacao: Optional[Dict[str, Dict[str, str]]] = None  # {"var_1": {"pt-BR": "...", "fr-FR": "..."}}
    audios_por_variacao: Optional[Dict[str, Dict[str, str]]] = None    # {"var_1": {"pt-BR": "/static/...", "fr-FR": "..."}}
    chars_processados_tts: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123",
                "status": "completed",
                "num_variacoes": 3,
                "roteiros_por_variacao": {
                    "variacao_1": {"pt-BR": "Roteiro 1...", "fr-FR": "Script 1..."},
                    "variacao_2": {"pt-BR": "Roteiro 2...", "fr-FR": "Script 2..."},
                    "variacao_3": {"pt-BR": "Roteiro 3...", "fr-FR": "Script 3..."}
                },
                "audios_por_variacao": {
                    "variacao_1": {"pt-BR": "/static/audio/abc_var1_pt.mp3", "fr-FR": "/static/audio/abc_var1_fr.mp3"}
                }
            }
        }

class JobCreationResponse(BaseModel):
    job_id: str

# --- Modelos para o Sistema de Usuários e Autenticação ---

class UserCreate(BaseModel):
    email: str
    password: str

class UserInDB(BaseModel):
    username: str
    hashed_password: str

# --- Schemas para Agentes ---
class VoiceConfig(BaseModel):
    """Configuração completa de uma voz para TTS"""
    voice_id: str
    speaking_rate: float = 0.95
    pitch: int = 0

class AgentBase(BaseModel):
    name: str
    idioma: str
    premise_prompt: str
    persona_and_global_rules_prompt: str
    block_structure_prompt: str
    
    # Novos campos para adaptação cultural e TTS
    cultural_adaptation_prompt: Optional[str] = None
    idiomas_alvo: List[str] = ["fr-FR"]
    cultural_configs: Dict[str, Any] = {}  # Aceita qualquer estrutura
    default_voices: Dict[str, Any] = {}  # Aceita string (voice_id) ou dict completo (VoiceConfig)

class AgentCreate(AgentBase):
    pass

class AgentOut(AgentBase):
    id: int

# --- Schemas para API Keys ---
class ApiKeyIn(BaseModel):
    key: str

class ApiKeyOut(BaseModel):
    id: int
    key: str