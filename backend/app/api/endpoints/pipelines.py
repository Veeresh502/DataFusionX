from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineOut,
    PipelineExecutionOut,
    DAGValidationRequest,
    DAGValidationResponse,
)
from app.services.etl_engine import run_pipeline
from app.services.dag_compiler import validate_and_compile_dag
from app.api.deps import get_current_user, RoleChecker

router = APIRouter()

require_write_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER"])
require_read_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER", "ANALYST", "VIEWER"])


@router.post("/validate-dag", response_model=DAGValidationResponse)
def validate_dag_endpoint(
    data: DAGValidationRequest,
    current_user: User = Depends(require_read_access),
) -> DAGValidationResponse:
    valid, errors, compiled_steps, source_id, destination_config = validate_and_compile_dag(
        data.dag_nodes, data.dag_edges
    )
    return DAGValidationResponse(
        valid=valid,
        errors=errors,
        steps=compiled_steps,
        source_id=source_id,
        destination_config=destination_config or {},
    )


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    data: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> PipelineOut:
    source_id = data.source_id
    steps = data.steps
    destination_config = data.destination_config
    dag_nodes = data.dag_nodes or []
    dag_edges = data.dag_edges or []

    # If DAG nodes and edges are provided, compile graph into linear steps
    if dag_nodes and dag_edges:
        valid, errors, compiled_steps, compiled_source_id, compiled_dest_config = validate_and_compile_dag(
            dag_nodes, dag_edges
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DAG Validation Failed: {'; '.join(errors)}"
            )
        if compiled_source_id:
            source_id = compiled_source_id
        if compiled_steps:
            steps = compiled_steps
        if compiled_dest_config:
            destination_config = compiled_dest_config

    if not source_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_id is required or must be configured in DAG Source node"
        )

    supported_transformations = {
        "remove_duplicates", "deduplicate", "fill_null", "fill_missing", "trim_text",
        "normalize_text", "filter_rows", "calculate_column", "derived_column",
        "rename_columns", "change_data_types", "drop_null"
    }

    supported_validations = {"not_null", "unique", "range", "regex"}

    # Validate step parameters & registry prior to saving
    for step in steps:
        cat = str(step.get("category", "")).lower()
        st_type = str(step.get("type", "")).lower()

        if cat == "transformation":
            if st_type not in supported_transformations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported transformation: '{st_type}'."
                )
            if st_type in ["calculate_column", "derived_column"]:
                col = step.get("column") or step.get("target_column")
                expr = step.get("expression") or step.get("formula")
                if not col or not expr or step.get("is_incomplete"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Step 'calculate_column' is missing required destination column or expression."
                    )
            elif st_type == "filter_rows" and not step.get("condition"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Step 'filter_rows' requires a filter condition."
                )
        elif cat == "validation":
            rule_tp = str(step.get("rule_type") or st_type).lower()
            if rule_tp not in supported_validations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported validation rule: '{rule_tp}'."
                )
            if not step.get("column"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation step '{step.get('rule_type', 'VALIDATION')}' requires a target column."
                )



    pipeline = Pipeline(
        name=data.name,
        description=data.description,
        source_id=source_id,
        steps=steps,
        destination_config=destination_config,
        dag_nodes=dag_nodes,
        dag_edges=dag_edges,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.get("", response_model=List[PipelineOut])
def list_pipelines(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[PipelineOut]:
    pipelines = db.query(Pipeline).filter(Pipeline.organization_id == current_user.organization_id).all()
    return pipelines


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> PipelineOut:
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == current_user.organization_id
    ).first()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found"
        )
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: int,
    data: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> PipelineOut:
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == current_user.organization_id
    ).first()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found"
        )

    if data.name is not None:
        pipeline.name = data.name
    if data.description is not None:
        pipeline.description = data.description
    if data.source_id is not None:
        pipeline.source_id = data.source_id
    if data.steps is not None:
        pipeline.steps = data.steps
    if data.destination_config is not None:
        pipeline.destination_config = data.destination_config

    if data.dag_nodes is not None:
        pipeline.dag_nodes = data.dag_nodes
    if data.dag_edges is not None:
        pipeline.dag_edges = data.dag_edges

    # Re-compile DAG if nodes and edges are present
    if pipeline.dag_nodes and pipeline.dag_edges:
        valid, errors, compiled_steps, compiled_source_id, compiled_dest_config = validate_and_compile_dag(
            pipeline.dag_nodes, pipeline.dag_edges
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DAG Validation Failed: {'; '.join(errors)}"
            )
        if compiled_source_id:
            pipeline.source_id = compiled_source_id
        if compiled_steps:
            pipeline.steps = compiled_steps
        if compiled_dest_config:
            pipeline.destination_config = compiled_dest_config

    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.post("/{pipeline_id}/clone", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def clone_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> PipelineOut:
    original = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == current_user.organization_id
    ).first()

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found"
        )

    cloned = Pipeline(
        name=f"{original.name} (Copy)",
        description=f"Cloned from {original.name}",
        source_id=original.source_id,
        steps=original.steps,
        destination_config=original.destination_config,
        dag_nodes=original.dag_nodes,
        dag_edges=original.dag_edges,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return cloned


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> None:
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == current_user.organization_id
    ).first()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found"
        )

    db.delete(pipeline)
    db.commit()
    return None


@router.post("/{pipeline_id}/run", response_model=PipelineExecutionOut)
def trigger_pipeline_run(

    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
) -> PipelineExecutionOut:
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == current_user.organization_id
    ).first()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found"
        )

    # 1. Create PipelineExecution record in PENDING state
    execution = PipelineExecution(
        pipeline_id=pipeline.id,
        organization_id=current_user.organization_id,
        status="PENDING",
        current_stage="PENDING",
        logs=[],
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    # 2. Dispatch Celery task (or execute eager/inline if test mode)
    try:
        from app.core.celery_app import celery_app
        from app.tasks.pipeline_tasks import execute_pipeline_task

        if getattr(celery_app.conf, "task_always_eager", False):
            execute_pipeline_task(execution.id, db=db)
        else:
            task = execute_pipeline_task.delay(execution.id)
            execution.celery_task_id = task.id
            db.commit()

        db.refresh(execution)
    except Exception as e:
        from app.tasks.pipeline_tasks import execute_pipeline_task
        execute_pipeline_task(execution.id, db=db)
        db.refresh(execution)

    return execution




@router.get("/{pipeline_id}/executions", response_model=List[PipelineExecutionOut])
def get_pipeline_executions(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[PipelineExecutionOut]:
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == current_user.organization_id
    ).first()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found"
        )

    executions = db.query(PipelineExecution).filter(
        PipelineExecution.pipeline_id == pipeline_id
    ).order_by(PipelineExecution.started_at.desc()).all()

    return executions


@router.get("/executions/{execution_id}", response_model=PipelineExecutionOut)
def get_single_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> PipelineExecutionOut:
    execution = db.query(PipelineExecution).filter(
        PipelineExecution.id == execution_id,
        PipelineExecution.organization_id == current_user.organization_id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline execution not found"
        )

    return execution
