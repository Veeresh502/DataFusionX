from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectOut
from app.api.deps import get_current_user, RoleChecker

router = APIRouter()

# Role checkers
require_write_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER"])
require_read_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER", "ANALYST", "VIEWER"])


@router.get("/projects", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access)
) -> List[ProjectOut]:
    # Tenant Isolation: Filter by current user's organization_id
    projects = db.query(Project).filter(Project.organization_id == current_user.organization_id).all()
    return projects


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access)
) -> ProjectOut:
    # Tenant Isolation: Project is linked directly to current user's organization_id
    project = Project(
        name=data.name,
        organization_id=current_user.organization_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
