from app.db.base import Base
from app.db.session import engine
from app.models import message, npc_session, persona, story, user, world  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
