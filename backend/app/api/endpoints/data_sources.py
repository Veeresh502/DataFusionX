from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_source import DataSource
from app.models.user import User
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceOut,
    RESTConnectionTestRequest,
    PostgresConnectionTestRequest,
    ConnectionTestResponse,
)
from app.services.data_source import (
    process_csv_bytes,
    process_excel_bytes,
    process_json_bytes,
    test_rest_api_connection,
    test_postgres_connection,
)
from app.core.encryption import encrypt_credentials
from app.api.deps import get_current_user, RoleChecker

router = APIRouter()

require_write_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER"])
require_read_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER", "ANALYST", "VIEWER"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


@router.post("/upload", response_model=DataSourceOut, status_code=status.HTTP_201_CREATED)
async def upload_data_source_file(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> DataSourceOut:
    filename = file.filename or "uploaded_file"
    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit of 10MB"
        )

    ext = filename.lower().split(".")[-1]
    if ext == "csv":
        source_type = "CSV"
        config = process_csv_bytes(contents, filename)
    elif ext in ["xlsx", "xls"]:
        source_type = "EXCEL"
        config = process_excel_bytes(contents, filename)
    elif ext == "json":
        source_type = "JSON"
        config = process_json_bytes(contents, filename)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{ext}'. Supported formats: .csv, .xlsx, .xls, .json"
        )

    source_name = name.strip() if name and name.strip() else filename

    from app.services.data_source import sanitize_json_obj
    sanitized_config = sanitize_json_obj(config)

    data_source = DataSource(
        name=source_name,
        type=source_type,
        description=description,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        configuration=sanitized_config,
        encrypted_credentials=None,
    )

    db.add(data_source)
    db.commit()
    db.refresh(data_source)
    return data_source



@router.post("/test-connection/rest", response_model=ConnectionTestResponse)
def test_rest_connection_endpoint(
    data: RESTConnectionTestRequest,
    current_user: User = Depends(require_read_access)
) -> ConnectionTestResponse:
    success, msg, details = test_rest_api_connection(
        url=data.url,
        method=data.method,
        headers=data.headers,
        auth_token=data.auth_token,
    )
    return ConnectionTestResponse(success=success, message=msg, details=details)


@router.post("/test-connection/postgres", response_model=ConnectionTestResponse)
def test_postgres_connection_endpoint(
    data: PostgresConnectionTestRequest,
    current_user: User = Depends(require_read_access)
) -> ConnectionTestResponse:
    success, msg, details = test_postgres_connection(
        host=data.host,
        port=data.port,
        database=data.database,
        username=data.username,
        password=data.password,
        schema_name=data.schema_name or "public",
        table=data.table,
    )
    return ConnectionTestResponse(success=success, message=msg, details=details)


@router.post("", response_model=DataSourceOut, status_code=status.HTTP_201_CREATED)
def create_data_source(
    data: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> DataSourceOut:
    encrypted_creds = None
    if data.credentials:
        encrypted_creds = encrypt_credentials(data.credentials)

    data_source = DataSource(
        name=data.name,
        type=data.type.upper(),
        description=data.description,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        configuration=data.configuration,
        encrypted_credentials=encrypted_creds,
    )

    db.add(data_source)
    db.commit()
    db.refresh(data_source)
    return data_source


@router.get("", response_model=List[DataSourceOut])
def list_data_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[DataSourceOut]:
    # Multi-tenant isolation: filter strictly by organization_id
    sources = db.query(DataSource).filter(DataSource.organization_id == current_user.organization_id).all()
    return sources


from app.schemas.data_profile import DataProfileOut
from app.services.profiling import get_or_create_data_profile

@router.get("/{source_id}", response_model=DataSourceOut)
def get_data_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> DataSourceOut:
    source = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.organization_id == current_user.organization_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found"
        )
    return source


@router.get("/{source_id}/profile", response_model=DataProfileOut)
def get_data_source_profile(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> DataProfileOut:
    source = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.organization_id == current_user.organization_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )

    profile = get_or_create_data_profile(source, db)
    return profile



@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> None:
    source = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.organization_id == current_user.organization_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found"
        )

    db.delete(source)
    db.commit()
    return None
