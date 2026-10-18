from __future__ import annotations

from collections.abc import Iterator

from fastapi import Query, Request
from sqlalchemy.orm import Session

from .config import Settings
from .inference import Detector
from .storage import Storage


def get_db(request: Request) -> Iterator[Session]:
    db: Session = request.app.state.sessionmaker()
    try:
        yield db
    finally:
        db.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_detector(request: Request) -> Detector:
    return request.app.state.detector


class PageParams:
    def __init__(self, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        self.limit, self.offset = limit, offset
