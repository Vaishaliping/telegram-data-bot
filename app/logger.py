"""
JSONL run logger with GitHub Gist upload.

Each bot run gets a fresh log. Events are written as JSONL lines.
After the run, upload_gist() posts the log to GitHub as a public Gist
and returns the raw URL (wget-able).
"""

import json
import time
import requests
from app.config import GITHUB_TOKEN


class RunLogger:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.run_id = f"run_{chat_id}_{int(time.time())}"
        self.events: list[dict] = []

    def log(self, role: str, content: str, **extra):
        """Append one JSONL event."""
        event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": self.run_id,
            "role": role,
            "content": content,
            **extra,
        }
        self.events.append(event)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e, ensure_ascii=False) for e in self.events)

    def upload_gist(self) -> str:
        """
        Upload the JSONL log to GitHub Gist and return the raw URL.
        Falls back to a data-URI if GITHUB_TOKEN is missing.
        """
        filename = f"{self.run_id}.jsonl"
        content = self.to_jsonl()

        if not GITHUB_TOKEN:
            # Fallback: inline data (not wget-able but won't crash the bot)
            return f"data:text/plain;base64,no-token"

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "description": f"Telegram bot run log — {self.run_id}",
            "public": True,
            "files": {filename: {"content": content}},
        }

        try:
            resp = requests.post(
                "https://api.github.com/gists",
                json=payload,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            # Return the raw URL of the JSONL file — wget-able
            raw_url = data["files"][filename]["raw_url"]
            return raw_url
        except Exception as e:
            # Log the failure but don't crash the bot
            self.log("system", f"Gist upload failed: {e}")
            return f"https://gist.github.com/{self.run_id}-upload-failed"
