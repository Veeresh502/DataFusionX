import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.core.security import get_password_hash, create_access_token
from app.services.dag_compiler import validate_and_compile_dag


@pytest.fixture
def dag_setup(db: Session):
    org = Organization(name="DAG Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        name="DAG Builder",
        email="dag@test.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org.id,
        role="ADMIN"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    src = DataSource(
        name="CSV Source",
        type="CSV",
        organization_id=org.id,
        created_by=user.id,
        configuration={"file_path": "data/sales.csv", "row_count": 10}
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    token = create_access_token(user.id)
    return user, org, src, token


def test_dag_cycle_detection():
    nodes = [
        {"id": "node_1", "category": "source", "type": "csv_source", "data": {"source_id": 1}},
        {"id": "node_2", "category": "transformation", "type": "remove_duplicates", "data": {}},
        {"id": "node_3", "category": "destination", "type": "postgres_destination", "data": {"table_name": "target"}},
    ]

    # Cycle: node_1 -> node_2 -> node_1, and node_2 -> node_3
    edges = [
        {"source": "node_1", "target": "node_2"},
        {"source": "node_2", "target": "node_1"},
        {"source": "node_2", "target": "node_3"},
    ]


    valid, errors, steps, source_id, dest_config = validate_and_compile_dag(nodes, edges)
    assert valid is False
    assert any("cycle" in e.lower() for e in errors)


def test_dag_orphan_node_detection():
    nodes = [
        {"id": "node_1", "category": "source", "type": "csv_source", "data": {"source_id": 1}},
        {"id": "node_2", "category": "transformation", "type": "remove_duplicates", "data": {}},
        {"id": "node_orphan", "category": "transformation", "type": "trim_text", "data": {}},
        {"id": "node_3", "category": "destination", "type": "postgres_destination", "data": {"table_name": "target"}},
    ]

    edges = [
        {"source": "node_1", "target": "node_2"},
        {"source": "node_2", "target": "node_3"},
    ]

    valid, errors, steps, source_id, dest_config = validate_and_compile_dag(nodes, edges)
    assert valid is False
    assert any("disconnected" in e.lower() for e in errors)


def test_dag_missing_source_or_destination():
    nodes = [
        {"id": "node_1", "category": "transformation", "type": "remove_duplicates", "data": {}},
        {"id": "node_2", "category": "destination", "type": "postgres_destination", "data": {"table_name": "target"}},
    ]
    edges = [{"source": "node_1", "target": "node_2"}]

    valid, errors, steps, source_id, dest_config = validate_and_compile_dag(nodes, edges)
    assert valid is False
    assert any("source node" in e.lower() for e in errors)


def test_dag_topological_sort_compilation():
    nodes = [
        {"id": "1", "category": "source", "type": "csv_source", "data": {"source_id": 10}},
        {"id": "2", "category": "transformation", "type": "remove_duplicates", "data": {"subset": ["email"]}},
        {"id": "3", "category": "transformation", "type": "calculate_column", "data": {"target_column": "total", "formula": "qty * price"}},
        {"id": "4", "category": "validation", "type": "NOT_NULL", "data": {"column": "total"}},
        {"id": "5", "category": "destination", "type": "postgres_destination", "data": {"table_name": "target_orders", "if_exists": "append"}},
    ]

    edges = [
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3"},
        {"source": "3", "target": "4"},
        {"source": "4", "target": "5"},
    ]

    valid, errors, steps, source_id, dest_config = validate_and_compile_dag(nodes, edges)
    assert valid is True
    assert len(errors) == 0
    assert source_id == 10
    assert dest_config["table_name"] == "target_orders"
    assert len(steps) == 3
    assert steps[0]["type"] == "remove_duplicates"
    assert steps[1]["type"] == "calculate_column"
    assert steps[2]["type"] == "NOT_NULL"


def test_pipeline_cloning_endpoint(client: TestClient, dag_setup):
    user, org, src, token = dag_setup

    create_res = client.post(
        "/api/pipelines",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Original DAG Pipeline",
            "source_id": src.id,
            "dag_nodes": [
                {"id": "s1", "category": "source", "type": "csv_source", "data": {"source_id": src.id}},
                {"id": "d1", "category": "destination", "type": "postgres_destination", "data": {"table_name": "cloned_target"}}
            ],
            "dag_edges": [
                {"source": "s1", "target": "d1"}
            ]
        }
    )
    assert create_res.status_code == 201
    pipe_id = create_res.json()["id"]

    # Clone Pipeline
    clone_res = client.post(
        f"/api/pipelines/{pipe_id}/clone",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert clone_res.status_code == 201
    cloned_data = clone_res.json()
    assert cloned_data["name"] == "Original DAG Pipeline (Copy)"
    assert cloned_data["source_id"] == src.id
    assert len(cloned_data["dag_nodes"]) == 2
