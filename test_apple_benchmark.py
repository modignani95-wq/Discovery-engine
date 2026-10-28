import requests
import time

app_id = "1404871703"
headers = {
    "X-Apple-Store-Front": "143467-2,29",
    "User-Agent": "iTunes/12.0 (Macintosh; OS X 10.10)",
    "Accept": "application/json",
}

print("Testing batch of 100 reviews in userReviewsRow...")
for b in [100, 200]:
    url = f"https://itunes.apple.com/WebObjects/MZStore.woa/wa/userReviewsRow?id={app_id}&displayable-kind=11&startIndex=0&endIndex={b-1}&sort=4"
    r = requests.get(url, headers=headers, timeout=10)
    rows = r.json().get("userReviewList", [])
    print(f"Requested endIndex={b-1} -> Returned rows: {len(rows)}")

print("\nTesting speed of fetching 3,000 reviews...")
total_fetched = 0
t0 = time.time()
batch_size = 50
for page in range(65):
    start = page * batch_size
    end = start + batch_size - 1
    url = f"https://itunes.apple.com/WebObjects/MZStore.woa/wa/userReviewsRow?id={app_id}&displayable-kind=11&startIndex={start}&endIndex={end}&sort=4"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        rows = r.json().get("userReviewList", [])
        if not rows:
            print(f"No more rows at page {page} (start={start})")
            break
        total_fetched += len(rows)
        if (page + 1) % 10 == 0:
            print(f"Page {page+1}: Total {total_fetched} Apple App Store reviews in {time.time()-t0:.1f}s")
        if total_fetched >= 3000:
            break
    except Exception as e:
        print(f"Error at page {page}: {e}")
        break

print(f"Finished! Total Apple reviews fetched: {total_fetched} in {time.time()-t0:.1f}s")
