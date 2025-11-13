# migrate_database.py
"""
Script para criar/atualizar tabelas do banco de dados.
"""
import sys
import logging
from sqlalchemy import inspect

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar modelos e database
from database import engine, Base
import models
import models_batch

def check_table_exists(table_name: str) -> bool:
    """
    Verifica se uma tabela existe no banco.
    
    Args:
        table_name: Nome da tabela
    
    Returns:
        True se existe, False caso contrário
    """
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_tables():
    """
    Cria todas as tabelas definidas nos modelos.
    """
    logger.info("=" * 80)
    logger.info("MIGRAÇÃO DO BANCO DE DADOS - BOLT IA")
    logger.info("=" * 80)
    
    # Listar todas as tabelas que serão criadas
    tables_to_create = []
    
    for table_name, table in Base.metadata.tables.items():
        exists = check_table_exists(table_name)
        status = "✓ Já existe" if exists else "⚠ Será criada"
        tables_to_create.append((table_name, exists))
        logger.info(f"{status}: {table_name}")
    
    logger.info("-" * 80)
    
    # Perguntar confirmação
    new_tables = [name for name, exists in tables_to_create if not exists]
    
    if new_tables:
        logger.info(f"Serão criadas {len(new_tables)} novas tabelas:")
        for table_name in new_tables:
            logger.info(f"  - {table_name}")
        
        response = input("\nDeseja continuar? (s/n): ")
        if response.lower() != 's':
            logger.info("Migração cancelada pelo usuário")
            return
        
        logger.info("-" * 80)
        logger.info("Criando tabelas...")
        
        try:
            # Criar apenas as tabelas que não existem
            Base.metadata.create_all(bind=engine, checkfirst=True)
            logger.info("✅ Tabelas criadas com sucesso!")
            
            # Verificar novamente
            logger.info("-" * 80)
            logger.info("Verificação pós-migração:")
            for table_name in new_tables:
                exists = check_table_exists(table_name)
                status = "✓" if exists else "✗"
                logger.info(f"{status} {table_name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabelas: {e}")
            sys.exit(1)
    else:
        logger.info("✅ Todas as tabelas já existem. Nenhuma migração necessária.")
    
    logger.info("=" * 80)


def drop_all_tables():
    """
    Remove todas as tabelas (CUIDADO: USE APENAS EM DESENVOLVIMENTO).
    """
    logger.warning("=" * 80)
    logger.warning("ATENÇÃO: VOCÊ ESTÁ PRESTES A DELETAR TODAS AS TABELAS!")
    logger.warning("=" * 80)
    
    response = input("Digite 'DELETE ALL' para confirmar: ")
    if response != "DELETE ALL":
        logger.info("Operação cancelada")
        return
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ Todas as tabelas foram removidas")
    except Exception as e:
        logger.error(f"❌ Erro ao remover tabelas: {e}")
        sys.exit(1)


def show_tables():
    """
    Mostra todas as tabelas existentes no banco.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    logger.info("=" * 80)
    logger.info(f"TABELAS NO BANCO DE DADOS ({len(tables)} total)")
    logger.info("=" * 80)
    
    for table_name in sorted(tables):
        columns = inspector.get_columns(table_name)
        logger.info(f"\n📋 {table_name} ({len(columns)} colunas)")
        for col in columns:
            logger.info(f"   - {col['name']}: {col['type']}")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Gerenciador de migrações do banco de dados")
    parser.add_argument(
        "action",
        choices=["migrate", "drop", "show"],
        help="Ação a executar: migrate (criar tabelas), drop (remover todas), show (listar tabelas)"
    )
    
    args = parser.parse_args()
    
    if args.action == "migrate":
        create_tables()
    elif args.action == "drop":
        drop_all_tables()
    elif args.action == "show":
        show_tables()
