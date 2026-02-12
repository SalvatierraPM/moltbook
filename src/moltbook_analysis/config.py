from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
DERIVED_DIR = DATA_DIR / "derived"
REPORTS_DIR = ROOT / "reports"


@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("MOLTBOOK_BASE_URL", "https://www.moltbook.com")
    api_token: str | None = os.getenv("MOLTBOOK_API_TOKEN")
    rate_limit_rps: float = float(os.getenv("MOLTBOOK_RATE_LIMIT_RPS", "1.0"))
    user_agent: str = os.getenv(
        "MOLTBOOK_USER_AGENT",
        "MoltbookAcademicBot/0.1 (contact: research@example.org)",
    )

    # Data directories
    raw_dir: Path = RAW_DIR
    normalized_dir: Path = NORMALIZED_DIR
    derived_dir: Path = DERIVED_DIR
    reports_dir: Path = REPORTS_DIR


def get_settings() -> Settings:
    return Settings()
