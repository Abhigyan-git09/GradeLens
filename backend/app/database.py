"""SQLAlchemy database setup with persistent SQLite production support."""

from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _normalize_database_url(database_url: str) -> URL:
    """Select Psycopg 3 when a provider returns a generic Postgres URL."""
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    return url


def _engine_options(database_url: str) -> dict:
    """Return dialect-safe engine arguments."""
    url = _normalize_database_url(database_url)
    options: dict = {
        "echo": False,
        "pool_pre_ping": True,
    }
    if url.get_backend_name() == "sqlite":
        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().resolve().parent.mkdir(
                parents=True,
                exist_ok=True,
            )
        options["connect_args"] = {
            "check_same_thread": False,
            "timeout": 30,
        }
    return options


engine = create_engine(
    _normalize_database_url(settings.DATABASE_URL),
    **_engine_options(settings.DATABASE_URL),
)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        """Enable integrity, concurrency, and bounded lock waits."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables and apply prototype-safe additive migrations."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        existing = {
            column["name"]
            for column in inspect(engine).get_columns("timeseries_points")
        }
        required = {
            "caliper_actual": "FLOAT DEFAULT 0.0",
            "caliper_setpoint": "FLOAT DEFAULT 0.0",
        }
        with engine.begin() as connection:
            for column, definition in required.items():
                if column not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE timeseries_points "
                            f"ADD COLUMN {column} {definition}"
                        )
                    )
