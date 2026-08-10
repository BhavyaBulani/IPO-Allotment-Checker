import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

MYSQL_USER = os.getenv("MYSQL_USER", "ipo_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ipo_password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ipo_checker")
MYSQL_SSL_MODE = os.getenv("MYSQL_SSL_MODE", "")

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

import logging
import time
from sqlalchemy import event

logger = logging.getLogger(__name__)

connect_args = {}
if MYSQL_SSL_MODE == "REQUIRED":
    connect_args["ssl"] = {}

# Configure connection pool
engine = create_engine(
    DATABASE_URL,
    pool_size=30, # To comfortably cover configured worker-pool concurrency (e.g. 10-30)
    max_overflow=10,
    pool_recycle=3600,
    connect_args=connect_args
)

# Pool monitoring
@event.listens_for(engine, 'checkout')
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    pool = engine.pool
    # If pool size is close to max, log a warning
    if pool.checkedout() >= pool.size() * 0.8:
        logger.warning(f"Connection pool saturation warning: {pool.checkedout()} connections checked out (size: {pool.size()})")

# Slow query monitoring
SLOW_QUERY_THRESHOLD_SEC = 0.5

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - context._query_start_time
    if total_time > SLOW_QUERY_THRESHOLD_SEC:
        logger.warning(f"Slow query detected ({total_time:.4f}s): {statement}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
