# models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, func, JSON
from database import Base # Importamos a Base do nosso database.py

# =================================================================
# == Modelos ORM (SQLAlchemy) - Para o Banco de Dados            ==
# =================================================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, index=True) # O UUID do Job
    status = Column(String, default="queued")
    titulo = Column(Text, nullable=True)  # NOVO: Título do roteiro para exibição (sem limite de tamanho)
    log = Column(Text, default="[]") # Guardaremos o log como um JSON em texto
    resultado = Column(Text, nullable=True)
    owner_email = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ====== NOVOS CAMPOS PARA MULTI-IDIOMA + TTS ======
    roteiro_master = Column(Text, nullable=True)  # Roteiro master original
    roteiros_adaptados = Column(JSON, nullable=True)  # {"fr-FR": "...", "pt-BR": "..."}
    audios_gerados = Column(JSON, nullable=True)  # {"fr-FR": "/static/audio/xxx_fr.mp3"}
    chars_processados_tts = Column(Integer, default=0)  # Total de caracteres processados
    duracao_total_segundos = Column(Integer, nullable=True)  # Duração total dos áudios
    
    # ====== NOVOS CAMPOS PARA MÚLTIPLAS VARIAÇÕES ======
    num_variacoes = Column(Integer, default=1)  # Quantas variações foram geradas (default 1 para retrocompatibilidade)
    roteiros_por_variacao = Column(JSON, nullable=True)  # {"variacao_1": {"pt-BR": "...", "fr-FR": "..."}, "variacao_2": {...}}
    audios_por_variacao = Column(JSON, nullable=True)  # {"variacao_1": {"pt-BR": "/static/...", "fr-FR": "..."}, "variacao_2": {...}}


# ============ Novas Tabelas: Agentes e API Keys por usuário ============
class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    idioma = Column(String, nullable=False)
    premise_prompt = Column(Text, nullable=False)
    persona_and_global_rules_prompt = Column(Text, nullable=False)
    block_structure_prompt = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ====== NOVOS CAMPOS PARA ADAPTAÇÃO CULTURAL ======
    cultural_adaptation_prompt = Column(Text, nullable=True)  # Prompt base do agente adaptador
    idiomas_alvo = Column(JSON, default=lambda: ["fr-FR"])  # Lista de idiomas-alvo
    cultural_configs = Column(JSON, default=dict)  # Configurações por idioma
    default_voices = Column(JSON, default=lambda: {
        "fr-FR": "fr-FR-Neural2-B",
        "pt-BR": "pt-BR-Neural2-B",
        "ar-XA": "ar-XA-Wavenet-B",
        "en-US": "en-US-Neural2-D"
    })  # Vozes padrão por idioma

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TtsApiKey(Base):
    """Tabela para armazenar API Keys de TTS (Google Cloud, ElevenLabs, etc)"""
    __tablename__ = "tts_api_keys"
    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


