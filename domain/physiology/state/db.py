"""
Unified Physiological State — conexión a base de datos.

SQLite embebido vía SQLAlchemy (decisión aprobada en PLAN.md Fase 0):
offline-first, sin infraestructura de servidor separada. El archivo vive en
`data/biocore_ups.db`, junto al resto de datos locales de la app
(`data/local/`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "biocore_ups.db"


def make_engine(db_path: Optional[Path] = None) -> Engine:
    """Crea un engine SQLite. `db_path=None` usa el archivo por defecto del
    proyecto; pasar una ruta explícita (p.ej. un archivo temporal) es lo que
    usan los tests para no tocar datos reales."""

    path = db_path if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Crea las tablas del UPS si no existen. Idempotente."""
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
