from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check(response: Response, db: Session = Depends(get_db)):
    """Health check endpoint: returns 200 OK if database responds, 503 Service Unavailable otherwise."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "Healthy", "database": "Connected"}
    except Exception as ex:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "Unhealthy", "database": str(ex)}

