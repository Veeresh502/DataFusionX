import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.data_profile import DataProfile
from app.core.security import get_password_hash, create_access_token
from app.services.profiling import profile_dataframe, get_or_create_data_profile


@pytest.fixture
def test_setup(db: Session):
    org = Organization(name="Profiling Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        name="Profile Tester",
        email="profiler@test.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org.id,
        role="ADMIN"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return user, org, token


def test_profiling_numerical_columns():
    df = pd.DataFrame({
        "age": [20, 22, 25, 30, 28, 100],  # 100 is an outlier
        "salary": [50000, 55000, 60000, 65000, 70000, 75000]
    })
    res = profile_dataframe(df)
    
    assert res["summary"]["row_count"] == 6
    assert res["summary"]["column_count"] == 2

    age_prof = next(c for c in res["column_profiles"] if c["name"] == "age")
    assert age_prof["min"] == 20
    assert age_prof["max"] == 100
    assert age_prof["median"] == 26.5
    assert age_prof["outlier_count"] >= 1


def test_profiling_categorical_columns():
    df = pd.DataFrame({
        "city": ["New York", "London", "New York", "Paris", "New York", "London"]
    })
    res = profile_dataframe(df)
    
    city_prof = res["column_profiles"][0]
    assert city_prof["cardinality"] == 3
    assert city_prof["top_values"][0]["value"] == "New York"
    assert city_prof["top_values"][0]["count"] == 3


def test_profiling_date_columns():
    df = pd.DataFrame({
        "joined_date": pd.to_datetime(["2023-01-15", "2023-05-20", "2024-02-10"])
    })
    res = profile_dataframe(df)
    
    date_prof = res["column_profiles"][0]
    assert "2023-01-15" in str(date_prof["min_date"])
    assert "2024-02-10" in str(date_prof["max_date"])


def test_profiling_missing_and_duplicates():
    df = pd.DataFrame({
        "a": [1, 1, None, 2],
        "b": ["X", "X", "Y", "Z"]
    })
    res = profile_dataframe(df)
    
    assert res["summary"]["duplicate_rows"] == 1  # (1, X) repeated
    col_a = next(c for c in res["column_profiles"] if c["name"] == "a")
    assert col_a["null_count"] == 1
    assert col_a["null_percentage"] == 25.0


def test_profiling_empty_dataset():
    df = pd.DataFrame(columns=["a", "b", "c"])
    res = profile_dataframe(df)
    
    assert res["summary"]["row_count"] == 0
    assert res["summary"]["column_count"] == 3
    assert res["quality_scores"]["completeness"] == 0.0


def test_profile_caching_and_api_endpoint(client: TestClient, test_setup, db: Session):
    user, org, token = test_setup
    
    csv_bytes = b"product,price\nLaptop,1200\nMouse,25\nKeyboard,75\nLaptop,1200"
    
    # 1. Upload CSV Data Source
    upload_res = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("inventory.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "Inventory CSV"}
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    # 2. Call GET /api/datasets/{id}/profile (First hit -> computes and stores in DB)
    res1 = client.get(
        f"/api/datasets/{source_id}/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["summary"]["row_count"] == 4
    assert data1["quality_scores"]["overall"] > 0

    # Verify profile object was cached in database
    cached = db.query(DataProfile).filter(DataProfile.data_source_id == source_id).first()
    assert cached is not None

    # 3. Call GET /api/sources/{id}/profile (Second hit -> returns cached profile)
    res2 = client.get(
        f"/api/sources/{source_id}/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res2.status_code == 200
    assert res2.json()["id"] == data1["id"]
