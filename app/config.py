"""Configuration settings for AutoPlan AI decision support application.

Manages loading environment variables, CSV file paths, and general settings.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Project directory structure
APP_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_DIR.parent
PROJECT_ROOT = WORKSPACE_ROOT

# Dynamically append package roots for seamless import resolution
sys.path.append(str(WORKSPACE_ROOT / "framework"))
sys.path.append(str(WORKSPACE_ROOT / "app"))

# Load workspace env
load_dotenv()

# Dataset paths
DATA_DIR = APP_DIR / "data"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

VEHICLES_CSV = DATA_DIR / "vehicles.csv"
INVENTORY_CSV = DATA_DIR / "inventory.csv"
SUPPLIERS_CSV = DATA_DIR / "suppliers.csv"
COSTS_CSV = DATA_DIR / "costs.csv"

# Gemini config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-8b")

# Server ports
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8001"))
