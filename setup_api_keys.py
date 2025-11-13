# setup_api_keys.py
"""
Script para configurar API keys no pool.
"""
import sys
import logging
from database import SessionLocal
import models_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_api_key(owner_email: str, service: str, api_key: str, requests_per_minute: int = 60):
    """
    Adiciona uma API key ao pool.
    
    Args:
        owner_email: Email do dono
        service: Serviço ('gemini' ou 'tts')
        api_key: A API key
        requests_per_minute: Limite de requisições por minuto
    """
    db = SessionLocal()
    
    try:
        # Verificar se já existe
        existing = db.query(models_batch.ApiKeyPool).filter(
            models_batch.ApiKeyPool.api_key == api_key
        ).first()
        
        if existing:
            logger.warning(f"API key já existe no pool (ID: {existing.id})")
            return
        
        # Criar nova entrada
        key_entry = models_batch.ApiKeyPool(
            owner_email=owner_email,
            service=service,
            api_key=api_key,
            is_active=1,
            requests_per_minute=requests_per_minute
        )
        
        db.add(key_entry)
        db.commit()
        db.refresh(key_entry)
        
        logger.info(f"✅ API key adicionada ao pool (ID: {key_entry.id}, Service: {service})")
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar API key: {e}")
        db.rollback()
    finally:
        db.close()


def list_api_keys():
    """
    Lista todas as API keys no pool.
    """
    db = SessionLocal()
    
    try:
        keys = db.query(models_batch.ApiKeyPool).all()
        
        logger.info("=" * 80)
        logger.info(f"API KEYS NO POOL ({len(keys)} total)")
        logger.info("=" * 80)
        
        for key in keys:
            status = "✓ Ativo" if key.is_active else "✗ Inativo"
            masked_key = key.api_key[:10] + "..." + key.api_key[-4:]
            logger.info(f"\nID: {key.id}")
            logger.info(f"  Service: {key.service}")
            logger.info(f"  Owner: {key.owner_email}")
            logger.info(f"  Key: {masked_key}")
            logger.info(f"  Status: {status}")
            logger.info(f"  Requests: {key.total_requests}")
            logger.info(f"  Failed: {key.failed_requests}")
            logger.info(f"  RPM Limit: {key.requests_per_minute}")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar API keys: {e}")
    finally:
        db.close()


def remove_api_key(key_id: int):
    """
    Remove uma API key do pool.
    
    Args:
        key_id: ID da API key
    """
    db = SessionLocal()
    
    try:
        key = db.query(models_batch.ApiKeyPool).filter(
            models_batch.ApiKeyPool.id == key_id
        ).first()
        
        if not key:
            logger.error(f"API key com ID {key_id} não encontrada")
            return
        
        db.delete(key)
        db.commit()
        
        logger.info(f"✅ API key removida (ID: {key_id})")
        
    except Exception as e:
        logger.error(f"❌ Erro ao remover API key: {e}")
        db.rollback()
    finally:
        db.close()


def toggle_api_key(key_id: int):
    """
    Ativa/desativa uma API key.
    
    Args:
        key_id: ID da API key
    """
    db = SessionLocal()
    
    try:
        key = db.query(models_batch.ApiKeyPool).filter(
            models_batch.ApiKeyPool.id == key_id
        ).first()
        
        if not key:
            logger.error(f"API key com ID {key_id} não encontrada")
            return
        
        key.is_active = 1 if key.is_active == 0 else 0
        db.commit()
        
        status = "ativada" if key.is_active else "desativada"
        logger.info(f"✅ API key {status} (ID: {key_id})")
        
    except Exception as e:
        logger.error(f"❌ Erro ao alterar status: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Gerenciador de API keys")
    subparsers = parser.add_subparsers(dest="command", help="Comando a executar")
    
    # Comando: add
    add_parser = subparsers.add_parser("add", help="Adicionar API key")
    add_parser.add_argument("--email", required=True, help="Email do dono")
    add_parser.add_argument("--service", required=True, choices=["gemini", "tts"], help="Serviço")
    add_parser.add_argument("--key", required=True, help="API key")
    add_parser.add_argument("--rpm", type=int, default=60, help="Requisições por minuto (padrão: 60)")
    
    # Comando: list
    list_parser = subparsers.add_parser("list", help="Listar API keys")
    
    # Comando: remove
    remove_parser = subparsers.add_parser("remove", help="Remover API key")
    remove_parser.add_argument("--id", type=int, required=True, help="ID da API key")
    
    # Comando: toggle
    toggle_parser = subparsers.add_parser("toggle", help="Ativar/desativar API key")
    toggle_parser.add_argument("--id", type=int, required=True, help="ID da API key")
    
    args = parser.parse_args()
    
    if args.command == "add":
        add_api_key(args.email, args.service, args.key, args.rpm)
    elif args.command == "list":
        list_api_keys()
    elif args.command == "remove":
        remove_api_key(args.id)
    elif args.command == "toggle":
        toggle_api_key(args.id)
    else:
        parser.print_help()
