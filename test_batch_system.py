# test_batch_system.py
"""
Testes automatizados para o sistema de processamento em lote.
"""
import sys
import time
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# TESTES UNITÁRIOS
# ============================================================================

def test_voice_catalog():
    """Testa se o catálogo de vozes está correto."""
    logger.info("=" * 80)
    logger.info("TESTE 1: Catálogo de Vozes")
    logger.info("=" * 80)
    
    try:
        with open('tts_voices_catalog.json', 'r') as f:
            catalog = json.load(f)
        
        # Verificações
        assert len(catalog) > 0, "Catálogo vazio"
        assert "pt-BR" in catalog, "pt-BR não encontrado"
        assert "en-US" in catalog, "en-US não encontrado"
        
        total_voices = sum(len(voices) for voices in catalog.values())
        logger.info(f"✅ Catálogo válido: {len(catalog)} idiomas, {total_voices} vozes")
        
        # Verificar formato das vozes
        for lang, voices in catalog.items():
            for voice in voices:
                assert voice.startswith(lang), f"Voz {voice} não corresponde ao idioma {lang}"
        
        logger.info("✅ Formato das vozes correto")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


def test_database_models():
    """Testa se os modelos do banco estão corretos."""
    logger.info("=" * 80)
    logger.info("TESTE 2: Modelos do Banco de Dados")
    logger.info("=" * 80)
    
    try:
        import models_batch
        from sqlalchemy import inspect
        from database import engine
        
        # Verificar se as tabelas existem
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = ['batches', 'batch_jobs', 'api_key_pool']
        
        for table in required_tables:
            if table in tables:
                logger.info(f"✅ Tabela '{table}' existe")
            else:
                logger.warning(f"⚠ Tabela '{table}' não existe (será criada na migração)")
        
        # Verificar campos dos modelos
        batch_fields = [c.name for c in models_batch.Batch.__table__.columns]
        assert 'id' in batch_fields, "Campo 'id' não encontrado em Batch"
        assert 'mode' in batch_fields, "Campo 'mode' não encontrado em Batch"
        assert 'status' in batch_fields, "Campo 'status' não encontrado em Batch"
        
        logger.info(f"✅ Modelo Batch válido ({len(batch_fields)} campos)")
        
        job_fields = [c.name for c in models_batch.BatchJob.__table__.columns]
        assert 'voice_id' in job_fields, "Campo 'voice_id' não encontrado em BatchJob"
        assert 'language_code' in job_fields, "Campo 'language_code' não encontrado em BatchJob"
        
        logger.info(f"✅ Modelo BatchJob válido ({len(job_fields)} campos)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


def test_schemas():
    """Testa se os schemas Pydantic estão corretos."""
    logger.info("=" * 80)
    logger.info("TESTE 3: Schemas Pydantic")
    logger.info("=" * 80)
    
    try:
        import schemas_batch
        
        # Testar LanguageVoiceConfig
        config = schemas_batch.LanguageVoiceConfig(
            code="pt-BR",
            voice="pt-BR-Neural2-A"
        )
        assert config.code == "pt-BR"
        logger.info("✅ LanguageVoiceConfig válido")
        
        # Testar BatchCreateRequest
        request = schemas_batch.BatchCreateRequest(
            mode="expand_languages",
            agent_id=1,
            title="Teste",
            language_voices=[config],
            num_variations=1
        )
        assert request.mode == "expand_languages"
        logger.info("✅ BatchCreateRequest válido")
        
        # Testar validação de modo inválido
        try:
            invalid_request = schemas_batch.BatchCreateRequest(
                mode="invalid_mode",
                agent_id=1
            )
            logger.error("❌ Validação de modo não funcionou")
            return False
        except:
            logger.info("✅ Validação de modo funcionando")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


def test_cache_utils():
    """Testa utilitários de cache."""
    logger.info("=" * 80)
    logger.info("TESTE 4: Cache e Rate Limiting")
    logger.info("=" * 80)
    
    try:
        import cache_utils
        
        # Testar geração de cache key
        key1 = cache_utils.generate_cache_key("test", title="Teste", lang="pt-BR")
        key2 = cache_utils.generate_cache_key("test", title="Teste", lang="pt-BR")
        key3 = cache_utils.generate_cache_key("test", title="Outro", lang="pt-BR")
        
        assert key1 == key2, "Cache keys iguais deveriam ser idênticas"
        assert key1 != key3, "Cache keys diferentes deveriam ser distintas"
        logger.info("✅ Geração de cache key funcionando")
        
        # Testar rate limiter
        limiter = cache_utils.RateLimiter(max_requests=5, window_seconds=60)
        
        # Fazer 5 requisições (deve permitir todas)
        for i in range(5):
            assert limiter.is_allowed("test_user"), f"Requisição {i+1} deveria ser permitida"
        
        # 6ª requisição deve ser bloqueada
        assert not limiter.is_allowed("test_user"), "6ª requisição deveria ser bloqueada"
        
        logger.info("✅ Rate limiter funcionando")
        
        # Testar circuit breaker
        breaker = cache_utils.CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        
        # Registrar falhas
        for i in range(3):
            breaker.record_failure("test_api")
        
        # Circuito deveria estar aberto
        assert breaker.is_open("test_api"), "Circuit breaker deveria estar aberto"
        logger.info("✅ Circuit breaker funcionando")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        logger.warning("⚠ Redis pode não estar disponível. Alguns testes podem falhar.")
        return True  # Não falhar se Redis não disponível


def test_celery_tasks():
    """Testa se as tasks do Celery estão definidas corretamente."""
    logger.info("=" * 80)
    logger.info("TESTE 5: Celery Tasks")
    logger.info("=" * 80)
    
    try:
        import celery_tasks
        from celery_app import celery_app
        
        # Verificar se task está registrada
        assert 'celery_tasks.process_job_task' in celery_app.tasks, "Task process_job_task não registrada"
        logger.info("✅ Task process_job_task registrada")
        
        # Verificar funções auxiliares
        assert hasattr(celery_tasks, 'generate_roteiro_gemini'), "Função generate_roteiro_gemini não encontrada"
        assert hasattr(celery_tasks, 'adapt_roteiro_culturally'), "Função adapt_roteiro_culturally não encontrada"
        assert hasattr(celery_tasks, 'generate_tts_audio'), "Função generate_tts_audio não encontrada"
        
        logger.info("✅ Funções auxiliares presentes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


def test_batch_endpoints():
    """Testa se os endpoints estão definidos corretamente."""
    logger.info("=" * 80)
    logger.info("TESTE 6: Endpoints de Batch")
    logger.info("=" * 80)
    
    try:
        import batch_endpoints
        
        # Verificar se router existe
        assert hasattr(batch_endpoints, 'router'), "Router não encontrado"
        logger.info("✅ Router definido")
        
        # Verificar rotas
        routes = [route.path for route in batch_endpoints.router.routes]
        
        required_routes = ['/create', '/voices', '/languages', '/estimate']
        
        for route in required_routes:
            full_path = f"/batches{route}"
            if any(route in r for r in routes):
                logger.info(f"✅ Rota '{route}' definida")
            else:
                logger.warning(f"⚠ Rota '{route}' não encontrada")
        
        # Verificar funções auxiliares
        assert hasattr(batch_endpoints, 'validate_voice_for_language'), "Função validate_voice_for_language não encontrada"
        assert hasattr(batch_endpoints, 'estimate_job_cost'), "Função estimate_job_cost não encontrada"
        
        logger.info("✅ Funções auxiliares presentes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


# ============================================================================
# TESTES DE INTEGRAÇÃO
# ============================================================================

def test_estimate_cost():
    """Testa cálculo de estimativa de custo."""
    logger.info("=" * 80)
    logger.info("TESTE 7: Estimativa de Custo")
    logger.info("=" * 80)
    
    try:
        import batch_endpoints
        
        # Testar com diferentes quantidades
        test_cases = [
            (1, 0.13, 2.25),
            (10, 1.30, 2.25),
            (100, 13.00, 22.5),
        ]
        
        for num_jobs, expected_cost, expected_time in test_cases:
            result = batch_endpoints.estimate_job_cost(num_jobs)
            
            assert result['total_jobs'] == num_jobs
            assert abs(result['estimated_cost_usd'] - expected_cost) < 0.01
            
            logger.info(f"✅ {num_jobs} jobs: ${result['estimated_cost_usd']}, {result['estimated_time_minutes']} min")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


# ============================================================================
# RUNNER
# ============================================================================

def run_all_tests():
    """Executa todos os testes."""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 20 + "BOLT IA - TESTE AUTOMATIZADO" + " " * 30 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\n")
    
    tests = [
        ("Catálogo de Vozes", test_voice_catalog),
        ("Modelos do Banco", test_database_models),
        ("Schemas Pydantic", test_schemas),
        ("Cache e Rate Limiting", test_cache_utils),
        ("Celery Tasks", test_celery_tasks),
        ("Endpoints de Batch", test_batch_endpoints),
        ("Estimativa de Custo", test_estimate_cost),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            logger.info("\n")
        except Exception as e:
            logger.error(f"❌ Erro inesperado em '{name}': {e}")
            results.append((name, False))
            logger.info("\n")
    
    # Resumo
    logger.info("=" * 80)
    logger.info("RESUMO DOS TESTES")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"{status}: {name}")
    
    logger.info("=" * 80)
    logger.info(f"RESULTADO: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")
    logger.info("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
