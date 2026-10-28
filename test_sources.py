import requests
import json
import re
import sys
import urllib.parse
from html.parser import HTMLParser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def test_apple():
    print("=== Testing Apple App Store Reviews ===")
    app_id = "1404871703"
    headers = {
        "X-Apple-Store-Front": "143467-2,29",
        "User-Agent": "iTunes/12.0 (Macintosh; OS X 10.10)",
        "Accept": "application/json",
    }
    url = f"https://itunes.apple.com/WebObjects/MZStore.woa/wa/userReviewsRow?id={app_id}&displayable-kind=11&startIndex=0&endIndex=9&sort=4"
    r = requests.get(url, headers=headers, timeout=10)
    print("Status:", r.status_code)
    if r.status_code == 200:
        reviews = r.json().get("userReviewList", [])
        print(f"Reviews fetched: {len(reviews)}")
        if reviews:
            print("First review:", reviews[0].get("title"), "| Rating:", reviews[0].get("rating"))
            print("Text:", reviews[0].get("body", "")[:100])

def test_playstore():
    print("\n=== Testing Google Play Store Reviews ===")
    from google_play_scraper import Sort, reviews as get_reviews
    revs, _ = get_reviews("com.nextbillion.groww", lang="en", country="in", sort=Sort.NEWEST, count=10)
    print(f"Reviews fetched: {len(revs)}")
    if revs:
        print("First review:", revs[0].get("userName"), "| Rating:", revs[0].get("score"))
        print("Text:", revs[0].get("content", "")[:100])

def test_tradingqna():
    print("\n=== Testing TradingQ&A Discourse Search ===")
    url = "https://tradingqna.com/search.json?q=Groww+SIP"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    print("Status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        posts = data.get("posts", [])
        topics = {t["id"]: t["title"] for t in data.get("topics", [])}
        print(f"Posts fetched: {len(posts)}")
        if posts:
            tid = posts[0].get("topic_id")
            print("Topic:", topics.get(tid))
            print("Author:", posts[0].get("username"))
            print("Snippet:", posts[0].get("blurb", "")[:100])

def test_ddg_lite():
    print("\n=== Testing DuckDuckGo Lite ===")
    queries = [
        "site:reddit.com/r/IndiaInvestments Groww SIP",
        "site:reddit.com/r/mutualfunds Groww SIP",
        "Groww SIP review TradingQ&A ValuePickr",
    ]
    for q in queries:
        url = "https://lite.duckduckgo.com/lite/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = requests.post(url, data={"q": q}, headers=headers, timeout=10)
        print(f"Query: '{q[:35]}' Status: {r.status_code}")
        if r.status_code == 200:
            snippets = re.findall(r'<td class=[\'"]result-snippet[\'"]>(.*?)</td>', r.text, re.DOTALL)
            links = re.findall(r'<a class=[\'"]result-link[\'"][^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', r.text)
            print(f"  Found {len(links)} links, {len(snippets)} snippets")
            for (href, title), snip in zip(links[:2], snippets[:2]):
                t_clean = re.sub(r'<[^>]+>', '', title).strip()
                s_clean = re.sub(r'<[^>]+>', '', snip).strip()
                print("  Title:", t_clean)
                print("  Snippet:", s_clean[:120])
                print("  Link:", href)


def test_youtube():
    print("\n=== Testing YouTube Search RSS / Invidious ===")
    # YouTube has public search feeds or public invidious instances
    # Or YouTube video search RSS: https://www.youtube.com/feeds/videos.xml?channel_id=...
    # Let's test querying YouTube public search or Google video search
    url = "https://www.youtube.com/results?search_query=Groww+SIP+review"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(url, headers=headers, timeout=10)
    print("YouTube search status:", r.status_code)
    # Extract video titles
    titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"', r.text)
    print(f"YouTube video titles extracted: {len(titles)}")
    for t in titles[:3]:
        print(" - Video:", t)

if __name__ == "__main__":
    test_apple()
    test_playstore()
    test_tradingqna()
    test_ddg_lite()
    test_youtube()

