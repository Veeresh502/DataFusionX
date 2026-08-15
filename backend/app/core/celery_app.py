from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "datafusionx",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pipeline_tasks", "app.tasks.schedule_tasks"]
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-scheduled-pipelines-every-15s": {
            "task": "app.tasks.schedule_tasks.check_and_dispatch_scheduled_pipelines",
            "schedule": 15.0,  # Run every 15 seconds
        },
    },
)

# Auto-discover tasks in app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])

