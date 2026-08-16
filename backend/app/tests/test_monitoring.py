import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def auth_setup(db: Session):
    org = Organization(name="Monitoring Org Test")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        organization_id=org.id,
        name="Test Monitor User",
        email="monitor_test@example.com",
        password_hash=get_password_hash("secret123"),
        role="ADMIN"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    return {"user": user, "org": org, "headers": headers}



def test_health_endpoint(client: TestClient, db: Session):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "celery" in data
    assert "version" in data


def test_root_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded", "unhealthy"]


def test_database_health_endpoint(client: TestClient):
    response = client.get("/api/health/database")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_prometheus_metrics_endpoint(client: TestClient):
    # Make a few API calls to populate metrics
    client.get("/api/health")
    
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text
    assert "http_requests_total" in content
    assert "pipeline_executions_total" in content
    assert "pipeline_stage_duration_seconds" in content


def test_monitoring_overview_endpoint(client: TestClient, auth_setup: dict):
    headers = auth_setup["headers"]
    response = client.get("/api/monitoring/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "system_health" in data
    assert "pipeline_overview" in data
    assert "quality_summary" in data
    assert "schedule_summary" in data

    assert data["system_health"]["api"] == "HEALTHY"
    assert "success_rate" in data["pipeline_overview"]


def test_monitoring_sub_endpoints(client: TestClient, auth_setup: dict):
    headers = auth_setup["headers"]
    # Test system health
    res1 = client.get("/api/monitoring/system-health", headers=headers)
    assert res1.status_code == 200

    # Test failures
    res2 = client.get("/api/monitoring/failures", headers=headers)
    assert res2.status_code == 200
    assert isinstance(res2.json(), list)

    # Test performance
    res3 = client.get("/api/monitoring/performance", headers=headers)
    assert res3.status_code == 200
    assert "slowest_pipelines" in res3.json()

    # Test data quality
    res4 = client.get("/api/monitoring/data-quality", headers=headers)
    assert res4.status_code == 200
    assert "average_quality_score" in res4.json()

    # Test schedules
    res5 = client.get("/api/monitoring/schedules", headers=headers)
    assert res5.status_code == 200
    assert "total_schedules" in res5.json()


def test_multi_tenant_monitoring_isolation(client: TestClient, db: Session, auth_setup: dict):
    headers_a = auth_setup["headers"]

    # Create Org B and Org B Pipeline Execution
    org_b = Organization(name="Tenant B Monitoring test")
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    source_b = DataSource(
        organization_id=org_b.id,
        name="Org B Source",
        type="CSV",
        configuration={"file_path": "sales_clean.csv"}
    )

    db.add(source_b)
    db.commit()
    db.refresh(source_b)

    pipe_b = Pipeline(
        organization_id=org_b.id,
        source_id=source_b.id,
        name="Org B Secret Pipeline",
        steps=[]
    )
    db.add(pipe_b)
    db.commit()
    db.refresh(pipe_b)

    exec_b = PipelineExecution(
        pipeline_id=pipe_b.id,
        organization_id=org_b.id,
        status="FAILED",
        records_processed=10,
        records_failed=50
    )
    db.add(exec_b)
    db.commit()

    # Query monitoring endpoints using User A (Org A)
    res = client.get("/api/monitoring/failures", headers=headers_a)
    assert res.status_code == 200
    failures = res.json()
    
    # Org A must NOT see Org B's failing pipeline
    for f in failures:
        assert f["pipeline_name"] != "Org B Secret Pipeline"
