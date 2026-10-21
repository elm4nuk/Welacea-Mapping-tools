"""Engine, sesi, dan tipe kolom yang portabel SQLite ↔ PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Simpan UTC, selalu kembalikan datetime ber-timezone (SQLite membuang tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime tidak diizinkan untuk kolom UTC")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Filter autogenerate/compare_metadata Alembic.

    surveys.field_id ditambahkan dengan ALTER TABLE ADD COLUMN … REFERENCES (migrasi 0002, tanpa membuat ulang tabel
    karena itu memicu ON DELETE CASCADE di SQLite). Refleksi SQLAlchemy untuk SQLite tidak membaca ON DELETE dari FK
    inline semacam itu, sehingga perbandingan selalu melihat drift palsu. FK aslinya diuji lewat PRAGMA di
    tests/test_mapping_migration.py."""
    if type_ == "foreign_key_constraint" and obj.table.name == "surveys" and \
            [c.name for c in obj.columns] == ["field_id"]:
        return False
    return True


def make_engine(url: str) -> Engine:
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()
    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
