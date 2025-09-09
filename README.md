# FemaleFoundersFeed — statisk MVP

Dette er et helt simpelt, **statisk** website: ingen build, ingen Node. Du kan uploade filerne direkte til GitHub og bruge **GitHub Pages**.

## Struktur
- `index.html` — selve siden
- `app.js` — logik (loader `news.json`, søgning, filtre)
- `news.json` — dine artikler (kan opdateres manuelt i starten)
- *(CSS ligger indlejret i `index.html` for enkelhed)*

## Sådan kører du lokalt
Åbn `index.html` i din browser. (Hvis du vil undgå CORS-problemer, åbn via en lille lokal server, fx `python3 -m http.server` og gå til http://localhost:8000)

## Deploy til GitHub Pages (uden Actions)
1. Opret et offentligt repo på GitHub, fx `femalefoundersfeed`.
2. Upload filerne (index.html, app.js, news.json).
3. Gå til **Settings → Pages**.
4. Vælg **Deploy from a branch** → **main** og **/ (root)** → **Save**.
5. Vent 1–2 minutter. Dit site ligger nu på `https://<brugernavn>.github.io/femalefoundersfeed/`

## Format for `news.json`
```json
[
  {
    "title": "Overskrift",
    "link": "https://eksempel.dk/artikel",
    "summary": "Kort resumé",
    "published": "2025-09-09T08:30:00Z",
    "source": "Mediets navn"
  }
]
```

## Næste trin
- Når du er klar, kobler vi en lille **aggregator** på, som automatisk opdaterer `news.json`.
- Senere kan vi skifte til et React- eller Next.js-setup — men **det behøver vi ikke** for at komme i luften nu.
