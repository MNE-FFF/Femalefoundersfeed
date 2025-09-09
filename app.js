// Simple static frontend for FemaleFoundersFeed
const TOPIC_RULES = {
  "Kapital": /(invest|kapital|rund(e|en)|seed|pre-seed|serie\s?a|funding|fond|vc)/i,
  "Rollemodeller": /(rollemodel|portræt|interview|stifter|founder|medstifter)/i,
  "Events": /(event|konference|techbbq|summit|pitch|demo\s?day)/i,
  "Politik & midler": /(pulje|ordning|erhvervsstyrelsen|innovation\s?fond)/i,
  "Internationalt": /(norden|europa|eu|global|international)/i,
};

function guessTopics(item) {
  const hay = `${item.title} ${item.summary || ""}`;
  return Object.entries(TOPIC_RULES)
    .filter(([_, re]) => re.test(hay))
    .map(([k]) => k);
}

function fmtDate(d) {
  if (!d) return "";
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return d;
  return dt.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const state = {
  items: [],
  filtered: [],
  q: "",
  activeTopics: new Set(),
};

const el = (sel) => document.querySelector(sel);

function renderChips() {
  const holder = el("#chips");
  holder.innerHTML = "";
  Object.keys(TOPIC_RULES).forEach((t) => {
    const b = document.createElement("button");
    b.className = "chip" + (state.activeTopics.has(t) ? " on" : "");
    b.textContent = t;
    b.onclick = () => {
      if (state.activeTopics.has(t)) state.activeTopics.delete(t);
      else state.activeTopics.add(t);
      applyFilters();
      renderChips();
    };
    holder.appendChild(b);
  });

  if (state.activeTopics.size > 0) {
    const reset = document.createElement("button");
    reset.className = "chip";
    reset.textContent = "Nulstil filtre";
    reset.onclick = () => {
      state.activeTopics.clear();
      applyFilters();
      renderChips();
    };
    holder.appendChild(reset);
  }
}

function applyFilters() {
  const q = state.q.toLowerCase();
  state.filtered = state.items
    .map((it) => ({ ...it, _topics: guessTopics(it) }))
    .filter((it) => {
      const inText =
        !q ||
        it.title.toLowerCase().includes(q) ||
        (it.summary || "").toLowerCase().includes(q) ||
        (it.source || "").toLowerCase().includes(q);
      const topicsOk =
        state.activeTopics.size === 0 ||
        it._topics.some((t) => state.activeTopics.has(t));
      return inText && topicsOk;
    });

  renderFeed();
}

function renderFeed() {
  const feed = el("#feed");
  const empty = el("#empty");
  const loading = el("#loading");

  loading.style.display = "none";

  if (state.filtered.length === 0) {
    feed.style.display = "none";
    empty.style.display = "block";
    return;
  } else {
    empty.style.display = "none";
    feed.style.display = "grid";
  }

  feed.innerHTML = "";
  state.filtered.forEach((it) => {
    const card = document.createElement("article");
    card.className = "card";

    const h3 = document.createElement("h3");
    const a = document.createElement("a");
    a.href = it.link;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = it.title;
    h3.appendChild(a);

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${it.source || "Kilde"}${it.published ? " · " + fmtDate(it.published) : ""}`;

    const sum = document.createElement("p");
    sum.className = "summary";
    sum.textContent = it.summary || "";

    const topics = document.createElement("div");
    topics.className = "topics";
    guessTopics(it).forEach((t) => {
      const tag = document.createElement("span");
      tag.className = "topic";
      tag.textContent = t;
      topics.appendChild(tag);
    });

    card.appendChild(h3);
    card.appendChild(meta);
    if (it.summary) card.appendChild(sum);
    card.appendChild(topics);
    feed.appendChild(card);
  });
}

async function load() {
  try {
    const res = await fetch("./news.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no news.json");
    const data = await res.json();
    state.items = data;
  } catch (e) {
    // fallback sample
    state.items = [
      {
        title: "Ny fond støtter kvindelige stiftere i seed-fasen",
        link: "https://example.com/kvindelige-stiftere-seed",
        summary: "Initiativet vil øge andelen af kapital til female founders i Danmark.",
        published: new Date().toISOString(),
        source: "Eksempelmedie",
      },
      {
        title: "Rollemodeller i fokus: 10 danske female founders du bør kende",
        link: "https://example.com/rollemodeller",
        summary: "Portrætter og læringer fra serieiværksættere i København og Aarhus.",
        published: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
        source: "Eksempelblog",
      },
    ];
  }

  // last updated
  const newest = state.items
    .map((i) => new Date(i.published || 0).getTime())
    .filter((n) => !isNaN(n))
    .sort((a, b) => b - a)[0];
  if (newest) {
    document.getElementById("lastUpdated").textContent = "Senest opdateret " + fmtDate(newest);
  }

  applyFilters();
}

window.addEventListener("DOMContentLoaded", () => {
  renderChips();
  el("#q").addEventListener("input", (e) => {
    state.q = e.target.value || "";
    applyFilters();
  });
  load();
});
