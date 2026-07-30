from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")   # GitHub PAT with 'gist' scope
WEBHOOK_URL = os.getenv("WEBHOOK_URL")     # e.g. https://your-app.koyeb.app