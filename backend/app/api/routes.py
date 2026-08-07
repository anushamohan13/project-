from fastapi import APIRouter

from app.api.auth_routes import router as auth_router
from app.api.chat_routes import router as chat_router
from app.api.finance_routes import router as finance_router
from app.api.notification_routes import router as notification_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(finance_router)
router.include_router(notification_router)
router.include_router(chat_router)
