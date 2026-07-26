"""SQLAlchemy database setup — SQLite for hackathon simplicity."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite-specific
    echo=False,
)

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
    """Create all tables. Called on startup."""
    Base.metadata.create_all(bind=engine)
    # Lightweight SQLite migration for fields added after the prototype DB
    # was first created. Production deployments should use Alembic.
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
