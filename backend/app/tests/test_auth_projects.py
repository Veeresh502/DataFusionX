import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project
from app.core.security import get_password_hash


def test_register_success(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Alice Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@org1.com"
    assert data["role"] == "ADMIN"
    assert "password_hash" not in data
    assert data["organization"]["name"] == "Org One"


def test_register_duplicate_email(client: TestClient):
    # Register first user
    client.post(
        "/api/auth/register",
        json={
            "name": "Alice Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    # Attempt second registration with same email
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Bob Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org Two"
        }
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_register_duplicate_org(client: TestClient):
    # Register first user/org
    client.post(
        "/api/auth/register",
        json={
            "name": "Alice Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    # Attempt registration with duplicate org name
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Bob Admin",
            "email": "bob@org2.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    assert response.status_code == 400
    assert "Organization name already exists" in response.json()["detail"]


def test_login_success(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "name": "Alice Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    response = client.post(
        "/api/auth/login",
        json={
            "email": "alice@org1.com",
            "password": "Password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "name": "Alice Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    response = client.post(
        "/api/auth/login",
        json={
            "email": "alice@org1.com",
            "password": "WrongPassword"
        }
    )
    assert response.status_code == 400
    assert "Incorrect email or password" in response.json()["detail"]


def test_auth_me_protected(client: TestClient):
    # Access /me without token
    response = client.get("/api/auth/me")
    assert response.status_code == 401

    # Register & Login
    client.post(
        "/api/auth/register",
        json={
            "name": "Alice Admin",
            "email": "alice@org1.com",
            "password": "Password123",
            "organization_name": "Org One"
        }
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": "alice@org1.com", "password": "Password123"}
    )
    token = login_res.json()["access_token"]

    # Access /me with token
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "alice@org1.com"


def test_projects_rbac(client: TestClient, db: Session):
    # Setup organization
    org = Organization(name="Test Org")
    db.add(org)
    db.commit()

    # Create users with different roles
    roles = ["ADMIN", "DATA_ENGINEER", "ANALYST", "VIEWER"]
    users = {}
    tokens = {}

    for role in roles:
        user = User(
            name=f"User {role}",
            email=f"{role.lower()}@test.com",
            password_hash=get_password_hash("Password123"),
            organization_id=org.id,
            role=role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        users[role] = user

        # Get token
        login_res = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "Password123"}
        )
        tokens[role] = login_res.json()["access_token"]

    # Test Project creation
    # ADMIN should succeed
    response = client.post(
        "/api/projects",
        json={"name": "Admin Project"},
        headers={"Authorization": f"Bearer {tokens['ADMIN']}"}
    )
    assert response.status_code == 201

    # DATA_ENGINEER should succeed
    response = client.post(
        "/api/projects",
        json={"name": "DE Project"},
        headers={"Authorization": f"Bearer {tokens['DATA_ENGINEER']}"}
    )
    assert response.status_code == 201

    # ANALYST should fail (requires ADMIN or DATA_ENGINEER)
    response = client.post(
        "/api/projects",
        json={"name": "Analyst Project"},
        headers={"Authorization": f"Bearer {tokens['ANALYST']}"}
    )
    assert response.status_code == 403

    # VIEWER should fail
    response = client.post(
        "/api/projects",
        json={"name": "Viewer Project"},
        headers={"Authorization": f"Bearer {tokens['VIEWER']}"}
    )
    assert response.status_code == 403


def test_projects_multi_tenant_isolation(client: TestClient, db: Session):
    # Setup Organization A and User A (ADMIN)
    org_a = Organization(name="Org A")
    db.add(org_a)
    db.commit()
    user_a = User(
        name="User A",
        email="a@orga.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org_a.id,
        role="ADMIN"
    )
    db.add(user_a)
    db.commit()

    # Setup Organization B and User B (ADMIN)
    org_b = Organization(name="Org B")
    db.add(org_b)
    db.commit()
    user_b = User(
        name="User B",
        email="b@orgb.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org_b.id,
        role="ADMIN"
    )
    db.add(user_b)
    db.commit()

    # Log in user A and B
    login_a = client.post("/api/auth/login", json={"email": "a@orga.com", "password": "Password123"}).json()
    login_b = client.post("/api/auth/login", json={"email": "b@orgb.com", "password": "Password123"}).json()
    token_a = login_a["access_token"]
    token_b = login_b["access_token"]

    # Create a project as User A (linked to Org A)
    client.post(
        "/api/projects",
        json={"name": "Project A"},
        headers={"Authorization": f"Bearer {token_a}"}
    )

    # User A lists projects -> should see Project A
    res_a = client.get("/api/projects", headers={"Authorization": f"Bearer {token_a}"})
    assert len(res_a.json()) == 1
    assert res_a.json()[0]["name"] == "Project A"

    # User B lists projects -> should NOT see Project A (Org A isolation)
    res_b = client.get("/api/projects", headers={"Authorization": f"Bearer {token_b}"})
    assert len(res_b.json()) == 0
