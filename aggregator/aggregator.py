#!/usr/bin/env python3
"""
FemaleFoundersFeed — RSS aggregator (scoring-version)

Idé:
- Vi scorer artikler i stedet for hårdt at afvise.
- +weight ved match på:
    * gender-ord (kvinde, women, …)
    * startup-ord (iværksætter, startup, founder, …)
    * business-ord (investering, direktør, kapital, …)
- Ekstra lille bonus hvis match findes i titlen.
- Ekskluderer artikler med "exclude_keywords" (fx sport) uanset score.

Config (aggregator/config.yaml):
  feeds: [ ... ]
  keywords_gender: [ ... ]
  keywords_startup: [ ... ]
  keywords_business: [ ... ]
  exclude_keywords: [ ... ]      # valgfri
  weights:                       # valgfri
    gender: 2
    startup: 2
    business: 1
    title_bonus: 1
  min_score: 2
  export_limit: 200
  max_age_days: 120              # NY: kun nyere end N dage

Kør lokalt:
  pip install -r aggregator/requirements.txt
  python aggregator/aggregator.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List

import feedparser
from bs4 import BeautifulSoup
import yaml

import requests
from urllib.parse import urlparse, urljoin


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

def hash_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # defaults
    cfg.setdefault("keywords_gender", [])
    cfg.setdefault("keywords_startup", [])
    cfg.setdefault("keywords_business", [])
    cfg.setdefault("exclude_keywords", [])
    cfg.setdefault("min_score", 2)
    cfg.setdefault("export_limit", 200)
    cfg.setdefault("weights", {"gender": 2, "startup": 2, "business": 1, "title_bonus": 1})
    cfg.setdefault("max_age_days", 120)
    return cfg

def compile_or_none(terms: List[str]) -> re.Pattern | None:
    terms = [t for t in terms if t and t.strip()]
    if not terms:
        return None
    return re.compile("(" + "|".join(terms) + ")", re.IGNORECASE)

def score_item(title: str, summary: str, regs: Dict[str, re.Pattern | None], weights: Dict[str, int]) -> int:
    """Returnerer samlet score for en artikel (kategori-vis, ikke pr. forekomst)."""
    hay = f"{title}\n{summary}"
    score = 0

    if regs["gender"] and regs["gender"].search(hay):
        score += int(weights.get("gender", 2))
        if regs["gender"].search(title):
            score += int(weights.get("title_bonus", 1))

    if regs["startup"] and regs["startup"].search(hay):
        score += int(weights.get("startup", 2))
        if regs["startup"].search(title):
            score += int(weights.get("title_bonus", 1))

    if regs["business"] and regs["business"].search(hay):
        score += int(weights.get("business", 1))
        if regs["business"].search(title):
            score += int(weights.get("title_bonus", 1))

    return score

def is_excluded(title: str, summary: str, rx_exclude: re.Pattern | None) -> bool:
    if not rx_exclude:
        return False
    hay = f"{title}\n{summary}"
    return bool(rx_exclude.search(hay))

def domain_of(u: str) -> str:
    try:
        host = urlparse(u).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""

def absolute_links(page_url: str, soup: BeautifulSoup) -> list[str]:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href: 
            continue
        absu = urljoin(page_url, href)
        links.append((absu, a.get_text(strip=True)))
    return links

def scrape_press_page(page_url: str, expected_domain: str, max_items: int = 30) -> list[dict]:
    """Henter en presseside (HTML), finder links på samme domæne og returnerer som entries.
       Rækkefølge bevares; vi tildeler kunstige timestamps (nu, nu-1min, ...)."""
    out = []
    try:
        r = requests.get(page_url, timeout=20, headers={"User-Agent": "FemaleFoundersFeed/1.0"})
        r.raise_for_status()
    except Exception as ex:
        print(f"[WARN] Failed to fetch press page {page_url}: {ex}", file=sys.stderr)
        return out

    soup = BeautifulSoup(r.text, "html.parser")
    pairs = absolute_links(page_url, soup)

    # Filtrér: samme domæne, rimelig linktekst, undgå sociale/fil-ting
    seen = set()
    filtered = []
    for absu, text in pairs:
        dom = domain_of(absu)
        if expected_domain and domain_of("https://" + expected_domain) != dom and expected_domain != dom:
            continue
        if any(s in absu.lower() for s in ["/wp-json", "/feed", ".pdf", "mailto:", "tel:"]):
            continue
        if len(text) < 6:  # undgå “Læs mere”, “Klik”, mm.
            continue
        key = (absu, text)
        if key in seen:
            continue
        seen.add(key)
        filtered.append((absu, text))

    # Behold top N i den rækkefølge de står (antag siden viser nyeste øverst)
    filtered = filtered[:max_items]

    # Kunstige tidsstempler for at bevare rækkefølge
    now = datetime.now(timezone.utc)
    for idx, (absu, text) in enumerate(filtered):
        ts = now - timedelta(minutes=idx)
        out.append({
            "title": text,
            "link": absu,
            "summary": "",                  # optional: kunne forsøge at hente teaser-tekst
            "published": ts.isoformat(),
            "source": expected_domain or domain_of(absu),
        })
    print(f"[INFO] Press page {page_url}: +{len(out)} items")
    return out



def main() -> None:
    cfg = load_config()
    feeds = cfg.get("feeds", [])
    if not feeds:
        print("[WARN] No feeds configured in config.yaml", file=sys.stderr)

    # compile regex
    regs = {
        "gender": compile_or_none(cfg.get("keywords_gender", [])),
        "startup": compile_or_none(cfg.get("keywords_startup", [])),
        "business": compile_or_none(cfg.get("keywords_business", [])),
    }
    rx_exclude = compile_or_none(cfg.get("exclude_keywords", []))
    weights = cfg.get("weights", {"gender": 2, "startup": 2, "business": 1, "title_bonus": 1})
    min_score = int(cfg.get("min_score", 2))
    max_age_days = int(cfg.get("max_age_days", 120))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    entries = []
    ids = set()

    for url in feeds:
        count_before = len(entries)
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

            # --- robust timestamp ---
            ts_struct = e.get("published_parsed") or e.get("updated_parsed")
            if ts_struct:
                ts = datetime.fromtimestamp(time.mktime(ts_struct), tz=timezone.utc)
            else:
                # fallback hvis feed mangler dato
                ts = datetime.now(timezone.utc)

            # filtrér gamle artikler væk
            if ts < cutoff:
                continue

            published = ts.isoformat()

            # eksklusionsord
            if is_excluded(title, summary, rx_exclude):
                continue

            # scoring + krav om gender-match
            s = score_item(title, summary, regs, weights)
            has_gender = regs["gender"] and regs["gender"].search(f"{title}\n{summary}")
            if s < min_score or not has_gender:
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

        added = len(entries) - count_before
        print(f"[INFO] {url}: +{added} items (total {len(entries)})")

     # --- NYT: håndtér pressesider uden RSS ---
        # --- NYT: håndtér pressesider uden RSS ---
    press_pages = cfg.get("press_pages", [])
    for p in press_pages:
        page_url = p.get("url")
        dom = p.get("domain") or (domain_of(page_url) if page_url else "")
        max_items = int(p.get("max_items", 30))
        if not page_url:
            continue

        press_entries = scrape_press_page(page_url, dom, max_items=max_items)
        # deduplikér mod eksisterende by link+title hash
        for item in press_entries:
            _id = hash_id(item["link"], item["title"])
            if _id in ids:
                continue
            ids.add(_id)
            entries.append(item)

   
    # sort newest first
    def ts_key(x):
        try:
            return datetime.fromisoformat(str(x["published"]).replace("Z", "+00:00"))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    entries.sort(key=ts_key, reverse=True)
    entries = entries[: int(cfg.get("export_limit", 200))]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote {len(entries)} items to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
