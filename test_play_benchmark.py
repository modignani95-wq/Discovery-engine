import google_play_scraper
import time

token = None
total = 0
t0 = time.time()
print("Starting Play Store pagination test...")
for b in range(1, 26):
    raw, token = google_play_scraper.reviews(
        'com.nextbillion.groww',
        lang='en',
        country='in',
        sort=google_play_scraper.Sort.NEWEST,
        count=200,
        continuation_token=token
    )
    if not raw:
        print("No raw reviews returned.")
        break
    total += len(raw)
    if b % 5 == 0:
        print(f"Batch {b}: {total} reviews fetched in {time.time()-t0:.1f}s, oldest: {raw[-1].get('at')}")
    if not token:
        print("No continuation token.")
        break
print(f"Finished benchmark. Total: {total}, Token present: {bool(token)}")
