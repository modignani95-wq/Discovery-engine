import urllib.request
import json
import urllib.error

import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("GROQ_API_KEY", "")

payload = {
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 5
}
req = urllib.request.Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
)
try:
    with urllib.request.urlopen(req) as resp:
        print("Status: 200")
        for h, v in resp.getheaders():
            if "ratelimit" in h.lower() or "retry" in h.lower():
                print(f"{h}: {v}")
except urllib.error.HTTPError as e:
    print("Status:", e.code)
    for h, v in e.headers.items():
        if "ratelimit" in h.lower() or "retry" in h.lower():
            print(f"{h}: {v}")
    print("Body:", e.read().decode())
