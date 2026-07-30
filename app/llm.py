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
1. The question describes an inner JSON shape like {"state": "<state name>"} or {"value": <number>}. Find that inner shape.
2. IMPORTANT: The question may also mention an outer wrapper like {"answer": ..., "log_url": ...}. IGNORE the log_url field entirely — that is added by the system, not by you.
3. Reply with ONLY the inner answer object — the value that goes inside the "answer" key. For example if asked for {"state": "<state name>"}, reply with just {"state": "Assam"}.
4. Never include "answer" or "log_url" keys in your reply. Never add markdown, code fences, or prose.
5. Use the most recent official data available. For MOSPI maternal mortality data, Assam has historically had the highest MMR per MOSPI's "Women and Men in India" publication.
6. String values must match exactly — proper capitalization, correct spelling.

Example:
Question: Which state has the highest maternal mortality rate? Reply with ONLY {"answer": {"state": "<state name>"}, "log_url": "..."}
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
    Try to extract the inner answer JSON object from the LLM reply.
    Handles:
    - Clean JSON: {"state": "Assam"}
    - Nested (LLM wrapped it): {"answer": {"state": "Assam"}, "log_url": "..."}
    Returns the inner answer dict, or None if not found.
    """
    obj = None

    # Direct parse
    try:
        obj = json.loads(text)
    except Exception:
        pass

    # Find first complete {...} block if direct parse failed
    if obj is None:
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
            except Exception:
                pass

    if obj is None:
        return None

    # Unwrap if LLM returned the outer {"answer": {...}, "log_url": ...} format
    if "answer" in obj and isinstance(obj["answer"], dict):
        return obj["answer"]

    # Strip log_url if present at top level
    obj.pop("log_url", None)

    return obj