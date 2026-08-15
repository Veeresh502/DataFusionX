import json
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session
import redis.asyncio as aioredis

from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User
from app.models.pipeline_execution import PipelineExecution

router = APIRouter()


def get_user_from_token(token: str, db: Session) -> Optional[User]:
    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()


@router.websocket("/ws/executions/{execution_id}")
async def websocket_execution_stream(
    websocket: WebSocket,
    execution_id: int,
    token: Optional[str] = Query(None),
):
    await websocket.accept()

    if not token:
        await websocket.send_json({"event": "ERROR", "message": "Authentication token missing"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    try:
        user = get_user_from_token(token, db)
        if not user:
            await websocket.send_json({"event": "ERROR", "message": "Invalid authentication token"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        execution = db.query(PipelineExecution).filter(
            PipelineExecution.id == execution_id,
            PipelineExecution.organization_id == user.organization_id,
        ).first()

        if not execution:
            await websocket.send_json({"event": "ERROR", "message": "Execution not found or access denied"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Send initial state immediately
        await websocket.send_json({
            "event": "EXECUTION_STATE",
            "execution_id": execution.id,
            "pipeline_id": execution.pipeline_id,
            "status": execution.status,
            "current_stage": execution.current_stage,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration_seconds": execution.duration_seconds,
            "records_read": execution.records_read,
            "records_processed": execution.records_processed,
            "records_failed": execution.records_failed,
            "records_loaded": execution.records_loaded,
            "retry_count": execution.retry_count,
            "logs": execution.logs,
            "error": execution.error,
        })

        if execution.status in ["SUCCESS", "FAILED", "CANCELLED"]:
            await websocket.send_json({"event": "EXECUTION_COMPLETE", "status": execution.status})
            await websocket.close()
            return

    finally:
        db.close()

    # Subscribe to Redis Pub/Sub channel for live events
    r = None
    pubsub = None
    try:
        r = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"execution:{execution_id}")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data_str = message.get("data")
                if data_str:
                    try:
                        event_payload = json.loads(data_str)
                        await websocket.send_json(event_payload)
                        if event_payload.get("event") in ["EXECUTION_SUCCESS", "EXECUTION_FAILED", "EXECUTION_CANCELLED"]:
                            await websocket.send_json({"event": "EXECUTION_COMPLETE", "status": event_payload.get("status")})
                            break
                    except Exception:
                        pass
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket Error] {e}")
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(f"execution:{execution_id}")
            except Exception:
                pass
        if r:
            try:
                await r.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
