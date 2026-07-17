import os

from dotenv import load_dotenv

load_dotenv()

NOTION_API_TOKEN = os.environ.get("NOTION_API_TOKEN", "")
NOTION_ADMIN_API_KEY = os.environ.get("NOTION_ADMIN_API_KEY", "")
MOVIMIENTOS_DB = os.environ.get("MOVIMIENTOS_DB", "")
PERIODO_DB = os.environ.get("PERIODO_DB", "39d06589-4ee5-8036-a3ef-c73eadeae4f8")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
