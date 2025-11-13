import asyncio
import uuid
import json
import re
import logging
import os
from datetime import datetime, timedelta
from typing import Annotated, List, Optional, Dict

from fastapi import FastAPI, Header, HTTPException, BackgroundTasks, Depends, status, Form, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
import google.generativeai as genai
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# --- Novas importações para SQLAlchemy e Configurações ---
from sqlalchemy.orm import Session
import models, schemas
from database import SessionLocal, engine
from settings import settings

# --- Importação dos endpoints de batch ---
import batch_endpoints

# Esta linha cria as tabelas no seu banco de dados se elas não existirem
models.Base.metadata.create_all(bind=engine)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dependência para obter a sessão do banco de dados nos endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Constantes de Segurança (agora do settings.py) ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# =================================================================
# == Funções CRUD (Lógica do Banco de Dados)                     ==
# =================================================================

# --- CRUD para Usuários ---
def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()

def create_db_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- CRUD para Jobs ---
def create_db_job(db: Session, job_id: str, owner_email: str, titulo: str = None) -> models.Job:
    log_inicial = json.dumps(["Job criado e enfileirado."])
    db_job = models.Job(id=job_id, owner_email=owner_email, titulo=titulo, log=log_inicial)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def get_db_job(db: Session, job_id: str) -> Optional[models.Job]:
    return db.query(models.Job).filter(models.Job.id == job_id).first()

def validate_cultural_configs(cultural_configs: dict, default_voices: dict) -> None:
    """
    Valida configurações culturais e vozes para TTS Multi-Idioma.
    
    Args:
        cultural_configs: Dict com configurações por idioma
        default_voices: Dict com vozes padrão por idioma
        
    Raises:
        HTTPException(400): Se validação falhar
    """
    if not cultural_configs and not default_voices:
        return  # Configs vazios são OK (usa defaults)
    
    # Validar cultural_configs
    for idioma, config in cultural_configs.items():
        if not isinstance(config, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Para idioma '{idioma}': configuração deve ser um objeto, recebido {type(config).__name__}"
            )
        
        # Validar speaking_rate (opcional)
        if 'speaking_rate' in config:
            rate = config['speaking_rate']
            try:
                rate_float = float(rate)
                if not (0.25 <= rate_float <= 4.0):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Para idioma '{idioma}': speaking_rate deve estar entre 0.25 e 4.0, recebido {rate}"
                    )
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Para idioma '{idioma}': speaking_rate deve ser um número, recebido {rate}"
                )
        
        # Validar pitch (opcional)
        if 'pitch' in config:
            pitch = config['pitch']
            try:
                pitch_int = int(pitch)
                if not (-20 <= pitch_int <= 20):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Para idioma '{idioma}': pitch deve estar entre -20 e 20, recebido {pitch}"
                    )
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Para idioma '{idioma}': pitch deve ser um número inteiro, recebido {pitch}"
                )
    
    # Validar default_voices
    for idioma, voice_config in default_voices.items():
        if isinstance(voice_config, dict):
            # Formato completo: {voice_id, speaking_rate, pitch}
            if 'voice_id' not in voice_config or not voice_config['voice_id']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Para idioma '{idioma}': voice_id é obrigatório em default_voices"
                )
            
            # Validar speaking_rate se presente
            if 'speaking_rate' in voice_config:
                rate = voice_config['speaking_rate']
                try:
                    rate_float = float(rate)
                    if not (0.25 <= rate_float <= 4.0):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Para idioma '{idioma}': speaking_rate em default_voices deve estar entre 0.25 e 4.0, recebido {rate}"
                        )
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Para idioma '{idioma}': speaking_rate deve ser um número"
                    )
            
            # Validar pitch se presente
            if 'pitch' in voice_config:
                pitch = voice_config['pitch']
                try:
                    pitch_int = int(pitch)
                    if not (-20 <= pitch_int <= 20):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Para idioma '{idioma}': pitch em default_voices deve estar entre -20 e 20, recebido {pitch}"
                        )
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Para idioma '{idioma}': pitch deve ser um número inteiro"
                    )
        
        elif isinstance(voice_config, str):
            # Formato simples: apenas voice_id string
            if not voice_config.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"Para idioma '{idioma}': voice_id não pode ser vazio"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Para idioma '{idioma}': default_voices deve ser string (voice_id) ou objeto, recebido {type(voice_config).__name__}"
            )

def update_job_status(db: Session, job_id: str, status: str, message: Optional[str] = None, resultado_final: Optional[str] = None):
    db_job = get_db_job(db, job_id)
    if not db_job:
        return

    db_job.status = status
    if message:
        current_log = json.loads(db_job.log)
        current_log.append(message)
        db_job.log = json.dumps(current_log)
    if resultado_final:
        db_job.resultado = resultado_final
    
    db.commit()

# --- Funções Auxiliares de Segurança (Atualizadas) ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire_minutes = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expire_minutes
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# =================================================================
# == Funções de Segmentação de Narrativas                        ==
# =================================================================

def segmentar_narrativa_em_blocos(texto: str, idioma: str = "português") -> List[Dict]:
    """
    Segmenta texto narrativo em blocos para processamento.
    
    DETECÇÃO AUTOMÁTICA:
    - Se o texto contém marcadores estruturados (# PARTE / # META / # REGRAS), 
      usa parsing manual (compatibilidade 100% com sistema antigo)
    - Se não, aplica segmentação automática baseada em heurísticas semânticas
    
    ESTRATÉGIA DE SEGMENTAÇÃO AUTOMÁTICA:
    1. Detecta quebras naturais (parágrafos duplos: \\n\\n)
    2. Identifica palavras de transição contextuais por idioma
    3. Respeita limite de ~1600 chars por bloco (flexível)
    4. NUNCA quebra no meio de frase ou parágrafo
    
    Args:
        texto: Conteúdo completo da estrutura de blocos ou narrativa contínua
        idioma: Idioma para detecção de palavras de transição
    
    Returns:
        Lista de dicts com estrutura:
        {
            'numero_bloco': int,        # Sequencial (1, 2, 3...)
            'titulo_bloco': str,        # Resumo automático ou nome da PARTE
            'conteudo': str,            # Texto do bloco
            'inicio_char': int,         # Offset inicial no texto original
            'fim_char': int,            # Offset final no texto original
            'tipo_demarcacao': str,     # 'manual' ou 'auto'
            'meta': str | None,         # META (só para blocos manuais)
            'regras': str | None        # REGRAS (só para blocos manuais)
        }
    
    Edge Cases:
        - Texto < 1000 chars → Retorna bloco único
        - Texto > 50k chars → Warning + segmentação forçada agressiva
        - Sem quebras de parágrafo → Fallback para corte por sentenças
        - Unicode/emojis → Tratamento seguro (len() conta corretamente)
    
    Performance:
        - O(n) no tamanho do texto
        - Máximo 2 passadas: detecção de formato + segmentação
    
    Limitações Conhecidas:
        - Análise semântica é baseada em heurísticas léxicas simples
        - Idiomas não latinos podem ter palavras de transição incompletas
        - Títulos automáticos são extraídos dos primeiros 20 palavras (não sumarizados por IA)
    """
    
    # Regex para detecção de estrutura manual
    REGEX_ESTRUTURA_MANUAL = re.compile(
        r"# PARTE.*?:(.*?)\n# META.*?:(.*?)\n# REGRAS.*?:(.*?)(?=\n# PARTE|\Z)", 
        re.DOTALL
    )
    
    # Palavras de transição por idioma (para detecção de quebras naturais)
    PALAVRAS_TRANSICAO = {
        "português": [
            r"\bMas\b", r"\bPorém\b", r"\bEntretanto\b", r"\bContudo\b",
            r"\bAlém disso\b", r"\bPor outro lado\b", r"\bEnquanto isso\b",
            r"\bAgora\b", r"\bDepois\b", r"\bFinalmente\b", r"\bPrimeiro\b"
        ],
        "inglês": [
            r"\bHowever\b", r"\bBut\b", r"\bYet\b", r"\bMeanwhile\b",
            r"\bMoreover\b", r"\bFurthermore\b", r"\bNow\b", r"\bThen\b",
            r"\bFinally\b", r"\bFirst\b", r"\bNext\b"
        ],
        "francês": [
            r"\bMais\b", r"\bCependant\b", r"\bPourtant\b", r"\bAlors\b",
            r"\bEnsuite\b", r"\bEnfin\b", r"\bD'abord\b", r"\bMaintenant\b"
        ],
        "espanhol": [
            r"\bPero\b", r"\bSin embargo\b", r"\bAhora\b", r"\bLuego\b",
            r"\bAdemás\b", r"\bFinalmente\b", r"\bPrimero\b", r"\bMientras\b"
        ]
    }
    
    # Normalizar idioma
    idioma_lower = idioma.lower()
    transicoes = PALAVRAS_TRANSICAO.get(idioma_lower, PALAVRAS_TRANSICAO["português"])
    
    # EDGE CASE 1: Texto muito curto
    if len(texto) < 1000:
        logger.info(f"[SEGMENTAÇÃO] Texto curto ({len(texto)} chars) → Bloco único")
        return [{
            'numero_bloco': 1,
            'titulo_bloco': _extrair_titulo_automatico(texto),
            'conteudo': texto,
            'inicio_char': 0,
            'fim_char': len(texto),
            'tipo_demarcacao': 'auto',
            'meta': None,
            'regras': None
        }]
    
    # EDGE CASE 2: Texto gigante
    if len(texto) > 50000:
        logger.warning(f"[SEGMENTAÇÃO] Texto gigante ({len(texto)} chars) → Segmentação forçada")
    
    # DETECÇÃO 1: Verificar se é estrutura manual (compatibilidade com sistema antigo)
    blocos_manuais = REGEX_ESTRUTURA_MANUAL.findall(texto)
    
    if blocos_manuais:
        logger.info(f"[SEGMENTAÇÃO] Estrutura MANUAL detectada → {len(blocos_manuais)} blocos")
        resultado = []
        offset_atual = 0
        
        for i, (nome_parte, meta, regras_parte) in enumerate(blocos_manuais, 1):
            nome_parte = nome_parte.strip()
            meta = meta.strip()
            regras_parte = regras_parte.strip()
            
            # Encontrar posição exata no texto original
            match = REGEX_ESTRUTURA_MANUAL.search(texto, offset_atual)
            if match:
                inicio = match.start()
                fim = match.end()
                conteudo_completo = match.group(0)
                offset_atual = fim
            else:
                # Fallback se regex falhar
                inicio = offset_atual
                fim = len(texto) if i == len(blocos_manuais) else offset_atual + 1000
                conteudo_completo = texto[inicio:fim]
            
            bloco = {
                'numero_bloco': i,
                'titulo_bloco': nome_parte,
                'conteudo': conteudo_completo,
                'inicio_char': inicio,
                'fim_char': fim,
                'tipo_demarcacao': 'manual',
                'meta': meta,
                'regras': regras_parte
            }
            resultado.append(bloco)
            
            logger.info(
                f"  BLOCO [{i}]: '{nome_parte}' "
                f"(chars: {inicio}-{fim}, tipo: manual)"
            )
        
        return resultado
    
    # DETECÇÃO 2: Segmentação automática
    logger.info(f"[SEGMENTAÇÃO] Estrutura AUTO detectada → Iniciando análise")
    return _segmentar_automaticamente(texto, transicoes)


def _segmentar_automaticamente(texto: str, palavras_transicao: List[str]) -> List[Dict]:
    """
    Aplica segmentação automática baseada em heurísticas textuais.
    
    ALGORITMO:
    1. Divide texto em parágrafos (\\n\\n)
    2. Agrupa parágrafos em blocos respeitando:
       - Limite alvo: 1600 chars (flexível ±400)
       - Quebras naturais (transições, mudanças de tema)
       - NUNCA quebra no meio de parágrafo
    3. Gera títulos automáticos para cada bloco
    
    Args:
        texto: Narrativa contínua
        palavras_transicao: Lista de regex patterns para transições
    
    Returns:
        Lista de blocos segmentados
    """
    
    MIN_CHARS_BLOCO = 1200
    TARGET_CHARS_BLOCO = 1600
    MAX_CHARS_BLOCO = 2000
    
    # PASSO 1: Dividir em parágrafos
    paragrafos = re.split(r'\n\n+', texto)
    paragrafos = [p.strip() for p in paragrafos if p.strip()]
    
    # EDGE CASE: Texto sem quebras de parágrafo
    if len(paragrafos) == 1:
        logger.warning("[SEGMENTAÇÃO] Sem quebras de parágrafo → Fallback para sentenças")
        return _segmentar_por_sentencas(texto, palavras_transicao)
    
    logger.info(f"[SEGMENTAÇÃO] {len(paragrafos)} parágrafos detectados")
    
    # PASSO 2: Agrupar parágrafos em blocos
    blocos = []
    bloco_atual = []
    chars_bloco_atual = 0
    offset_global = 0
    inicio_bloco_char = 0
    
    for i, paragrafo in enumerate(paragrafos):
        len_paragrafo = len(paragrafo)
        
        # Verificar se adicionar este parágrafo ultrapassa o limite
        nova_contagem = chars_bloco_atual + len_paragrafo
        
        # Detectar palavras de transição (sugerem quebra natural)
        tem_transicao = any(re.search(pattern, paragrafo[:100]) for pattern in palavras_transicao)
        
        # DECISÃO DE QUEBRA:
        # 1. Se já estamos no mínimo E (atingimos target OU há transição OU é último parágrafo)
        # 2. Se ultrapassamos o máximo absoluto
        deve_quebrar = (
            (chars_bloco_atual >= MIN_CHARS_BLOCO and 
             (nova_contagem >= TARGET_CHARS_BLOCO or tem_transicao or i == len(paragrafos) - 1))
            or nova_contagem >= MAX_CHARS_BLOCO
        )
        
        if deve_quebrar and bloco_atual:
            # Finalizar bloco atual
            conteudo_bloco = "\n\n".join(bloco_atual)
            fim_bloco_char = inicio_bloco_char + len(conteudo_bloco)
            
            blocos.append({
                'numero_bloco': len(blocos) + 1,
                'titulo_bloco': _extrair_titulo_automatico(conteudo_bloco),
                'conteudo': conteudo_bloco,
                'inicio_char': inicio_bloco_char,
                'fim_char': fim_bloco_char,
                'tipo_demarcacao': 'auto',
                'meta': None,
                'regras': None
            })
            
            logger.info(
                f"  BLOCO [{len(blocos)}]: '{blocos[-1]['titulo_bloco']}' "
                f"(chars: {inicio_bloco_char}-{fim_bloco_char}, tipo: auto, "
                f"motivo: {'transição' if tem_transicao else 'tamanho'})"
            )
            
            # Iniciar novo bloco
            bloco_atual = [paragrafo]
            chars_bloco_atual = len_paragrafo
            inicio_bloco_char = fim_bloco_char + 2  # +2 pelos \n\n
        else:
            # Adicionar ao bloco atual
            bloco_atual.append(paragrafo)
            chars_bloco_atual += len_paragrafo
    
    # PASSO 3: Finalizar último bloco
    if bloco_atual:
        conteudo_bloco = "\n\n".join(bloco_atual)
        fim_bloco_char = inicio_bloco_char + len(conteudo_bloco)
        
        blocos.append({
            'numero_bloco': len(blocos) + 1,
            'titulo_bloco': _extrair_titulo_automatico(conteudo_bloco),
            'conteudo': conteudo_bloco,
            'inicio_char': inicio_bloco_char,
            'fim_char': fim_bloco_char,
            'tipo_demarcacao': 'auto',
            'meta': None,
            'regras': None
        })
        
        logger.info(
            f"  BLOCO [{len(blocos)}]: '{blocos[-1]['titulo_bloco']}' "
            f"(chars: {inicio_bloco_char}-{fim_bloco_char}, tipo: auto)"
        )
    
    logger.info(f"[SEGMENTAÇÃO] Total de {len(blocos)} blocos gerados")
    return blocos


def _segmentar_por_sentencas(texto: str, palavras_transicao: List[str]) -> List[Dict]:
    """
    Fallback para textos sem quebras de parágrafo.
    Segmenta por sentenças (pontos finais) respeitando limites de tamanho.
    
    Args:
        texto: Texto contínuo sem parágrafos
        palavras_transicao: Patterns de transição
    
    Returns:
        Lista de blocos segmentados
    """
    
    TARGET_CHARS = 1600
    
    # Dividir por sentenças (aproximação simples)
    sentencas = re.split(r'([.!?]+\s+)', texto)
    sentencas = [''.join(sentencas[i:i+2]) for i in range(0, len(sentencas)-1, 2)]
    
    blocos = []
    bloco_atual = []
    chars_atual = 0
    offset = 0
    
    for sentenca in sentencas:
        len_sentenca = len(sentenca)
        
        if chars_atual + len_sentenca >= TARGET_CHARS and bloco_atual:
            # Finalizar bloco
            conteudo = ''.join(bloco_atual)
            blocos.append({
                'numero_bloco': len(blocos) + 1,
                'titulo_bloco': _extrair_titulo_automatico(conteudo),
                'conteudo': conteudo,
                'inicio_char': offset,
                'fim_char': offset + len(conteudo),
                'tipo_demarcacao': 'auto',
                'meta': None,
                'regras': None
            })
            
            offset += len(conteudo)
            bloco_atual = [sentenca]
            chars_atual = len_sentenca
        else:
            bloco_atual.append(sentenca)
            chars_atual += len_sentenca
    
    # Último bloco
    if bloco_atual:
        conteudo = ''.join(bloco_atual)
        blocos.append({
            'numero_bloco': len(blocos) + 1,
            'titulo_bloco': _extrair_titulo_automatico(conteudo),
            'conteudo': conteudo,
            'inicio_char': offset,
            'fim_char': offset + len(conteudo),
            'tipo_demarcacao': 'auto',
            'meta': None,
            'regras': None
        })
    
    logger.info(f"[SEGMENTAÇÃO FALLBACK] {len(blocos)} blocos gerados por sentenças")
    return blocos


def _extrair_titulo_automatico(texto: str, max_palavras: int = 15) -> str:
    """
    Extrai um título automático dos primeiros N palavras do texto.
    
    ESTRATÉGIA:
    - Remove quebras de linha e espaços múltiplos
    - Pega as primeiras 10-20 palavras
    - Adiciona reticências se texto for mais longo
    
    Args:
        texto: Conteúdo do bloco
        max_palavras: Máximo de palavras no título
    
    Returns:
        Título formatado (10-20 palavras)
    """
    
    # Limpar e normalizar
    texto_limpo = re.sub(r'\s+', ' ', texto.strip())
    
    # Extrair primeiras palavras
    palavras = texto_limpo.split()[:max_palavras]
    titulo = ' '.join(palavras)
    
    # Adicionar reticências se necessário
    if len(palavras) == max_palavras and len(texto_limpo.split()) > max_palavras:
        titulo += "..."
    
    # Limitar tamanho absoluto (segurança)
    if len(titulo) > 120:
        titulo = titulo[:117] + "..."
    
    return titulo


# =================================================================
# == FUNÇÕES DE ADAPTAÇÃO CULTURAL E TTS                         ==
# =================================================================

async def adaptar_culturalmente(
    roteiro_master: str,
    idioma_master: str,
    idioma_alvo: str,
    cultural_config: dict,
    base_prompt: str,
    api_key: str
) -> str:
    """
    Adapta roteiro culturalmente usando Gemini API.
    
    Args:
        roteiro_master: texto do roteiro original
        idioma_master: código do idioma original (ex: "fr-FR")
        idioma_alvo: código do idioma-alvo (ex: "pt-BR")
        cultural_config: dict com adaptacao_prompt, sensibilidade, formato
        base_prompt: prompt base de adaptação cultural
        api_key: Google API Key (mesma do Gemini)
    
    Returns:
        Roteiro adaptado culturalmente
    """
    # Se idiomas iguais, retorna sem mudanças
    if idioma_master == idioma_alvo:
        logger.info(f"[ADAPTAÇÃO] Idiomas idênticos ({idioma_master}), pulando adaptação")
        return roteiro_master
    
    logger.info(f"[ADAPTAÇÃO] {idioma_master} → {idioma_alvo}")
    
    # Extrai configurações específicas
    adaptacao_prompt = cultural_config.get('adaptacao_prompt', 
        'Adapte mantendo reverência e clareza.')
    sensibilidade = cultural_config.get('sensibilidade', 
        'Respeite diferentes crenças e foque em lições universais.')
    formato = cultural_config.get('formato', 
        'Narração clara e envolvente.')
    
    # Constrói prompt de adaptação
    # IMPORTANTE: base_prompt contém META-INSTRUÇÕES para o AI, não deve aparecer no output
    instrucoes_meta = ""
    if base_prompt:
        instrucoes_meta = f"""
IMPORTANTE - LEIA ESTAS META-INSTRUÇÕES (NÃO INCLUA NO OUTPUT):
{base_prompt}

"""
    
    len_original = len(roteiro_master)
    
    prompt_adaptacao = f"""
Você é um especialista em localização cultural de conteúdo espiritual/religioso.

{instrucoes_meta}TAREFA CRÍTICA: Adapte COMPLETAMENTE o roteiro abaixo do idioma {idioma_master} para {idioma_alvo}.

⚠️ ATENÇÃO: O roteiro original tem {len_original} caracteres. 
Sua adaptação DEVE ter entre {int(len_original * 0.9)} e {int(len_original * 1.1)} caracteres (±10%).

DIRETRIZES ESPECÍFICAS PARA {idioma_alvo}:
- ADAPTAÇÃO: {adaptacao_prompt}
- SENSIBILIDADE: {sensibilidade}
- FORMATO: {formato}

REGRAS OBRIGATÓRIAS - LEIA COM ATENÇÃO:
✅ Adapte TODO O CONTEÚDO - não resuma, não corte, não omita parágrafos
✅ Mantenha ESTRUTURA NARRATIVA idêntica (mesma sequência de eventos)
✅ Preserve TODOS OS BLOCOS/SEÇÕES (se há 6 partes, mantenha 6 partes)
✅ Mantenha COMPRIMENTO SIMILAR (±10% = {int(len_original * 0.9)}-{int(len_original * 1.1)} chars)
✅ Adapte REFERÊNCIAS CULTURAIS mas preserve o conteúdo completo
✅ Ajuste REGISTRO/TOM conforme cultura-alvo
✅ Substitua METÁFORAS por equivalentes culturais
❌ NÃO resuma ou encurte o texto
❌ NÃO pule seções ou parágrafos
❌ NÃO adicione ou remova blocos estruturais
❌ NÃO traduza mecanicamente palavra por palavra
❌ NÃO inclua as meta-instruções acima no roteiro final

ROTEIRO ORIGINAL COMPLETO ({idioma_master}) - {len_original} caracteres:
{roteiro_master}

Agora gere o roteiro COMPLETO adaptado para {idioma_alvo} (esperado: ~{len_original} chars).
IMPORTANTE: Adapte TODO o conteúdo acima, do início ao fim, mantendo o comprimento similar:
"""
    
    # Chama Gemini API (usa modelo de TEXTO, não TTS)
    genai.configure(api_key=api_key)
    
    # Calcula tokens necessários (aprox. 1 char = 0.25 tokens para português/francês)
    tokens_estimados = int(len_original * 0.3) + 1000  # +1000 para margem de segurança
    max_tokens = min(max(tokens_estimados, 8192), 32768)  # Entre 8K e 32K tokens
    
    logger.info(f"[ADAPTAÇÃO] Configurando max_output_tokens={max_tokens} para {len_original} chars")
    
    # Tentar gemini-2.5-pro primeiro, fallback para 1.5-pro se falhar
    modelos_disponiveis = ["gemini-2.5-pro", "gemini-1.5-pro"]
    response = None
    
    for modelo_nome in modelos_disponiveis:
        try:
            logger.info(f"[ADAPTAÇÃO] Tentando modelo: {modelo_nome}")
            model = genai.GenerativeModel(modelo_nome, 
                                         generation_config={"temperature": 0.7, "max_output_tokens": max_tokens})
            response = await model.generate_content_async(prompt_adaptacao)
            logger.info(f"[ADAPTAÇÃO] ✅ Usando modelo: {modelo_nome}")
            break
        except Exception as e:
            logger.warning(f"[ADAPTAÇÃO] ⚠️ Modelo {modelo_nome} indisponível: {str(e)[:100]}")
            if modelo_nome == modelos_disponiveis[-1]:  # Último modelo da lista
                logger.error(f"[ADAPTAÇÃO] ❌ Todos os modelos falharam!")
                raise
            continue
    
    if not response:
        raise Exception("Falha ao gerar adaptação: nenhum modelo Gemini disponível")
    
    roteiro_adaptado = response.text.strip()
    
    # Validação de tamanho (±10% do original)
    len_adaptado = len(roteiro_adaptado)
    diferenca_percentual = abs(len_adaptado - len_original) / len_original * 100
    
    # TAREFA 5: Calcular e logar ratio de tamanho
    ratio = (len_adaptado / len_original) * 100
    
    logger.info(f"[ADAPTAÇÃO] Concluída: {len_adaptado} chars gerados - Ratio: {ratio:.1f}%")
    logger.info(f"[ADAPTAÇÃO] Original: {len_original} chars | Adaptado: {len_adaptado} chars | Diferença: {diferenca_percentual:.1f}%")
    
    # Avisos baseados em thresholds de ratio (TAREFA 5)
    if ratio < 90 or ratio > 110:
        logger.warning(f"[ADAPTAÇÃO] ⚠️ Adaptação '{idioma_alvo}' ficou em {ratio:.1f}% (esperado: 90-110%)")
    if ratio < 80 or ratio > 120:
        logger.error(f"[ADAPTAÇÃO] ❌ Adaptação '{idioma_alvo}' fora de range crítico: {ratio:.1f}% (esperado: 80-120%)")
    
    # Verificar se foi cortado drasticamente (mais de 50% menor)
    if len_adaptado < len_original * 0.5:
        logger.error(f"[ADAPTAÇÃO] ❌ ERRO CRÍTICO: Texto cortado drasticamente! ({diferenca_percentual:.1f}% menor)")
        logger.error(f"[ADAPTAÇÃO] Possível causa: max_output_tokens insuficiente ou modelo resumindo ao invés de adaptar")
        logger.warning(f"[ADAPTAÇÃO] Tentando com prompt mais enfático...")
        
        # Segunda tentativa com prompt ainda mais enfático
        prompt_retry = f"""
ATENÇÃO: Você DEVE adaptar TODO o conteúdo abaixo para {idioma_alvo}.
NÃO resuma, NÃO corte, NÃO omita parágrafos.

O texto original tem {len_original} caracteres.
Sua adaptação DEVE ter pelo menos {int(len_original * 0.9)} caracteres.

Adapte COMPLETAMENTE cada parágrafo, cada seção, cada frase.
Preserve a estrutura e o comprimento total.

TEXTO ORIGINAL COMPLETO para adaptar:
{roteiro_master}

Inicie a adaptação COMPLETA agora:
"""
        response = await model.generate_content_async(prompt_retry)
        roteiro_adaptado = response.text.strip()
        len_adaptado = len(roteiro_adaptado)
        diferenca_percentual = abs(len_adaptado - len_original) / len_original * 100
        logger.info(f"[ADAPTAÇÃO] Segunda tentativa: {len_adaptado} chars ({diferenca_percentual:.1f}%)")
    
    if diferenca_percentual > 10:
        logger.warning(f"[ADAPTAÇÃO] ⚠️ ATENÇÃO: Diferença de tamanho ({diferenca_percentual:.1f}%) excede 10%!")
        logger.warning(f"[ADAPTAÇÃO] Esperado: {len_original * 0.9:.0f}-{len_original * 1.1:.0f} chars | Obtido: {len_adaptado} chars")
    else:
        logger.info(f"[ADAPTAÇÃO] ✅ Tamanho dentro da margem de 10%")
    
    return roteiro_adaptado


# =================================================================
# == FUNÇÃO PARA GERAR MÚLTIPLAS VARIAÇÕES DE ROTEIRO           ==
# =================================================================

async def gerar_variacoes_roteiro(
    titulo: str,
    num_variacoes: int,
    agente_config: schemas.AgenteConfig,
    api_key: str,
    temperature: float = 0.95
) -> Dict[str, str]:
    """
    Gera N roteiros GENUINAMENTE DIFERENTES sobre o mesmo tema.
    
    Args:
        titulo: Tema/título do roteiro
        num_variacoes: Quantas variações gerar (1-5 recomendado)
        agente_config: Configuração do agente (prompts, idioma, etc)
        api_key: Google Gemini API Key
        temperature: Criatividade do modelo (0.9-1.0 para maior diversidade)
    
    Returns:
        Dict com variações: {
            "variacao_1": "Roteiro master 1...",
            "variacao_2": "Roteiro master 2...",
            ...
        }
    """
    logger.info(f"[VARIAÇÕES] 🎬 Gerando {num_variacoes} variações para '{titulo}'")
    
    genai.configure(api_key=api_key)
    
    # Define aspectos/ângulos diferentes para cada variação
    aspectos_disponiveis = [
        "emocional e psicológico",
        "espiritual e filosófico",
        "prático e acional",
        "histórico e narrativo",
        "científico e analítico"
    ]
    
    # Seleciona aspectos baseado no número de variações
    aspectos_selecionados = aspectos_disponiveis[:num_variacoes]
    
    # Constrói o prompt
    aspectos_formatados = "\n".join([
        f"   - Variação {i+1}: Foco em {aspecto}"
        for i, aspecto in enumerate(aspectos_selecionados)
    ])
    
    prompt_variacoes = f"""
Você é um expert em criar roteiros de vídeo com ângulos diferentes e criativos.

TAREFA: Gerar {num_variacoes} roteiros GENUINAMENTE DIFERENTES sobre o mesmo tema.

TEMA/TÍTULO: {titulo}

CONTEXTO DO AGENTE:
- Idioma primário: {agente_config.idioma}
- Premissa: {agente_config.premise_prompt[:300]}...
- Persona/Tom: {agente_config.persona_and_global_rules_prompt[:300]}...
- Estrutura: {agente_config.block_structure_prompt[:200]}...

INSTRUÇÕES OBRIGATÓRIAS PARA CADA VARIAÇÃO:

1. CADA roteiro deve ter um ÂNGULO ÚNICO e DISTINTO:
{aspectos_formatados}

2. ESTRUTURA DIFERENTE para cada:
   ❌ NÃO repita a ordem dos eventos
   ❌ NÃO use os mesmos exemplos
   ❌ NÃO repita as mesmas metáforas
   ❌ NÃO comece da mesma forma
   ✅ Use introduções completamente diferentes
   ✅ Desenvolva argumentos por caminhos distintos
   ✅ Use exemplos e histórias únicos para cada variação

3. MENSAGEM CENTRAL CONSISTENTE:
   ✅ Todos devem falar sobre o tema "{titulo}"
   ✅ Todos devem ter a mesma conclusão/lição final
   ✅ Mas chegam por CAMINHOS COMPLETAMENTE DIFERENTES

4. COMPRIMENTO:
   - Cada roteiro deve ter entre 6000-10000 caracteres
   - Manter comprimento similar entre variações (±20%)
   - Desenvolver completamente cada ideia

5. FORMATO DE SAÍDA:
   - Gere um roteiro por vez
   - Separe cada roteiro com o marcador exato: [=== VARIAÇÃO X COMPLETA ===]
   - Não use outros marcadores ou separadores
   - Escreva o roteiro completo antes de passar para o próximo

6. QUALIDADE:
   - Desenvolva cada variação completamente
   - Não resuma ou corte ideias
   - Mantenha profundidade e riqueza de conteúdo
   - Use linguagem envolvente e cativante

COMECE AGORA gerando as {num_variacoes} variações:

[=== VARIAÇÃO 1 ===]
"""
    
    # Lista de modelos Gemini disponíveis (ordem de preferência)
    modelos_disponiveis = [
        "gemini-2.0-pro",
        "gemini-2.0-flash",
    ]
    
    response = None
    modelo_usado = None
    
    for modelo_nome in modelos_disponiveis:
        try:
            logger.info(f"[VARIAÇÕES] Tentando modelo: {modelo_nome}")
            model = genai.GenerativeModel(modelo_nome)
            
            response = await model.generate_content_async(
                prompt_variacoes,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=100000,  # Espaço suficiente para múltiplos roteiros longos
                    top_p=0.95,
                    top_k=40
                )
            )
            
            modelo_usado = modelo_nome
            logger.info(f"[VARIAÇÕES] ✅ Modelo {modelo_nome} respondeu com sucesso")
            break
            
        except Exception as e:
            logger.warning(f"[VARIAÇÕES] ⚠️ Modelo {modelo_nome} indisponível: {str(e)[:100]}")
            if modelo_nome == modelos_disponiveis[-1]:
                logger.error(f"[VARIAÇÕES] ❌ Todos os modelos falharam!")
                raise
            continue
    
    if not response:
        raise Exception("Falha ao gerar variações: nenhum modelo Gemini disponível")
    
    # Parser: Extrair cada variação do response
    texto_completo = response.text
    roteiros = {}
    
    logger.info(f"[VARIAÇÕES] 📝 Resposta completa tem {len(texto_completo)} caracteres")
    logger.info(f"[VARIAÇÕES] 🔍 Iniciando parser de variações...")
    
    # Regex para encontrar variações com mais flexibilidade
    import re
    
    # Padrão: procura por "VARIAÇÃO X" (case insensitive, com ou sem === )
    padrao_variacao = r'\[?={0,3}\s*VARIAÇÃO\s+(\d+)[^\]]*\]?={0,3}'
    
    matches = list(re.finditer(padrao_variacao, texto_completo, re.IGNORECASE))
    
    if not matches:
        logger.warning(f"[VARIAÇÕES] ⚠️ Nenhum marcador de variação encontrado!")
        logger.warning(f"[VARIAÇÕES] Tentando fallback: dividir por tamanho...")
        
        # Fallback: dividir texto em partes iguais
        tamanho_medio = len(texto_completo) // num_variacoes
        for i in range(num_variacoes):
            inicio = i * tamanho_medio
            fim = (i + 1) * tamanho_medio if i < num_variacoes - 1 else len(texto_completo)
            roteiro = texto_completo[inicio:fim].strip()
            
            # Limpar possíveis marcadores residuais
            roteiro = re.sub(r'\[?={0,3}\s*VARIAÇÃO\s+\d+[^\]]*\]?={0,3}', '', roteiro, flags=re.IGNORECASE).strip()
            
            if roteiro:
                roteiros[f"variacao_{i+1}"] = roteiro
                logger.info(f"[VARIAÇÕES] ✅ Variação {i+1} extraída (fallback): {len(roteiro)} chars")
    
    else:
        logger.info(f"[VARIAÇÕES] 🎯 Encontrados {len(matches)} marcadores de variação")
        
        for i, match in enumerate(matches):
            num_var = match.group(1)  # Número da variação do regex
            inicio = match.end()  # Fim do marcador é o início do conteúdo
            
            # Fim é o início do próximo marcador (ou fim do texto)
            if i < len(matches) - 1:
                fim = matches[i + 1].start()
            else:
                fim = len(texto_completo)
            
            roteiro = texto_completo[inicio:fim].strip()
            
            # Limpar marcadores de fim (se houver)
            roteiro = re.sub(r'\[?={0,3}\s*FIM\s*\]?={0,3}', '', roteiro, flags=re.IGNORECASE).strip()
            roteiro = re.sub(r'\[?={0,3}\s*VARIAÇÃO\s+\d+\s+COMPLETA\s*\]?={0,3}', '', roteiro, flags=re.IGNORECASE).strip()
            
            if roteiro:
                key = f"variacao_{i+1}"
                roteiros[key] = roteiro
                logger.info(f"[VARIAÇÕES] ✅ Variação {i+1} extraída: {len(roteiro)} chars")
    
    # Validação
    if len(roteiros) < num_variacoes:
        logger.warning(f"[VARIAÇÕES] ⚠️ Apenas {len(roteiros)}/{num_variacoes} variações extraídas com sucesso")
        logger.warning(f"[VARIAÇÕES] Primeiros 500 chars da resposta: {texto_completo[:500]}")
    
    if not roteiros:
        logger.error(f"[VARIAÇÕES] ❌ ERRO: Nenhuma variação extraída!")
        logger.error(f"[VARIAÇÕES] Resposta completa (primeiros 1000 chars): {texto_completo[:1000]}")
        raise Exception("Falha ao extrair variações da resposta do modelo")
    
    # Estatísticas
    tamanhos = [len(r) for r in roteiros.values()]
    tamanho_medio = sum(tamanhos) / len(tamanhos)
    
    logger.info(f"[VARIAÇÕES] 📊 Estatísticas:")
    logger.info(f"[VARIAÇÕES]    - Variações geradas: {len(roteiros)}/{num_variacoes}")
    logger.info(f"[VARIAÇÕES]    - Tamanho médio: {tamanho_medio:.0f} chars")
    logger.info(f"[VARIAÇÕES]    - Variação de tamanho: {min(tamanhos)}-{max(tamanhos)} chars")
    logger.info(f"[VARIAÇÕES]    - Modelo usado: {modelo_usado}")
    logger.info(f"[VARIAÇÕES]    - Temperature: {temperature}")
    
    return roteiros


def dividir_texto_em_chunks(texto: str, max_chars: int = 4000) -> List[str]:
    """
    Divide texto em chunks sem quebrar frases.
    Google Cloud TTS limite: 5000 chars, usamos 4000 para segurança.
    Remove quebras de linha excessivas para garantir áudio contínuo.
    
    Args:
        texto: Roteiro completo
        max_chars: Máximo de caracteres por chunk
    
    Returns:
        Lista de chunks de texto (sem quebras excessivas)
    """
    # Remover quebras de linha múltiplas e espaços extras
    # Substitui múltiplas quebras por espaço simples
    texto_limpo = ' '.join(texto.split())
    
    # Dividir por frases (usando pontos) para não quebrar no meio
    frases = []
    for sentenca in texto_limpo.split('. '):
        if sentenca.strip():
            frases.append(sentenca.strip() + '.')
    
    chunks = []
    current_chunk = ""
    
    for frase in frases:
        # Se adicionar essa frase ultrapassar o limite, criar novo chunk
        if len(current_chunk) + len(frase) + 1 <= max_chars:
            current_chunk += " " + frase if current_chunk else frase
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = frase
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Fallback: se não conseguiu dividir por frases, dividir por tamanho
    if not chunks:
        chunks = [texto_limpo[i:i+max_chars] for i in range(0, len(texto_limpo), max_chars)]
    
    logger.info(f"[TTS CHUNKS] Texto dividido em {len(chunks)} chunks (contínuos, sem pausas)")
    for i, chunk in enumerate(chunks):
        logger.debug(f"[TTS CHUNK {i+1}] {len(chunk)} chars: {chunk[:100]}...")
    
    return chunks


async def gerar_audio_gemini_tts(
    texto: str,
    idioma: str,
    api_key: str,
    speaker: str = "Callirhoe",
    model_name: str = "gemini-2.5-flash-tts",
    prompt_style: str = "Say the following in a natural and engaging way"
) -> bytes:
    """
    Gera áudio usando Gemini TTS API.
    
    Args:
        texto: roteiro completo
        idioma: código do idioma (ex: "pt-BR")
        api_key: API Key do Gemini TTS
        speaker: nome do speaker (ex: "Callirhoe", "Orus")
        model_name: "gemini-2.5-flash-tts" (rápido) ou "gemini-2.5-pro-tts" (qualidade)
        prompt_style: instruções de estilo para o TTS
    
    Returns:
        Bytes do arquivo de áudio completo
    """
    logger.info(f"[GEMINI TTS] Gerando áudio para {idioma} com speaker {speaker}")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        # Divide texto em chunks (Gemini TTS também tem limite)
        chunks = dividir_texto_em_chunks(texto, max_chars=4000)
        
        audio_segments = []
        for idx, chunk in enumerate(chunks, 1):
            logger.info(f"[GEMINI TTS] Processando chunk {idx}/{len(chunks)} ({len(chunk)} chars)")
            
            # Prompt para Gemini TTS
            full_prompt = f"{prompt_style}\n\n{chunk}"
            
            response = await model.generate_content_async(
                full_prompt,
                generation_config={
                    "speaker": speaker,
                    "response_mime_type": "audio/mp3"
                }
            )
            
            # Extrai bytes do áudio da resposta
            if hasattr(response, 'audio'):
                audio_segments.append(response.audio)
            else:
                logger.warning(f"[GEMINI TTS] Chunk {idx} não retornou áudio")
        
        # Une todos os segmentos
        audio_completo = b''.join(audio_segments)
        logger.info(f"[GEMINI TTS] Áudio gerado: {len(audio_completo)} bytes")
        
        return audio_completo
        
    except Exception as e:
        logger.error(f"[GEMINI TTS] Erro ao gerar áudio: {str(e)}")
        return b''  # Retorna vazio mas não quebra pipeline


def calcular_duracao_mp3(file_path: str) -> float:
    """
    Calcula a duração de um arquivo MP3 em segundos.
    
    Args:
        file_path: Caminho absoluto ou relativo para o arquivo MP3
    
    Returns:
        Duração em segundos (float), ou 0.0 se falhar
    """
    try:
        from mutagen.mp3 import MP3
        from mutagen.mp3 import HeaderNotFoundError
        
        audio = MP3(file_path)
        duration = audio.info.length
        return duration
        
    except (HeaderNotFoundError, Exception) as e:
        logger.warning(f"[DURACAO MP3] Não foi possível calcular duração de {file_path}: {e}")
        return 0.0


async def gerar_audio_google_tts(
    texto: str,
    idioma: str,
    voice_id: str,
    speaking_rate: float = 0.95,
    pitch: int = 0,
    api_key: str = None
) -> bytes:
    """
    Gera áudio usando Google Cloud TTS.
    
    Args:
        texto: roteiro completo
        idioma: código do idioma (ex: "pt-BR")
        voice_id: ID da voz (ex: "pt-BR-Neural2-B")
        speaking_rate: velocidade (0.25-4.0)
        pitch: tom (-20 a 20)
        api_key: API Key do Google Cloud TTS (opcional, usa credenciais padrão se não fornecido)
    
    Returns:
        Bytes do arquivo MP3 completo (ou bytes vazios em modo demo)
    """
    try:
        from google.cloud import texttospeech
        from google.api_core import client_options as client_options_lib
        from google.auth.credentials import Credentials
    except ImportError:
        logger.warning("[TTS] Google Cloud TTS não instalado - modo demo")
        return b''  # Retorna vazio mas não quebra o pipeline
    
    # TAREFA 4: Validação de comprimento de texto
    texto_len = len(texto)
    logger.info(f"[TTS] Gerando áudio para {idioma} com voz {voice_id} ({texto_len} chars)")
    
    if texto_len > 50000:
        logger.warning(f"[TTS] ⚠️ Roteiro muito longo ({texto_len} chars). Recomendado: <50K. Tempo estimado: {texto_len / 1000:.1f} minutos")
    
    if texto_len > 100000:
        raise Exception(f"[TTS] ❌ Roteiro excede limite máximo de 100.000 chars (recebido: {texto_len}). Divida o roteiro em partes menores.")
    
    try:
        # Configurar cliente com API Key se fornecida
        if api_key:
            logger.info("[TTS] Usando API Key fornecida")
            client_opts = client_options_lib.ClientOptions(
                api_key=api_key
            )
            client = texttospeech.TextToSpeechClient(client_options=client_opts)
        else:
            logger.info("[TTS] Usando credenciais padrão (GOOGLE_APPLICATION_CREDENTIALS)")
            client = texttospeech.TextToSpeechClient()
        
        # Divide texto em chunks
        chunks = dividir_texto_em_chunks(texto, max_chars=4000)
        
        audio_segments = []
        for idx, chunk in enumerate(chunks, 1):
            logger.info(f"[TTS] Processando chunk {idx}/{len(chunks)} ({len(chunk)} chars)")
            
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code=idioma,
                name=voice_id
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speaking_rate,
                pitch=pitch,
                sample_rate_hertz=24000,
                effects_profile_id=["medium-bluetooth-speaker-class-device"]
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            audio_segments.append(response.audio_content)
        
        # Une todos os segmentos
        audio_completo = b''.join(audio_segments)
        logger.info(f"[TTS] Áudio gerado: {len(audio_completo)} bytes")
        
        return audio_completo
        
    except Exception as e:
        # Modo demo: se der erro de credenciais ou API, retorna vazio mas não quebra
        error_msg = str(e).lower()
        if "credentials" in error_msg or "authentication" in error_msg or "permission" in error_msg or "500" in error_msg or "internal error" in error_msg or "api key" in error_msg:
            logger.warning(f"[TTS] ⚠️ Modo demo ativado - TTS desabilitado: {str(e)[:200]}")
            return b''  # Retorna vazio mas pipeline continua
        else:
            # Outros erros são relançados
            logger.error(f"[TTS] ❌ Erro ao gerar áudio: {str(e)}")
            raise


# =================================================================
# == FUNÇÕES AUXILIARES PARA VOZES                               ==
# =================================================================

LANGUAGE_NAMES = {
    "pt-BR": "Português (Brasil)",
    "pt-PT": "Português (Portugal)",
    "fr-FR": "Français",
    "ar-XA": "العربية",
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "es-ES": "Español",
    "de-DE": "Deutsch",
    "it-IT": "Italiano",
    "ja-JP": "日本語",
    "ko-KR": "한국어",
    "zh-CN": "中文",
    "hi-IN": "हिन्दी",
    "ru-RU": "Русский"
}

def get_language_name(language_code: str) -> str:
    """Retorna nome legível do idioma"""
    return LANGUAGE_NAMES.get(language_code, language_code)


def extract_voice_type(voice_name: str) -> str:
    """Extrai tipo de voz do nome"""
    if "Neural2" in voice_name:
        return "Neural2"
    elif "Wavenet" in voice_name or "WaveNet" in voice_name:
        return "WaveNet"
    elif "Chirp" in voice_name:
        return "Chirp 3 HD"
    elif "Studio" in voice_name:
        return "Studio"
    elif "Polyglot" in voice_name:
        return "Polyglot"
    else:
        return "Standard"


# =================================================================
# == Configuração da Aplicação                                   ==
# =================================================================

# --- Configuração da Aplicação ---
app = FastAPI(
    title="API Gerador de Roteiros com Jobs",
    description="Uma API que processa roteiros em background usando um banco de dados."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization", "X-API-Key"],
)

# Incluir router de batch endpoints
app.include_router(batch_endpoints.router)

# Configuração de arquivos estáticos com caminho absoluto (funciona na AWS)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- Handler de Erros de Validação ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"[VALIDATION ERROR] URL: {request.url}")
    logger.error(f"[VALIDATION ERROR] Body: {await request.body()}")
    logger.error(f"[VALIDATION ERROR] Errors: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# --- Lógica de Geração (Atualizada para usar o DB) ---

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def _chamar_api_com_tentativas(model, prompt: str, max_tentativas: int = 3) -> str:
    """Função auxiliar que chama a API e retorna o texto ou levanta uma exceção."""
    for i in range(max_tentativas):
        try:
            response = await model.generate_content_async(prompt)
            if response and response.parts:
                return response.text
            else:
                raise Exception("Resposta vazia ou bloqueada pela API.")
        except Exception as e:
            if i < max_tentativas - 1:
                await asyncio.sleep(2)
            else:
                raise e
    raise Exception(f"Falha na API após {max_tentativas} tentativas.")

def sanitizar_nome_arquivo(titulo: str, max_length: int = 50) -> str:
    """
    Converte título em nome de arquivo seguro.
    
    Exemplo:
        "Uma criança de 7 anos, órfã..." → "Uma_crianca_de_7_anos_orfa"
    """
    import unicodedata
    import re
    
    # Remover acentos
    titulo_normalizado = unicodedata.normalize('NFD', titulo)
    titulo_sem_acento = ''.join(char for char in titulo_normalizado if unicodedata.category(char) != 'Mn')
    
    # Remover caracteres especiais, manter apenas letras, números, espaços e hífens
    titulo_limpo = re.sub(r'[^\w\s-]', '', titulo_sem_acento)
    
    # Substituir espaços por underscores
    titulo_limpo = re.sub(r'\s+', '_', titulo_limpo.strip())
    
    # Limitar comprimento
    if len(titulo_limpo) > max_length:
        titulo_limpo = titulo_limpo[:max_length].rstrip('_')
    
    return titulo_limpo or "roteiro"

async def run_generation_task(job_id: str, request: schemas.GenerationRequest, api_key: str):
    """
    Esta é a função que roda em background.
    Ela atualiza o status do job no banco de dados.
    
    PIPELINE DE GERAÇÃO (REFATORADO):
    1. Gerar premissa estratégica
    2. Segmentar estrutura de blocos (manual ou automático)
    3. Gerar cada bloco sequencialmente com contexto acumulativo
    4. Finalizar e salvar resultado
    """
    db = SessionLocal()
    try:
        # 1. Configurar o modelo de IA
        genai.configure(api_key=api_key)
        generation_config = {"temperature": 0.8, "max_output_tokens": 8192}
        model = genai.GenerativeModel(request.modelo_ia, generation_config=generation_config)
        agente = request.agente_config
        
        # 1.5. Buscar TTS API Key do usuário (se disponível)
        db_job = get_db_job(db, job_id)
        owner_email = db_job.owner_email if db_job else None
        tts_api_key = None
        
        if owner_email:
            # Buscar primeira TTS key ativa do usuário
            tts_keys = db.query(models.TtsApiKey).filter(
                models.TtsApiKey.owner_email == owner_email
            ).all()
            
            if tts_keys:
                tts_api_key = tts_keys[0].key
                logger.info(f"[JOB {job_id}] TTS API Key encontrada para {owner_email}")
            else:
                logger.warning(f"[JOB {job_id}] Nenhuma TTS API Key encontrada para {owner_email} - modo demo")
        
        # 2. Atualizar status para "rodando"
        update_job_status(db, job_id, status='running', message='Iniciando geração...')

        # --- ESTÁGIO 1: GERAÇÃO DA PREMISSA ---
        update_job_status(db, job_id, status='running', message="Estágio 1/3: Gerando Premissa Estratégica...")
        
        prompt1 = f"""{agente.premise_prompt}

**INSTRUÇÃO OBRIGATÓRIA:** O idioma de toda a geração deve ser **{agente.idioma}**.

TÍTULO DO VÍDEO: '{request.titulo}'"""
        
        premissa_detalhada = await _chamar_api_com_tentativas(model, prompt1)
        update_job_status(db, job_id, status='running', message="Premissa gerada com sucesso!")

        # --- ESTÁGIO 2: SEGMENTAÇÃO DA ESTRUTURA ---
        update_job_status(
            db, job_id, status='running', 
            message="Estágio 2/3: Analisando e segmentando estrutura de blocos..."
        )
        
        try:
            blocos = segmentar_narrativa_em_blocos(
                texto=agente.block_structure_prompt,
                idioma=agente.idioma
            )
            
            estrategia = blocos[0]['tipo_demarcacao'] if blocos else 'desconhecida'
            update_job_status(
                db, job_id, status='running',
                message=f"Segmentação concluída: {len(blocos)} blocos detectados (estratégia: {estrategia})"
            )
            
        except Exception as e:
            error_msg = f"Falha na segmentação de blocos: {e}"
            logger.error(f"[JOB {job_id}] {error_msg}")
            update_job_status(db, job_id, status='failed', message=error_msg, resultado_final=error_msg)
            return

        # --- ESTÁGIO 3: GERAÇÃO EM BLOCOS ---
        update_job_status(
            db, job_id, status='running', 
            message="Estágio 3/3: Construindo Roteiro Final (Bloco a Bloco)..."
        )
        
        roteiro_acumulado = ""
        total_blocos = len(blocos)
        
        for bloco in blocos:
            i = bloco['numero_bloco']
            nome_bloco = bloco['titulo_bloco']
            tipo = bloco['tipo_demarcacao']
            
            update_job_status(
                db, job_id, status='running',
                message=f"Gerando Bloco {i}/{total_blocos}: '{nome_bloco}' (tipo: {tipo})..."
            )
            
            # Contexto: últimos 2000 chars do roteiro acumulado
            contexto = roteiro_acumulado[-2000:] if roteiro_acumulado else "(Início do roteiro)"
            
            # PROMPT DIFERENCIADO: Manual vs. Auto
            if tipo == 'manual':
                # Formato antigo: PARTE, META, REGRAS explícitas
                meta = bloco.get('meta', '')
                regras = bloco.get('regras', '')
                
                prompt_bloco = f"""{agente.persona_and_global_rules_prompt}

**INSTRUÇÃO OBRIGATÓRIA:** O idioma de toda a geração deve ser **{agente.idioma}**.

**BRIEFING CRIATIVO (PREMISSA GERADA):**
{premissa_detalhada}

**CONTEXTO (ÚLTIMO TRECHO ESCRITO):**
{contexto}

**TAREFA ATUAL (BLOCO {i}/{total_blocos}: {nome_bloco}):**
Sua tarefa agora é escrever APENAS este bloco da narrativa, continuando a partir do contexto. Siga as regras e metas com precisão. Seja expansivo e detalhado para atingir a meta de caracteres.
- METAS: {meta}
- REGRAS: {regras}

Comece a escrever a continuação da narrativa agora.
"""
            else:
                # Formato automático: sem META/REGRAS, usa guia contextual
                conteudo_bloco_guia = bloco['conteudo'][:500]  # Primeiros 500 chars como guia
                
                prompt_bloco = f"""{agente.persona_and_global_rules_prompt}

**INSTRUÇÃO OBRIGATÓRIA:** O idioma de toda a geração deve ser **{agente.idioma}**.

**BRIEFING CRIATIVO (PREMISSA GERADA):**
{premissa_detalhada}

**CONTEXTO (ÚLTIMO TRECHO ESCRITO):**
{contexto}

**TAREFA ATUAL (BLOCO {i}/{total_blocos}: {nome_bloco}):**
Continue a narrativa de forma natural e fluida. Este é o bloco {i} de {total_blocos} no roteiro.

GUIA TEMÁTICO (referência do que deve ser abordado neste bloco):
{conteudo_bloco_guia}

Escreva de forma expansiva e detalhada (~1200-1600 caracteres), mantendo coesão com o contexto anterior.
"""
            
            try:
                resultado_bloco = await _chamar_api_com_tentativas(model, prompt_bloco)
                roteiro_acumulado += resultado_bloco + "\n\n"
                
                logger.info(
                    f"[JOB {job_id}] Bloco {i}/{total_blocos} gerado "
                    f"({len(resultado_bloco)} chars, tipo: {tipo})"
                )
                
            except Exception as e:
                error_msg = f"Erro ao gerar bloco {i}: {e}"
                logger.error(f"[JOB {job_id}] {error_msg}")
                update_job_status(db, job_id, status='failed', message=error_msg, resultado_final=error_msg)
                return
        
        # 3. Finalizar e salvar o resultado
        roteiro_final = roteiro_acumulado.strip()
        idioma_master = agente.idioma
        
        # Detectar número de variações solicitadas
        num_variacoes = getattr(request, 'num_variacoes', 1)
        logger.info(f"[JOB {job_id}] Número de variações solicitadas: {num_variacoes}")
        
        # Salvar roteiro master
        db_job = get_db_job(db, job_id)
        db_job.roteiro_master = roteiro_final
        db_job.num_variacoes = num_variacoes  # Salvar número de variações no banco
        db.commit()
        
        update_job_status(
            db, job_id,
            status='running',
            message=f"Roteiro Master ({idioma_master}) concluído! {len(roteiro_final)} caracteres"
        )
        
        logger.info(f"[JOB {job_id}] Roteiro master salvo: {len(roteiro_final)} chars")
        
        # ============================================================
        # === NOVO: ESTÁGIO 2.3 - GERAÇÃO DE MÚLTIPLAS VARIAÇÕES ===
        # ============================================================
        
        if num_variacoes > 1:
            logger.info(f"[JOB {job_id}] 🎬 Iniciando geração de {num_variacoes} variações diferentes")
            
            update_job_status(
                db, job_id, status='running',
                message=f"Estágio 2.3: Gerando {num_variacoes} variações genuinamente diferentes..."
            )
            
            try:
                # Gerar N variações diferentes do roteiro
                variacoes_masters = await gerar_variacoes_roteiro(
                    titulo=request.titulo,
                    num_variacoes=num_variacoes,
                    agente_config=agente,
                    api_key=api_key,
                    temperature=0.95
                )
                
                logger.info(f"[JOB {job_id}] ✅ {len(variacoes_masters)} variações geradas com sucesso!")
                
                # Estrutura para armazenar roteiros e áudios por variação
                roteiros_por_variacao = {}
                audios_por_variacao = {}
                
                # Para cada variação, fazer adaptação cultural + TTS
                idiomas_alvo = getattr(agente, 'idiomas_alvo', None) or []
                
                for var_key, roteiro_var_master in variacoes_masters.items():
                    var_num = var_key.split('_')[1]  # Ex: "variacao_1" -> "1"
                    
                    logger.info(f"[JOB {job_id}] 📝 Processando {var_key}: {len(roteiro_var_master)} chars")
                    
                    update_job_status(
                        db, job_id, status='running',
                        message=f"Processando Variação {var_num}/{num_variacoes}: Adaptando para idiomas..."
                    )
                    
                    # Dict para armazenar roteiros desta variação em cada idioma
                    roteiros_var = {
                        idioma_master: roteiro_var_master  # Roteiro master original
                    }
                    
                    # Adaptar para cada idioma alvo
                    if idiomas_alvo and len(idiomas_alvo) > 0:
                        for idioma in idiomas_alvo:
                            try:
                                update_job_status(
                                    db, job_id, status='running',
                                    message=f"Variação {var_num}: Adaptando para {idioma}..."
                                )
                                
                                cultural_configs = getattr(agente, 'cultural_configs', {}) or {}
                                cultural_config = cultural_configs.get(idioma, {})
                                base_prompt = getattr(agente, 'cultural_adaptation_prompt', '') or ''
                                
                                roteiro_adaptado = await adaptar_culturalmente(
                                    roteiro_master=roteiro_var_master,
                                    idioma_master=idioma_master,
                                    idioma_alvo=idioma,
                                    cultural_config=cultural_config,
                                    base_prompt=base_prompt,
                                    api_key=api_key
                                )
                                
                                roteiros_var[idioma] = roteiro_adaptado
                                
                                logger.info(f"[JOB {job_id}] ✅ {var_key} adaptado para {idioma}: {len(roteiro_adaptado)} chars")
                                
                            except Exception as e:
                                error_msg = f"Erro ao adaptar {var_key} para {idioma}: {str(e)}"
                                logger.error(f"[JOB {job_id}] {error_msg}")
                                update_job_status(db, job_id, status='running', message=f"⚠️ {error_msg}")
                    
                    # Salvar roteiros desta variação
                    roteiros_por_variacao[var_key] = roteiros_var
                    
                    # Gerar áudios para cada idioma desta variação
                    update_job_status(
                        db, job_id, status='running',
                        message=f"Variação {var_num}: Gerando áudios para {len(roteiros_var)} idioma(s)..."
                    )
                    
                    audios_var = {}
                    
                    import os
                    os.makedirs("static/audio", exist_ok=True)
                    
                    for idioma, roteiro in roteiros_var.items():
                        try:
                            update_job_status(
                                db, job_id, status='running',
                                message=f"Variação {var_num}: Gerando áudio {idioma}..."
                            )
                            
                            # Extrair configurações de voz
                            cultural_configs = getattr(agente, 'cultural_configs', {}) or {}
                            config = cultural_configs.get(idioma, {})
                            
                            default_voices = getattr(agente, 'default_voices', {}) or {}
                            voice_config = default_voices.get(idioma, "fr-FR-Neural2-B")
                            
                            # Suportar tanto string simples quanto dict completo
                            if isinstance(voice_config, str):
                                voice_id = voice_config
                                speaking_rate = config.get('speaking_rate', 0.95)
                                pitch = config.get('pitch', 0)
                            elif isinstance(voice_config, dict):
                                voice_id = voice_config.get('voice_id', 'fr-FR-Neural2-B')
                                speaking_rate = voice_config.get('speaking_rate', 0.95)
                                pitch = voice_config.get('pitch', 0)
                            else:
                                voice_id = "fr-FR-Neural2-B"
                                speaking_rate = 0.95
                                pitch = 0
                            
                            logger.info(f"[TTS {var_key}] {idioma}: {len(roteiro)} chars | Voice: {voice_id}")
                            
                            # Gerar áudio (com TTS API Key se disponível)
                            audio_bytes = await gerar_audio_google_tts(
                                texto=roteiro,
                                idioma=idioma,
                                voice_id=voice_id,
                                speaking_rate=speaking_rate,
                                pitch=pitch,
                                api_key=tts_api_key
                            )
                            
                            # Salvar arquivo com título sanitizado + sufixo da variação
                            titulo_sanitizado = sanitizar_nome_arquivo(request.titulo, max_length=40)
                            audio_filename = f"{titulo_sanitizado}_{var_key}_{idioma.replace('-', '_')}.mp3"
                            audio_path = f"static/audio/{audio_filename}"
                            
                            with open(audio_path, 'wb') as f:
                                f.write(audio_bytes)
                            
                            # NOVO: Calcular duração do MP3
                            duracao_audio = calcular_duracao_mp3(audio_path)
                            
                            audios_var[idioma] = f"/{audio_path}"
                            
                            logger.info(f"[TTS {var_key}] ✅ {idioma}: {len(audio_bytes)} bytes, {duracao_audio:.1f}s → {audio_path}")
                            
                        except Exception as e:
                            error_msg = f"Erro ao gerar áudio {var_key}/{idioma}: {str(e)}"
                            logger.error(f"[JOB {job_id}] {error_msg}")
                            update_job_status(db, job_id, status='running', message=f"⚠️ {error_msg}")
                    
                    # Salvar áudios desta variação
                    audios_por_variacao[var_key] = audios_var
                    
                    logger.info(f"[JOB {job_id}] ✅ {var_key} completa: {len(roteiros_var)} roteiros + {len(audios_var)} áudios")
                
                # Salvar estruturas completas no banco
                db_job.roteiros_por_variacao = roteiros_por_variacao
                db_job.audios_por_variacao = audios_por_variacao
                db.commit()
                
                # Estatísticas finais
                total_roteiros = sum(len(r) for r in roteiros_por_variacao.values())
                total_audios = sum(len(a) for a in audios_por_variacao.values())
                
                logger.info(f"[JOB {job_id}] ============ RESUMO MÚLTIPLAS VARIAÇÕES ============")
                logger.info(f"[JOB {job_id}] Total de variações: {num_variacoes}")
                logger.info(f"[JOB {job_id}] Total de roteiros: {total_roteiros}")
                logger.info(f"[JOB {job_id}] Total de áudios: {total_audios}")
                for var_key in roteiros_por_variacao.keys():
                    num_rots = len(roteiros_por_variacao[var_key])
                    num_auds = len(audios_por_variacao.get(var_key, {}))
                    logger.info(f"[JOB {job_id}] ✅ {var_key}: {num_rots} roteiros + {num_auds} áudios")
                logger.info(f"[JOB {job_id}] ====================================================")
                
                update_job_status(
                    db, job_id,
                    status='completed',
                    message=f"✅ Concluído! {num_variacoes} variações × {total_roteiros//num_variacoes} idiomas = {total_roteiros} roteiros + {total_audios} áudios",
                    resultado_final=roteiro_final
                )
                
                logger.info(f"[JOB {job_id}] 🎉 Geração de múltiplas variações concluída com sucesso!")
                
                # Retornar ANTES do fluxo de variação única
                return
                
            except Exception as e:
                error_msg = f"Erro ao gerar múltiplas variações: {str(e)}"
                logger.error(f"[JOB {job_id}] {error_msg}")
                update_job_status(db, job_id, status='failed', message=error_msg, resultado_final=error_msg)
                return
        
        # ============================================================
        # === FLUXO ORIGINAL: UMA ÚNICA VARIAÇÃO (num_variacoes=1) ==
        # ============================================================
        
        # --- ESTÁGIO 2.5: ADAPTAÇÃO CULTURAL MULTI-IDIOMA ---
        idiomas_alvo = getattr(agente, 'idiomas_alvo', None) or []
        logger.info(f"[JOB {job_id}] Idiomas alvo detectados: {idiomas_alvo}")
        logger.info(f"[JOB {job_id}] Tipo de idiomas_alvo: {type(idiomas_alvo)}")
        
        if idiomas_alvo and len(idiomas_alvo) > 0:
            roteiros_adaptados = {}
            total_idiomas = len(idiomas_alvo)
            
            update_job_status(
                db, job_id, status='running',
                message=f"Estágio 2.5: Adaptando para {total_idiomas} idioma(s)..."
            )
            
            for idx, idioma in enumerate(idiomas_alvo, 1):
                try:
                    update_job_status(
                        db, job_id, status='running',
                        message=f"Stage 2.5 ({idx}/{total_idiomas}): Adaptando para {idioma}..."
                    )
                    
                    cultural_configs = getattr(agente, 'cultural_configs', {}) or {}
                    cultural_config = cultural_configs.get(idioma, {})
                    base_prompt = getattr(agente, 'cultural_adaptation_prompt', '') or ''
                    
                    roteiro_adaptado = await adaptar_culturalmente(
                        roteiro_master=roteiro_final,
                        idioma_master=idioma_master,
                        idioma_alvo=idioma,
                        cultural_config=cultural_config,
                        base_prompt=base_prompt,
                        api_key=api_key
                    )
                    
                    # TAREFA 4: Log de comprimento após adaptação
                    logger.info(f"[JOB {job_id}] Roteiro {idioma} adaptado: {len(roteiro_adaptado)} chars (original: {len(roteiro_final)} chars)")
                    
                    roteiros_adaptados[idioma] = roteiro_adaptado
                    
                    update_job_status(
                        db, job_id, status='running',
                        message=f"✅ Adaptação para {idioma} concluída ({len(roteiro_adaptado)} chars)"
                    )
                    
                except Exception as e:
                    error_msg = f"Erro ao adaptar para {idioma}: {str(e)}"
                    logger.error(f"[JOB {job_id}] {error_msg}")
                    update_job_status(db, job_id, status='running', message=f"⚠️ {error_msg}")
                    # Continua com outros idiomas
            
            # Salvar roteiros adaptados
            db_job.roteiros_adaptados = roteiros_adaptados
            db.commit()
            
            logger.info(f"[JOB {job_id}] {len(roteiros_adaptados)} roteiros adaptados salvos")
            
            # Log consolidado de todos os tamanhos
            logger.info(f"[JOB {job_id}] ============ RESUMO DE TAMANHOS ============")
            logger.info(f"[JOB {job_id}] Roteiro Master ({idioma_master}): {len(roteiro_final)} chars")
            for idioma, roteiro in roteiros_adaptados.items():
                diff_pct = abs(len(roteiro) - len(roteiro_final)) / len(roteiro_final) * 100
                status_icon = "✅" if diff_pct <= 10 else "⚠️"
                logger.info(f"[JOB {job_id}] {status_icon} Roteiro {idioma}: {len(roteiro)} chars ({diff_pct:+.1f}%)")
            logger.info(f"[JOB {job_id}] ============================================")
            
            # --- ESTÁGIO 3: TTS MULTI-IDIOMA ---
            update_job_status(
                db, job_id, status='running',
                message=f"Estágio 3: Gerando áudios para {len(roteiros_adaptados)} idioma(s)..."
            )
            
            audios_gerados = {}
            total_chars_tts = 0
            duracao_total_segundos = 0.0  # NOVO: acumular duração
            
            import os
            os.makedirs("static/audio", exist_ok=True)
            
            for idx, (idioma, roteiro) in enumerate(roteiros_adaptados.items(), 1):
                try:
                    update_job_status(
                        db, job_id, status='running',
                        message=f"Stage 3 ({idx}/{len(roteiros_adaptados)}): Gerando áudio {idioma}..."
                    )
                    
                    # Extrair configurações de voz
                    cultural_configs = getattr(agente, 'cultural_configs', {}) or {}
                    config = cultural_configs.get(idioma, {})
                    
                    default_voices = getattr(agente, 'default_voices', {}) or {}
                    voice_config = default_voices.get(idioma, "fr-FR-Neural2-B")
                    
                    # Suportar tanto string simples quanto dict completo
                    if isinstance(voice_config, str):
                        voice_id = voice_config
                        speaking_rate = config.get('speaking_rate', 0.95)
                        pitch = config.get('pitch', 0)
                    elif isinstance(voice_config, dict):
                        voice_id = voice_config.get('voice_id', 'fr-FR-Neural2-B')
                        speaking_rate = voice_config.get('speaking_rate', 0.95)
                        pitch = voice_config.get('pitch', 0)
                    else:
                        # Fallback
                        voice_id = "fr-FR-Neural2-B"
                        speaking_rate = 0.95
                        pitch = 0
                    
                    logger.info(f"[TTS {idx}/{len(roteiros_adaptados)}] Iniciando {idioma}")
                    logger.info(f"[TTS {idx}/{len(roteiros_adaptados)}] Texto: {len(roteiro)} chars | Voice: {voice_id} | Rate: {speaking_rate} | Pitch: {pitch}")
                    
                    # Gerar áudio (com TTS API Key se disponível)
                    audio_bytes = await gerar_audio_google_tts(
                        texto=roteiro,
                        idioma=idioma,
                        voice_id=voice_id,
                        speaking_rate=speaking_rate,
                        pitch=pitch,
                        api_key=tts_api_key
                    )
                    
                    # Salvar arquivo com título sanitizado
                    titulo_sanitizado = sanitizar_nome_arquivo(request.titulo, max_length=40)
                    audio_filename = f"{titulo_sanitizado}_{idioma.replace('-', '_')}.mp3"
                    audio_path = f"static/audio/{audio_filename}"
                    
                    with open(audio_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    # NOVO: Calcular duração do MP3
                    duracao_audio = calcular_duracao_mp3(audio_path)
                    duracao_total_segundos += duracao_audio
                    
                    audios_gerados[idioma] = f"/{audio_path}"
                    total_chars_tts += len(roteiro)
                    
                    logger.info(f"[TTS {idx}/{len(roteiros_adaptados)}] ✅ {idioma} concluído: {len(audio_bytes)} bytes, {duracao_audio:.1f}s → {audio_path}")
                    
                    update_job_status(
                        db, job_id, status='running',
                        message=f"✅ Áudio {idioma} gerado: {len(audio_bytes)} bytes ({voice_id})"
                    )
                    
                except Exception as e:
                    error_msg = f"Erro ao gerar áudio para {idioma}: {str(e)}"
                    logger.error(f"[JOB {job_id}] {error_msg}")
                    update_job_status(db, job_id, status='running', message=f"⚠️ {error_msg}")
                    # Continua com outros idiomas
            
            # Atualizar Job com resultados finais
            db_job.audios_gerados = audios_gerados
            db_job.chars_processados_tts = total_chars_tts
            db_job.duracao_total_segundos = int(duracao_total_segundos)  # NOVO: salvar duração
            db.commit()
            
            # Resumo final consolidado
            logger.info(f"[JOB {job_id}] ============ RESUMO FINAL TTS ============")
            logger.info(f"[JOB {job_id}] Total de áudios gerados: {len(audios_gerados)}")
            logger.info(f"[JOB {job_id}] Total de chars processados: {total_chars_tts}")
            logger.info(f"[JOB {job_id}] Duração total dos áudios: {duracao_total_segundos:.1f}s ({duracao_total_segundos/60:.1f} minutos)")
            for idioma, audio_path in audios_gerados.items():
                len_roteiro = len(roteiros_adaptados.get(idioma, ''))
                logger.info(f"[JOB {job_id}] ✅ {idioma}: {len_roteiro} chars → {audio_path}")
            logger.info(f"[JOB {job_id}] ===========================================")
            
            update_job_status(
                db, job_id,
                status='completed',
                message=f"✅ Concluído! {len(roteiros_adaptados)} roteiros + {len(audios_gerados)} áudios gerados. Total chars TTS: {total_chars_tts}",
                resultado_final=roteiro_final
            )
        else:
            # Sem adaptação cultural, apenas finaliza
            update_job_status(
                db, job_id,
                status='completed',
                message=f"Roteiro Final concluído! (Total: {len(roteiro_final)} caracteres, {total_blocos} blocos processados)",
                resultado_final=roteiro_final
            )
        
        logger.info(
            f"[JOB {job_id}] Geração concluída com sucesso: "
            f"{total_blocos} blocos, {len(roteiro_final)} chars totais"
        )

    except Exception as e:
        # 4. Em caso de erro, salvar o status de falha
        error_message = f"Erro fatal durante a geração: {e}"
        logger.error(f"[JOB {job_id}] {error_message}")
        update_job_status(db, job_id, status='failed', message=error_message, resultado_final=error_message)
    finally:
        db.close()

# --- Endpoints de Autenticação (Atualizados) ---
@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_create: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_email(db, user_create.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")
    create_db_user(db, user_create)
    return {"message": "Usuário criado com sucesso!"}

# --- Dependência de Usuário Autenticado (Atualizada) ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais de usuário inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return user

# --- Endpoints de Geração (Atualizados) ---
@app.post("/gerar-roteiro", response_model=schemas.JobCreationResponse)
async def gerar_roteiro_endpoint(
    request: schemas.GenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    api_key: str | None = Header(None, alias="X-API-Key")
):
    if not api_key:
        raise HTTPException(status_code=400, detail="A API Key do Gemini não foi fornecida.")
    
    job_id = str(uuid.uuid4())
    create_db_job(db, job_id=job_id, owner_email=current_user.email, titulo=request.titulo)
    
    background_tasks.add_task(run_generation_task, job_id, request, api_key)
    return schemas.JobCreationResponse(job_id=job_id)

@app.get("/status/{job_id}", response_model=schemas.JobResponse)
async def get_status_endpoint(
    job_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    db_job = get_db_job(db, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    
    # Garante que o usuário só possa ver seus próprios jobs
    if db_job.owner_email != current_user.email:
        raise HTTPException(status_code=403, detail="Não autorizado a ver este job.")
        
    return schemas.JobResponse(
        id=db_job.id,
        status=db_job.status,
        titulo=db_job.titulo,
        log=json.loads(db_job.log),
        resultado=db_job.resultado,
        roteiro_master=db_job.roteiro_master,
        roteiros_adaptados=db_job.roteiros_adaptados,
        audios_gerados=db_job.audios_gerados,
        chars_processados_tts=db_job.chars_processados_tts or 0,
        duracao_total_segundos=db_job.duracao_total_segundos
    )

# --- Outros Endpoints ---
@app.post("/testar-chave")
async def testar_chave_gemini(api_key: str | None = Header(None, alias="X-API-Key")):
    """
    Valida API Key do GEMINI (Google AI Studio).
    Testa apenas modelos Gemini, não TTS.
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key não fornecida")
    
    # Normaliza a chave (remove espaços/aspas/backticks acidentais)
    key = api_key.strip().strip('"').strip("'").strip('`')
    
    # Validação básica de formato: chaves do Google AI Studio começam com 'AIza'
    if not re.match(r"^AIza[0-9A-Za-z_\-]{10,}$", key):
        logger.error(f"[TESTAR CHAVE] ❌ Formato inválido: {key[:10]}...")
        raise HTTPException(
            status_code=400,
            detail="Formato de API Key inválido. A chave deve começar com 'AIza' (I maiúsculo) e conter apenas letras, números, _ ou -"
        )

    try:
        genai.configure(api_key=key)
        
        # Tenta os modelos em ordem de prioridade: 2.5-pro → 2.0-flash → 1.5-pro (fallback robusto)
        candidatos = [
            "gemini-2.5-pro",
            "gemini-2.0-flash",
        ]
        
        ultimo_erro: str | None = None
        
        for nome in candidatos:
            try:
                logger.info(f"[TESTAR CHAVE] Testando modelo: {nome}")
                model = genai.GenerativeModel(nome)
                response = await model.generate_content_async("Responda apenas: OK")
                
                # Verifica se recebeu resposta válida
                if not response or not response.text:
                    raise Exception("Resposta vazia do modelo")
                
                logger.info(f"[TESTAR CHAVE] ✅ Modelo validado: {nome}")
                return JSONResponse(
                    content={
                        "status": "valida", 
                        "model": nome,
                        "message": f"API Key validada com sucesso usando {nome}"
                    }, 
                    status_code=200
                )
                
            except Exception as e:
                erro_msg = str(e)
                logger.warning(f"[TESTAR CHAVE] ⚠️ Modelo {nome} falhou: {erro_msg[:200]}")
                ultimo_erro = erro_msg
                
                # Se for erro de permissão/autenticação, não tenta outros modelos
                if any(x in erro_msg.lower() for x in ["permission", "api key", "authentication", "401", "403"]):
                    logger.error(f"[TESTAR CHAVE] ❌ Erro de autenticação detectado: {erro_msg[:100]}")
                    raise HTTPException(
                        status_code=401, 
                        detail=f"API Key inválida ou sem permissão: {erro_msg[:200]}"
                    )
                continue
        
        # Se nenhum modelo funcionou (mas não foi erro de auth)
        logger.error(f"[TESTAR CHAVE] ❌ Nenhum modelo disponível. Último erro: {ultimo_erro}")
        raise HTTPException(
            status_code=503, 
            detail=f"Nenhum modelo Gemini disponível no momento. Modelos testados: {', '.join(candidatos)}. Último erro: {ultimo_erro[:200]}"
        )
        
    except HTTPException:
        # Re-raise HTTPException (já tratadas acima)
        raise
        
    except Exception as e:
        # Erros inesperados
        logger.error(f"[TESTAR CHAVE] ❌ Erro inesperado: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao validar API Key: {str(e)[:200]}"
        )


@app.post("/testar-chave-tts")
async def testar_chave_tts(api_key: str | None = Header(None, alias="X-API-Key")):
    """
    Valida API Key do GOOGLE CLOUD TTS.
    Testa apenas serviço TTS, não modelos Gemini.
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key do TTS não fornecida")
    
    # Normaliza a chave (remove espaços/aspas/backticks acidentais)
    key = api_key.strip().strip('"').strip("'").strip('`')
    
    # Validação básica de formato: chaves do Google Cloud também começam com 'AIza'
    if not re.match(r"^AIza[0-9A-Za-z_\-]{10,}$", key):
        logger.error(f"[TESTAR CHAVE TTS] ❌ Formato inválido: {key[:10]}...")
        raise HTTPException(
            status_code=400,
            detail="Formato de API Key inválido. A chave deve começar com 'AIza' (I maiúsculo) e conter apenas letras, números, _ ou -"
        )

    try:
        from google.cloud import texttospeech
        from google.api_core import client_options as client_options_lib
    except ImportError:
        logger.error("[TESTAR CHAVE TTS] ❌ google-cloud-texttospeech não instalado")
        raise HTTPException(
            status_code=500, 
            detail="Google Cloud TTS não instalado. Execute: pip install google-cloud-texttospeech"
        )

    try:
        logger.info(f"[TESTAR CHAVE TTS] Testando chave TTS...")
        
        # Configurar cliente TTS com API Key
        client_opts = client_options_lib.ClientOptions(api_key=key)
        client = texttospeech.TextToSpeechClient(client_options=client_opts)
        
        # Tentar listar vozes (operação mais leve que sintetizar)
        try:
            logger.info("[TESTAR CHAVE TTS] Tentando listar vozes...")
            response = client.list_voices(language_code="pt-BR")
            
            if not response.voices:
                raise Exception("Nenhuma voz retornada")
            
            # Contar vozes disponíveis
            total_voices = len(response.voices)
            voice_names = [v.name for v in response.voices[:3]]  # Primeiras 3 vozes
            
            logger.info(f"[TESTAR CHAVE TTS] ✅ Chave validada: {total_voices} vozes disponíveis")
            
            return JSONResponse(
                content={
                    "status": "valida", 
                    "service": "Google Cloud TTS",
                    "total_voices": total_voices,
                    "sample_voices": voice_names,
                    "message": f"API Key TTS validada com sucesso. {total_voices} vozes disponíveis."
                }, 
                status_code=200
            )
            
        except Exception as e:
            erro_msg = str(e)
            logger.error(f"[TESTAR CHAVE TTS] ❌ Erro ao listar vozes: {erro_msg[:200]}")
            
            # Se for erro de permissão/autenticação
            if any(x in erro_msg.lower() for x in ["permission", "api key", "authentication", "401", "403", "credentials"]):
                raise HTTPException(
                    status_code=401, 
                    detail=f"API Key TTS inválida ou sem permissão para Google Cloud TTS: {erro_msg[:200]}"
                )
            
            # Outros erros
            raise HTTPException(
                status_code=500, 
                detail=f"Erro ao testar serviço TTS: {erro_msg[:200]}"
            )
        
    except HTTPException:
        # Re-raise HTTPException (já tratadas acima)
        raise
        
    except Exception as e:
        # Erros inesperados
        logger.error(f"[TESTAR CHAVE TTS] ❌ Erro inesperado: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao validar API Key TTS: {str(e)[:200]}"
        )


@app.get("/register", response_model=None)
async def serve_register_page():
    return FileResponse("static/register.html")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

@app.get("/teste-usuario")
async def serve_teste_usuario():
    """Interface de teste completa para usuários"""
    return FileResponse("static/teste-usuario.html")

# ================== Endpoint de Teste para Segmentação ==================

@app.post("/testar-segmentacao")
async def testar_segmentacao_endpoint(request: dict):
    """
    Endpoint de teste para validar a segmentação automática.
    Aceita texto e idioma, retorna blocos segmentados.
    """
    try:
        texto = request.get("texto", "")
        idioma = request.get("idioma", "português")
        
        if not texto:
            raise HTTPException(status_code=400, detail="Texto não fornecido")
        
        # Chamar função de segmentação
        blocos = segmentar_narrativa_em_blocos(texto, idioma)
        
        # Retornar resultado formatado
        return {
            "total_blocos": len(blocos),
            "estrategia": blocos[0]['tipo_demarcacao'] if blocos else 'desconhecida',
            "tamanho_texto": len(texto),
            "blocos": blocos
        }
    
    except Exception as e:
        logger.error(f"Erro na segmentação de teste: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================== Persistência de Agentes e API Keys ==================

@app.get("/me/agents", response_model=List[schemas.AgentOut])
async def list_agents(current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    rows = db.query(models.Agent).filter(models.Agent.owner_email == current_user.email).all()
    return [schemas.AgentOut(
        id=r.id, name=r.name, idioma=r.idioma,
        premise_prompt=r.premise_prompt,
        persona_and_global_rules_prompt=r.persona_and_global_rules_prompt,
        block_structure_prompt=r.block_structure_prompt,
        cultural_adaptation_prompt=r.cultural_adaptation_prompt,
        idiomas_alvo=r.idiomas_alvo,
        cultural_configs=r.cultural_configs,
        default_voices=r.default_voices
    ) for r in rows]

@app.post("/me/agents", response_model=schemas.AgentOut, status_code=201)
async def create_agent(agent: schemas.AgentCreate, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    # Validar cultural_configs e default_voices antes de salvar
    validate_cultural_configs(agent.cultural_configs, agent.default_voices)
    
    row = models.Agent(
        owner_email=current_user.email,
        name=agent.name,
        idioma=agent.idioma,
        premise_prompt=agent.premise_prompt,
        persona_and_global_rules_prompt=agent.persona_and_global_rules_prompt,
        block_structure_prompt=agent.block_structure_prompt,
        # Novos campos para adaptação cultural e TTS
        cultural_adaptation_prompt=agent.cultural_adaptation_prompt,
        idiomas_alvo=agent.idiomas_alvo,
        cultural_configs=agent.cultural_configs,
        default_voices=agent.default_voices,
    )
    db.add(row); db.commit(); db.refresh(row)
    return schemas.AgentOut(
        id=row.id, name=row.name, idioma=row.idioma,
        premise_prompt=row.premise_prompt,
        persona_and_global_rules_prompt=row.persona_and_global_rules_prompt,
        block_structure_prompt=row.block_structure_prompt,
        cultural_adaptation_prompt=row.cultural_adaptation_prompt,
        idiomas_alvo=row.idiomas_alvo,
        cultural_configs=row.cultural_configs,
        default_voices=row.default_voices,
    )

@app.put("/me/agents/{agent_id}", response_model=schemas.AgentOut)
async def update_agent(agent_id: int, agent: schemas.AgentCreate, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    try:
        logger.info(f"[UPDATE AGENT] ID: {agent_id}, User: {current_user.email}")
        logger.info(f"[UPDATE AGENT] Data recebida: {agent.dict()}")
        logger.info(f"[UPDATE AGENT] default_voices recebido: {agent.default_voices}")
        
        # Validar cultural_configs e default_voices antes de atualizar
        validate_cultural_configs(agent.cultural_configs, agent.default_voices)
        
        row = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.owner_email == current_user.email).first()
        if not row:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        row.name = agent.name
        row.idioma = agent.idioma
        row.premise_prompt = agent.premise_prompt
        row.persona_and_global_rules_prompt = agent.persona_and_global_rules_prompt
        row.block_structure_prompt = agent.block_structure_prompt
        # Novos campos para adaptação cultural e TTS
        row.cultural_adaptation_prompt = agent.cultural_adaptation_prompt
        row.idiomas_alvo = agent.idiomas_alvo
        row.cultural_configs = agent.cultural_configs
        row.default_voices = agent.default_voices
        logger.info(f"[UPDATE AGENT] default_voices ANTES do commit: {row.default_voices}")
        db.commit(); db.refresh(row)
        logger.info(f"[UPDATE AGENT] default_voices DEPOIS do commit: {row.default_voices}")
        return schemas.AgentOut(
            id=row.id, name=row.name, idioma=row.idioma,
            premise_prompt=row.premise_prompt,
            persona_and_global_rules_prompt=row.persona_and_global_rules_prompt,
            block_structure_prompt=row.block_structure_prompt,
            cultural_adaptation_prompt=row.cultural_adaptation_prompt,
            idiomas_alvo=row.idiomas_alvo,
            cultural_configs=row.cultural_configs,
            default_voices=row.default_voices,
        )
    except Exception as e:
        logger.error(f"[UPDATE AGENT ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"[UPDATE AGENT TRACEBACK] {traceback.format_exc()}")
        raise

@app.delete("/me/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    row = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.owner_email == current_user.email).first()
    if not row:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    db.delete(row); db.commit()
    return JSONResponse(content=None, status_code=204)

@app.get("/me/apikeys", response_model=List[schemas.ApiKeyOut])
async def list_apikeys(current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    rows = db.query(models.ApiKey).filter(models.ApiKey.owner_email == current_user.email).all()
    return [schemas.ApiKeyOut(id=r.id, key=r.key) for r in rows]

@app.post("/me/apikeys", response_model=schemas.ApiKeyOut, status_code=201)
async def add_apikey(item: schemas.ApiKeyIn, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    row = models.ApiKey(owner_email=current_user.email, key=item.key)
    db.add(row); db.commit(); db.refresh(row)
    return schemas.ApiKeyOut(id=row.id, key=row.key)

@app.delete("/me/apikeys/{key_id}", status_code=204)
async def delete_apikey(key_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    row = db.query(models.ApiKey).filter(models.ApiKey.id == key_id, models.ApiKey.owner_email == current_user.email).first()
    if not row:
        raise HTTPException(status_code=404, detail="Chave não encontrada")
    db.delete(row); db.commit()
    return JSONResponse(content=None, status_code=204)


# =================================================================
# == ENDPOINTS DE TTS API KEYS                                   ==
# =================================================================

@app.get("/me/ttskeys", response_model=List[schemas.ApiKeyOut])
async def list_ttskeys(current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    """Lista todas as TTS API Keys do usuário"""
    rows = db.query(models.TtsApiKey).filter(models.TtsApiKey.owner_email == current_user.email).all()
    return [schemas.ApiKeyOut(id=r.id, key=r.key) for r in rows]

@app.post("/me/ttskeys", response_model=schemas.ApiKeyOut, status_code=201)
async def add_ttskey(item: schemas.ApiKeyIn, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    """Adiciona uma nova TTS API Key"""
    row = models.TtsApiKey(owner_email=current_user.email, key=item.key)
    db.add(row); db.commit(); db.refresh(row)
    return schemas.ApiKeyOut(id=row.id, key=row.key)

@app.delete("/me/ttskeys/{key_id}", status_code=204)
async def delete_ttskey(key_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Session = Depends(get_db)):
    """Remove uma TTS API Key"""
    row = db.query(models.TtsApiKey).filter(models.TtsApiKey.id == key_id, models.TtsApiKey.owner_email == current_user.email).first()
    if not row:
        raise HTTPException(status_code=404, detail="TTS Key não encontrada")
    db.delete(row); db.commit()
    return JSONResponse(content=None, status_code=204)


# =================================================================
# == ENDPOINTS DE TTS E VOZES                                    ==
# =================================================================

@app.get("/tts/voices")
async def list_all_voices():
    """Lista todas as 380+ vozes disponíveis na Google Cloud TTS"""
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="Google Cloud TTS não instalado. Execute: pip install google-cloud-texttospeech"
        )
    
    try:
        client = texttospeech.TextToSpeechClient()
        voices_response = client.list_voices()
        
        voices = []
        for voice in voices_response.voices:
            for language_code in voice.language_codes:
                voices.append({
                    "name": voice.name,
                    "language_code": language_code,
                    "language_name": get_language_name(language_code),
                    "ssml_gender": voice.ssml_gender.name,
                    "voice_type": extract_voice_type(voice.name),
                    "natural_sample_rate": voice.natural_sample_rate_hertz
                })
        
        return {
            "total_voices": len(voices),
            "voices": voices
        }
    except Exception as e:
        # Modo demo: retornar lista hardcoded se não tiver credenciais
        if "credentials" in str(e).lower() or "authentication" in str(e).lower():
            return {
                "total_voices": 12,
                "voices": [
                    {"name": "pt-BR-Neural2-A", "language_code": "pt-BR", "language_name": "Português (Brasil)", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "pt-BR-Neural2-B", "language_code": "pt-BR", "language_name": "Português (Brasil)", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "pt-BR-Neural2-C", "language_code": "pt-BR", "language_name": "Português (Brasil)", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "pt-BR-Wavenet-A", "language_code": "pt-BR", "language_name": "Português (Brasil)", "ssml_gender": "FEMALE", "voice_type": "WaveNet", "natural_sample_rate": 24000},
                    {"name": "fr-FR-Neural2-A", "language_code": "fr-FR", "language_name": "Français", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "fr-FR-Neural2-B", "language_code": "fr-FR", "language_name": "Français", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "ar-XA-Wavenet-A", "language_code": "ar-XA", "language_name": "العربية", "ssml_gender": "FEMALE", "voice_type": "WaveNet", "natural_sample_rate": 24000},
                    {"name": "ar-XA-Wavenet-B", "language_code": "ar-XA", "language_name": "العربية", "ssml_gender": "MALE", "voice_type": "WaveNet", "natural_sample_rate": 24000},
                    {"name": "en-US-Neural2-A", "language_code": "en-US", "language_name": "English (US)", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "en-US-Neural2-D", "language_code": "en-US", "language_name": "English (US)", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "es-ES-Neural2-A", "language_code": "es-ES", "language_name": "Español", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "es-ES-Neural2-B", "language_code": "es-ES", "language_name": "Español", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000}
                ],
                "note": "⚠️ Modo demo (sem credenciais Google Cloud). Para ver todas as 380+ vozes, configure GOOGLE_APPLICATION_CREDENTIALS."
            }
        raise HTTPException(status_code=500, detail=f"Erro ao listar vozes: {str(e)}")


@app.get("/tts/voices/{language_code}")
async def list_voices_by_language(language_code: str):
    """Lista vozes para um idioma específico"""
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="Google Cloud TTS não instalado. Execute: pip install google-cloud-texttospeech"
        )
    
    try:
        client = texttospeech.TextToSpeechClient()
        voices_response = client.list_voices(language_code=language_code)
        
        voices = []
        for voice in voices_response.voices:
            voices.append({
                "name": voice.name,
                "ssml_gender": voice.ssml_gender.name,
                "voice_type": extract_voice_type(voice.name),
                "natural_sample_rate": voice.natural_sample_rate_hertz
            })
        
        return {
            "language_code": language_code,
            "language_name": get_language_name(language_code),
            "total_voices": len(voices),
            "voices": voices
        }
    except Exception as e:
        # Modo demo: retornar lista hardcoded se não tiver credenciais
        if "credentials" in str(e).lower() or "authentication" in str(e).lower():
            demo_voices = {
                "pt-BR": [
                    {"name": "pt-BR-Neural2-A", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "pt-BR-Neural2-B", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "pt-BR-Neural2-C", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "pt-BR-Wavenet-A", "ssml_gender": "FEMALE", "voice_type": "WaveNet", "natural_sample_rate": 24000},
                ],
                "fr-FR": [
                    {"name": "fr-FR-Neural2-A", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "fr-FR-Neural2-B", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                ],
                "ar-XA": [
                    {"name": "ar-XA-Wavenet-A", "ssml_gender": "FEMALE", "voice_type": "WaveNet", "natural_sample_rate": 24000},
                    {"name": "ar-XA-Wavenet-B", "ssml_gender": "MALE", "voice_type": "WaveNet", "natural_sample_rate": 24000},
                ],
                "en-US": [
                    {"name": "en-US-Neural2-A", "ssml_gender": "FEMALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                    {"name": "en-US-Neural2-D", "ssml_gender": "MALE", "voice_type": "Neural2", "natural_sample_rate": 24000},
                ]
            }
            
            voices = demo_voices.get(language_code, [])
            return {
                "language_code": language_code,
                "language_name": get_language_name(language_code),
                "total_voices": len(voices),
                "voices": voices,
                "note": "⚠️ Modo demo (sem credenciais Google Cloud). Para ver todas as vozes, configure GOOGLE_APPLICATION_CREDENTIALS."
            }
        raise HTTPException(status_code=500, detail=f"Erro ao listar vozes: {str(e)}")


@app.post("/tts/test-voice")
async def test_voice(
    voice_id: str,
    language_code: str,
    text: str = "Este é um teste de voz. Como soa esta narração para você?",
    speaking_rate: float = 0.95,
    pitch: int = 0
):
    """Gera amostra de áudio de 10 segundos para testar voz"""
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="Google Cloud TTS não instalado. Execute: pip install google-cloud-texttospeech"
        )
    
    try:
        import hashlib
        import os
        
        client = texttospeech.TextToSpeechClient()
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_id
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Gera nome único
        os.makedirs("static/samples", exist_ok=True)
        
        file_hash = hashlib.md5(f"{voice_id}_{text}_{speaking_rate}_{pitch}".encode()).hexdigest()[:8]
        filename = f"test_{voice_id}_{file_hash}.mp3"
        filepath = f"static/samples/{filename}"
        
        with open(filepath, "wb") as f:
            f.write(response.audio_content)
        
        # Calcula duração aproximada (palavras / velocidade)
        words = len(text.split())
        duration_seconds = (words / 150) * 60 / speaking_rate
        
        return {
            "audio_url": f"/{filepath}",
            "duration_seconds": round(duration_seconds, 1),
            "voice_id": voice_id,
            "language_code": language_code
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar amostra: {str(e)}")


# =================================================================
# 🎯 NOVOS ENDPOINTS - MELHORIAS DE PRIORIDADE ALTA
# =================================================================

@app.get("/jobs/{job_id}/audio/{language}")
async def download_job_audio(
    job_id: str,
    language: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Download direto do áudio gerado para um idioma específico.
    Retorna o arquivo MP3 com metadata.
    """
    job = get_db_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # Verificar se áudio existe
    audios_gerados = job.audios_gerados or {}
    
    if language not in audios_gerados:
        raise HTTPException(
            status_code=404,
            detail=f"Áudio para idioma '{language}' não encontrado. Idiomas disponíveis: {list(audios_gerados.keys())}"
        )
    
    audio_path = audios_gerados[language]
    
    # Remover barra inicial se existir
    if audio_path.startswith('/'):
        audio_path = audio_path[1:]
    
    # Verificar se arquivo existe
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail=f"Arquivo de áudio não encontrado: {audio_path}")
    
    # Obter metadata do job
    roteiros_adaptados = job.roteiros_adaptados or {}
    roteiro = roteiros_adaptados.get(language, "")
    chars_processed = len(roteiro)
    
    # Estimar duração (150 palavras por minuto)
    words = len(roteiro.split())
    duration_seconds = (words / 150) * 60
    
    from fastapi.responses import FileResponse
    
    # Retornar arquivo com headers customizados
    headers = {
        "X-Audio-Language": language,
        "X-Audio-Chars": str(chars_processed),
        "X-Audio-Duration": str(round(duration_seconds, 1)),
        "X-Job-ID": job_id
    }
    
    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=f"audio_{language}_{job_id[:8]}.mp3",
        headers=headers
    )


@app.get("/jobs/{job_id}/progress")
async def get_job_progress(
    job_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Retorna progresso detalhado do job com porcentagem e stage atual.
    """
    job = get_db_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # Calcular progresso baseado nos dados do job
    progress = {
        "job_id": job_id,
        "status": job.status,
        "progress_percentage": 0,
        "current_stage": "initializing",
        "stages_completed": [],
        "estimated_time_remaining": None
    }
    
    # Analisar logs para determinar stage atual
    logs = job.log or []
    last_log = logs[-1] if logs else ""
    
    # Stage 1: Geração do Roteiro Master
    if job.roteiro_master:
        progress["stages_completed"].append("roteiro_master")
        progress["progress_percentage"] = 33
        progress["current_stage"] = "roteiro_master_completed"
    elif "Stage 1" in last_log or "Gerando roteiro" in last_log:
        progress["current_stage"] = "generating_master_script"
        progress["progress_percentage"] = 15
    
    # Stage 2.5: Adaptação Cultural
    roteiros_adaptados = job.roteiros_adaptados or {}
    if roteiros_adaptados:
        progress["stages_completed"].append("cultural_adaptation")
        progress["progress_percentage"] = 66
        progress["current_stage"] = "cultural_adaptation_completed"
    elif "Stage 2.5" in last_log or "Adaptando" in last_log:
        progress["current_stage"] = "adapting_culturally"
        progress["progress_percentage"] = 50
    
    # Stage 3: Geração de Áudio
    audios_gerados = job.audios_gerados or {}
    if audios_gerados:
        progress["stages_completed"].append("audio_generation")
        progress["progress_percentage"] = 100
        progress["current_stage"] = "completed"
    elif "Stage 3" in last_log or "Gerando áudio" in last_log:
        progress["current_stage"] = "generating_audio"
        progress["progress_percentage"] = 85
    
    # Se status é completed/failed, ajustar
    if job.status == "completed":
        progress["progress_percentage"] = 100
        progress["current_stage"] = "completed"
    elif job.status == "failed":
        progress["progress_percentage"] = 0
        progress["current_stage"] = "failed"
    
    # Adicionar informações sobre idiomas
    if roteiros_adaptados:
        progress["languages_adapted"] = list(roteiros_adaptados.keys())
    if audios_gerados:
        progress["audios_generated"] = list(audios_gerados.keys())
    
    return progress


@app.get("/jobs/{job_id}/variacoes", response_model=schemas.JobResponseVariacoes)
async def get_job_variacoes(
    job_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Retorna todas as variações de roteiros e áudios de um job.
    
    **Retrocompatibilidade:**
    - Jobs antigos (num_variacoes=1 ou NULL) são convertidos automaticamente para o formato novo
    - Retorna sempre a estrutura padronizada com variações
    
    **Estrutura de resposta:**
    ```json
    {
        "job_id": "abc-123",
        "num_variacoes": 3,
        "roteiros_por_variacao": {
            "variacao_1": {"pt-BR": "...", "fr-FR": "..."},
            "variacao_2": {"pt-BR": "...", "fr-FR": "..."},
            "variacao_3": {"pt-BR": "...", "fr-FR": "..."}
        },
        "audios_por_variacao": {
            "variacao_1": {"pt-BR": "/static/audio/...", "fr-FR": "/static/audio/..."},
            "variacao_2": {"pt-BR": "/static/audio/...", "fr-FR": "/static/audio/..."},
            "variacao_3": {"pt-BR": "/static/audio/...", "fr-FR": "/static/audio/..."}
        }
    }
    ```
    """
    logger.info(f"[API] GET /jobs/{job_id}/variacoes - User: {current_user.email}")
    
    job = get_db_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # Verificar propriedade
    if job.owner_email != current_user.email:
        raise HTTPException(status_code=403, detail="Acesso negado: você não é o dono deste job")
    
    # Verificar se job está completo
    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job ainda não concluído. Status atual: {job.status}"
        )
    
    # Detectar número de variações
    num_variacoes = job.num_variacoes if job.num_variacoes else 1
    
    logger.info(f"[API] Job {job_id}: num_variacoes={num_variacoes}")
    
    # === CASO 1: JOB NOVO COM MÚLTIPLAS VARIAÇÕES ===
    if num_variacoes > 1 and job.roteiros_por_variacao and job.audios_por_variacao:
        logger.info(f"[API] Job {job_id}: Retornando formato de múltiplas variações (novo)")
        
        return schemas.JobResponseVariacoes(
            job_id=job_id,
            titulo=job.titulo,
            num_variacoes=num_variacoes,
            roteiros_por_variacao=job.roteiros_por_variacao,
            audios_por_variacao=job.audios_por_variacao
        )
    
    # === CASO 2: JOB ANTIGO (RETROCOMPATIBILIDADE) ===
    # Converter formato antigo para novo formato
    logger.info(f"[API] Job {job_id}: Convertendo formato antigo para novo (retrocompatibilidade)")
    
    roteiros_por_variacao = {}
    audios_por_variacao = {}
    
    # Detectar idioma master e roteiro master
    idioma_master = job.agente_config.get('idioma', 'pt-BR') if job.agente_config else 'pt-BR'
    roteiro_master = job.roteiro_master or ""
    
    # Construir dicionário de roteiros (variacao_1)
    roteiros_variacao_1 = {}
    
    if roteiro_master:
        roteiros_variacao_1[idioma_master] = roteiro_master
    
    # Adicionar roteiros adaptados (se existirem)
    roteiros_adaptados = job.roteiros_adaptados or {}
    for idioma, roteiro in roteiros_adaptados.items():
        roteiros_variacao_1[idioma] = roteiro
    
    roteiros_por_variacao["variacao_1"] = roteiros_variacao_1
    
    # Construir dicionário de áudios (variacao_1)
    audios_variacao_1 = {}
    audios_gerados = job.audios_gerados or {}
    
    for idioma, audio_path in audios_gerados.items():
        audios_variacao_1[idioma] = audio_path
    
    audios_por_variacao["variacao_1"] = audios_variacao_1
    
    logger.info(f"[API] Job {job_id}: Conversão concluída - variacao_1 com {len(roteiros_variacao_1)} roteiros + {len(audios_variacao_1)} áudios")
    
    return schemas.JobResponseVariacoes(
        job_id=job_id,
        titulo=job.titulo,
        num_variacoes=1,
        roteiros_por_variacao=roteiros_por_variacao,
        audios_por_variacao=audios_por_variacao
    )


@app.get("/me/jobs")
async def list_user_jobs(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Lista todos os jobs do usuário com filtros opcionais.
    """
    # Query base
    query = db.query(models.Job).filter(models.Job.owner_email == current_user.email)
    
    # Filtro por status
    if status:
        query = query.filter(models.Job.status == status)
    
    # Ordenar por data de criação (mais recentes primeiro)
    query = query.order_by(models.Job.id.desc())
    
    # Paginação
    total = query.count()
    jobs = query.offset(offset).limit(limit).all()
    
    # Formatar resposta
    jobs_list = []
    for job in jobs:
        roteiros_adaptados = job.roteiros_adaptados or {}
        audios_gerados = job.audios_gerados or {}
        
        jobs_list.append({
            "job_id": job.id,
            "status": job.status,
            "created_at": job.id[:8],  # Primeiros 8 chars do UUID como timestamp aproximado
            "has_master_script": bool(job.roteiro_master),
            "languages_adapted": list(roteiros_adaptados.keys()),
            "audios_available": list(audios_gerados.keys()),
            "total_chars_tts": job.chars_processados_tts or 0,
            "last_message": job.log[-1] if job.log else None
        })
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": jobs_list
    }