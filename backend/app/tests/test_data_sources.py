import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.core.security import get_password_hash, create_access_token
from app.core.encryption import decrypt_credentials


@pytest.fixture
def test_user_and_token(db: Session):
    org = Organization(name="Source Test Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        name="Source Admin",
        email="sourceadmin@test.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org.id,
        role="ADMIN"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return user, org, token


def test_csv_file_upload(client: TestClient, test_user_and_token):
    _, _, token = test_user_and_token
    csv_content = b"id,name,amount\n1,Alpha,100.5\n2,Beta,250.0\n3,Gamma,75.25"
    
    response = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test_sales.csv", io.BytesIO(csv_content), "text/csv")},
        data={"name": "Sales CSV Data"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sales CSV Data"
    assert data["type"] == "CSV"
    assert data["configuration"]["row_count"] == 3
    assert data["configuration"]["column_count"] == 3
    assert "id" in data["configuration"]["columns"]
    assert len(data["configuration"]["preview"]) == 3


def test_csv_with_nan_values_upload(client: TestClient, test_user_and_token):
    _, _, token = test_user_and_token
    # CSV containing empty fields / missing values (NaN)
    csv_content = b"order_id,customer_name,city,quantity\nORD001,Priya Nair,,4\nORD002,Rahul Sharma,Mumbai,\nORD003,Pooja,,10"
    
    response = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sales_clean.csv", io.BytesIO(csv_content), "text/csv")},
        data={"name": "Sales Clean CSV"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sales Clean CSV"
    assert data["configuration"]["row_count"] == 3
    # Verify NaN values were converted to None (null in JSON)
    preview = data["configuration"]["preview"]
    assert preview[0]["city"] is None
    assert preview[1]["quantity"] is None



def test_json_file_upload(client: TestClient, test_user_and_token):
    _, _, token = test_user_and_token
    json_data = json.dumps([
        {"user": "Alice", "score": 95},
        {"user": "Bob", "score": 88}
    ]).encode("utf-8")

    response = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("users.json", io.BytesIO(json_data), "application/json")},
        data={"name": "User Scores"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "JSON"
    assert data["configuration"]["row_count"] == 2


def test_rest_api_connection_test(client: TestClient, test_user_and_token, monkeypatch):
    _, _, token = test_user_and_token
    
    # Mock httpx.Client response to ensure reliable test execution offline
    class MockResponse:
        status_code = 200
        reason_phrase = "OK"
        def json(self):
            return [{"id": 1, "item": "Widget A"}]

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers=None):
            return MockResponse()

    monkeypatch.setattr("httpx.Client", MockClient)

    response = client.post(
        "/api/sources/test-connection/rest",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://api.example.com/v1/data",
            "method": "GET"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["details"]["row_count"] == 1



def test_credential_encryption(client: TestClient, test_user_and_token, db: Session):
    _, _, token = test_user_and_token
    sensitive_password = "super_secret_db_password_123"

    response = client.post(
        "/api/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Production Postgres DB",
            "type": "POSTGRESQL",
            "description": "Main transactional database",
            "configuration": {
                "host": "db.example.com",
                "port": 5432,
                "database": "proddb",
                "table": "orders"
            },
            "credentials": {
                "username": "dbuser",
                "password": sensitive_password
            }
        }
    )
    assert response.status_code == 201
    res_data = response.json()
    
    # 1. Ensure password is NOT present anywhere in the API response output
    assert "credentials" not in res_data
    assert "encrypted_credentials" not in res_data
    assert sensitive_password not in json.dumps(res_data)

    # 2. Verify in database that credentials are encrypted with AES-256-GCM
    source_id = res_data["id"]
    db_obj = db.query(DataSource).filter(DataSource.id == source_id).first()
    assert db_obj.encrypted_credentials is not None
    assert db_obj.encrypted_credentials != sensitive_password
    
    # Decrypt and verify
    decrypted = decrypt_credentials(db_obj.encrypted_credentials)
    assert decrypted["password"] == sensitive_password


def test_data_source_tenant_isolation(client: TestClient, db: Session):
    # Org A User
    org_a = Organization(name="Org A Source")
    db.add(org_a)
    db.commit()
    user_a = User(name="User A", email="usera@orga.com", password_hash=get_password_hash("Pass123"), organization_id=org_a.id, role="ADMIN")
    db.add(user_a)
    db.commit()
    token_a = create_access_token(user_a.id)

    # Org B User
    org_b = Organization(name="Org B Source")
    db.add(org_b)
    db.commit()
    user_b = User(name="User B", email="userb@orgb.com", password_hash=get_password_hash("Pass123"), organization_id=org_b.id, role="ADMIN")
    db.add(user_b)
    db.commit()
    token_b = create_access_token(user_b.id)

    # Org A uploads file
    csv_bytes = b"id,val\n1,A"
    res_upload = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("a.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "Org A Source"}
    )
    source_id = res_upload.json()["id"]

    # User B lists sources -> Should NOT see Org A's source
    res_b_list = client.get("/api/sources", headers={"Authorization": f"Bearer {token_b}"})
    assert len(res_b_list.json()) == 0

    # User B attempts direct fetch by ID -> Should get HTTP 404
    res_b_get = client.get(f"/api/sources/{source_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_get.status_code == 404
