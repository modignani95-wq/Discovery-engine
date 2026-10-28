import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("MISTRAL_API_KEY")

test_models = [
    "open-mistral-7b",
    "mistral-tiny",
    "ministral-3b-latest",
    "ministral-8b-latest",
    "codestral-latest",
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
]

for m in test_models:
    payload = {"model": m, "messages": [{"role": "user", "content": "Hi"}]}
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    )
    try:
        res = urllib.request.urlopen(req, timeout=10)
        print(f"SUCCESS: {m} returned {res.status}!")
        break
    except urllib.error.HTTPError as e:
        limit = e.headers.get("x-ratelimit-limit-req-minute")
        body = e.read().decode("utf-8", errors="ignore")
        print(f"{m} -> HTTP {e.code} | limit-req-minute: {limit} | body: {body[:100]}")
    except Exception as exc:
        print(f"{m} -> error: {exc}")
