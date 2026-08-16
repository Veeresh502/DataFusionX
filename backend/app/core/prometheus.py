import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# --- API METRICS ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total number of HTTP errors (4xx/5xx)",
    ["method", "endpoint", "status"]
)

# --- GLOBAL PIPELINE METRICS ---
PIPELINE_EXECUTIONS_TOTAL = Counter(
    "pipeline_executions_total",
    "Total pipeline executions by status, trigger type, and destination",
    ["status", "trigger_type", "destination_type"]
)

PIPELINE_EXECUTION_DURATION_SECONDS = Histogram(
    "pipeline_execution_duration_seconds",
    "Pipeline execution duration in seconds",
    ["status", "trigger_type"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

PIPELINE_STAGE_DURATION_SECONDS = Histogram(
    "pipeline_stage_duration_seconds",
    "Pipeline stage execution duration in seconds",
    ["stage"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

PIPELINE_EXEC_SUCCESS_COUNT = Gauge(
    "pipeline_exec_success_count",
    "Total successful pipeline executions derived from DB"
)

PIPELINE_EXEC_FAILED_COUNT = Gauge(
    "pipeline_exec_failed_count",
    "Total failed pipeline executions derived from DB"
)

PIPELINE_EXEC_AVG_DURATION = Gauge(
    "pipeline_exec_avg_duration_seconds",
    "Average pipeline execution duration in seconds derived from DB"
)

PIPELINE_RECORDS_READ_TOTAL = Gauge(
    "pipeline_records_read_total",
    "Total records read across all pipeline executions"
)

PIPELINE_RECORDS_PROCESSED_TOTAL = Gauge(
    "pipeline_records_processed_total",
    "Total records processed across all pipeline executions"
)

PIPELINE_RECORDS_LOADED_TOTAL = Gauge(
    "pipeline_records_loaded_total",
    "Total records loaded into target destinations"
)

PIPELINE_FAILURES_TOTAL = Gauge(
    "pipeline_failures_total",
    "Total pipeline execution failures"
)

PIPELINE_RETRIES_TOTAL = Gauge(
    "pipeline_retries_total",
    "Total pipeline execution retry attempts"
)

PIPELINE_THROUGHPUT = Gauge(
    "pipeline_throughput",
    "Latest records processed per second throughput rate"
)

# --- SALES DOMAIN METRICS ---
SALES_EXEC_SUCCESS_COUNT = Gauge(
    "sales_exec_success_count",
    "Total successful Sales domain pipeline executions"
)

SALES_RECORDS_PROCESSED_TOTAL = Gauge(
    "sales_records_processed_total",
    "Total Sales domain records processed"
)

SALES_RECORDS_LOADED_TOTAL = Gauge(
    "sales_records_loaded_total",
    "Total Sales domain fact/dim records loaded into warehouse"
)

SALES_PIPELINE_THROUGHPUT = Gauge(
    "sales_pipeline_throughput",
    "Sales pipeline processing throughput (rec/sec)"
)

# --- MANUFACTURING DOMAIN METRICS ---
MANUFACTURING_EXEC_SUCCESS_COUNT = Gauge(
    "manufacturing_exec_success_count",
    "Total successful Manufacturing domain pipeline executions"
)

MANUFACTURING_RECORDS_PROCESSED_TOTAL = Gauge(
    "manufacturing_records_processed_total",
    "Total Manufacturing domain batch records processed"
)

MANUFACTURING_RECORDS_LOADED_TOTAL = Gauge(
    "manufacturing_records_loaded_total",
    "Total Manufacturing domain production records loaded into warehouse"
)

MANUFACTURING_PIPELINE_THROUGHPUT = Gauge(
    "manufacturing_pipeline_throughput",
    "Manufacturing pipeline processing throughput (rec/sec)"
)

# --- DATA QUALITY METRICS ---
PIPELINE_DATA_QUALITY_SCORE = Gauge(
    "pipeline_data_quality_score",
    "Data quality score (0.0 to 100.0)"
)

PIPELINE_VALIDATION_ERRORS_TOTAL = Counter(
    "pipeline_validation_errors_total",
    "Total data validation errors encountered"
)

PIPELINE_VALIDATION_WARNINGS_TOTAL = Counter(
    "pipeline_validation_warnings_total",
    "Total data validation warnings encountered"
)

PIPELINE_INVALID_RECORDS_TOTAL = Counter(
    "pipeline_invalid_records_total",
    "Total invalid records encountered during validation"
)

# --- SYSTEM HEALTH METRICS ---
CELERY_WORKERS_ONLINE = Gauge(
    "celery_workers_online",
    "Number of active online Celery workers"
)

DATABASE_CONNECTED = Gauge(
    "database_connected",
    "PostgreSQL database connection health (1=healthy, 0=unhealthy)"
)

REDIS_CONNECTED = Gauge(
    "redis_connected",
    "Redis broker connection health (1=healthy, 0=unhealthy)"
)

PIPELINE_SCHEDULES_ENABLED = Gauge(
    "pipeline_schedules_enabled",
    "Total active enabled pipeline schedules"
)


# --- HTTP METRICS MIDDLEWARE ---
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/sources/"):
            endpoint = "/api/sources/{id}"
        elif path.startswith("/api/pipelines/"):
            endpoint = "/api/pipelines/{id}"
        elif path.startswith("/api/schedules/"):
            endpoint = "/api/schedules/{id}"
        elif path.startswith("/api/warehouse/"):
            endpoint = "/api/warehouse/{table}"
        elif path.startswith("/api/monitoring/"):
            endpoint = "/api/monitoring/{section}"
        else:
            endpoint = path

        start_time = time.time()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.time() - start_time
            method = request.method

            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status_code).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)
            if status_code.startswith("4") or status_code.startswith("5"):
                HTTP_ERRORS_TOTAL.labels(method=method, endpoint=endpoint, status=status_code).inc()

        return response


def sync_db_metrics():
    """Dynamically refresh gauges from live database state before Prometheus scrapes /metrics."""
    try:
        from app.db.session import SessionLocal
        from sqlalchemy import func, case
        from app.models.pipeline import Pipeline
        from app.models.pipeline_execution import PipelineExecution
        from app.models.pipeline_schedule import PipelineSchedule
        from app.models.data_profile import DataProfile
        from app.services.health import check_redis_health, check_celery_health

        db = SessionLocal()
        try:
            # Overall Pipeline Stats
            stats = db.query(
                func.sum(PipelineExecution.records_read).label("read"),
                func.sum(PipelineExecution.records_processed).label("processed"),
                func.sum(PipelineExecution.records_loaded).label("loaded"),
                func.sum(case((PipelineExecution.status == "SUCCESS", 1), else_=0)).label("succ_cnt"),
                func.sum(case((PipelineExecution.status == "FAILED", 1), else_=0)).label("failed_cnt"),
                func.sum(case((PipelineExecution.status == "RETRYING", 1), else_=0)).label("retry_cnt"),
                func.avg(PipelineExecution.duration_seconds).label("avg_dur"),
                func.sum(PipelineExecution.duration_seconds).label("total_dur")
            ).first()

            if stats:
                r_cnt = int(stats.read or 0)
                p_cnt = int(stats.processed or 0)
                l_cnt = int(stats.loaded or 0)
                s_cnt = int(stats.succ_cnt or 0)
                f_cnt = int(stats.failed_cnt or 0)
                ret_cnt = int(stats.retry_cnt or 0)
                a_dur = float(stats.avg_dur or 0)
                dur = float(stats.total_dur or 0)

                PIPELINE_RECORDS_READ_TOTAL.set(r_cnt)
                PIPELINE_RECORDS_PROCESSED_TOTAL.set(p_cnt)
                PIPELINE_RECORDS_LOADED_TOTAL.set(l_cnt)
                PIPELINE_FAILURES_TOTAL.set(f_cnt)
                PIPELINE_RETRIES_TOTAL.set(ret_cnt)
                PIPELINE_EXEC_SUCCESS_COUNT.set(s_cnt)
                PIPELINE_EXEC_FAILED_COUNT.set(f_cnt)
                PIPELINE_EXEC_AVG_DURATION.set(round(a_dur, 2))

                if p_cnt > 0 and dur > 0:
                    PIPELINE_THROUGHPUT.set(round(p_cnt / dur, 2))
                else:
                    PIPELINE_THROUGHPUT.set(0.0)

            # --- DOMAIN METRICS: SALES DOMAIN ---
            sales_execs = db.query(PipelineExecution).join(
                Pipeline, PipelineExecution.pipeline_id == Pipeline.id
            ).all()

            sales_processed = 0
            sales_loaded = 0
            sales_succ = 0
            sales_dur = 0.0

            mfg_processed = 0
            mfg_loaded = 0
            mfg_succ = 0
            mfg_dur = 0.0

            for ex in sales_execs:
                pipe = ex.pipeline
                name_str = (pipe.name if pipe else "").lower()
                dest_str = str((pipe.destination_config if pipe else {}) or "").lower()

                is_mfg = "manufacturing" in name_str or "production" in name_str or "fact_production" in dest_str or "manufacturing" in dest_str

                if is_mfg:
                    mfg_processed += (ex.records_processed or 0)
                    mfg_loaded += (ex.records_loaded or 0)
                    if ex.status == "SUCCESS":
                        mfg_succ += 1
                    mfg_dur += (ex.duration_seconds or 0.0)
                else:
                    sales_processed += (ex.records_processed or 0)
                    sales_loaded += (ex.records_loaded or 0)
                    if ex.status == "SUCCESS":
                        sales_succ += 1
                    sales_dur += (ex.duration_seconds or 0.0)

            SALES_EXEC_SUCCESS_COUNT.set(sales_succ)
            SALES_RECORDS_PROCESSED_TOTAL.set(sales_processed)
            SALES_RECORDS_LOADED_TOTAL.set(sales_loaded)
            SALES_PIPELINE_THROUGHPUT.set(round(sales_processed / sales_dur, 2) if sales_dur > 0 else 0.0)

            MANUFACTURING_EXEC_SUCCESS_COUNT.set(mfg_succ)
            MANUFACTURING_RECORDS_PROCESSED_TOTAL.set(mfg_processed)
            MANUFACTURING_RECORDS_LOADED_TOTAL.set(mfg_loaded)
            MANUFACTURING_PIPELINE_THROUGHPUT.set(round(mfg_processed / mfg_dur, 2) if mfg_dur > 0 else 0.0)

            # Quality score
            avg_score = db.query(func.avg(DataProfile.quality_score)).scalar()
            PIPELINE_DATA_QUALITY_SCORE.set(round(float(avg_score or 100.0), 1))

            # Active schedules
            sched_cnt = db.query(func.count(PipelineSchedule.id)).filter(PipelineSchedule.enabled == True).scalar() or 0
            PIPELINE_SCHEDULES_ENABLED.set(sched_cnt)

            # System Health
            DATABASE_CONNECTED.set(1.0)
            REDIS_CONNECTED.set(1.0 if check_redis_health() == "healthy" else 0.0)
            CELERY_WORKERS_ONLINE.set(1.0 if check_celery_health() == "healthy" else 0.0)

        finally:
            db.close()
    except Exception:
        DATABASE_CONNECTED.set(0.0)


def get_metrics_response() -> Response:
    """Returns standard Prometheus metrics exposition payload."""
    sync_db_metrics()
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
