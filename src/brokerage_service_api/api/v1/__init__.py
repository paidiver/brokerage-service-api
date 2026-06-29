"""FastAPI module that represent the v1 version root of the API."""

from brokerage_service_api.api.v1.search import router as search_router

__all__ = ["search_router"]
