from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

# =========================================================
# DATABASE CONFIG (ENV-DRIVEN ONLY)
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
ENV = os.getenv("ENV", "dev")  # dev | test | prod

# =========================================================
# VALIDATION (FAIL FAST)
# =========================================================
if ENV != "test" and not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

if ENV == "test" and not TEST_DATABASE_URL:
    raise ValueError("TEST_DATABASE_URL is not set for test environment")

# =========================================================
# ACTIVE DATABASE SELECTION
# =========================================================
ACTIVE_DB_URL = TEST_DATABASE_URL if ENV == "test" else DATABASE_URL

# =========================================================
# ENGINE
# =========================================================
engine = create_engine(
    ACTIVE_DB_URL,
    pool_pre_ping=True
)

# =========================================================
# SESSION
# =========================================================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# =========================================================
# BASE
# =========================================================
Base = declarative_base()
