# app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL as DEFAULT_DATABASE_URL

engine = None
SessionLocal = None
Base = declarative_base()
_is_test_db_initialized = False # Flag to indicate test DB setup

def initialize_database(db_url: str = None, is_test_setup: bool = False):
    global engine, SessionLocal, _is_test_db_initialized
    
    if _is_test_db_initialized and not is_test_setup:
        print(f"DEBUG DB: Test database is active ({engine.url if engine else 'N/A'}). Main DB initialization with '{db_url if db_url else DEFAULT_DATABASE_URL}' skipped.")
        return

    effective_db_url = None

    if is_test_setup:
        # For tests, db_url should be the shared memory URI with uri=true in the query string.
        # The dialect sqlite+pysqlite is also good practice.
        effective_db_url = "sqlite+pysqlite:///file:memdb1?mode=memory&cache=shared&uri=true"
        print(f"DEBUG DB: Initializing TEST database with URI: {effective_db_url}")
        _is_test_db_initialized = True
    else:
        effective_db_url = db_url if db_url else DEFAULT_DATABASE_URL
        print(f"DEBUG DB: Initializing MAIN database with URL: {effective_db_url}")

    if not effective_db_url:
        raise ValueError("Database URL must be provided for initialization.")

    connect_args = {}
    # For SQLite, check_same_thread=False is generally needed for FastAPI/multi-threaded access.
    if "sqlite" in effective_db_url:
        connect_args = {"check_same_thread": False}
        
    # The uri=True parameter is not a direct argument to create_engine.
    # It's part of the connection string for SQLite URI filenames.
    engine = create_engine(effective_db_url, connect_args=connect_args)
        
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print(f"DEBUG DB: Engine set to {engine.url}, SessionLocal configured.")

def get_engine():
    if not engine:
        print("DEBUG DB: get_engine() called before explicit initialization. Initializing with default URL.")
        initialize_database()
    return engine

def get_session_local():
    if not SessionLocal:
        print("DEBUG DB: get_session_local() called before explicit initialization. Initializing with default URL.")
        initialize_database()
    return SessionLocal

def create_db_and_tables(target_engine):
    print(f"DEBUG DB: Creating tables on engine {target_engine.url}")
    Base.metadata.create_all(bind=target_engine)
    print("DEBUG DB: Tables created.")

