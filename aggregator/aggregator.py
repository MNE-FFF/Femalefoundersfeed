#!/usr/bin/env python3
"""
FemaleFoundersFeed — RSS aggregator (simple, keyword-based)
- Reads feeds from config.yaml
- Filters for women + entrepreneurship keywords
- Writes ./news.json (consumed by index.html)

Run locally:
  pip install -r aggregator/requirements.txt
  python aggregator.py

Notes:
- Keep to RSS/Atom (respect robots.txt and site terms).
- This is a simple heuristic baseline. Improve as needed.
"""
from __future__ import annotations
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
from bs4 import BeautifulSoup
import yaml

ROOT = Path(__file__).resolve().parent.parent  # repo root
CONFIG_PATH = ROOT / "aggregator" / "config.yaml"
OUTPUT_PATH = ROOT / "news.json"

def clean_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def hash_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()

def main():
    cfg = load_config()
    feeds = cfg.get("feeds", [])
    if not feeds:
        print("[WARN] No feeds configured in config.yaml", file=sys.stderr)

    # compile regex
    kw_gender = re.compile("(" + "|".join(cfg["keywords_gender"]) + ")", re.IGNORECASE)
    kw_startup = re.compile("(" + "|".join(cfg["keywords_startup"]) + ")", re.IGNORECASE)

    entries = []
    ids = set()

    for url in feeds:
        try:
            parsed = feedparser.parse(url)
        except Exception as ex:
            print(f"[WARN] Failed to parse {url}: {ex}", file=sys.stderr)
            continue

        for e in parsed.entries:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link:
                continue

            summary = clean_html(e.get("summary") or e.get("description") or "")
            published = (
                e.get("published")
                or e.get("updated")
                or e.get("pubDate")
                or now_iso()
            )

          hay = f"{title}\n{summary}"

kw_business = re.compile("(" + "|".join(cfg.get("keywords_business", [])) + ")", re.IGNORECASE)
has_gender = bool(kw_gender.search(hay))
has_startup = bool(kw_startup.search(hay))
has_business = bool(kw_business.search(hay))

# Kræv kvinde-vinkel, og derudover enten startup-ELLER business-ord
if not (has_gender and (has_startup or has_business)):
    continue


            _id = hash_id(link, title)
            if _id in ids:
                continue
            ids.add(_id)

            source = parsed.feed.get("title") or parsed.feed.get("link") or url

            entries.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
                "source": source,
            })

    # sort newest first by published if parseable
    def ts(x):
        try:
            return datetime.fromisoformat(str(x["published"]).replace("Z", "+00:00"))
        except Exception:
            return datetime(1970,1,1, tzinfo=timezone.utc)

    entries.sort(key=ts, reverse=True)

    limit = int(cfg.get("export_limit", 200))
    entries = entries[:limit]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote {len(entries)} items to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
