from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.health import DatabaseHealthStatus


def check_database_health(db: Session) -> DatabaseHealthStatus:
    try:
        db.execute(text("SELECT 1"))
        return DatabaseHealthStatus(status="healthy", database="connected")
    except Exception as e:
        return DatabaseHealthStatus(status="unhealthy", database=f"disconnected: {str(e)}")
