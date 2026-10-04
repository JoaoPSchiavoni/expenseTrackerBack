"""
System Status and Monitoring Router.

Endpoints:
30. GET /health (Health check and PostgreSQL database connectivity verification)
"""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.web.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Verify PostgreSQL connectivity and API health",
)
def health_check(session: Session = Depends(get_db)) -> JSONResponse:
    """Verifies that the application can actively communicate with the database engine.

    Why: Allows load balancers, Kubernetes liveness/readiness probes, and orchestrators
    to monitor service availability before routing traffic.
    """
    try:
        # Why: Executes a minimal query to confirm connection availability
        session.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "database": "connected",
                "message": "Expense Tracker API is operational.",
            },
        )
    except Exception as exc:
        logger.error("Database health check failed: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": "Failed to connect to database.",
            },
        )
