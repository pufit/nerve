"""Notification routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nerve.gateway.auth import require_auth
from nerve.gateway.routes._deps import get_deps

router = APIRouter()


class NotificationAnswerRequest(BaseModel):
    answer: str


@router.get("/api/notifications")
async def list_notifications(
    status: str = "",
    type: str = "",
    session_id: str = "",
    limit: int = 50,
    user: dict = Depends(require_auth),
):
    deps = get_deps()
    notifications = await deps.db.list_notifications(
        status=status or None,
        type=type or None,
        session_id=session_id or None,
        limit=min(limit, 200),
        channel="web",
    )
    pending_count = await deps.db.count_pending_notifications(channel="web")
    return {"notifications": notifications, "pending_count": pending_count}


@router.get("/api/notifications/{notification_id}")
async def get_notification(notification_id: str, user: dict = Depends(require_auth)):
    deps = get_deps()
    notif = await deps.db.get_notification(notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif


@router.post("/api/notifications/{notification_id}/answer")
async def answer_notification(
    notification_id: str,
    req: NotificationAnswerRequest,
    user: dict = Depends(require_auth),
):
    deps = get_deps()
    if not deps.notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")
    success = await deps.notification_service.handle_answer(
        notification_id=notification_id,
        answer=req.answer,
        answered_by="web",
    )
    if not success:
        raise HTTPException(status_code=409, detail="Notification already answered or not found")
    return {"notification_id": notification_id, "answered": True}


@router.post("/api/notifications/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: str,
    user: dict = Depends(require_auth),
):
    deps = get_deps()
    if not deps.notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")
    success = await deps.notification_service.handle_dismiss(notification_id)
    if not success:
        raise HTTPException(status_code=409, detail="Notification not pending")
    return {"notification_id": notification_id, "dismissed": True}


@router.post("/api/notifications/dismiss-all")
async def dismiss_all_notifications(user: dict = Depends(require_auth)):
    deps = get_deps()
    count = await deps.db.dismiss_all_notifications()
    return {"dismissed": count}
