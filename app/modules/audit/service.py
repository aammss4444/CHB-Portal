from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User
from app.modules.audit.ai_engine import AuditAIEngine
from app.modules.audit.ai_service import AuditAIService


class AuditService:
    def __init__(self) -> None:
        self.ai_service = AuditAIService(AuditAIEngine())

    async def get_ai_report(self, db: AsyncSession, current_user: User, days: int) -> Dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
        rows = (
            await db.execute(
                select(AuditLog, User.role)
                .join(User, User.id == AuditLog.user_id)
                .where(AuditLog.timestamp >= cutoff)
                .order_by(AuditLog.timestamp.desc())
            )
        ).all()

        logs: List[Dict[str, Any]] = []
        for log, role in rows:
            logs.append(
                {
                    "id": log.id,
                    "entity_name": log.entity_name,
                    "entity_id": log.entity_id,
                    "action": log.action,
                    "user_id": log.user_id,
                    "role": role.value if hasattr(role, "value") else str(role),
                    "timestamp": log.timestamp,
                }
            )
        return await self.ai_service.build_ai_report(logs)
