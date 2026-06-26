"""FastAPI module that represent the v1 version root of the API."""

from brokerage_service_api.api.v1.source_health import router as source_health_router

__all__ = ["source_health_router"]
