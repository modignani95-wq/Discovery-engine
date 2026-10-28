import requests, re

url = "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = requests.get(url, headers=headers)

scripts = re.findall(r'src=["\'](https://[^"\']+?\.js)["\']', r.text)
print("Found scripts:", len(scripts))
token = None
for s in scripts[:10]:
    print("Checking script:", s)
    try:
        js = requests.get(s, headers=headers, timeout=10).text
        jwts = re.findall(r'Bearer\s+(eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)', js, re.IGNORECASE)
        if not jwts:
            jwts = re.findall(r'["\'](eyJ[a-zA-Z0-9_\-]{20,}\.eyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]+)["\']', js)
        if jwts:
            token = jwts[0]
            print(">>> FOUND TOKEN IN JS:", token[:60], "from", s)
            break
    except Exception as e:
        print("Error fetching script:", e)

if token:
    print("\nTesting amp-api with token...")
    amp_url = "https://amp-api.apps.apple.com/v1/catalog/in/apps/1404871703/reviews"
    amp_headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://apps.apple.com",
        "User-Agent": headers["User-Agent"]
    }
    amp_res = requests.get(amp_url, headers=amp_headers, params={"l": "en-GB", "offset": "0", "limit": "20"})
    print("Amp API status:", amp_res.status_code)
    if amp_res.status_code == 200:
        data = amp_res.json()
        print("Amp API reviews count:", len(data.get("data", [])))
        print("Next url:", data.get("next"))
else:
    print("\nNo token found in scripts.")
