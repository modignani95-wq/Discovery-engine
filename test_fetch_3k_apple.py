import requests, time

app_id = "1404871703"
headers = {
    "X-Apple-Store-Front": "143467-2,29",
    "User-Agent": "iTunes/12.0 (Macintosh; OS X 10.10)",
    "Accept": "application/json",
}

t0 = time.time()
reviews = []
batch_size = 50
print("Starting 3,000 Apple App Store reviews fetch test...")
for page in range(65):
    start = page * batch_size
    end = start + batch_size - 1
    r = requests.get(
        f"https://itunes.apple.com/WebObjects/MZStore.woa/wa/userReviewsRow?id={app_id}&displayable-kind=11&startIndex={start}&endIndex={end}&sort=4",
        headers=headers,
        timeout=10
    )
    raw = r.json().get("userReviewList", [])
    if not raw:
        print(f"No more reviews at page {page}")
        break
    reviews.extend(raw)
    if (page + 1) % 15 == 0:
        print(f"Page {page+1}: {len(reviews)} reviews fetched in {time.time()-t0:.1f}s")
    if len(reviews) >= 3000:
        break

oldest = reviews[-1].get("date") if reviews else "N/A"
print(f"Done! Total Apple reviews: {len(reviews)} in {time.time()-t0:.1f}s. Oldest: {oldest}")
