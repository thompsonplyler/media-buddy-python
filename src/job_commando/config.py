import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# --- Load Environment ---
# This file is the single source of truth for loading environment variables.
# It should be imported before any other local module that needs these variables.
# We explicitly point to the .env file in the project root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=True)

# --- Riot API Configuration ---
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_PUUID = os.getenv("RIOT_PUUID")
RIOT_API_BASE_URL = "https://americas.api.riotgames.com"

# --- Obsidian API Configuration ---
OBSIDIAN_API_KEY = os.getenv("OBSIDIAN_API_KEY")
if not OBSIDIAN_API_KEY:
    # This is a critical failure, the app cannot run without it.
    raise ValueError("OBSIDIAN_API_KEY not found in .env file. The application cannot access the vault.")

OBSIDIAN_API_BASE_URL = "https://127.0.0.1:27124"

# --- Application Logic ---
CHECK_INTERVAL_SECONDS = 900  # 15 minutes
LEAGUE_TRIGGER_COUNT = 3
RADIO_SILENCE_HOUR = 20 # 8:00 PM
USER_TIMEZONE = ZoneInfo("America/New_York")
DATE_FORMAT = "%Y-%m-%d"

# --- Paths within the Vault ---
# These are not file system paths, but paths for the API endpoint.
DAILY_LOG_PATH_PREFIX = "Areas/Resources/Log"
STATE_PATH_PREFIX = ".job-commando/state"

# --- General Configuration ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OBSIDIAN_LOG_PATH = os.getenv('OBSIDIAN_LOG_PATH')
DATABASE_URL = os.environ.get('DATABASE_URL') or \
    'sqlite:///app.db'

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False 