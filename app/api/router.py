from fastapi import APIRouter

from app.api.routes import auth, health, internal, messages, persona

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(persona.router, prefix="/persona", tags=["persona"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
