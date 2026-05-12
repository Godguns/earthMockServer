from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_from_token
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.message import MessageChannel
from app.models.user import User
from app.schemas.message import (
    EventTriggerRequest,
    MessageListResponse,
    MessageRead,
    RandomMessageResponse,
)
from app.services.message_service import (
    create_event_messages,
    deliver_due_messages,
    generate_random_message_for_user,
    list_new_user_messages,
    list_user_messages,
    mark_message_as_read,
    run_random_push_cycle,
)

router = APIRouter()


@router.get("", response_model=MessageListResponse)
def read_messages(
    channel: MessageChannel | None = Query(default=None),
    unread_only: bool = False,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageListResponse:
    items = list_user_messages(
        db=db,
        user=current_user,
        channel=channel,
        unread_only=unread_only,
        limit=limit,
    )
    return MessageListResponse(
        items=[MessageRead.model_validate(item) for item in items],
        server_time=datetime.now(UTC),
    )


@router.get("/poll", response_model=MessageListResponse)
def poll_messages(
    since: datetime | None = None,
    channel: MessageChannel | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageListResponse:
    deliver_due_messages(db)
    run_random_push_cycle(db)
    items = list_new_user_messages(
        db=db,
        user=current_user,
        since=since,
        channel=channel,
        limit=limit,
    )
    return MessageListResponse(
        items=[MessageRead.model_validate(item) for item in items],
        server_time=datetime.now(UTC),
    )


@router.get("/stream")
async def stream_messages(
    request: Request,
    access_token: str = Query(min_length=1),
    channel: MessageChannel | None = Query(default=None),
) -> StreamingResponse:
    with SessionLocal() as db:
        user = get_user_from_token(db, access_token)
        user_id = user.id

    async def event_generator():
        cursor = datetime.now(UTC)
        yield _format_sse("ready", {"server_time": cursor.isoformat()})

        while not await request.is_disconnected():
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if user is None:
                    yield _format_sse("error", {"message": "User not found"})
                    return

                deliver_due_messages(db)
                run_random_push_cycle(db)
                items = list_new_user_messages(
                    db=db,
                    user=user,
                    since=cursor,
                    channel=channel,
                    limit=100,
                )
                server_time = datetime.now(UTC)
                if items:
                    payload = {
                        "items": [
                            MessageRead.model_validate(item).model_dump(mode="json")
                            for item in items
                        ],
                        "server_time": server_time.isoformat(),
                    }
                    yield _format_sse("messages", payload)
                else:
                    yield _format_sse("heartbeat", {"server_time": server_time.isoformat()})
                cursor = server_time

            await asyncio.sleep(settings.message_stream_interval_seconds)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/trigger/random", response_model=RandomMessageResponse, status_code=status.HTTP_201_CREATED)
def trigger_random_message(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RandomMessageResponse:
    created_messages = generate_random_message_for_user(db, current_user)
    return RandomMessageResponse(
        created=[MessageRead.model_validate(item) for item in created_messages]
    )


@router.post("/trigger/event", response_model=RandomMessageResponse, status_code=status.HTTP_201_CREATED)
def trigger_event_message(
    payload: EventTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RandomMessageResponse:
    created_messages = create_event_messages(db, current_user, payload)
    return RandomMessageResponse(
        created=[MessageRead.model_validate(item) for item in created_messages]
    )


@router.post("/{message_id}/read", response_model=MessageRead)
def read_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageRead:
    message = mark_message_as_read(db, current_user, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return MessageRead.model_validate(message)


def _format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
