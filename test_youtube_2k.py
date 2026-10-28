import os
import sys
import time
from dotenv import load_dotenv

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

load_dotenv()
key = os.getenv("YOUTUBE_API_KEY")
print("YOUTUBE_API_KEY present:", bool(key))

from googleapiclient.discovery import build
yt = build("youtube", "v3", developerKey=key, cache_discovery=False)

# Search queries covering major Groww SIP tutorial topics
queries = [
    "Groww SIP mutual funds",
    "Groww SIP kaise kare",
    "Groww SIP pause cancel",
    "Groww autopay failed mandate",
    "Groww mutual fund withdrawal"
]

all_comments = []
seen_comment_ids = set()
t0 = time.time()

for q in queries:
    if len(all_comments) >= 2000:
        break
    print(f"\nSearching videos for query: '{q}'...")
    try:
        s_res = yt.search().list(q=q, part="id,snippet", maxResults=15, type="video").execute()
    except Exception as e:
        print("Search error:", e)
        continue

    for item in s_res.get("items", []):
        if len(all_comments) >= 2000:
            break
        vid = item.get("id", {}).get("videoId")
        if not vid:
            continue
        v_title = item.get("snippet", {}).get("title", "Video")
        ch_title = item.get("snippet", {}).get("channelTitle", "Channel")

        page_token = None
        while len(all_comments) < 2000:
            try:
                ct_res = yt.commentThreads().list(
                    part="snippet",
                    videoId=vid,
                    maxResults=100,
                    pageToken=page_token,
                    textFormat="plainText",
                ).execute()

                items = ct_res.get("items", [])
                if not items:
                    break

                new_count = 0
                for c in items:
                    cid = c.get("id")
                    if cid in seen_comment_ids:
                        continue
                    seen_comment_ids.add(cid)
                    snip = c.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    text = (snip.get("textDisplay") or "").strip()
                    if text:
                        all_comments.append({
                            "id": cid,
                            "text": text,
                            "author": snip.get("authorDisplayName", "User"),
                            "date": snip.get("publishedAt"),
                            "video": v_title,
                            "channel": ch_title,
                        })
                        new_count += 1
                        if len(all_comments) >= 2000:
                            break

                page_token = ct_res.get("nextPageToken")
                if not page_token:
                    break
            except Exception as exc:
                # Comments disabled or rate limit
                # print(f"Error on video {vid}: {exc}")
                break

        print(f"Total collected so far: {len(all_comments)} (Video: {v_title[:45]}...)")

print(f"\nFinished! Total comments retrieved: {len(all_comments)} in {time.time()-t0:.1f}s")
if all_comments:
    print("Sample comment:", all_comments[0])
