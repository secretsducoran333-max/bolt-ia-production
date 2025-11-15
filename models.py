# models.py - Modelos do Banco de Dados para BoredFy AI

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Date, JSON, ForeignKey
from sqlalchemy.sql import func
from database import Base

class User(Base):
    """Modelo de usuário com autenticação"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    """Chaves de API do Gemini por usuário"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_value = Column(String, nullable=False)  # Armazenada de forma segura
    service = Column(String, default="Gemini", nullable=False)
    is_valid = Column(Boolean, default=False)
    last_validated = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TtsApiKey(Base):
    """Chaves de API para TTS (Google Cloud TTS)"""
    __tablename__ = "tts_api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_value = Column(String, nullable=False)
    service = Column(String, default="GoogleTTS", nullable=False)
    is_valid = Column(Boolean, default=False)
    last_validated = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Agent(Base):
    """Agentes de geração de roteiros"""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, index=True, nullable=False)
    agent_type = Column(String, default="premissa")  # "premissa" ou "classic"
    
    # Idioma principal
    idioma_principal = Column(String, nullable=False)
    
    # Prompts do agente
    premise_prompt = Column(Text, nullable=False)
    script_prompt = Column(Text, nullable=False)  # Regras globais
    block_structure = Column(Text, nullable=False)
    cultural_adaptation_prompt = Column(Text, nullable=True)
    
    # Idiomas adicionais
    idiomas_adicionais = Column(JSON, default=list)  # ["en-US", "es-ES"]
    
    # Configuração de TTS
    tts_enabled = Column(Boolean, default=False)
    tts_voices = Column(JSON, default=dict)  # {"pt-BR": "pt-BR-Neural2-A", "en-US": "en-US-Neural2-D"}
    
    # Configuração de Mídia Visual
    visual_media_enabled = Column(Boolean, default=False)
    visual_media_type = Column(String, nullable=True)  # "images" ou "video"
    visual_media_config = Column(JSON, default=dict)  # Configurações específicas
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Job(Base):
    """Jobs de geração de roteiros"""
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    
    status = Column(String, default="pending")  # pending, processing, completed, cancelled, failed
    progress = Column(Integer, default=0)  # 0-100
    
    # Dados do job
    titulo = Column(Text, nullable=True)
    log = Column(Text, default="[]")  # JSON array de mensagens de log
    
    # Resultados
    roteiro_master = Column(Text, nullable=True)
    roteiros_adaptados = Column(JSON, nullable=True)  # {"pt-BR": "...", "en-US": "..."}
    audios_gerados = Column(JSON, nullable=True)  # {"pt-BR": "/files/audio/xxx.mp3"}
    imagens_geradas = Column(JSON, nullable=True)  # ["/files/images/xxx.png", ...]
    video_gerado = Column(String, nullable=True)  # "/files/videos/xxx.mp4"
    
    # Métricas
    chars_processados_tts = Column(Integer, default=0)
    duracao_total_segundos = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserStats(Base):
    """Estatísticas de gamificação do usuário"""
    __tablename__ = "user_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Scripts
    scripts_today = Column(Integer, default=0)
    scripts_week = Column(Integer, default=0)
    scripts_month = Column(Integer, default=0)
    scripts_total = Column(Integer, default=0)
    
    # TTS
    tts_today = Column(Integer, default=0)
    tts_week = Column(Integer, default=0)
    tts_month = Column(Integer, default=0)
    tts_total = Column(Integer, default=0)
    
    # Métricas
    total_audio_duration = Column(Integer, default=0)  # segundos
    days_active = Column(Integer, default=0)
    
    # Gamificação
    streak_count = Column(Integer, default=0)
    last_active_date = Column(Date, nullable=True)
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VisualMedia(Base):
    """Mídia visual gerada (imagens/vídeos)"""
    __tablename__ = "visual_media"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    media_type = Column(String, nullable=False)  # "image" ou "video"
    url = Column(String, nullable=False)
    prompt_used = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GeneratedFile(Base):
    """Arquivos gerados (roteiros, áudios, imagens, vídeos)"""
    __tablename__ = "generated_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True)
    
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "script", "audio", "image", "video"
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)  # bytes
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
