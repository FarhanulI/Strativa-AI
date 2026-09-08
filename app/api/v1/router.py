from fastapi import APIRouter

from app.api.v1.audience_intelligence import router as audience_intelligence_router
from app.api.v1.audience_objections import router as audience_objections_router
from app.api.v1.audience_questions import router as audience_questions_router
from app.api.v1.audience_signals import router as audience_signals_router
from app.api.v1.brands import router as brands_router
from app.api.v1.business_context import router as business_context_router
from app.api.v1.competitors import router as competitors_router
from app.api.v1.content_briefs import router as content_briefs_router
from app.api.v1.content_drafts import router as content_drafts_router
from app.api.v1.content_opportunities import router as content_opportunities_router
from app.api.v1.content_profiles import router as content_profiles_router
from app.api.v1.desires import router as desires_router
from app.api.v1.health import router as health_router
from app.api.v1.market_intelligence import router as market_intelligence_router
from app.api.v1.market_signals import router as market_signals_router
from app.api.v1.offers import router as offers_router
from app.api.v1.pain_points import router as pain_points_router
from app.api.v1.performance import router as performance_router
from app.api.v1.personas import router as personas_router
from app.api.v1.products import router as products_router
from app.api.v1.services import router as services_router
from app.api.v1.topics import router as topics_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(workspaces_router)
api_router.include_router(content_profiles_router)
api_router.include_router(content_opportunities_router)
api_router.include_router(content_briefs_router)
api_router.include_router(content_drafts_router)
api_router.include_router(audience_intelligence_router)
api_router.include_router(personas_router)
api_router.include_router(pain_points_router)
api_router.include_router(desires_router)
api_router.include_router(audience_questions_router)
api_router.include_router(audience_signals_router)
api_router.include_router(audience_objections_router)
api_router.include_router(brands_router)
api_router.include_router(business_context_router)
api_router.include_router(products_router)
api_router.include_router(services_router)
api_router.include_router(offers_router)
api_router.include_router(market_intelligence_router)
api_router.include_router(topics_router)
api_router.include_router(market_signals_router)
api_router.include_router(competitors_router)
api_router.include_router(performance_router)
