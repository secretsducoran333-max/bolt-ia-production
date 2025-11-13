# models_batch.py
"""
Modelos de dados para processamento em lote.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func, JSON, ForeignKey, Float
from database import Base

class Batch(Base):
    """
    Representa um lote de processamento contendo múltiplos jobs.
    """
    __tablename__ = "batches"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    owner_email = Column(String, index=True, nullable=False)
    
    # Modo operacional
    mode = Column(String(20), nullable=False)  # 'expand_languages', 'expand_titles', 'matrix'
    
    # Status
    status = Column(String(20), default="pending", index=True)  # pending, processing, completed, failed, paused
    
    # Estatísticas
    total_jobs = Column(Integer, default=0)
    completed_jobs = Column(Integer, default=0)
    failed_jobs = Column(Integer, default=0)
    running_jobs = Column(Integer, default=0)
    
    # Progresso
    progress_percentage = Column(Float, default=0.0)
    estimated_completion_time = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadados (guarda configuração original)
    metadata_config = Column(JSON, nullable=True)  # {titles, languages, agent_id, num_variations}
    
    # Custos estimados
    estimated_cost_usd = Column(Float, nullable=True)
    actual_cost_usd = Column(Float, nullable=True)


class BatchJob(Base):
    """
    Representa um job individual dentro de um batch.
    Estende o modelo Job existente com campos específicos para lote.
    """
    __tablename__ = "batch_jobs"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    batch_id = Column(String, ForeignKey('batches.id'), nullable=False, index=True)
    owner_email = Column(String, index=True, nullable=False)
    
    # Configuração do job
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=True)
    title = Column(Text, nullable=False)
    language_code = Column(String(10), nullable=False, index=True)  # 'pt-BR', 'en-US', etc
    voice_id = Column(String(100), nullable=False)  # 'pt-BR-Neural2-A', etc
    variation_number = Column(Integer, default=1)  # Para A/B testing
    
    # Status
    status = Column(String(20), default="queued", index=True)  # queued, running, completed, failed, retrying
    
    # Resultados
    roteiro_text = Column(Text, nullable=True)  # Conteúdo inline (opcional)
    roteiro_url = Column(String(500), nullable=True)  # S3 URL
    audio_url = Column(String(500), nullable=True)  # S3 URL
    
    # Metadados do resultado
    roteiro_char_count = Column(Integer, nullable=True)
    audio_duration_seconds = Column(Float, nullable=True)
    audio_file_size_bytes = Column(Integer, nullable=True)
    
    # Erro
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Performance
    processing_time_seconds = Column(Integer, nullable=True)
    api_calls_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Cache key (para reutilização)
    cache_key = Column(String(64), nullable=True, index=True)  # SHA256 hash


class ApiKeyPool(Base):
    """
    Pool de API Keys para distribuição round-robin.
    """
    __tablename__ = "api_key_pool"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    service = Column(String(50), nullable=False)  # 'gemini', 'tts'
    api_key = Column(String(500), nullable=False)
    
    # Status
    is_active = Column(Integer, default=1)  # 1 = ativo, 0 = desativado
    
    # Estatísticas de uso
    total_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Rate limiting
    requests_per_minute = Column(Integer, default=60)
    current_minute_requests = Column(Integer, default=0)
    minute_window_start = Column(DateTime(timezone=True), nullable=True)
    
    # Circuit breaker
    consecutive_failures = Column(Integer, default=0)
    circuit_open_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserVoicePreference(Base):
    """
    Preferências de voz do usuário por idioma.
    """
    __tablename__ = "user_voice_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    language_code = Column(String(10), nullable=False)
    preferred_voice_id = Column(String(100), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
