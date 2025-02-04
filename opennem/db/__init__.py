import logging
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from opennem.exporter.encoders import opennem_deserialize, opennem_serialize
from opennem.settings import settings

DeclarativeBase = declarative_base()

logger = logging.getLogger(__name__)


def db_connect(
    db_conn_str: Optional[str] = None, debug: bool = False, timeout: int = 100
) -> Engine:
    """
    Performs database connection using database settings from settings.py.

    Returns sqlalchemy engine instance
    """
    if not db_conn_str:
        db_conn_str = settings.db_url

    connect_args = {}

    if db_conn_str.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    if settings.db_debug:
        debug = True

    keepalive_kwargs = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 5,
        "keepalives_count": 5,
    }

    try:
        return create_engine(
            db_conn_str,
            json_serializer=opennem_serialize,
            json_deserializer=opennem_deserialize,
            echo=debug,
            pool_size=30,
            max_overflow=20,
            pool_recycle=100,
            pool_timeout=timeout,
            pool_pre_ping=True,
            pool_use_lifo=True,
            connect_args={
                **connect_args,
                **keepalive_kwargs,
            },
        )
    except Exception as exc:
        logger.error("Could not connect to database: %s", exc)
        raise exc


engine = db_connect()

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

SessionAutocommit = sessionmaker(bind=engine, autocommit=True, autoflush=True)


def get_database_session() -> Generator[sessionmaker, None, None]:
    """
    Gets a database session

    """
    s = None

    try:
        s = SessionLocal()
        yield s
    except Exception as e:
        raise e
    finally:
        if s:
            s.close()


def get_database_engine() -> Engine:
    """
    Gets a database engine connection

    """
    _engine = db_connect()
    return _engine


engine.dispose()
