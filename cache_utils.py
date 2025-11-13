# cache_utils.py
"""
Utilitários para cache e rate limiting.
"""
import os
import redis
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)

# Conexão Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = None

def get_redis_client():
    """Obtém cliente Redis (singleton)."""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            redis_client.ping()  # Testar conexão
            logger.info("Conexão Redis estabelecida")
        except Exception as e:
            logger.error(f"Erro ao conectar Redis: {e}")
            redis_client = None
    return redis_client


# ============================================================================
# CACHE
# ============================================================================

def generate_cache_key(prefix: str, **kwargs) -> str:
    """
    Gera chave de cache baseada em parâmetros.
    
    Args:
        prefix: Prefixo da chave (ex: 'roteiro', 'audio')
        **kwargs: Parâmetros para gerar hash
    
    Returns:
        Chave de cache
    """
    # Ordenar kwargs para garantir consistência
    sorted_params = sorted(kwargs.items())
    data = json.dumps(sorted_params, sort_keys=True)
    hash_value = hashlib.sha256(data.encode()).hexdigest()
    return f"{prefix}:{hash_value}"


def cache_get(key: str) -> Optional[Any]:
    """
    Busca valor no cache.
    
    Args:
        key: Chave do cache
    
    Returns:
        Valor ou None se não encontrado
    """
    client = get_redis_client()
    if not client:
        return None
    
    try:
        value = client.get(key)
        if value:
            logger.info(f"Cache HIT: {key}")
            return json.loads(value)
        logger.info(f"Cache MISS: {key}")
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar cache: {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 2592000):
    """
    Salva valor no cache.
    
    Args:
        key: Chave do cache
        value: Valor a ser salvo
        ttl: Time to live em segundos (padrão: 30 dias)
    """
    client = get_redis_client()
    if not client:
        return
    
    try:
        serialized = json.dumps(value)
        client.setex(key, ttl, serialized)
        logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
    except Exception as e:
        logger.error(f"Erro ao salvar cache: {e}")


def cache_delete(key: str):
    """
    Remove valor do cache.
    
    Args:
        key: Chave do cache
    """
    client = get_redis_client()
    if not client:
        return
    
    try:
        client.delete(key)
        logger.info(f"Cache DELETE: {key}")
    except Exception as e:
        logger.error(f"Erro ao deletar cache: {e}")


def cache_clear_pattern(pattern: str):
    """
    Remove todas as chaves que correspondem ao padrão.
    
    Args:
        pattern: Padrão (ex: 'roteiro:*')
    """
    client = get_redis_client()
    if not client:
        return
    
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
            logger.info(f"Cache CLEAR: {len(keys)} chaves removidas ({pattern})")
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {e}")


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """
    Rate limiter usando Redis.
    Implementa algoritmo de sliding window.
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Args:
            max_requests: Número máximo de requisições
            window_seconds: Janela de tempo em segundos
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Verifica se a requisição é permitida.
        
        Args:
            identifier: Identificador único (ex: user_id, api_key)
        
        Returns:
            True se permitido, False caso contrário
        """
        client = get_redis_client()
        if not client:
            return True  # Permitir se Redis não disponível
        
        key = f"ratelimit:{identifier}"
        now = datetime.utcnow().timestamp()
        window_start = now - self.window_seconds
        
        try:
            # Remover requisições antigas
            client.zremrangebyscore(key, 0, window_start)
            
            # Contar requisições na janela
            count = client.zcard(key)
            
            if count < self.max_requests:
                # Adicionar nova requisição
                client.zadd(key, {str(now): now})
                client.expire(key, self.window_seconds)
                return True
            else:
                logger.warning(f"Rate limit excedido para {identifier}")
                return False
                
        except Exception as e:
            logger.error(f"Erro no rate limiter: {e}")
            return True  # Permitir em caso de erro
    
    def get_remaining(self, identifier: str) -> int:
        """
        Retorna número de requisições restantes.
        
        Args:
            identifier: Identificador único
        
        Returns:
            Número de requisições restantes
        """
        client = get_redis_client()
        if not client:
            return self.max_requests
        
        key = f"ratelimit:{identifier}"
        now = datetime.utcnow().timestamp()
        window_start = now - self.window_seconds
        
        try:
            client.zremrangebyscore(key, 0, window_start)
            count = client.zcard(key)
            return max(0, self.max_requests - count)
        except Exception as e:
            logger.error(f"Erro ao obter remaining: {e}")
            return self.max_requests


# Instâncias de rate limiters
api_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100 req/min
user_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 req/min por usuário


def rate_limit(limiter: RateLimiter, identifier_func=None):
    """
    Decorator para aplicar rate limiting.
    
    Args:
        limiter: Instância de RateLimiter
        identifier_func: Função para extrair identificador (opcional)
    
    Example:
        @rate_limit(user_rate_limiter, lambda request: request.user.email)
        async def my_endpoint(request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extrair identificador
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                # Usar IP como fallback
                identifier = "default"
            
            # Verificar rate limit
            if not limiter.is_allowed(identifier):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit excedido. Tente novamente mais tarde."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """
    Circuit breaker para proteger contra falhas em cascata.
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        """
        Args:
            failure_threshold: Número de falhas para abrir circuito
            timeout_seconds: Tempo para tentar fechar circuito novamente
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
    
    def is_open(self, identifier: str) -> bool:
        """
        Verifica se o circuito está aberto.
        
        Args:
            identifier: Identificador (ex: api_key_id)
        
        Returns:
            True se aberto (bloqueado), False se fechado (permitido)
        """
        client = get_redis_client()
        if not client:
            return False
        
        key = f"circuit:{identifier}"
        
        try:
            data = client.get(key)
            if not data:
                return False
            
            circuit_data = json.loads(data)
            
            # Verificar se timeout passou
            if circuit_data.get("open_until"):
                open_until = datetime.fromisoformat(circuit_data["open_until"])
                if datetime.utcnow() > open_until:
                    # Timeout passou, tentar fechar circuito
                    self.reset(identifier)
                    return False
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao verificar circuit breaker: {e}")
            return False
    
    def record_failure(self, identifier: str):
        """
        Registra uma falha.
        
        Args:
            identifier: Identificador
        """
        client = get_redis_client()
        if not client:
            return
        
        key = f"circuit:{identifier}"
        
        try:
            data = client.get(key)
            if data:
                circuit_data = json.loads(data)
            else:
                circuit_data = {"failures": 0}
            
            circuit_data["failures"] = circuit_data.get("failures", 0) + 1
            
            # Abrir circuito se atingir threshold
            if circuit_data["failures"] >= self.failure_threshold:
                open_until = datetime.utcnow() + timedelta(seconds=self.timeout_seconds)
                circuit_data["open_until"] = open_until.isoformat()
                logger.warning(f"Circuit OPEN para {identifier} até {open_until}")
            
            client.setex(key, self.timeout_seconds * 2, json.dumps(circuit_data))
            
        except Exception as e:
            logger.error(f"Erro ao registrar falha: {e}")
    
    def record_success(self, identifier: str):
        """
        Registra um sucesso (reseta contador de falhas).
        
        Args:
            identifier: Identificador
        """
        self.reset(identifier)
    
    def reset(self, identifier: str):
        """
        Reseta o circuit breaker.
        
        Args:
            identifier: Identificador
        """
        client = get_redis_client()
        if not client:
            return
        
        key = f"circuit:{identifier}"
        
        try:
            client.delete(key)
            logger.info(f"Circuit RESET para {identifier}")
        except Exception as e:
            logger.error(f"Erro ao resetar circuit breaker: {e}")


# Instância global de circuit breaker
api_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)


# ============================================================================
# ESTATÍSTICAS
# ============================================================================

def increment_counter(key: str, amount: int = 1):
    """
    Incrementa contador no Redis.
    
    Args:
        key: Chave do contador
        amount: Valor a incrementar
    """
    client = get_redis_client()
    if not client:
        return
    
    try:
        client.incrby(key, amount)
    except Exception as e:
        logger.error(f"Erro ao incrementar contador: {e}")


def get_counter(key: str) -> int:
    """
    Obtém valor do contador.
    
    Args:
        key: Chave do contador
    
    Returns:
        Valor do contador
    """
    client = get_redis_client()
    if not client:
        return 0
    
    try:
        value = client.get(key)
        return int(value) if value else 0
    except Exception as e:
        logger.error(f"Erro ao obter contador: {e}")
        return 0
