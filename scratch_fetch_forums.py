import urllib.request
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# 1. TradingQnA
try:
    url = 'https://tradingqna.com/search.json?q=mutual%20fund%20sip%20mandate'
    req = urllib.request.Request(url, headers=headers)
    data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode('utf-8'))
    topics = data.get('topics', [])
    print(f"TradingQnA topics found: {len(topics)}")
    for t in topics[:6]:
        print(f"  - [{t.get('id')}] {t.get('title')} (views: {t.get('views')}, posts: {t.get('posts_count')})")
except Exception as e:
    print("TradingQnA error:", e)

# 2. ValuePickr
try:
    url = 'https://forum.valuepickr.com/search.json?q=SIP%20allocation'
    req = urllib.request.Request(url, headers=headers)
    data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode('utf-8'))
    topics = data.get('topics', [])
    print(f"\nValuePickr topics found: {len(topics)}")
    for t in topics[:6]:
        print(f"  - [{t.get('id')}] {t.get('title')} (views: {t.get('views')}, posts: {t.get('posts_count')})")
except Exception as e:
    print("ValuePickr error:", e)
