const PAGE_SIZE = 30; // vis 30 ad gangen

const TOPIC_RULES = {
  "Kapital": /(invest|kapital|runde|seed|pre-?seed|serie\s?a|funding|fond|vc|venture|angel)/i,
  "Rollemodeller": /(rollemodel|portræt|interview|stifter|founder|medstifter|leder|direktør)/i,
  "Events": /(event|konference|techbbq|summit|pitch|demo\s?day)/i,
  "Politik & midler": /(pulje|ordning|erhvervsstyrelsen|innovation\s?fond|støtte|tilskud)/i,
  "Internationalt": /(norden|europa|eu|global|international)/i,
};

const state = { items: [], filtered: [], q: "", activeTopics: new Set(), page: 1 };
const $ = (sel) => document.querySelector(sel);

function guessTopics(item) {
  const hay = `${item.title} ${item.summary || ""}`;
  return Object.entries(TOPIC_RULES).filter(([_, re]) => re.test(hay)).map(([k]) => k);
}

function fmtDate(d) {
  if (!d) return "";
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return d;
  const rtf = new Intl.RelativeTimeFormat(navigator.language || "da", { numeric: "auto" });
  const diffMs = dt.getTime() - Date.now();
  const mins = Math.round(diffMs / 60000);
  const hours = Math.round(mins / 60);
  const days = Math.round(hours / 24);
  if (Math.abs(mins) < 60) return rtf.format(mins, "minute");
  if (Math.abs(hours) < 24) return rtf.format(hours, "hour");
  if (Math.abs(days) < 7) return rtf.format(days, "day");
  return dt.toLocaleString(undefined, { year:"numeric", month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit" });
}

function setTheme(t){
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem("fff-theme", t);
  const btn = $("#themeBtn");
  btn.textContent = t === "dark" ? "☀️ Lys" : "🌙 Mørk";
}

function initTheme(){
  // Bold Startup: start i mørk, men respekter tidligere valg
  const saved = localStorage.getItem("fff-theme");
  setTheme(saved || "dark");
}

function renderChips(){
  const holder = $("#chips"); holder.innerHTML = "";
  Object.keys(TOPIC_RULES).forEach((t) => {
    const b = document.createElement("button");
    b.className = "chip" + (state.activeTopics.has(t) ? " on" : "");
    b.textContent = t;
    b.onclick = () => {
      if (state.activeTopics.has(t)) state.activeTopics.delete(t); else state.activeTopics.add(t);
      applyFilters(); renderChips();
    };
    holder.appendChild(b);
  });
  if (state.activeTopics.size > 0){
    const reset = document.createElement("button");
    reset.className = "chip";
    reset.textContent = "Nulstil filtre";
    reset.onclick = () => { state.activeTopics.clear(); applyFilters(); renderChips(); };
    holder.appendChild(reset);
  }
}

function applyFilters(){
  const q = state.q.toLowerCase();
  state.filtered = state.items
    .map((it) => ({ ...it, _topics: guessTopics(it) }))
    .filter((it) => {
      const inText = !q
        || it.title.toLowerCase().includes(q)
        || (it.summary || "").toLowerCase().includes(q)
        || (it.source || "").toLowerCase().includes(q);
      const topicsOk = state.activeTopics.size === 0 || it._topics.some((t) => state.activeTopics.has(t));
      return inText && topicsOk;
    });

  state.page = 1; // start forfra ved nye filtre/søgning
  renderFeed();
}

function renderFeed(){
  const feed = $("#feed"), empty = $("#empty"), loading = $("#loading");
  const pager = $("#pager"), moreBtn = $("#moreBtn"), countInfo = $("#countInfo");
  loading.style.display = "none";

  const total = state.filtered.length;
  if (total === 0){
    feed.style.display = "none"; pager.style.display = "none"; empty.style.display = "block"; return;
  }
  empty.style.display = "none"; feed.style.display = "grid";

  const end = state.page * PAGE_SIZE;
  const subset = state.filtered.slice(0, end);

  feed.innerHTML = "";
  subset.forEach((it) => {
    const card = document.createElement("article"); card.className = "card";
    const h3 = document.createElement("h3");
    const a = document.createElement("a"); a.href = it.link; a.target="_blank"; a.rel="noopener"; a.textContent = it.title; h3.appendChild(a);
    const meta = document.createElement("div"); meta.className = "meta";
    meta.textContent = `${it.source || "Kilde"}${it.published ? " · " + fmtDate(it.published) : ""}`;
    const sum = document.createElement("p"); sum.className="summary"; sum.textContent = it.summary || "";
    const topics = document.createElement("div"); topics.className="topics";
    guessTopics(it).forEach((t) => { const tag=document.createElement("span"); tag.className="topic"; tag.textContent=t; topics.appendChild(tag); });
    card.appendChild(h3); card.appendChild(meta); if (it.summary) card.appendChild(sum); card.appendChild(topics);
    feed.appendChild(card);
  });

  // Pager
  if (end < total){
    pager.style.display = "block";
    moreBtn.style.display = "inline-block";
    countInfo.textContent = `Viser ${subset.length} af ${total}`;
    moreBtn.onclick = () => { state.page += 1; renderFeed(); };
  } else {
    pager.style.display = "block";
    moreBtn.style.display = "none";
    countInfo.textContent = `Alle ${total} er vist`;
  }
}

async function load(){
  try{
    const res = await fetch("./news.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no news.json");
    state.items = await res.json();
  }catch(e){
    state.items = [
      { title:"Ny fond støtter kvindelige stiftere i seed-fasen", link:"#", summary:"Initiativet vil øge andelen af kapital til female founders i Danmark.", published:new Date().toISOString(), source:"Eksempel" }
    ];
  }
  const newest = state.items.map(i => new Date(i.published||0).getTime()).filter(n => !isNaN(n)).sort((a,b)=>b-a)[0];
  if (newest) $("#lastUpdated").textContent = "Senest opdateret " + fmtDate(newest);
  applyFilters();
}

window.addEventListener("DOMContentLoaded", () => {
  initTheme();
  $("#themeBtn").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    setTheme(cur === "dark" ? "light" : "dark");
  });
  renderChips();
  $("#q").addEventListener("input", (e) => { state.q = e.target.value || ""; applyFilters(); });
  load();
});
