#!/usr/bin/env python3
"""
update_ui_platforms.py
Ensures Twitter (X) and Instagram pills, tags, and counts are added
to retrieval_discovery_engine.html, index.html, and sip_dashboard.html.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
RDE_FILE = BASE_DIR / "static" / "retrieval_discovery_engine.html"
INDEX_FILE = BASE_DIR / "index.html"
SIP_DASH_FILE = BASE_DIR / "static" / "sip_dashboard.html"

# 1. Update retrieval_discovery_engine.html and index.html
for target_path in [RDE_FILE, INDEX_FILE]:
    if not target_path.exists():
        continue
    content = target_path.read_text(encoding="utf-8")

    # Add CSS tags
    if ".tag-twitter" not in content:
        content = content.replace(
            ".tag-reddit { background: var(--groww-red-soft); color: var(--groww-red); border: 1px solid var(--groww-red-border); }",
            ".tag-reddit { background: var(--groww-red-soft); color: var(--groww-red); border: 1px solid var(--groww-red-border); }\n    .tag-twitter { background: #f3e8ff; color: #7c3aed; border: 1px solid #ddd6fe; }\n    .tag-instagram { background: #fdf2f8; color: #db2777; border: 1px solid #fbcfe8; }"
        )

    # Add Pills in Explorer
    old_pills = """          <button class="pill-btn" id="pill-plat-tradingqna" onclick="filterEpisodes('platform', 'tradingqna', this)">TradingQ&amp;A (79)</button>"""
    new_pills = """          <button class="pill-btn" id="pill-plat-twitter" onclick="filterEpisodes('platform', 'twitter', this)">Twitter / X (36)</button>
          <button class="pill-btn" id="pill-plat-instagram" onclick="filterEpisodes('platform', 'instagram', this)">Instagram (30)</button>
          <button class="pill-btn" id="pill-plat-tradingqna" onclick="filterEpisodes('platform', 'tradingqna', this)">TradingQ&amp;A (79)</button>"""
    if "pill-plat-twitter" not in content and old_pills in content:
        content = content.replace(old_pills, new_pills)

    # Update counts in JS
    old_counts = """    if (el('pill-plat-reddit')) el('pill-plat-reddit').textContent = `Reddit (${countPlat('reddit')})`;"""
    new_counts = """    if (el('pill-plat-reddit')) el('pill-plat-reddit').textContent = `Reddit (${countPlat('reddit')})`;
    if (el('pill-plat-twitter')) el('pill-plat-twitter').textContent = `Twitter / X (${countPlat('twitter')})`;
    if (el('pill-plat-instagram')) el('pill-plat-instagram').textContent = `Instagram (${countPlat('instagram')})`;"""
    if "pill-plat-twitter" not in content or old_counts in content:
        content = content.replace(old_counts, new_counts)

    target_path.write_text(content, encoding="utf-8")
    print(f"Updated {target_path.name}")

# 2. Update sip_dashboard.html
if SIP_DASH_FILE.exists():
    content = SIP_DASH_FILE.read_text(encoding="utf-8")
    old_sd_pills = """          <div class="src-pill" data-plat="reddit" onclick="setSipDashPlatFilter('reddit', this)" style="padding:3px 8px;font-size:.72rem;">Reddit (116)</div>
          <div class="src-pill" data-plat="tradingqna" onclick="setSipDashPlatFilter('tradingqna', this)" style="padding:3px 8px;font-size:.72rem;">TradingQ&A (79)</div>"""
    new_sd_pills = """          <div class="src-pill" data-plat="reddit" onclick="setSipDashPlatFilter('reddit', this)" style="padding:3px 8px;font-size:.72rem;">Reddit (419)</div>
          <div class="src-pill" data-plat="twitter" onclick="setSipDashPlatFilter('twitter', this)" style="padding:3px 8px;font-size:.72rem;">Twitter / X (36)</div>
          <div class="src-pill" data-plat="instagram" onclick="setSipDashPlatFilter('instagram', this)" style="padding:3px 8px;font-size:.72rem;">Instagram (30)</div>
          <div class="src-pill" data-plat="tradingqna" onclick="setSipDashPlatFilter('tradingqna', this)" style="padding:3px 8px;font-size:.72rem;">TradingQ&A (80)</div>"""
    if old_sd_pills in content:
        content = content.replace(old_sd_pills, new_sd_pills)
        SIP_DASH_FILE.write_text(content, encoding="utf-8")
        print(f"Updated {SIP_DASH_FILE.name}")
    else:
        print(f"Pills pattern in {SIP_DASH_FILE.name} check")

