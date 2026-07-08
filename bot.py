"""Standalone bot entry point (without web server). Prefer run.py for production."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Skip env validation for standalone bot mode
os.environ["SKIP_ENV_VALIDATION"] = "1"

from run import run_bot

if __name__ == "__main__":
    asyncio.run(run_bot())
