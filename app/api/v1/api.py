from fastapi import APIRouter
from app.api.v1.endpoints import leads, webhooks

api_router = APIRouter()
api_router.include_router(leads.router, tags=["Leads"])
api_router.include_router(webhooks.router, tags=["Webhooks"])
