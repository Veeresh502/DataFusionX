import pytest
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.user import User
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.services.ai_service import (
    generate_pipeline_proposal_service,
    process_natural_language_query,
    explain_pipeline_failure_service
)


def get_test_users(db: Session):
    org_a = db.query(Organization).filter(Organization.name == "Copilot Test Org A").first()
    if not org_a:
        org_a = Organization(name="Copilot Test Org A")
        db.add(org_a); db.commit(); db.refresh(org_a)

    user_a = db.query(User).filter(User.email == "user_copilot_a@example.com").first()
    if not user_a:
        user_a = User(email="user_copilot_a@example.com", password_hash="hash", name="User A", organization_id=org_a.id, role="ADMIN")
        db.add(user_a); db.commit(); db.refresh(user_a)

    org_b = db.query(Organization).filter(Organization.name == "Copilot Test Org B").first()
    if not org_b:
        org_b = Organization(name="Copilot Test Org B")
        db.add(org_b); db.commit(); db.refresh(org_b)

    user_b = db.query(User).filter(User.email == "user_copilot_b@example.com").first()
    if not user_b:
        user_b = User(email="user_copilot_b@example.com", password_hash="hash", name="User B", organization_id=org_b.id, role="ADMIN")
        db.add(user_b); db.commit(); db.refresh(user_b)

    return user_a, user_b


def create_sample_datasource(db: Session, user: User, name: str, ds_type: str, preview_data: list) -> DataSource:
    ds = DataSource(
        organization_id=user.organization_id,
        name=name,
        type=ds_type,
        configuration={"preview": preview_data}
    )
    db.add(ds); db.commit(); db.refresh(ds)
    return ds


# TEST 1 — Basic Generic Pipeline Generation
def test_1_basic_generic_pipeline_generation(db: Session):
    user_a, _ = get_test_users(db)
    emp_data = [
        {"employee_id": "EMP01", "employee_name": "Alice", "department": "Engineering", "salary": 85000},
        {"employee_id": "EMP02", "employee_name": "Bob", "department": "Sales", "salary": 72000},
    ]
    ds = create_sample_datasource(db, user_a, "employee_data.csv", "CSV", emp_data)

    prompt = "Clean the employee data, remove duplicates, fill missing values, normalize department names, validate employee_id, and load it into the Generic Warehouse."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["source_id"] == ds.id
    assert "employee_id" in proposal["detected_columns"]
    assert len(proposal["steps"]) >= 2
    assert proposal["destination_config"]["warehouse_model_slug"] == "generic"
    assert len(proposal["dag_nodes"]) >= 3
    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True

    pipes = db.query(Pipeline).filter(Pipeline.source_id == ds.id).all()
    assert len(pipes) == 0


# TEST 15 — Malformed / Unsupported AI Pipeline Request (BUG FIX TEST 15)
def test_15_invalid_malformed_transformation_magic_clean(db: Session):
    user_a, _ = get_test_users(db)
    emp_data = [{"employee_id": "EMP01", "salary": 85000}]
    ds = create_sample_datasource(db, user_a, "magic_clean_test.csv", "CSV", emp_data)

    prompt = '{"transformation": "magic_clean"}'
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    # Must be marked INVALID, can_approve False, is_valid False
    assert proposal["status"] == "INVALID"
    assert proposal["can_approve"] is False
    assert proposal["is_valid"] is False
    assert "magic_clean" in proposal["unsupported_operations"]
    assert any(e["type"] == "UNSUPPORTED_TRANSFORMATION" for e in proposal["errors"])
    assert any("Unsupported transformation: 'magic_clean'" in e["message"] for e in proposal["errors"])


# TEST 15B — Second Unsupported Transformation
def test_15b_unsupported_transformation_super_clean_ai(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "super_clean_test.csv", "CSV", [{"id": 1}])

    prompt = "Apply the super_clean_ai transformation to this dataset."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] == "INVALID"
    assert proposal["can_approve"] is False
    assert proposal["is_valid"] is False
    assert "super_clean_ai" in proposal["unsupported_operations"]


# TEST A — Valid Zero-Transformation Pipeline
def test_a_valid_zero_transformation_pipeline(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "passthrough.csv", "CSV", [{"id": 1, "val": "A"}])

    prompt = "Load this CSV into Generic Warehouse without applying any transformations."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] == "VALID"
    assert proposal["can_approve"] is True
    assert proposal["is_valid"] is True
    assert len(proposal["steps"]) == 0
    assert len(proposal["unsupported_operations"]) == 0


# TEST B — Valid Transformation Pipeline
def test_b_valid_transformation_pipeline(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "dedup_test.csv", "CSV", [{"employee_id": "EMP1"}])

    prompt = "Remove duplicates and load into Generic Warehouse."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True
    assert proposal["is_valid"] is True
    assert len(proposal["steps"]) >= 1
    assert proposal["steps"][0]["type"] == "remove_duplicates"


# TEST D — Mixed Valid + Unsupported (Entire Proposal Invalid)
def test_d_mixed_valid_and_unsupported_invalidates_entire_proposal(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "mixed_test.csv", "CSV", [{"id": 1}])

    prompt = "Use magic_clean and remove_duplicates."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] == "INVALID"
    assert proposal["can_approve"] is False
    assert proposal["is_valid"] is False
    assert "magic_clean" in proposal["unsupported_operations"]


# TEST E — Incomplete Calculated Column Request
def test_e_incomplete_calculated_column_request(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "calc_incomp.csv", "CSV", [{"salary": 80000}])

    prompt = "Create a calculated column."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] == "INCOMPLETE"
    assert proposal["can_approve"] is False
    assert proposal["is_valid"] is False


# TEST F — Valid Calculation Request
def test_f_valid_calculation_request(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "calc_valid.csv", "CSV", [{"quantity": 5, "unit_price": 100}])

    prompt = "Calculate total_value = quantity * unit_price"
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True
    assert proposal["is_valid"] is True
    calc_steps = [s for s in proposal["steps"] if s.get("type") == "calculate_column"]
    assert len(calc_steps) == 1
    assert calc_steps[0]["column"] == "total_value"


# TEST 2 — Invalid Column Detection
def test_2_invalid_column_hallucination_prevention(db: Session):
    user_a, _ = get_test_users(db)
    emp_data = [
        {"employee_id": "EMP01", "employee_name": "Alice", "department": "Engineering", "salary": 85000},
    ]
    ds = create_sample_datasource(db, user_a, "employee_data_no_age.csv", "CSV", emp_data)

    prompt = "Filter employees where age is greater than 30."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] == "INVALID"
    assert proposal["can_approve"] is False
    assert any("Column 'age' does not exist" in w for w in proposal["warnings"])


# TEST 12A — Domain Incompatibility Warning (inventory_data.csv -> Sales Analytics)
def test_12a_domain_incompatibility_inventory_to_sales(db: Session):
    user_a, _ = get_test_users(db)
    inv_data = [{"item_id": "INV101", "stock_quantity": 500, "warehouse": "WH-North"}]
    ds = create_sample_datasource(db, user_a, "inventory_data_sales_test.csv", "CSV", inv_data)

    prompt = "Load this inventory data into Sales Analytics."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["status"] == "INVALID"
    assert proposal["can_approve"] is False
    assert any("not compatible with the Sales Analytics" in w for w in proposal["warnings"])


# TEST 12B — Domain Compatibility (inventory_data.csv -> Generic Warehouse)
def test_12b_domain_compatibility_inventory_to_generic(db: Session):
    user_a, _ = get_test_users(db)
    inv_data = [{"item_id": "INV101", "stock_quantity": 500, "warehouse": "WH-North"}]
    ds = create_sample_datasource(db, user_a, "inventory_data_generic_test.csv", "CSV", inv_data)

    prompt = "Clean this inventory data and load it into the Generic Warehouse."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["destination_config"]["warehouse_model_slug"] == "generic"
    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True


# TEST 12C — Domain Compatibility (sales_clean_m65.csv -> Sales Analytics)
def test_12c_domain_compatibility_sales_to_sales(db: Session):
    user_a, _ = get_test_users(db)
    sales_data = [{"order_id": "O100", "product_name": "Laptop", "customer_name": "Acme", "revenue": 1500, "quantity": 1, "unit_price": 1500}]
    ds = create_sample_datasource(db, user_a, "sales_clean_m65.csv", "CSV", sales_data)

    prompt = "Prepare this sales data for Sales Analytics."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["destination_config"]["warehouse_model_slug"] == "sales"
    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True


# TEST 12D — Domain Compatibility (manufacturing_clean_m65.csv -> Manufacturing Analytics)
def test_12d_domain_compatibility_mfg_to_mfg(db: Session):
    user_a, _ = get_test_users(db)
    mfg_data = [{"production_id": "P900", "machine_name": "M01", "plant_location": "Facility-A", "units_produced": 400, "defect_count": 2}]
    ds = create_sample_datasource(db, user_a, "manufacturing_clean_m65.csv", "CSV", mfg_data)

    prompt = "Prepare this production data for Manufacturing Analytics."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["destination_config"]["warehouse_model_slug"] == "manufacturing"
    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True


# TEST 12E — Domain Compatibility (sensorreadings.json -> Generic Warehouse)
def test_12e_domain_compatibility_sensor_to_generic(db: Session):
    user_a, _ = get_test_users(db)
    sensor_data = [{"sensor_id": "S101", "temperature": 24.5, "humidity": 60}]
    ds = create_sample_datasource(db, user_a, "sensorreadings.json", "JSON", sensor_data)

    prompt = "Clean sensor readings and load into Generic Warehouse."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert proposal["source_type"] == "JSON"
    assert proposal["destination_config"]["warehouse_model_slug"] == "generic"
    assert proposal["status"] in ["VALID", "WARNING"]
    assert proposal["can_approve"] is True


# TEST 9 — Human Approval Workflow
def test_9_human_approval_workflow(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "approval_data.csv", "CSV", [{"id": 1}])

    prompt = "Clean and validate dataset."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    db_pipes_before = db.query(Pipeline).filter(Pipeline.source_id == ds.id).count()
    assert db_pipes_before == 0

    pipe = Pipeline(
        organization_id=user_a.organization_id,
        name=proposal["proposed_name"],
        source_id=proposal["source_id"],
        steps=proposal["steps"],
        destination_config=proposal["destination_config"],
        dag_nodes=proposal["dag_nodes"],
        dag_edges=proposal["dag_edges"]
    )
    db.add(pipe); db.commit(); db.refresh(pipe)

    assert pipe.id is not None
    exec_count = db.query(PipelineExecution).filter(PipelineExecution.pipeline_id == pipe.id).count()
    assert exec_count == 0


# TEST 10 — Visual DAG Compiler Compatibility
def test_10_visual_dag_compiler_compatibility(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_sample_datasource(db, user_a, "dag_test.csv", "CSV", [{"id": 1, "val": "X"}])

    prompt = "Remove duplicates, normalize text, validate id, and load to Generic Warehouse."
    proposal = generate_pipeline_proposal_service(db, user_a, ds.id, prompt)

    assert len(proposal["dag_nodes"]) >= 3
    assert len(proposal["dag_edges"]) >= 2
    assert proposal["dag_nodes"][0]["type"] == "sourceNode"
    assert proposal["dag_nodes"][-1]["type"] == "destinationNode"


# TEST 11 — M11 AI SQL Assistant Regression
def test_11_ai_sql_assistant_regression(db: Session):
    user_a, _ = get_test_users(db)
    res = process_natural_language_query(
        db=db,
        user=user_a,
        question="Show total units produced by machine",
        warehouse_model_slug="manufacturing"
    )

    assert res["sql"] is not None
    assert "fact_production" in res["sql"].lower() or "dim_machine" in res["sql"].lower()


# TEST 12 — M11 AI Failure Assistant Regression
def test_12_ai_failure_assistant_regression(db: Session):
    user_a, _ = get_test_users(db)
    p = Pipeline(organization_id=user_a.organization_id, name="Failed Pipe", source_id=1, steps=[], destination_config={})
    db.add(p); db.commit(); db.refresh(p)

    exec_obj = PipelineExecution(
        organization_id=user_a.organization_id,
        pipeline_id=p.id,
        status="FAILED",
        current_stage="VALIDATE",
        error="Validation rule NOT_NULL failed on column employee_id",
        records_read=10,
        records_failed=10
    )
    db.add(exec_obj); db.commit(); db.refresh(exec_obj)

    analysis = explain_pipeline_failure_service(db, user_a, exec_obj.id)
    assert analysis["stage"] == "VALIDATE"
    assert "validation" in analysis["summary"].lower()


# TEST 13 — Multi-Tenant Isolation Protection
def test_13_multi_tenant_isolation_protection(db: Session):
    user_a, user_b = get_test_users(db)
    ds_a = create_sample_datasource(db, user_a, "org_a_secret.csv", "CSV", [{"secret": 123}])

    with pytest.raises(ValueError) as exc_info:
        generate_pipeline_proposal_service(db, user_b, ds_a.id, "Clean secret data")

    assert "access denied" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()
