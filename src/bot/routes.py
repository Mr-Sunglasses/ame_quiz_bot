from __future__ import annotations

from aiogram import Router
from .handlers_quiz_creation import router as creation_router
from .handlers_attempts import router as attempts_router
from .handlers_admin import router as admin_router
from .handlers_misc import router as misc_router

router = Router()
router.include_router(creation_router)
router.include_router(attempts_router)
router.include_router(admin_router)
router.include_router(misc_router)
