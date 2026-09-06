from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.ai import (
    AIQueryRequest, AIQueryResponse,
    AIPipelineExplainRequest, AIPipelineExplainResponse,
    AIHealthResponse,
    AIPipelineGenerateRequest, AIPipelineProposalResponse
)
from app.schemas.data_quality import DataQualityAnalysisResponse
from app.services.ai_service import (
    process_natural_language_query,
    explain_pipeline_failure_service,
    generate_pipeline_proposal_service,
    analyze_data_quality_service
)

from app.services.sql_safety import SQLSafetyError
from app.core.config import settings

router = APIRouter()


@router.post("/query", response_model=AIQueryResponse)
def ai_query_endpoint(
    req: AIQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIQueryResponse:

    """
    DataFusionX AI Copilot: Natural Language to SQL Endpoint.
    Translates natural language questions into safe, read-only SQL, executes the query,
    and returns structured results with an AI explanation.
    """
    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question parameter cannot be empty."
        )

    try:
        res = process_natural_language_query(
            db=db,
            user=current_user,
            question=req.question.strip(),
            warehouse_model_slug=req.warehouse_model
        )
        return AIQueryResponse(**res)
    except SQLSafetyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Service error: {str(e)}"
        )


@router.post("/explain-pipeline", response_model=AIPipelineExplainResponse)
def explain_pipeline_failure_endpoint(
    req: AIPipelineExplainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIPipelineExplainResponse:
    """
    Pipeline Failure Assistant:
    Analyzes failed pipeline execution logs and step configurations for the user's organization,
    returning structured root cause analysis and recommended fixes.
    """
    try:
        res = explain_pipeline_failure_service(
            db=db,
            user=current_user,
            execution_id=req.execution_id
        )
        return AIPipelineExplainResponse(**res)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline Failure Assistant error: {str(e)}"
        )


@router.get("/health", response_model=AIHealthResponse)
def ai_health_endpoint(
    current_user: User = Depends(get_current_user),
) -> AIHealthResponse:

    """Returns AI Copilot service health and provider configuration."""
    provider = settings.LLM_PROVIDER.lower() if settings.LLM_PROVIDER else "mock"
    return AIHealthResponse(
        status="healthy",
        provider=provider,
        model=settings.LLM_MODEL_NAME if provider == "openai" else "mock-heuristic-engine"
    )


@router.post("/generate-pipeline", response_model=AIPipelineProposalResponse)
def generate_pipeline_endpoint(
    req: AIPipelineGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIPipelineProposalResponse:
    """
    AI Pipeline Copilot:
    Translates natural language ETL requirements into a structured, validated pipeline proposal.
    Inspects actual dataset schema for tenant isolation, checks hallucinated columns, and returns
    M7-compatible visual DAG nodes/edges ready for user review and approval.
    """
    if not req.user_prompt or not req.user_prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ETL requirement prompt cannot be empty."
        )

    try:
        res = generate_pipeline_proposal_service(
            db=db,
            user=current_user,
            source_id=req.source_id,
            user_prompt=req.user_prompt.strip()
        )
        return AIPipelineProposalResponse(**res)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Pipeline Copilot error: {str(e)}"
        )


@router.get("/data-quality/{source_id}", response_model=DataQualityAnalysisResponse)
def analyze_data_quality_endpoint(
    source_id: int,
    target_model_slug: str = "generic",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataQualityAnalysisResponse:
    """
    M13 AI Data Quality & Anomaly Intelligence:
    Calculates deterministic profiling metrics, detects anomalies (NULL spikes, duplicate keys,
    numeric outliers, text casing inconsistencies, format errors, schema mismatches),
    computes deterministic Quality Score (0-100), and provides AI explanations & recommendations.
    Enforces multi-tenant tenant isolation.
    """
    try:
        res = analyze_data_quality_service(
            db=db,
            user=current_user,
            source_id=source_id,
            target_model_slug=target_model_slug
        )
        return DataQualityAnalysisResponse(**res)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Data Quality error: {str(e)}"
        )


