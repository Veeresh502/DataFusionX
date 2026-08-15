import io
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_schedule import PipelineSchedule
from app.models.pipeline_execution import PipelineExecution
from app.core.security import get_password_hash, create_access_token
from app.services.schedule_service import (
    validate_cron_expression,
    validate_timezone_str,
    calculate_next_run,
    create_schedule,
    get_schedules,
    get_schedule_by_id,
    update_schedule,
    toggle_schedule,
    delete_schedule,
    utcnow,
    make_utc_aware,
)

from app.tasks.schedule_tasks import check_and_dispatch_scheduled_pipelines
from app.services.warehouse import clear_warehouse_sales_data, get_warehouse_analytics, clear_warehouse_manufacturing_data


@pytest.fixture
def two_org_users(db: Session):
    # Org A
    org_a = Organization(name="Sched Org A")
    db.add(org_a)
    db.commit()
    db.refresh(org_a)

    user_a = User(
        name="User A",
        email="usera@sched.com",
        password_hash=get_password_hash("Password123!"),
        organization_id=org_a.id,
        role="ADMIN"
    )
    db.add(user_a)

    # Org B
    org_b = Organization(name="Sched Org B")
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        name="User B",
        email="userb@sched.com",
        password_hash=get_password_hash("Password123!"),
        organization_id=org_b.id,
        role="ADMIN"
    )
    db.add(user_b)
    db.commit()

    token_a = create_access_token(user_a.id)
    token_b = create_access_token(user_b.id)

    return (user_a, org_a, token_a), (user_b, org_b, token_b)


def test_cron_and_timezone_validation():
    # Valid crons
    assert validate_cron_expression("*/5 * * * *") is True
    assert validate_cron_expression("0 9 * * *") is True
    assert validate_cron_expression("0 0 * * 1-5") is True

    # Invalid crons
    assert validate_cron_expression("invalid_cron") is False
    assert validate_cron_expression("60 * * * *") is False
    assert validate_cron_expression("") is False

    # Valid timezones
    assert validate_timezone_str("UTC") is True
    assert validate_timezone_str("Asia/Kolkata") is True
    assert validate_timezone_str("America/New_York") is True

    # Invalid timezones
    assert validate_timezone_str("Invalid/Timezone") is False
    assert validate_timezone_str("") is False


def test_next_run_calculation():
    now_utc = datetime(2026, 8, 15, 8, 0, 0, tzinfo=timezone.utc)
    # Cron '0 9 * * *' in Asia/Kolkata (+5:30)
    # 8:00 UTC = 13:30 IST on Aug 15. Next 9:00 AM IST is 09:00 IST on Aug 16 = 03:30 UTC Aug 16
    next_run = calculate_next_run("0 9 * * *", "Asia/Kolkata", start_dt=now_utc)
    assert next_run > now_utc
    assert next_run.strftime("%Y-%m-%d %H:%M") == "2026-08-16 03:30"


def test_schedule_crud_and_multi_tenant_isolation(client: TestClient, two_org_users, db: Session):
    (user_a, org_a, token_a), (user_b, org_b, token_b) = two_org_users

    # Create Data Source & Pipeline for Org A
    source_a = DataSource(
        organization_id=org_a.id,
        name="Org A Source",
        type="CSV",
        configuration={"records": [{"order_id": "O1", "quantity": 1}], "preview": []}
    )
    db.add(source_a)
    db.commit()
    db.refresh(source_a)

    pipe_a = Pipeline(
        organization_id=org_a.id,
        name="Org A Pipeline",
        source_id=source_a.id,
        steps=[],
        destination_config={"destination_type": "WAREHOUSE_STAR_SCHEMA", "table_name": "fact_sales"}
    )
    db.add(pipe_a)
    db.commit()
    db.refresh(pipe_a)

    # 1. Org A creates Schedule successfully
    res_create = client.post(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Org A Daily Sales Schedule",
            "pipeline_id": pipe_a.id,
            "cron_expression": "0 9 * * *",
            "timezone": "Asia/Kolkata",
            "enabled": True
        }
    )
    assert res_create.status_code == 201
    sched_data = res_create.json()
    assert sched_data["name"] == "Org A Daily Sales Schedule"
    assert sched_data["timezone"] == "Asia/Kolkata"
    assert sched_data["next_run_at"] is not None
    sched_id = sched_data["id"]

    # 2. Org B attempts to list schedules -> Empty list (isolation)
    res_b_list = client.get(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_list.status_code == 200
    assert len(res_b_list.json()) == 0

    # 3. Org B attempts to access Org A's schedule -> HTTP 404
    res_b_get = client.get(
        f"/api/schedules/{sched_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_get.status_code == 404

    # 4. Org B attempts to update Org A's schedule -> HTTP 400/404
    res_b_put = client.put(
        f"/api/schedules/{sched_id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"name": "Hacked Name"}
    )
    assert res_b_put.status_code == 400

    # 5. Org B attempts to create schedule for Org A's pipeline -> HTTP 400
    res_b_create = client.post(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "name": "Org B Unauthorized Schedule",
            "pipeline_id": pipe_a.id,
            "cron_expression": "0 9 * * *",
            "timezone": "UTC"
        }
    )
    assert res_b_create.status_code == 400

    # 6. Invalid Cron rejection test
    res_invalid_cron = client.post(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Invalid Cron Schedule",
            "pipeline_id": pipe_a.id,
            "cron_expression": "invalid_cron_string",
            "timezone": "UTC"
        }
    )
    assert res_invalid_cron.status_code == 400
    assert "Invalid cron expression" in res_invalid_cron.json()["detail"]


def test_celery_beat_dispatch_task(db: Session):
    # Setup test org & pipeline
    org = Organization(name="Beat Test Org")
    db.add(org)
    db.commit()

    source = DataSource(
        organization_id=org.id,
        name="Beat Source",
        type="CSV",
        configuration={"records": [{"order_id": "O-BEAT-1", "quantity": 5}], "preview": []}
    )
    db.add(source)
    db.commit()

    pipeline = Pipeline(
        organization_id=org.id,
        name="Beat Pipeline",
        source_id=source.id,
        steps=[],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "beat_out", "if_exists": "replace"}
    )
    db.add(pipeline)
    db.commit()

    # Create schedule with next_run_at in the past (due for execution)
    past_time = utcnow() - timedelta(minutes=5)
    schedule = PipelineSchedule(
        organization_id=org.id,
        pipeline_id=pipeline.id,
        name="Past Due Beat Schedule",
        cron_expression="*/5 * * * *",
        timezone="UTC",
        enabled=True,
        next_run_at=past_time
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    # Trigger Beat tick task
    beat_result = check_and_dispatch_scheduled_pipelines(db=db)
    assert beat_result["status"] == "SUCCESS"
    assert beat_result["dispatched"] >= 1


    # Verify schedule was updated with new next_run_at > past_time
    db.refresh(schedule)
    assert schedule.last_run_at is not None
    assert make_utc_aware(schedule.next_run_at) > make_utc_aware(past_time)


    # Verify Execution record created with trigger_type="SCHEDULED"
    execution = db.query(PipelineExecution).filter(
        PipelineExecution.schedule_id == schedule.id
    ).first()
    assert execution is not None
    assert execution.trigger_type == "SCHEDULED"
    assert execution.pipeline_id == pipeline.id


def test_overlap_and_duplicate_prevention(db: Session):
    org = Organization(name="Overlap Org")
    db.add(org)
    db.commit()

    source = DataSource(organization_id=org.id, name="Src", type="CSV", configuration={"records": []})
    db.add(source)
    db.commit()

    pipeline = Pipeline(organization_id=org.id, name="Overlap Pipe", source_id=source.id, steps=[], destination_config={})
    db.add(pipeline)
    db.commit()

    # Create an active RUNNING execution for this pipeline
    active_exec = PipelineExecution(
        pipeline_id=pipeline.id,
        organization_id=org.id,
        status="RUNNING",
        current_stage="TRANSFORM"
    )
    db.add(active_exec)

    # Create due schedule
    past_time = utcnow() - timedelta(minutes=10)
    schedule = PipelineSchedule(
        organization_id=org.id,
        pipeline_id=pipeline.id,
        name="Overlap Schedule",
        cron_expression="*/5 * * * *",
        timezone="UTC",
        enabled=True,
        next_run_at=past_time
    )
    db.add(schedule)
    db.commit()

    # Run Beat check
    beat_result = check_and_dispatch_scheduled_pipelines(db=db)
    assert beat_result["status"] == "SUCCESS"


    # Verify no new execution was dispatched (overlap prevented)
    sched_execs = db.query(PipelineExecution).filter(PipelineExecution.schedule_id == schedule.id).all()
    assert len(sched_execs) == 0

    # Verify schedule.next_run_at was advanced so Beat doesn't get stuck
    db.refresh(schedule)
    assert make_utc_aware(schedule.next_run_at) > make_utc_aware(past_time)



def test_scheduled_sales_warehouse_execution(client: TestClient, two_org_users, db: Session):
    clear_warehouse_sales_data(db)
    (user_a, org_a, token_a), _ = two_org_users

    # Upload Sales CSV
    csv_bytes = (
        b"order_id,order_date,customer_id,customer_name,city,product_id,product_name,category,quantity,unit_price,discount\n"
        b"ORD-SCHED-1,2026-08-15,C-100,Acme Sched,New York,P-100,Server Sched,Hardware,5,2000,100\n"
    )
    upload_res = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("sales_sched.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "Sales Sched Dataset"}
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    # Create Sales Pipeline
    pipe_res = client.post(
        "/api/pipelines",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Scheduled Sales Pipeline",
            "source_id": source_id,
            "steps": [],
            "destination_config": {
                "destination_type": "WAREHOUSE_STAR_SCHEMA",
                "table_name": "fact_sales"
            }
        }
    )
    assert pipe_res.status_code == 201
    pipeline_id = pipe_res.json()["id"]

    # Create Schedule
    sched_res = client.post(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Hourly Sales Load",
            "pipeline_id": pipeline_id,
            "cron_expression": "0 * * * *",
            "timezone": "UTC"
        }
    )
    assert sched_res.status_code == 201
    sched_id = sched_res.json()["id"]

    # Manually trigger schedule dispatch via Beat task logic
    schedule = db.query(PipelineSchedule).filter(PipelineSchedule.id == sched_id).first()
    schedule.next_run_at = utcnow() - timedelta(seconds=1)
    db.commit()

    check_and_dispatch_scheduled_pipelines(db=db)

    # Get execution record

    exec_record = db.query(PipelineExecution).filter(PipelineExecution.schedule_id == sched_id).first()
    assert exec_record is not None
    assert exec_record.trigger_type == "SCHEDULED"

    # Verify execution history endpoint
    hist_res = client.get(
        f"/api/schedules/{sched_id}/executions",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert len(hist_data) == 1
    assert hist_data[0]["trigger_type"] == "SCHEDULED"
