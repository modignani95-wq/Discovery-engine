import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
key = os.getenv("YOUTUBE_API_KEY")

from googleapiclient.discovery import build
yt = build("youtube", "v3", developerKey=key, cache_discovery=False)

channels = [
    {"handle": "ETMONEY", "name": "ET Money"},
    {"handle": "shankarnath", "name": "Shankar Nath"},
    {"handle": "pranjalkamra", "name": "Pranjal Kamra (Finology)"},
    {"handle": "LabourLawAdvisor", "name": "Labour Law Advisor (LLA)"},
    {"handle": "Zero1byZerodha", "name": "Zero1 by Zerodha"},
    {"handle": "freefincal", "name": "Freefincal"},
    {"handle": "YadnyaInvestmentAcademy", "name": "Yadnya Investment Academy"},
    {"handle": "CARachanaRanade", "name": "CA Rachana Phadke Ranade"},
    {"handle": "AssetYogi", "name": "Asset Yogi"},
    {"handle": "warikoo", "name": "Ankur Warikoo"}
]

print(f"Testing channel resolution for {len(channels)} channels...")
for ch in channels:
    try:
        # Try getting channel info via forHandle
        res = yt.channels().list(forHandle=ch["handle"], part="id,snippet").execute()
        items = res.get("items", [])
        if items:
            cid = items[0]["id"]
            title = items[0]["snippet"]["title"]
            print(f"  [OK] @{ch['handle']} -> ID: {cid} ({title})")
        else:
            # Fallback search
            s = yt.search().list(q=ch["handle"], type="channel", part="id,snippet", maxResults=1).execute()
            s_items = s.get("items", [])
            if s_items:
                cid = s_items[0]["id"]["channelId"]
                title = s_items[0]["snippet"]["title"]
                print(f"  [SEARCH-OK] @{ch['handle']} -> ID: {cid} ({title})")
            else:
                print(f"  [FAIL] @{ch['handle']}")
    except Exception as e:
        print(f"  [ERR] @{ch['handle']}: {e}")
