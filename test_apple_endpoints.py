import requests
import json

app_id = "1404871703"
headers = {
    "X-Apple-Store-Front": "143467-2,29",
    "User-Agent": "iTunes/12.0 (Macintosh; OS X 10.10)",
    "Accept": "application/json",
}

print("Testing userReviewsRow beyond index 500...")
for start in [0, 50, 100, 450, 500, 550, 1000, 2000, 3000]:
    end = start + 49  # try batch of 50
    url = f"https://itunes.apple.com/WebObjects/MZStore.woa/wa/userReviewsRow?id={app_id}&displayable-kind=11&startIndex={start}&endIndex={end}&sort=4"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        rows = data.get("userReviewList", [])
        total = data.get("totalNumberOfReviews", "N/A")
        print(f"start={start}, end={end} -> Status: {r.status_code}, Returned rows: {len(rows)}, Total reported: {total}")
        if rows:
            first_title = rows[0].get("title", "")
            first_user = rows[0].get("userReviewId", "")
            print(f"   Sample: ID {first_user} - Title: '{first_title}'")
    except Exception as e:
        print(f"start={start}, end={end} -> Error: {e}")
