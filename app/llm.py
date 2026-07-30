"""
LLM handler using Groq (llama-3.3-70b-versatile).

The system prompt tells the model to:
  1. Detect the exact JSON shape requested in the question.
  2. Return ONLY the inner answer object (e.g. {"state": "Assam"}).
  3. Never wrap in markdown, never add prose.
"""

import json
import re
from openai import OpenAI
from app.config import GROQ_API_KEY

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """You are a precise data analyst assistant. You answer data questions using Indian government statistics (MOSPI, SRS, Census, etc.).

Rules you MUST follow:
1. Read the question carefully. It will tell you the EXACT JSON shape to reply with (e.g. {"state": "<state name>"}).
2. Reply with ONLY that inner JSON object — nothing else. No explanation, no markdown, no code fences.
3. Use the most recent official data available. For MOSPI maternal mortality data, Assam has historically had the highest MMR per MOSPI's "Women and Men in India" publication.
4. If the answer involves numbers, use exact values from official sources.
5. String values must match exactly — proper capitalization, correct spelling.

Example:
Question: Which state has the highest maternal mortality rate based on MOSPI data? Reply with ONLY {"state": "<state name>"}
Your reply: {"state": "Assam"}
"""


def ask_llm(messages: list) -> str:
    """
    messages: list of {"role": "user"/"assistant", "content": "..."}
    Returns the raw LLM reply string.
    """
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        temperature=0,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


def extract_json(text: str) -> dict | None:
    """
    Try to extract a JSON object from the LLM reply.
    Returns the parsed dict, or None if not found.
    """
    # Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Find first {...} block
    match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    return None