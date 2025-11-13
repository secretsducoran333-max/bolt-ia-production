# celery_app.py
"""
Configuração do Celery para processamento distribuído de jobs.
"""
from celery import Celery
from kombu import Queue
import os

# Configuração do broker Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_BACKEND = os.getenv("REDIS_BACKEND", "redis://localhost:6379/1")

# Criar aplicação Celery
celery_app = Celery(
    'bolt_ia',
    broker=REDIS_URL,
    backend=REDIS_BACKEND,
    include=['celery_tasks']  # Módulo com as tasks
)

# Configurações do Celery
celery_app.conf.update(
    # Serialização
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Timezone
    timezone='America/Sao_Paulo',
    enable_utc=True,
    
    # Workers
    worker_prefetch_multiplier=1,  # 1 task por vez (evita sobrecarga)
    worker_max_tasks_per_child=50,  # Restart worker após 50 tasks (evita memory leaks)
    worker_disable_rate_limits=False,
    
    # Tasks
    task_acks_late=True,  # Confirma task apenas após conclusão
    task_reject_on_worker_lost=True,  # Rejeita task se worker morrer
    task_track_started=True,  # Rastreia quando task inicia
    
    # Timeout
    task_soft_time_limit=3600,  # 1 hora (soft limit - levanta exceção)
    task_time_limit=3900,  # 1h 5min (hard limit - mata processo)
    
    # Retry
    task_autoretry_for=(Exception,),  # Retry automático em exceções
    task_retry_kwargs={'max_retries': 3, 'countdown': 60},  # 3 tentativas, espera 60s
    task_retry_backoff=True,  # Backoff exponencial
    task_retry_backoff_max=600,  # Máximo 10 minutos de espera
    task_retry_jitter=True,  # Adiciona jitter para evitar thundering herd
    
    # Resultados
    result_expires=86400,  # Resultados expiram em 24 horas
    result_backend_transport_options={'master_name': 'mymaster'},
    
    # Filas
    task_default_queue='bolt_ia_default',
    task_queues=(
        Queue('bolt_ia_default', routing_key='task.#'),
        Queue('bolt_ia_high_priority', routing_key='priority.high'),
        Queue('bolt_ia_low_priority', routing_key='priority.low'),
    ),
    
    # Rotas
    task_routes={
        'celery_tasks.process_job_task': {'queue': 'bolt_ia_default'},
        'celery_tasks.process_batch_task': {'queue': 'bolt_ia_high_priority'},
    },
    
    # Monitoramento
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Configuração de logging
celery_app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
celery_app.conf.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

if __name__ == '__main__':
    celery_app.start()
