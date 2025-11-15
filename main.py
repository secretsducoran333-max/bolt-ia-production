# main.py - Backend FastAPI para BoredFy AI

import os
import uuid
import json
import logging
import asyncio
import base64
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Annotated
from pathlib import Path

from fastapi import (
    FastAPI, HTTPException, Depends, status, 
    BackgroundTasks, UploadFile, File, Form, Request
)
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from argon2 import PasswordHasher
from sqlalchemy.orm import Session
from sqlalchemy import func

import google.generativeai as genai
from google.cloud import texttospeech
from langdetect import detect

import models
import schemas
from database import SessionLocal, engine
from settings import settings
from voices_config import PREMIUM_VOICES, get_all_voices, get_voice_by_id

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar tabelas no banco de dados
models.Base.metadata.create_all(bind=engine)

# Criar diretórios necessários
os.makedirs("files/audio", exist_ok=True)
os.makedirs("files/scripts", exist_ok=True)
os.makedirs("files/images", exist_ok=True)
os.makedirs("files/videos", exist_ok=True)

# Configuração do FastAPI
app = FastAPI(
    title="BoredFy AI API",
    description="Backend para geração de roteiros e TTS com IA",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar domínios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
app.mount("/files", StaticFiles(directory="files"), name="files")

# Segurança
pwd_hasher = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Configurações JWT
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# =================================================================
# == DEPENDÊNCIAS
# =================================================================

def get_db():
    """Dependência para obter sessão do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
) -> models.User:
    """Obtém o usuário atual a partir do token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# =================================================================
# == FUNÇÕES AUXILIARES
# =================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Cria um token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha está correta"""
    try:
        pwd_hasher.verify(hashed_password, plain_password)
        return True
    except:
        return False

def get_password_hash(password: str) -> str:
    """Gera hash da senha"""
    return pwd_hasher.hash(password)

def mask_api_key(key: str) -> str:
    """Mascara a API key para exibição"""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"

def update_user_stats(db: Session, user_id: int, stat_type: str, value: int = 1):
    """Atualiza estatísticas do usuário e gamificação"""
    stats = db.query(models.UserStats).filter(models.UserStats.user_id == user_id).first()
    
    if not stats:
        stats = models.UserStats(user_id=user_id)
        db.add(stats)
    
    # Atualizar streak
    today = date.today()
    if stats.last_active_date != today:
        if stats.last_active_date == today - timedelta(days=1):
            stats.streak_count += 1
        else:
            stats.streak_count = 1
        stats.last_active_date = today
        stats.days_active += 1
    
    # Atualizar stats específicas
    if stat_type == "script":
        stats.scripts_today += value
        stats.scripts_week += value
        stats.scripts_month += value
        stats.scripts_total += value
        stats.xp += 10 * value  # 10 XP por roteiro
    elif stat_type == "tts":
        stats.tts_today += value
        stats.tts_week += value
        stats.tts_month += value
        stats.tts_total += value
        stats.xp += 5 * value  # 5 XP por TTS
    elif stat_type == "audio_duration":
        stats.total_audio_duration += value
    
    # Calcular nível baseado em XP
    stats.level = (stats.xp // 100) + 1
    
    db.commit()
    db.refresh(stats)
    return stats

# =================================================================
# == ENDPOINTS DE AUTENTICAÇÃO
# =================================================================

@app.post("/auth/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Registra um novo usuário"""
    # Verificar se o email já existe
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    # Criar usuário
    hashed_password = get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Criar stats iniciais
    stats = models.UserStats(user_id=new_user.id)
    db.add(stats)
    db.commit()
    
    return new_user

@app.post("/auth/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Faz login e retorna token JWT"""
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=schemas.User)
def get_me(current_user: models.User = Depends(get_current_user)):
    """Retorna informações do usuário atual"""
    return current_user

# =================================================================
# == ENDPOINTS DE API KEYS
# =================================================================

@app.post("/api-keys/validate")
async def validate_api_key(
    data: schemas.ApiKeyValidate,
    current_user: models.User = Depends(get_current_user)
):
    """Valida uma API key do Gemini"""
    try:
        # Configurar Gemini com a chave
        genai.configure(api_key=data.api_key)
        
        # Fazer uma chamada de teste simples
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content("Test")
        
        if response:
            return {"is_valid": True, "message": "Chave válida"}
        else:
            return {"is_valid": False, "message": "Chave inválida"}
    except Exception as e:
        logger.error(f"Erro ao validar API key: {str(e)}")
        return {"is_valid": False, "message": f"Erro: {str(e)}"}

@app.post("/api-keys/add")
async def add_api_key(
    data: schemas.ApiKeyAdd,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Adiciona uma API key após validação"""
    # Validar a chave primeiro
    validation = await validate_api_key(schemas.ApiKeyValidate(api_key=data.api_key), current_user)
    
    if not validation["is_valid"]:
        raise HTTPException(status_code=400, detail="Chave de API inválida")
    
    # Verificar se já existe
    existing = db.query(models.ApiKey).filter(
        models.ApiKey.user_id == current_user.id,
        models.ApiKey.key_value == data.api_key
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Esta chave já foi adicionada")
    
    # Adicionar ao banco
    new_key = models.ApiKey(
        user_id=current_user.id,
        key_value=data.api_key,
        service=data.service,
        is_valid=True,
        last_validated=datetime.utcnow()
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    
    return {
        "success": True,
        "message": "Chave adicionada com sucesso!",
        "key_id": new_key.id
    }

@app.get("/api-keys", response_model=List[schemas.ApiKeyResponse])
def get_api_keys(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna as API keys do usuário (mascaradas)"""
    keys = db.query(models.ApiKey).filter(models.ApiKey.user_id == current_user.id).all()
    
    return [
        schemas.ApiKeyResponse(
            id=key.id,
            service=key.service,
            key_masked=mask_api_key(key.key_value),
            is_valid=key.is_valid,
            last_validated=key.last_validated,
            created_at=key.created_at
        )
        for key in keys
    ]

@app.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deleta uma API key"""
    key = db.query(models.ApiKey).filter(
        models.ApiKey.id == key_id,
        models.ApiKey.user_id == current_user.id
    ).first()
    
    if not key:
        raise HTTPException(status_code=404, detail="Chave não encontrada")
    
    db.delete(key)
    db.commit()
    
    return {"success": True, "message": "Chave removida com sucesso"}


# =================================================================
# == ENDPOINTS DE AGENTES
# =================================================================

@app.post("/agents", response_model=schemas.AgentResponse)
def create_agent(
    agent: schemas.AgentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cria um novo agente"""
    new_agent = models.Agent(
        user_id=current_user.id,
        name=agent.name,
        agent_type=agent.agent_type,
        idioma_principal=agent.idioma_principal,
        premise_prompt=agent.premise_prompt,
        script_prompt=agent.script_prompt,
        block_structure=agent.block_structure,
        cultural_adaptation_prompt=agent.cultural_adaptation_prompt,
        idiomas_adicionais=agent.idiomas_adicionais,
        tts_enabled=agent.tts_enabled,
        tts_voices=agent.tts_voices,
        visual_media_enabled=agent.visual_media_enabled,
        visual_media_type=agent.visual_media_type,
        visual_media_config=agent.visual_media_config
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    
    return new_agent

@app.get("/agents", response_model=List[schemas.AgentResponse])
def get_agents(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna todos os agentes do usuário"""
    agents = db.query(models.Agent).filter(models.Agent.user_id == current_user.id).all()
    return agents

@app.get("/agents/{agent_id}", response_model=schemas.AgentResponse)
def get_agent(
    agent_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna um agente específico"""
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    return agent

@app.put("/agents/{agent_id}", response_model=schemas.AgentResponse)
def update_agent(
    agent_id: int,
    agent_update: schemas.AgentUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza um agente"""
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    # Atualizar campos fornecidos
    update_data = agent_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    
    db.commit()
    db.refresh(agent)
    
    return agent

@app.delete("/agents/{agent_id}")
def delete_agent(
    agent_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deleta um agente"""
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    db.delete(agent)
    db.commit()
    
    return {"success": True, "message": "Agente removido com sucesso"}

# =================================================================
# == ENDPOINTS DE VOZES
# =================================================================

@app.get("/voices")
def get_voices():
    """Retorna todas as vozes premium disponíveis"""
    return {"voices": get_all_voices()}

@app.get("/voices/{language_code}")
def get_voices_by_language(language_code: str):
    """Retorna vozes para um idioma específico"""
    voices = [v for v in PREMIUM_VOICES if v["language_code"] == language_code]
    return {"language_code": language_code, "voices": voices}


# =================================================================
# == FUNÇÕES DE GERAÇÃO (GEMINI)
# =================================================================

async def generate_script_with_gemini(
    api_key: str,
    agent: models.Agent,
    titulo: str
) -> str:
    """Gera um roteiro usando o Gemini"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Construir o prompt completo
        prompt = f"""
{agent.premise_prompt}

{agent.script_prompt}

{agent.block_structure}

Título/Premissa: {titulo}

Gere um roteiro completo seguindo as instruções acima.
"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        logger.error(f"Erro ao gerar roteiro: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar roteiro: {str(e)}")

async def adapt_script_to_language(
    api_key: str,
    agent: models.Agent,
    script: str,
    target_language: str
) -> str:
    """Adapta um roteiro para outro idioma com adaptação cultural"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        cultural_prompt = agent.cultural_adaptation_prompt or "Adapte culturalmente o seguinte roteiro:"
        
        prompt = f"""
{cultural_prompt}

Idioma alvo: {target_language}

Roteiro original:
{script}

Adapte o roteiro acima para o idioma {target_language}, mantendo a essência mas adaptando referências culturais, expressões e contexto para o público local.
"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        logger.error(f"Erro ao adaptar roteiro: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao adaptar roteiro: {str(e)}")

async def generate_tts_audio(
    tts_api_key: str,
    text: str,
    voice_id: str,
    output_path: str
) -> int:
    """Gera áudio usando Google Cloud TTS"""
    try:
        # Configurar cliente TTS
        os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'] = tts_api_key
        client = texttospeech.TextToSpeechClient()
        
        # Obter informações da voz
        voice_info = get_voice_by_id(voice_id)
        if not voice_info:
            raise HTTPException(status_code=400, detail=f"Voz {voice_id} não encontrada")
        
        # Configurar síntese
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_info["language_code"],
            name=voice_id
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )
        
        # Gerar áudio
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Salvar arquivo
        with open(output_path, "wb") as out:
            out.write(response.audio_content)
        
        # Retornar duração aproximada (caracteres / 15 = segundos aproximados)
        duration = len(text) // 15
        return duration
    
    except Exception as e:
        logger.error(f"Erro ao gerar TTS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar TTS: {str(e)}")

async def generate_image_with_gemini(
    api_key: str,
    prompt: str,
    output_path: str
) -> str:
    """Gera uma imagem usando Gemini Imagen"""
    try:
        # Nota: A API do Gemini Imagen 3 ainda não está totalmente disponível
        # Por enquanto, vamos simular com um placeholder
        # Quando disponível, usar: genai.ImageGenerationModel('imagen-3.0-generate-001')
        
        logger.warning("Geração de imagens ainda não implementada - usando placeholder")
        
        # Placeholder: retornar uma imagem de exemplo
        return f"https://picsum.photos/1024/1024?random={uuid.uuid4()}"
    
    except Exception as e:
        logger.error(f"Erro ao gerar imagem: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar imagem: {str(e)}")

# =================================================================
# == BACKGROUND TASKS PARA GERAÇÃO
# =================================================================

async def process_job_generation(
    job_id: str,
    user_id: int,
    agent_id: int,
    titulo: str,
    db_session: Session
):
    """Processa a geração de um job em background"""
    try:
        # Buscar job
        job = db_session.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} não encontrado")
            return
        
        # Atualizar status
        job.status = "processing"
        job.progress = 10
        db_session.commit()
        
        # Buscar agente
        agent = db_session.query(models.Agent).filter(models.Agent.id == agent_id).first()
        if not agent:
            job.status = "failed"
            job.log = json.dumps(["Agente não encontrado"])
            db_session.commit()
            return
        
        # Buscar API key do Gemini
        api_key_obj = db_session.query(models.ApiKey).filter(
            models.ApiKey.user_id == user_id,
            models.ApiKey.is_valid == True
        ).first()
        
        if not api_key_obj:
            job.status = "failed"
            job.log = json.dumps(["Nenhuma API key válida encontrada"])
            db_session.commit()
            return
        
        api_key = api_key_obj.key_value
        
        # Gerar roteiro master
        job.progress = 20
        db_session.commit()
        
        roteiro_master = await generate_script_with_gemini(api_key, agent, titulo)
        job.roteiro_master = roteiro_master
        job.progress = 40
        db_session.commit()
        
        # Salvar roteiro master em arquivo
        script_filename = f"{job_id}_{agent.idioma_principal}.txt"
        script_path = f"files/scripts/{script_filename}"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(roteiro_master)
        
        # Registrar arquivo
        file_record = models.GeneratedFile(
            user_id=user_id,
            job_id=job_id,
            filename=script_filename,
            file_type="script",
            file_path=script_path,
            file_size=len(roteiro_master.encode('utf-8'))
        )
        db_session.add(file_record)
        
        # Adaptar para idiomas adicionais
        roteiros_adaptados = {agent.idioma_principal: roteiro_master}
        
        if agent.idiomas_adicionais:
            for idx, idioma in enumerate(agent.idiomas_adicionais):
                progress = 40 + (idx + 1) * (20 // (len(agent.idiomas_adicionais) + 1))
                job.progress = progress
                db_session.commit()
                
                roteiro_adaptado = await adapt_script_to_language(
                    api_key, agent, roteiro_master, idioma
                )
                roteiros_adaptados[idioma] = roteiro_adaptado
                
                # Salvar arquivo adaptado
                adapted_filename = f"{job_id}_{idioma}.txt"
                adapted_path = f"files/scripts/{adapted_filename}"
                with open(adapted_path, "w", encoding="utf-8") as f:
                    f.write(roteiro_adaptado)
                
                file_record = models.GeneratedFile(
                    user_id=user_id,
                    job_id=job_id,
                    filename=adapted_filename,
                    file_type="script",
                    file_path=adapted_path,
                    file_size=len(roteiro_adaptado.encode('utf-8'))
                )
                db_session.add(file_record)
        
        job.roteiros_adaptados = roteiros_adaptados
        job.progress = 60
        db_session.commit()
        
        # Gerar TTS se habilitado
        audios_gerados = {}
        total_duration = 0
        
        if agent.tts_enabled and agent.tts_voices:
            # Buscar TTS API key
            tts_key_obj = db_session.query(models.TtsApiKey).filter(
                models.TtsApiKey.user_id == user_id,
                models.TtsApiKey.is_valid == True
            ).first()
            
            if tts_key_obj:
                tts_api_key = tts_key_obj.key_value
                
                for idx, (idioma, roteiro) in enumerate(roteiros_adaptados.items()):
                    if idioma in agent.tts_voices:
                        voice_id = agent.tts_voices[idioma]
                        
                        progress = 60 + (idx + 1) * (30 // len(roteiros_adaptados))
                        job.progress = progress
                        db_session.commit()
                        
                        audio_filename = f"{job_id}_{idioma}.mp3"
                        audio_path = f"files/audio/{audio_filename}"
                        
                        duration = await generate_tts_audio(
                            tts_api_key, roteiro, voice_id, audio_path
                        )
                        
                        audios_gerados[idioma] = f"/files/audio/{audio_filename}"
                        total_duration += duration
                        
                        # Registrar arquivo
                        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
                        file_record = models.GeneratedFile(
                            user_id=user_id,
                            job_id=job_id,
                            filename=audio_filename,
                            file_type="audio",
                            file_path=audio_path,
                            file_size=file_size
                        )
                        db_session.add(file_record)
                        
                        # Atualizar stats
                        update_user_stats(db_session, user_id, "tts", 1)
        
        job.audios_gerados = audios_gerados
        job.duracao_total_segundos = total_duration
        job.progress = 90
        db_session.commit()
        
        # Gerar imagens se habilitado
        imagens_geradas = []
        
        if agent.visual_media_enabled and agent.visual_media_type == "images":
            config = agent.visual_media_config
            image_count = config.get("image_count", 1)
            prompt_template = config.get("prompt_template", "")
            
            for i in range(min(image_count, 20)):  # Máximo 20 imagens
                image_filename = f"{job_id}_image_{i+1}.png"
                image_path = f"files/images/{image_filename}"
                
                image_url = await generate_image_with_gemini(
                    api_key, prompt_template, image_path
                )
                
                imagens_geradas.append(f"/files/images/{image_filename}")
                
                # Registrar arquivo
                file_record = models.GeneratedFile(
                    user_id=user_id,
                    job_id=job_id,
                    filename=image_filename,
                    file_type="image",
                    file_path=image_path,
                    file_size=0  # Placeholder
                )
                db_session.add(file_record)
        
        job.imagens_geradas = imagens_geradas
        job.progress = 100
        job.status = "completed"
        db_session.commit()
        
        # Atualizar stats do usuário
        update_user_stats(db_session, user_id, "script", 1)
        if total_duration > 0:
            update_user_stats(db_session, user_id, "audio_duration", total_duration)
        
        logger.info(f"Job {job_id} concluído com sucesso")
    
    except Exception as e:
        logger.error(f"Erro ao processar job {job_id}: {str(e)}")
        job = db_session.query(models.Job).filter(models.Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.log = json.dumps([f"Erro: {str(e)}"])
            db_session.commit()


# =================================================================
# == ENDPOINTS DE JOBS
# =================================================================

@app.post("/jobs/generate", response_model=List[schemas.JobResponse])
async def create_generation_jobs(
    job_data: schemas.JobCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cria jobs de geração para múltiplos títulos"""
    jobs = []
    
    for titulo in job_data.titulos:
        # Criar job
        job_id = str(uuid.uuid4())
        new_job = models.Job(
            id=job_id,
            user_id=current_user.id,
            agent_id=job_data.agent_id,
            titulo=titulo,
            status="pending",
            progress=0,
            log=json.dumps(["Job criado"])
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        
        # Adicionar tarefa em background
        background_tasks.add_task(
            process_job_generation,
            job_id,
            current_user.id,
            job_data.agent_id,
            titulo,
            db
        )
        
        jobs.append(new_job)
    
    return jobs

@app.get("/jobs/queue", response_model=List[schemas.JobResponse])
def get_job_queue(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna a fila de jobs do usuário"""
    jobs = db.query(models.Job).filter(
        models.Job.user_id == current_user.id
    ).order_by(models.Job.created_at.desc()).limit(50).all()
    
    return jobs

@app.get("/jobs/{job_id}", response_model=schemas.JobDetailResponse)
def get_job_detail(
    job_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna detalhes de um job específico"""
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # Parsear log
    try:
        log_list = json.loads(job.log) if job.log else []
    except:
        log_list = []
    
    return schemas.JobDetailResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        titulo=job.titulo,
        log=log_list,
        roteiro_master=job.roteiro_master,
        roteiros_adaptados=job.roteiros_adaptados,
        audios_gerados=job.audios_gerados,
        imagens_geradas=job.imagens_geradas,
        video_gerado=job.video_gerado,
        created_at=job.created_at,
        updated_at=job.updated_at
    )

@app.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancela um job em andamento"""
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Job já finalizado")
    
    job.status = "cancelled"
    db.commit()
    
    return {"success": True, "message": "Job cancelado com sucesso"}

# =================================================================
# == ENDPOINTS DE STATS
# =================================================================

@app.get("/stats/dashboard", response_model=schemas.UserStatsResponse)
def get_user_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna estatísticas do dashboard do usuário"""
    stats = db.query(models.UserStats).filter(
        models.UserStats.user_id == current_user.id
    ).first()
    
    if not stats:
        # Criar stats iniciais se não existir
        stats = models.UserStats(user_id=current_user.id)
        db.add(stats)
        db.commit()
        db.refresh(stats)
    
    return stats

# =================================================================
# == ENDPOINTS DE ARQUIVOS
# =================================================================

@app.get("/files/recent", response_model=List[schemas.GeneratedFileResponse])
def get_recent_files(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna arquivos gerados nas últimas 24 horas"""
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    
    files = db.query(models.GeneratedFile).filter(
        models.GeneratedFile.user_id == current_user.id,
        models.GeneratedFile.created_at >= cutoff_time
    ).order_by(models.GeneratedFile.created_at.desc()).all()
    
    return [
        schemas.GeneratedFileResponse(
            id=f.id,
            filename=f.filename,
            file_type=f.file_type,
            file_size=f.file_size,
            download_url=f"/{f.file_path}",
            created_at=f.created_at
        )
        for f in files
    ]

@app.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deleta um arquivo gerado"""
    file_record = db.query(models.GeneratedFile).filter(
        models.GeneratedFile.id == file_id,
        models.GeneratedFile.user_id == current_user.id
    ).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Deletar arquivo físico
    try:
        if os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
    except Exception as e:
        logger.error(f"Erro ao deletar arquivo físico: {str(e)}")
    
    # Deletar registro do banco
    db.delete(file_record)
    db.commit()
    
    return {"success": True, "message": "Arquivo deletado com sucesso"}

# =================================================================
# == ENDPOINTS DE CRIAÇÃO DE AGENTE COM IA
# =================================================================

@app.post("/agents/create-with-ai", response_model=schemas.AIAgentPreview)
async def create_agent_with_ai(
    agent_name: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cria um agente a partir da análise de roteiros com IA"""
    try:
        # Validar número de arquivos
        if len(files) > 6:
            raise HTTPException(status_code=400, detail="Máximo de 6 arquivos permitidos")
        
        # Ler conteúdo dos arquivos
        scripts_content = []
        for file in files:
            if file.size > 5 * 1024 * 1024:  # 5MB
                raise HTTPException(status_code=400, detail=f"Arquivo {file.filename} muito grande (máx 5MB)")
            
            content = await file.read()
            scripts_content.append(content.decode('utf-8'))
        
        # Buscar API key
        api_key_obj = db.query(models.ApiKey).filter(
            models.ApiKey.user_id == current_user.id,
            models.ApiKey.is_valid == True
        ).first()
        
        if not api_key_obj:
            raise HTTPException(status_code=400, detail="Nenhuma API key válida encontrada")
        
        # Configurar Gemini
        genai.configure(api_key=api_key_obj.key_value)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Criar prompt de análise
        analysis_prompt = f"""
Analise os seguintes roteiros e extraia padrões para criar templates de um agente de geração:

{chr(10).join([f"=== ROTEIRO {i+1} ==={chr(10)}{script}" for i, script in enumerate(scripts_content)])}

Com base nesses roteiros, gere:

1. **Template de Premissa**: Um padrão para a ideia inicial dos roteiros
2. **Template de Roteiro (Regras Globais)**: Regras de formatação, tom, estilo e estrutura
3. **Estrutura de Blocos**: A organização narrativa típica (ex: Introdução, Desenvolvimento, Conclusão)
4. **Template de Adaptação Cultural**: Como adaptar o conteúdo para diferentes culturas

Retorne em formato JSON com as chaves: premise_template, script_template, block_structure, cultural_adaptation_template
"""
        
        response = model.generate_content(analysis_prompt)
        
        # Tentar parsear resposta como JSON
        try:
            # Extrair JSON da resposta
            response_text = response.text
            # Remover markdown code blocks se existirem
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text.strip())
        except:
            # Se falhar, criar estrutura manual
            result = {
                "premise_template": response.text[:500],
                "script_template": response.text[500:1000] if len(response.text) > 500 else response.text,
                "block_structure": "Bloco 1: Introdução\nBloco 2: Desenvolvimento\nBloco 3: Conclusão",
                "cultural_adaptation_template": "Adapte referências culturais, expressões idiomáticas e contexto para o público local."
            }
        
        return schemas.AIAgentPreview(
            agent_name=agent_name,
            premise_template=result.get("premise_template", ""),
            script_template=result.get("script_template", ""),
            block_structure=result.get("block_structure", ""),
            cultural_adaptation_template=result.get("cultural_adaptation_template", "")
        )
    
    except Exception as e:
        logger.error(f"Erro ao criar agente com IA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

# =================================================================
# == ENDPOINT DE HEALTH CHECK
# =================================================================

@app.get("/health")
def health_check():
    """Verifica se a API está funcionando"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# =================================================================
# == ROTAS PARA SERVIR O FRONTEND
# =================================================================

@app.get("/")
def serve_login():
    """Serve a página de login"""
    return FileResponse("login.html")

@app.get("/index.html")
def serve_index():
    """Serve a página principal"""
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
