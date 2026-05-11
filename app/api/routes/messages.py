from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
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
    generate_random_message_for_user,
    list_user_messages,
    mark_message_as_read,
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
    return MessageListResponse(items=[MessageRead.model_validate(item) for item in items])


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

