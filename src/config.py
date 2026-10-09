import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Zernio API Configuration
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY", "")
ZERNIO_BASE_URL = os.getenv("ZERNIO_BASE_URL", "https://zernio.com/api/v1").rstrip("/")
ZERNIO_WEBHOOK_SECRET = os.getenv("ZERNIO_WEBHOOK_SECRET", "")
ZERNIO_PROFILE_ID_INSTAGRAM = os.getenv("ZERNIO_PROFILE_ID_INSTAGRAM", "")
ZERNIO_PROFILE_ID_FACEBOOK = os.getenv("ZERNIO_PROFILE_ID_FACEBOOK", "")
ZERNIO_PROFILE_ID_TIKTOK = os.getenv("ZERNIO_PROFILE_ID_TIKTOK", "")

# Model API Configuration
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")
# OpenAI-compatible embeddings endpoint used by RAG (see scripts/embedding_bridge.py).
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

# Auto send and handover hold
AUTO_SEND = os.getenv("AUTO_SEND", "false").lower() in ("true", "1", "yes")
HOLD_ON_HANDOVER = os.getenv("HOLD_ON_HANDOVER", "true").lower() in ("true", "1", "yes")

# Environment (prod, test, dev)
APP_ENV = os.getenv("APP_ENV", "prod")

# PostHog Analytics & Session Recording Configuration
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "phc_Ab8smdwdH5D7Ymwg6VivfPT5FaC2ThyewEaa6fNXPHWZ").strip()
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com").strip().rstrip("/")
POSTHOG_ENABLE_RECORDING = os.getenv("POSTHOG_ENABLE_RECORDING", "true").lower() in ("true", "1", "yes")
POSTHOG_PROJECT_ID = os.getenv("POSTHOG_PROJECT_ID", "654868").strip()

# Database configuration (PostgreSQL for Cloud/Render or SQLite local)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "events.db"))

# Knowledge directories
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
# Built at runtime from knowledge/ and kept out of git, so each host indexes with its own embedding model.
VECTOR_STORE_PATH = Path(os.getenv("VECTOR_STORE_PATH", str(BASE_DIR / "data" / "vector_store.json")))

# Platform character & length limits (Configurable per platform, not hardcoded in prompts)
PLATFORM_LIMITS: Dict[str, Dict[str, Any]] = {
    "ig": {
        "comment_max_words": 20,
        "comment_max_chars": 140,
        "dm_max_chars": 600,
    },
    "fb": {
        "comment_max_words": 30,
        "comment_max_chars": 200,
        "dm_max_chars": 800,
    },
    "tiktok": {
        "comment_max_words": 25,
        "comment_max_chars": 150,
        "dm_max_chars": 500,
    },
}
