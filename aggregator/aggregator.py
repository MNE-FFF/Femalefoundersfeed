#!/usr/bin/env python3
"""
FemaleFoundersFeed — RSS aggregator (keyword-baseline)

- Læser feeds fra aggregator/config.yaml
- Filtrerer artikler ud fra:
    * mindst ét "køn"-ord (kvinde/women/female/…)
    * OG (mindst ét "startup"-ord ELLER mindst ét "business"-ord)
- Skriver resultater til ./news.json (læses af index.html)

Kør lokalt:
  pip install -r aggregator/requirements.txt
  python aggregator/aggregator.py

Bemærk:
- Hold dig til RSS/Atom (respektér robots.txt og vilkår).
- Dette er en simpel baseline. Udvid senere med bedre NLP/deduplikering efter behov.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
from bs4 import BeautifulSoup
import yaml


# --- Stier ---
ROOT = Path(__file__).resolve().parent.parent  # repo-roden
CONFIG_PATH = ROOT / "aggregator" / "config.yaml"
OUTPUT_PATH = ROOT / "news.json"


# --- Hjælpere ---
def clean_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def hash_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()


# --- Hovedprogram ---
def main() -> None:
    cfg = load_config()
    feeds = cfg.get("feeds", [])
    if not feeds:
        print("[WARN] No feeds configured in config.yaml", file=sys.stderr)

    # Kompiler søgeord (robust mod tomme lister)
    kg = cfg.get("keywords_gender", [])
    ks = cfg.get("keywords_startup", [])
    kb = cfg.get("keywords_business", [])

    if not kg or not ks:
        print("[WARN] Missing keywords_gender or keywords_startup in config.yaml", file=sys.stderr)

    kw_gender = re.compile("(" + "|".join(kg) + ")", re.IGNORECASE) if kg else None
    kw_startup = re.compile("(" + "|".join(ks) + ")", re.IGNORECASE) if ks else None
    kw_business = re.compile("(" + "|".join(kb) + ")", re.IGNORECASE) if kb else None

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

            has_gender = bool(kw_gender.search(hay)) if kw_gender else False
            has_startup = bool(kw_startup.search(hay)) if kw_startup else False
            has_business = bool(kw_business.search(hay)) if kw_business else False

            # Kræv kvinde-vinkel, og derudover enten startup- ELLER business-ord
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

    # Sortér nyeste først (tåler ikke-ISO datoer ved fallback)
    def ts(x):
        try:
            # håndtér 'Z'
            return datetime.fromisoformat(str(x["published"]).replace("Z", "+00:00"))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    entries.sort(key=ts, reverse=True)

    # Begræns mængde for et let JSON
    limit = int(cfg.get("export_limit", 200))
    entries = entries[:limit]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote {len(entries)} items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
