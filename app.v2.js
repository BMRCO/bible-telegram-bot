/* =========================
   LaBible.app — app.v2.js
   Fonte: /data/lsg1910.json
   ========================= */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const LS = {
  theme: "labible:theme",
  font:  "labible:font",
  last:  "labible:lastRef",
  fav:   "labible:favs",
  hist:  "labible:history",
  plan:  "labible:plan365",
  vdd:   "labible:vddCache"
};

const DATA_URL     = "/data/lsg1910.json";
const DATA_URL_CDN = "https://cdn.jsdelivr.net/gh/BMRCO/labible@main/data/lsg1910.json";

const state = {
  bible:         null,
  index:         null,
  indexing:      false,
  current:       { book: 0, chapter: 1 },
  deferredPrompt: null,
  readFont:      16,
  vddRef:        null,
  selectedVerse: null,
  explications:  null,
  versetsThemes: null
};

/* ---------- helpers ---------- */
function toast(msg){
  const el = $("#toast");
  if(!el) return;
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}
function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }
function normalize(s){
  return (s||"").toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .replace(/['']/g,"'").replace(/\s+/g," ").trim();
}
function escapeRegExp(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"); }
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}
function nowIso(){ return new Date().toISOString(); }
function dateKey(d=new Date()){
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}

/* ---------- verse action bar ---------- */
function buildVerseShareText(bookName, chapter, verse, text){
  const cleanText = String(text||"").replace(/^¶\s*/,"").trim();
  const ref = `${bookName} ${chapter}:${verse}`;
  return `« ${cleanText} »\n— ${ref} (LSG 1910)`;
}
function buildVerseUrl(bookName, chapter){
  return `https://labible.app/#${bookName}-${chapter}`;
}

function showVerseActions(bookName, chapter, verse, text, el){
  $$(".verse.selected").forEach(p => p.classList.remove("selected"));
  el.classList.add("selected");
  state.selectedVerse = { bookName, chapter, verse, text };
  $("#verseActionBar")?.remove();

  const bar = document.createElement("div");
  bar.id = "verseActionBar";
  bar.style.cssText = `display:flex;gap:8px;padding:8px 12px;margin-top:4px;background:rgba(226,197,122,.1);border-radius:12px;border:1px solid rgba(226,197,122,.25);flex-wrap:wrap;`;
  const ref = `${bookName} ${chapter}:${verse}`;

  const btnFav = document.createElement("button");
  btnFav.className = "chip";
  const isFav = getFavs().some(f => f.type==="verse" && f.ref===ref);
  btnFav.textContent = isFav ? "✅ Favori" : "🔖 Favori";
  btnFav.onclick = () => { toggleFavVerse(bookName, chapter, verse, text); bar.remove(); el.classList.remove("selected"); state.selectedVerse=null; };

  const btnCopy = document.createElement("button");
  btnCopy.className = "chip";
  btnCopy.textContent = "📎 Copier";
  btnCopy.onclick = async () => { await copyText(`${buildVerseShareText(bookName, chapter, verse, text)}\n📖 ${buildVerseUrl(bookName, chapter)}`); bar.remove(); el.classList.remove("selected"); state.selectedVerse=null; };

  const btnShare = document.createElement("button");
  btnShare.className = "chip";
  btnShare.textContent = "🔗 Partager";
  btnShare.onclick = async () => { await shareVerse(bookName, chapter, verse, text); bar.remove(); el.classList.remove("selected"); state.selectedVerse=null; };

  const btnImg = document.createElement("button");
  btnImg.className = "chip";
  btnImg.textContent = "🖼️ Image";
  btnImg.onclick = async () => { await shareVerseImage(bookName, chapter, verse, text); bar.remove(); el.classList.remove("selected"); state.selectedVerse=null; };

  const btnClose = document.createElement("button");
  btnClose.className = "chip";
  btnClose.textContent = "✕";
  btnClose.style.marginLeft = "auto";
  btnClose.onclick = () => { bar.remove(); el.classList.remove("selected"); state.selectedVerse=null; };

  bar.append(btnFav, btnCopy, btnShare, btnImg, btnClose);
  el.insertAdjacentElement("afterend", bar);

  // Explication du verset (si disponible) — bouton + panneau dans la barre
  attachExplication(bar, `${bookName} ${chapter}:${verse}`);
  const _cb = state.bible.books[state.current.book];
  if(_cb) attachReferences(bar, _cb.nr, chapter, verse);
}

async function loadExplications(){
  if(state.explications) return state.explications;
  try{
    const res = await fetch("/data/explications.json");
    state.explications = res.ok ? await res.json() : {};
  } catch { state.explications = {}; }
  return state.explications;
}

/* ---------- vue "Versets" (thèmes) — intégrée à l'app ---------- */
async function loadVersetsThemes(){
  if(state.versetsThemes) return state.versetsThemes;
  try{
    const res = await fetch("/data/versets_themes.json");
    state.versetsThemes = res.ok ? await res.json() : {};
  } catch { state.versetsThemes = {}; }
  return state.versetsThemes;
}

function versetsShowHub(){
  $("#versetsTheme").style.display = "none";
  $("#versetsHub").style.display = "";
}

function versetsShowTheme(key){
  const themes = state.versetsThemes || {};
  const t = themes[key];
  if(!t) return;

  $("#themeIcon").innerHTML = t.icon;
  $("#themeLabel").textContent = t.label;
  $("#themeLead").innerHTML = `${escapeHtml(t.lead)} <strong>${t.refs.length} versets</strong> — Bible Louis Segond 1910.`;

  const list = $("#themeVerseList");
  list.innerHTML = "";
  t.refs.forEach(([bookName, c, v]) => {
    const bi = findBookIndex(bookName);
    if(bi < 0) return;
    const bookMap = getBookData(bi);
    const verses  = bookMap?.get(c) || [];
    const text    = verses[v - 1];
    if(text === undefined) return;

    const a = document.createElement("a");
    a.className = "versetItem";
    a.href = "#";
    const refSpan = document.createElement("span");
    refSpan.className = "versetRef";
    refSpan.textContent = `${bookName} ${c}:${v}`;
    const textSpan = document.createElement("span");
    textSpan.className = "versetText";
    textSpan.textContent = `« ${String(text).replace(/^¶\s*/g, "").trim()} »`;
    a.append(refSpan, textSpan);
    a.addEventListener("click", async (e) => { e.preventDefault(); await openReference({ bi, c, v }); });
    list.appendChild(a);
  });

  $("#versetsHub").style.display = "none";
  $("#versetsTheme").style.display = "";
  $("#versetsTheme").scrollIntoView({ block: "start", behavior: "instant" });
}

// Libellés courts pour les cartes du hub (l'entête "Versets par thème" donne déjà
// le contexte ; le titre complet — "Versets sur…" — reste utilisé dans la vue détail).
const VERSETS_SHORT_LABEL = {
  protection: "Protection", guerison: "Guérison", paix: "Paix",
  amour: "Amour de Dieu", esperance: "Espérance", priere: "Prière",
  promesses: "Promesses de Dieu", deuil: "Réconfort dans le deuil", pardon: "Pardon",
  peur: "Peur et angoisse", confiance: "Confiance en Dieu", force: "Force et courage",
  famille: "Famille", gratitude: "Gratitude et louange", combat: "Combat spirituel",
  solitude: "Présence de Dieu"
};

async function renderVersetsHub(){
  const themes = await loadVersetsThemes();
  const grid = $("#themeGrid");
  if(grid.dataset.built === "1") return;
  grid.innerHTML = "";
  Object.entries(themes).forEach(([key, t]) => {
    const card = document.createElement("a");
    card.className = "themeCard";
    card.href = "#";
    const short = VERSETS_SHORT_LABEL[key] || t.label;
    card.innerHTML = `<span class="em">${t.icon}</span> ${escapeHtml(short)}`;
    card.addEventListener("click", (e) => { e.preventDefault(); versetsShowTheme(key); });
    grid.appendChild(card);
  });
  grid.dataset.built = "1";
}

function attachExplication(bar, refKey){
  function inject(map){
    if(!map || !map[refKey]) return;
    if(bar.querySelector(".btnExplain")) return;
    const btnExp = document.createElement("button");
    btnExp.className = "chip btnExplain";
    btnExp.style.borderColor = "rgba(226,197,122,.4)";
    btnExp.textContent = "💡 Expliquer";
    bar.insertBefore(btnExp, bar.lastChild);

    const panel = document.createElement("div");
    panel.style.cssText = "display:none;width:100%;margin-top:8px;padding:12px 14px;background:rgba(226,197,122,.07);border:1px solid rgba(226,197,122,.22);border-radius:12px;line-height:1.65;font-size:14.5px;";
    panel.textContent = map[refKey];
    bar.appendChild(panel);

    btnExp.addEventListener("click", () => {
      const open = panel.style.display !== "none";
      panel.style.display = open ? "none" : "block";
      btnExp.textContent = open ? "💡 Expliquer" : "▲ Masquer";
    });
  }
  if(state.explications) inject(state.explications);
  else loadExplications().then(inject);
}

async function loadCrossRefs(){
  if(state.crossrefs) return state.crossrefs;
  try{
    const res = await fetch("/data/crossrefs.json");
    state.crossrefs = res.ok ? await res.json() : {};
  } catch { state.crossrefs = {}; }
  return state.crossrefs;
}

function _biFromNr(nr){
  const b = state.bible.books;
  for(let i=0;i<b.length;i++) if(b[i].nr === nr) return i;
  return -1;
}
function _refVerseText(nr, c, v){
  const bm = state.bible.data.get(nr);
  const arr = bm && bm.get(c);
  const t = arr && arr[v-1];
  return t ? String(t).replace(/¶/g,"").replace(/\s+/g," ").trim() : "";
}

function attachReferences(bar, bookNr, chapter, verse){
  loadCrossRefs().then(map => {
    const byBook = map && map[String(bookNr)];
    const list = byBook && byBook[`${chapter}:${verse}`];
    if(!list || !list.length) return;
    if(bar.querySelector(".btnRefs")) return;

    const btn = document.createElement("button");
    btn.className = "chip btnRefs";
    btn.style.borderColor = "rgba(226,197,122,.4)";
    btn.textContent = "🔗 Références";
    bar.insertBefore(btn, bar.lastChild);

    const panel = document.createElement("div");
    panel.style.cssText = "display:none;width:100%;margin-top:8px;padding:6px;background:rgba(226,197,122,.05);border:1px solid rgba(226,197,122,.22);border-radius:12px;";

    for(const [tb,tc,tv] of list){
      const bi = _biFromNr(tb);
      if(bi < 0) continue;
      const name = state.bible.books[bi].name;
      const row = document.createElement("a");
      row.href = `#${name}-${tc}`;
      row.style.cssText = "display:block;padding:9px 10px;border-radius:9px;text-decoration:none;color:inherit;";
      const rref = document.createElement("div");
      rref.style.cssText = "font-family:'EB Garamond',serif;font-weight:600;font-size:15px;color:#c9a640;";
      rref.textContent = `${name} ${tc}:${tv}`;
      const rtxt = document.createElement("div");
      rtxt.style.cssText = "font-family:'EB Garamond',serif;font-size:13.5px;opacity:.6;margin-top:2px;line-height:1.4;";
      const t = _refVerseText(tb, tc, tv);
      rtxt.textContent = t.length > 120 ? t.slice(0,118).trim()+"…" : t;
      row.append(rref, rtxt);
      row.addEventListener("click", async (e) => { e.preventDefault(); await openReference({ bi, c:tc, v:tv }); });
      panel.appendChild(row);
    }

    const credit = document.createElement("div");
    credit.style.cssText = "font-size:10.5px;opacity:.4;text-align:center;padding:7px 4px 3px;";
    credit.textContent = "Références croisées · OpenBible.info · CC BY";
    panel.appendChild(credit);

    bar.appendChild(panel);
    btn.addEventListener("click", () => {
      const open = panel.style.display !== "none";
      panel.style.display = open ? "none" : "block";
      btn.textContent = open ? "🔗 Références" : "▲ Masquer";
    });
  });
}

async function shareVerse(bookName, chapter, verse, text){
  const shareText = buildVerseShareText(bookName, chapter, verse, text);
  const url = buildVerseUrl(bookName, chapter);
  if(navigator.share){
    try{ await navigator.share({ title:`${bookName} ${chapter}:${verse} — LaBible.app`, text: shareText, url }); } catch{}
  } else { await copyText(`${shareText}\n📖 ${url}`); }
}

async function shareVerseImage(bookName, chapter, verse, text){
  try{
    const cv = await renderVerseImage(bookName, chapter, verse, text);
    const blob = await new Promise(r => cv.toBlob(r, "image/png"));
    if(!blob){ toast("Impossible de générer l'image."); return; }
    const fname = `labible-${bookName}-${chapter}-${verse}.png`.replace(/[^\w.-]+/g, "_");
    const file = new File([blob], fname, { type:"image/png" });
    const url = buildVerseUrl(bookName, chapter);
    const caption = `${bookName} ${chapter}:${verse} — LaBible.app\n📖 ${url}`;
    if(navigator.canShare && navigator.canShare({ files:[file] })){
      try{ await navigator.share({ files:[file], title:`${bookName} ${chapter}:${verse} — LaBible.app`, text: caption }); return; }
      catch(e){ if(e && e.name === "AbortError") return; }
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = fname;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast("Image enregistrée.");
  } catch(e){ toast("Erreur lors de la création de l'image."); }
}

function _roundRect(ctx,x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }

function _wrapCanvas(ctx, text, maxW){
  const words = text.split(" ").filter(Boolean);
  const lines = []; let cur = words[0] || "";
  for(let i=1;i<words.length;i++){
    const w = words[i];
    if(ctx.measureText(cur + " " + w).width <= maxW) cur += " " + w;
    else { lines.push(cur); cur = w; }
  }
  if(cur) lines.push(cur);
  return lines;
}

const IMG_PALETTES = {
  psaume:    { top:[8,16,40],  bot:[4,9,24],   accent:[150,185,220], wm:[100,130,165] },
  proverbe:  { top:[26,18,8],  bot:[15,10,4],  accent:[214,170,90],  wm:[150,120,70] },
  jesus:     { top:[12,12,12], bot:[4,4,4],    accent:[205,180,120], wm:[125,112,72] },
  prophetie: { top:[22,10,38], bot:[13,5,24],  accent:[190,160,210], wm:[140,120,165] },
  default:   { top:[10,14,30], bot:[6,10,22],  accent:[201,166,64],  wm:[130,120,80] },
};
function _norm(s){ return String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim(); }
const _WISDOM = ["proverbes","ecclesiaste","job"];
const _GOSPELS = ["matthieu","marc","luc","jean"];
const _PROPHETS = ["esaie","jeremie","lamentations","ezechiel","daniel","osee","joel","amos","abdias","jonas","michee","nahum","habacuc","sophonie","aggee","zacharie","malachie","apocalypse"];
function paletteForBook(bookName){
  const b = _norm(bookName);
  if(b.indexOf("psaume") === 0) return IMG_PALETTES.psaume;
  if(_WISDOM.includes(b)) return IMG_PALETTES.proverbe;
  if(_GOSPELS.includes(b)) return IMG_PALETTES.jesus;
  if(_PROPHETS.includes(b)) return IMG_PALETTES.prophetie;
  return IMG_PALETTES.default;
}

async function renderVerseImage(bookName, chapter, verse, text){
  const W = 1080, H = 1080;
  const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
  const ctx = cv.getContext("2d");
  try{
    await document.fonts.load('400 60px "EB Garamond"');
    await document.fonts.load('600 46px "EB Garamond"');
    await document.fonts.load('600 30px "DM Sans"');
    await document.fonts.ready;
  } catch {}
  // fond dégradé + halo doré + cadre
  const P = paletteForBook(bookName);
  const rgb = (c,a) => (a==null ? `rgb(${c[0]},${c[1]},${c[2]})` : `rgba(${c[0]},${c[1]},${c[2]},${a})`);
  const g = ctx.createLinearGradient(0,0,0,H);
  g.addColorStop(0, rgb(P.top)); g.addColorStop(1, rgb(P.bot));
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);
  const rg = ctx.createRadialGradient(W/2,-140,40,W/2,-140,760);
  rg.addColorStop(0, rgb(P.accent,0.12)); rg.addColorStop(1, rgb(P.accent,0));
  ctx.fillStyle = rg; ctx.fillRect(0,0,W,H);
  ctx.strokeStyle = rgb(P.accent,0.22); ctx.lineWidth = 2;
  _roundRect(ctx,40,40,W-80,H-80,26); ctx.stroke();

  // texte — typographie FR : espace insécable avant ; : ! ? et guillemets liés
  let t = String(text).replace(/¶/g,"").replace(/\s+/g," ").trim();
  t = t.replace(/\s*([;:!?])/g, "\u00a0$1");
  const quoted = "«\u00a0" + t + "\u00a0»";

  const PAD = 110, maxW = W - 2*PAD;
  const topLimit = 160, bottomLimit = H - 150;
  ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  let size = 60, lines = [];
  for(; size >= 28; size -= 2){
    ctx.font = `400 ${size}px "EB Garamond", Georgia, serif`;
    lines = _wrapCanvas(ctx, quoted, maxW);
    if(lines.length * (size*1.34) + 130 <= (bottomLimit - topLimit)) break;
  }
  const lh = size*1.34;
  const blockH = lines.length*lh + 130;
  let y = topLimit + ((bottomLimit - topLimit) - blockH)/2 + size;
  ctx.fillStyle = "#f0ead8";
  ctx.font = `400 ${size}px "EB Garamond", Georgia, serif`;
  for(const ln of lines){ ctx.fillText(ln, W/2, y); y += lh; }
  y += 4;
  ctx.strokeStyle = rgb(P.accent,0.5); ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(W/2-60, y); ctx.lineTo(W/2+60, y); ctx.stroke();
  y += 56;
  ctx.fillStyle = rgb(P.accent);
  ctx.font = `600 46px "EB Garamond", Georgia, serif`;
  ctx.fillText(`${bookName} ${chapter}:${verse}`, W/2, y);

  // filigrane
  ctx.font = `600 30px "DM Sans", system-ui, sans-serif`;
  ctx.textAlign = "left";
  const wa = ctx.measureText("LaBible.app").width, wb = ctx.measureText("  ·  LSG 1910").width;
  const x0 = (W - (wa + wb))/2;
  ctx.fillStyle = rgb(P.accent); ctx.fillText("LaBible.app", x0, H-64);
  ctx.fillStyle = rgb(P.wm); ctx.fillText("  ·  LSG 1910", x0 + wa, H-64);

  return cv;
}

/* ---------- views ---------- */
function setView(view){
  $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.view === view));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  if(view === "library") renderLibrary();
  if(view === "versets"){ versetsShowHub(); renderVersetsHub(); }
  $("#verseActionBar")?.remove();
  $$(".verse.selected").forEach(p => p.classList.remove("selected"));
  state.selectedVerse = null;
}
function bindTabs(){
  $$(".tab[data-view]").forEach(tab => tab.addEventListener("click", () => setView(tab.dataset.view)));
  $("#btnBackThemes")?.addEventListener("click", (e) => { e.preventDefault(); versetsShowHub(); });
  $("#btnThemeReadAll")?.addEventListener("click", (e) => { e.preventDefault(); setView("read"); });
}

/* ---------- theme / font ---------- */
const ICON_SUN  = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2.8v2.4M12 18.8v2.4M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M2.8 12h2.4M18.8 12h2.4M4.9 19.1l1.7-1.7M17.4 6.6l1.7-1.7"/></svg>';
const ICON_MOON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
function applyTheme(theme){
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(LS.theme, theme);
  const btn = $("#btnTheme");
  if(btn){ btn.innerHTML = theme === "light" ? ICON_MOON : ICON_SUN; btn.setAttribute("aria-label", theme === "light" ? "Passer en mode sombre" : "Passer en mode clair"); }
}
function loadTheme(){ applyTheme(localStorage.getItem(LS.theme) === "light" ? "light" : "dark"); }
function applyFont(px){
  state.readFont = clamp(px, 14, 22);
  document.documentElement.style.setProperty("--readFont", `${state.readFont}px`);
  localStorage.setItem(LS.font, String(state.readFont));
}
function loadFont(){
  const v = parseInt(localStorage.getItem(LS.font) || "16", 10);
  applyFont(isFinite(v) ? v : 16);
}

/* ---------- charger la bible ---------- */
async function loadBible(){
  let res;
  try{
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    res = await fetch(DATA_URL, { signal: ctrl.signal });
    clearTimeout(timer);
    if(!res.ok) throw new Error("local failed");
  } catch(e){
    try{
      res = await fetch(DATA_URL_CDN);
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch(e2){
      throw new Error("Impossible de charger la Bible. Vérifiez votre connexion.");
    }
  }

  const raw = await res.json();
  const verses = Array.isArray(raw) ? raw : (raw.verses || raw.data || raw);
  if(!Array.isArray(verses) || !verses.length) throw new Error("Format lsg1910.json invalide.");

  const dataMap  = new Map();
  const bookMeta = new Map();

  for(const v of verses){
    const bookNr  = v.book ?? v.book_nr ?? v.bookNumber ?? v.b;
    const chapNr  = v.chapter ?? v.chap ?? v.c;
    const verseNr = v.verse ?? v.v;
    const text    = String(v.text ?? v.t ?? "")
      .replace(/\\u([0-9a-fA-F]{4})/g, (_,h) => String.fromCharCode(parseInt(h,16)))
      .trim();
    const bname   = v.book_name ?? v.bookName ?? v.name ?? `Livre ${bookNr}`;
    if(!bookNr || !chapNr || !verseNr) continue;
    if(!bookMeta.has(bookNr)) bookMeta.set(bookNr, bname);
    if(!dataMap.has(bookNr)) dataMap.set(bookNr, new Map());
    const bookMap = dataMap.get(bookNr);
    if(!bookMap.has(chapNr)) bookMap.set(chapNr, []);
    bookMap.get(chapNr)[verseNr - 1] = text;
  }

  const sortedNrs = [...bookMeta.keys()].sort((a,b) => a - b);
  const books = sortedNrs.map(nr => ({ nr, name: bookMeta.get(nr), abbr: [] }));
  state.bible = { books, data: dataMap };

  initSelectors();

  const hashRef = parseHashRef();
  if(hashRef){
    state.current.book = hashRef.bi;
    state.current.chapter = hashRef.c;
  } else {
    const last = localStorage.getItem(LS.last);
    if(last){
      const ref = parseReference(last);
      if(ref){ state.current.book = ref.bi; state.current.chapter = ref.c; }
    }
  }

  $("#bookSelect").value = String(state.current.book);
  refreshChapterSelect();
  renderReading(hashRef && hashRef.v ? hashRef.v : null);

  await computeVerseOfDay();
  await renderPlan();
  renderLibrary();
  buildIndex();
  loadExplications();
  loadCrossRefs();
  loadVersetsThemes();
}

/* ---------- sélecteurs ---------- */
function initSelectors(){
  const bookSelect    = $("#bookSelect");
  const chapterSelect = $("#chapterSelect");

  bookSelect.innerHTML = "";
  state.bible.books.forEach((b, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = b.name;
    bookSelect.appendChild(opt);
  });

  bookSelect.addEventListener("change", async () => {
    state.current.book = parseInt(bookSelect.value, 10);
    state.current.chapter = 1;
    refreshChapterSelect();
    renderReading();
  });
  chapterSelect.addEventListener("change", () => {
    state.current.chapter = parseInt(chapterSelect.value, 10);
    renderReading();
  });
  $("#verseSelect")?.addEventListener("change", (e) => {
    renderReading(parseInt(e.target.value, 10));
  });

  $("#btnPrev")?.addEventListener("click", () => navChapter(-1));
  $("#btnNext")?.addEventListener("click", () => navChapter(+1));
  $("#btnCopyRef")?.addEventListener("click", () => {
    if(state.selectedVerse){ const { bookName, chapter, verse, text } = state.selectedVerse; copyText(buildVerseShareText(bookName, chapter, verse, text)); }
    else { copyText(currentRefString()); }
  });
  $("#btnShare")?.addEventListener("click", () => {
    if(state.selectedVerse){ const { bookName, chapter, verse, text } = state.selectedVerse; shareVerse(bookName, chapter, verse, text); }
    else { shareCurrent(); }
  });
  $("#btnBookmark")?.addEventListener("click", toggleFavCurrent);
  $("#btnFontMinus")?.addEventListener("click", () => applyFont(state.readFont - 1));
  $("#btnFontPlus")?.addEventListener("click",  () => applyFont(state.readFont + 1));
  $("#btnVDD")?.addEventListener("click", async () => {
    await computeVerseOfDay(true);
    if(state.vddRef){ await openReference(state.vddRef); toast("Verset du jour ✅"); }
  });
}

function getBookData(bi){
  const book = state.bible.books[bi];
  if(!book) return null;
  return state.bible.data.get(book.nr) || null;
}

function refreshChapterSelect(){
  const chapterSelect = $("#chapterSelect");
  const bookMap = getBookData(state.current.book);
  const total   = bookMap ? bookMap.size : 1;
  chapterSelect.innerHTML = "";
  for(let c = 1; c <= total; c++){
    const opt = document.createElement("option");
    opt.value = String(c);
    opt.textContent = String(c);
    chapterSelect.appendChild(opt);
  }
  state.current.chapter = clamp(state.current.chapter, 1, total);
  chapterSelect.value = String(state.current.chapter);
}

function refreshVerseSelect(total, selected){
  const vs = $("#verseSelect");
  if(!vs) return;
  total = total || 1;
  vs.innerHTML = "";
  for(let v = 1; v <= total; v++){
    const opt = document.createElement("option");
    opt.value = String(v);
    opt.textContent = String(v);
    vs.appendChild(opt);
  }
  vs.value = String(clamp(selected || 1, 1, total));
}

async function navChapter(delta){
  const bi     = state.current.book;
  const bookMap = getBookData(bi);
  const total  = bookMap ? bookMap.size : 1;
  let c = state.current.chapter + delta;
  if(c < 1){
    if(bi > 0){ state.current.book -= 1; $("#bookSelect").value = String(state.current.book); const prevMap = getBookData(state.current.book); state.current.chapter = prevMap ? prevMap.size : 1; refreshChapterSelect(); renderReading(); }
    else toast("Début de la Bible.");
    return;
  }
  if(c > total){
    if(bi < state.bible.books.length - 1){ state.current.book += 1; $("#bookSelect").value = String(state.current.book); state.current.chapter = 1; refreshChapterSelect(); renderReading(); }
    else toast("Fin de la Bible.");
    return;
  }
  state.current.chapter = c;
  $("#chapterSelect").value = String(c);
  renderReading();
}

function currentRefString(){
  const book = state.bible.books[state.current.book];
  return `${book.name} ${state.current.chapter}`;
}

/* ---------- favoris / historique ---------- */
function getFavs(){ try{ return JSON.parse(localStorage.getItem(LS.fav)||"[]"); }catch{ return []; } }
function setFavs(a){ localStorage.setItem(LS.fav, JSON.stringify(a)); }
function getHistory(){ try{ return JSON.parse(localStorage.getItem(LS.hist)||"[]"); }catch{ return []; } }
function setHistory(a){ localStorage.setItem(LS.hist, JSON.stringify(a)); }

function pushHistory(ref){
  let arr = getHistory().filter(x => x?.ref !== ref);
  arr.unshift({ ref, at: nowIso() });
  setHistory(arr.slice(0, 30));
}

function updateFavButtonState(){
  const ref = currentRefString();
  const btn = $("#btnBookmark");
  if(btn) btn.textContent = getFavs().some(f => f.type==="ref" && f.ref===ref) ? "✅ Favori" : "🔖 Favori";
}

function toggleFavCurrent(){
  const ref  = currentRefString();
  const favs = getFavs();
  const idx  = favs.findIndex(f => f.type==="ref" && f.ref===ref);
  if(idx >= 0){ favs.splice(idx,1); toast("Favori supprimé."); }
  else { favs.unshift({ type:"ref", ref, at: nowIso() }); toast("Favori ajouté."); }
  setFavs(favs.slice(0, 120));
  updateFavButtonState();
  renderLibrary();
}

function toggleFavVerse(bookName, chapter, verse, text){
  const ref  = `${bookName} ${chapter}:${verse}`;
  const favs = getFavs();
  const idx  = favs.findIndex(f => f.type==="verse" && f.ref===ref);
  if(idx >= 0){ favs.splice(idx,1); toast("Verset retiré."); }
  else { favs.unshift({ type:"verse", ref, text: String(text||""), at: nowIso() }); toast("Verset ajouté ⭐"); }
  setFavs(favs.slice(0, 200));
  renderLibrary();
}

/* ---------- rendu lecture ---------- */
function renderReading(highlightVerse=null){
  try{
    $("#verseActionBar")?.remove();
    state.selectedVerse = null;

    const book    = state.bible.books[state.current.book];
    const bookMap = getBookData(state.current.book);
    const c       = state.current.chapter;
    const verses  = bookMap?.get(c) || [];

    $("#pageHeader").textContent = `${book.name} ${c}`;
    const box = $("#verses");
    box.innerHTML = "";

    verses.forEach((t, i) => {
      if(t === undefined || t === null) return;
      const p = document.createElement("p");
      p.className = "verse";

      const vnum = document.createElement("span");
      vnum.className = "vnum";
      vnum.textContent = String(i + 1);

      const span = document.createElement("span");
      span.textContent = " " + String(t).replace(/^¶\s*/g, "").trim();

      p.append(vnum, span);
      p.addEventListener("click", () => {
        if(p.classList.contains("selected")){ $("#verseActionBar")?.remove(); p.classList.remove("selected"); state.selectedVerse = null; }
        else { showVerseActions(book.name, c, i+1, t, p); }
      });

      if(highlightVerse && (i+1) === highlightVerse){
        p.style.outline = "2px solid rgba(226,197,122,.35)";
        p.style.borderRadius = "12px";
        p.style.padding = "6px 8px";
        setTimeout(() => p.scrollIntoView({ block:"center", behavior:"smooth" }), 80);
      }
      box.appendChild(p);
    });

    const refStr = `${book.name} ${c}`;
    localStorage.setItem(LS.last, refStr);
    pushHistory(refStr);
    updateFavButtonState();
    history.replaceState(null, "", `#${book.name}-${c}`);
    document.title = `${book.name} ${c} \u2014 LaBible.app`;
    refreshVerseSelect(verses.length, highlightVerse);
  } catch(err){
    $("#pageHeader").textContent = "Erreur";
    $("#verses").innerHTML = `<p class="verse"><span class="vnum">!</span><span>${escapeHtml(err.message)}</span></p>`;
  }
}

/* ---------- swipe ---------- */
function bindSwipe(){
  const page = $("#readerPage");
  if(!page) return;
  let sx=0, sy=0, active=false;
  page.addEventListener("touchstart", e => { const t = e.touches?.[0]; if(!t) return; sx=t.clientX; sy=t.clientY; active=true; }, {passive:true});
  page.addEventListener("touchend", e => {
    if(!active) return; active=false;
    const t = e.changedTouches?.[0]; if(!t) return;
    const dx = t.clientX - sx; const dy = t.clientY - sy;
    if(Math.abs(dx) < 55 || Math.abs(dx) < Math.abs(dy)*1.2) return;
    navChapter(dx < 0 ? +1 : -1);
  }, {passive:true});
}

/* ---------- recherche ---------- */
function findBookIndex(bookPart){
  const key = normalize(bookPart);
  const books = state.bible.books;
  for(let i=0;i<books.length;i++) if(normalize(books[i].name) === key) return i;
  for(let i=0;i<books.length;i++){ const n = normalize(books[i].name); if(n.startsWith(key) || n.includes(key)) return i; }
  return -1;
}

function parseReference(input){
  const s = normalize(input);
  const m = s.match(/(\d+)\s*(?::\s*(\d+))?\s*$/);
  if(!m) return null;
  const chap = parseInt(m[1],10);
  const verse = m[2] ? parseInt(m[2],10) : null;
  const bookPart = s.slice(0, m.index).trim();
  if(!bookPart) return null;
  const bi = findBookIndex(bookPart);
  if(bi < 0) return null;
  return { bi, c: chap, v: verse };
}

// Lit un lien profond "#Livre-Chapitre" ou "#Livre-Chapitre:Verset"
function parseHashRef(){
  try{
    const s = decodeURIComponent((location.hash || "").replace(/^#/, "")).trim();
    if(!s) return null;
    const m = s.match(/^(.+)-(\d+)(?::(\d+))?$/);
    if(!m) return null;
    const bi = findBookIndex(m[1].trim());
    if(bi < 0) return null;
    const ref = { bi, c: parseInt(m[2], 10) };
    if(m[3]) ref.v = parseInt(m[3], 10);
    return ref;
  } catch { return null; }
}

function highlightText(text, query, exact){
  if(exact){
    // Recherche exacte : ne surligne que le mot/l'expression entière, pas les mots qui la contiennent
    // (ex: "destin" ne surligne pas "destinés"). Les bornes tolèrent les lettres accentuées.
    const w = String(query || "").trim();
    if(!w) return escapeHtml(text);
    const esc = escapeRegExp(w);
    const re = new RegExp(`(?<![\\p{L}\\p{N}])(${esc})(?![\\p{L}\\p{N}])`, "giu");
    return escapeHtml(text).replace(re, m => `<span class="hl">${m}</span>`);
  }
  const q = normalize(query);
  if(q.length < 2) return escapeHtml(text);
  let out = escapeHtml(text);
  q.split(" ").filter(w=>w.length>=2).slice(0,6).forEach(w => {
    const re = new RegExp(escapeRegExp(w), "ig");
    out = out.replace(re, m => `<span class="hl">${escapeHtml(m)}</span>`);
  });
  return out;
}

async function openReference(ref){
  state.current.book = ref.bi;
  const bookMap = getBookData(ref.bi);
  const total   = bookMap ? bookMap.size : 1;
  state.current.chapter = clamp(ref.c, 1, total);
  $("#bookSelect").value = String(ref.bi);
  refreshChapterSelect();
  $("#chapterSelect").value = String(state.current.chapter);
  setView("read");
  const verses = bookMap?.get(state.current.chapter) || [];
  renderReading(ref.v ? clamp(ref.v, 1, verses.length || 1) : null);
}

async function buildIndex(force=false){
  if(state.index && !force) return;
  if(state.indexing) return;
  state.indexing = true;
  const items = [];
  for(let bi=0; bi<state.bible.books.length; bi++){
    const book = state.bible.books[bi];
    const bookMap = state.bible.data.get(book.nr);
    if(!bookMap) continue;
    for(const [chapNr, verses] of bookMap){
      verses.forEach((t, vi) => {
        if(!t) return;
        const clean = String(t).replace(/¶/g, "").replace(/\s+/g, " ").trim();
        items.push({ bi, c: chapNr, v: vi+1, norm: normalize(clean), original: clean });
      });
    }
  }
  state.index = items;
  state.indexing = false;
}

window.appSearch = function(qRaw){
  if(!state.bible) return null;
  if(!state.index) return null;

  // Recherche exacte : "mot" ou «mot» → le mot (ou l'expression) entier uniquement,
  // pas les mots qui le contiennent (ex: "destin" ne renvoie pas "destinés", "prédestinés").
  const trimmed = String(qRaw || "").trim();
  let exactWord = null;
  let m;
  if((m = trimmed.match(/^["“](.*)["”]$/)) || (m = trimmed.match(/^«\s*(.*?)\s*»$/))){
    exactWord = m[1].trim();
  }
  const isExact = exactWord !== null;

  const q = normalize(isExact ? exactWord : trimmed);
  if(!q) return [];

  if(!isExact){
    const ref = parseReference(qRaw);
    if(ref){
      const book = state.bible.books[ref.bi];
      const bookMap = getBookData(ref.bi);
      const verses  = bookMap?.get(ref.c) || [];
      const text    = ref.v ? String(verses[ref.v - 1] || "") : "";
      return [{ ref: `${book.name} ${ref.c}${ref.v ? ":"+ref.v : ""}`, text, _parsed: ref }];
    }
  }

  let matchFn;
  if(isExact){
    const esc = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`(^|[^a-z0-9])${esc}($|[^a-z0-9])`, "i");
    matchFn = norm => re.test(norm);
  } else {
    matchFn = norm => norm.includes(q);
  }

  // Sem teto: devolve TODAS as ocorrências, em ordem bíblica (Genèse -> Apocalypse).
  // A paginação (50 + "Afficher plus") é tratada na UI (index.html).
  const results = [];
  for(const item of state.index){
    if(matchFn(item.norm)){
      const bName = state.bible.books[item.bi].name;
      results.push({ ref: `${bName} ${item.c}:${item.v}`, text: item.original, textHtml: highlightText(item.original, isExact ? exactWord : qRaw, isExact), _parsed: { bi: item.bi, c: item.c, v: item.v } });
    }
  }
  return results;
};

window.appGoTo = async function(refStr){
  const ref = parseReference(refStr);
  if(ref) await openReference(ref);
};

/* ---------- clipboard / share ---------- */
async function copyText(t){
  try{ await navigator.clipboard.writeText(t); toast("Copié ✅"); }
  catch{ toast("Impossible de copier."); }
}

async function shareCurrent(){
  const book = state.bible.books[state.current.book];
  const c    = state.current.chapter;
  const bookMap = getBookData(state.current.book);
  const verses  = bookMap?.get(c) || [];
  const first   = verses[0] ? String(verses[0]).replace(/^¶\s*/, "").slice(0, 100) : "";
  const url     = `https://labible.app/#${book.name}-${c}`;
  const shareText = first ? `${book.name} ${c} :\n"${first}…"` : `${book.name} ${c}`;
  if(navigator.share){ try{ await navigator.share({ title:`${book.name} ${c} \u2014 LaBible.app`, text: shareText, url }); } catch{} }
  else { await copyText(`${shareText}\n\n📖 ${url}`); }
}

/* ---------- verset du jour ---------- */

// Versículos curados — impactantes e compreensíveis sem contexto
const VDD_CURATED = [
  ["Jean", 3, 16], ["Philippiens", 4, 13], ["Jérémie", 29, 11],
  ["Psaumes", 23, 1], ["Romains", 8, 28], ["Matthieu", 11, 28],
  ["Proverbes", 3, 5], ["Ésaïe", 40, 31], ["Josué", 1, 9],
  ["Psaumes", 46, 2], ["Jean", 14, 6], ["Romains", 8, 38],
  ["Galates", 2, 20], ["Ésaïe", 41, 10], ["Psaumes", 118, 24],
  ["Matthieu", 6, 33], ["Luc", 1, 37], ["Jean", 10, 10],
  ["Romains", 5, 8], ["Éphésiens", 2, 8], ["1 Jean", 4, 8],
  ["Psaumes", 27, 1], ["Proverbes", 18, 10], ["Jean", 8, 32],
  ["Matthieu", 5, 16], ["Colossiens", 3, 23], ["Psaumes", 34, 9],
  ["Romains", 12, 2], ["2 Corinthiens", 5, 17], ["Ésaïe", 43, 2],
  ["Jean", 16, 33], ["Hébreux", 11, 1], ["Psaumes", 37, 4],
  ["Proverbes", 16, 3], ["Matthieu", 28, 20], ["Apocalypse", 21, 4],
  ["Psaumes", 139, 14], ["Romains", 15, 13], ["1 Corinthiens", 13, 4],
  ["Ésaïe", 55, 8], ["Jean", 15, 5], ["Psaumes", 91, 1],
  ["Proverbes", 31, 25], ["Michée", 6, 8], ["Lamentations", 3, 22],
  ["Zacharie", 4, 6], ["Psaumes", 19, 2], ["Jean", 11, 25],
  ["Romains", 8, 1], ["Matthieu", 7, 7], ["Psaumes", 16, 11],
  ["Proverbes", 4, 23], ["Ésaïe", 26, 3], ["Jean", 14, 27],
  ["Hébreux", 4, 16], ["Psaumes", 145, 18], ["Galates", 5, 22],
  ["Romains", 1, 16], ["1 Pierre", 5, 7], ["Psaumes", 32, 8],
  ["Colossiens", 4, 6], ["Ésaïe", 53, 5], ["Jean", 6, 35],
];

function seededRand(seed){
  let x = seed >>> 0;
  x ^= x << 13; x >>>= 0; x ^= x >> 17; x >>>= 0; x ^= x << 5; x >>>= 0;
  return x >>> 0;
}

async function computeVerseOfDay(force=false){
  const k = dateKey();
  if(!force){
    try{
      const cached = JSON.parse(localStorage.getItem(LS.vdd)||"null");
      if(cached?.key===k && cached?.ref){
        state.vddRef = cached.ref;
        const el = $("#vddBox");
        if(el) el.textContent = cached.text || "—";
        return;
      }
    } catch{}
  }

  const seed  = seededRand(Number(k.replace(/-/g,""))||1);
  const entry = VDD_CURATED[seed % VDD_CURATED.length];
  const [bookName, chapNr, verseNr] = entry;

  const bi = findBookIndex(bookName);
  if(bi < 0) return;

  const bookMap = getBookData(bi);
  if(!bookMap) return;

  const verses = bookMap.get(chapNr) || [];
  const text   = String(verses[verseNr - 1] || "").replace(/^¶\s*/g, "").trim();
  if(!text) return;

  const books  = state.bible.books;
  state.vddRef = { bi, c: chapNr, v: verseNr };
  const line   = `${books[bi].name} ${chapNr}:${verseNr} — ${text}`;
  const el     = $("#vddBox");
  if(el) el.textContent = line;
  localStorage.setItem(LS.vdd, JSON.stringify({ key:k, ref:state.vddRef, text:line, at:nowIso() }));
}

/* ---------- plan 365 ---------- */
async function ensurePlan(){
  let st = null;
  try{ st = JSON.parse(localStorage.getItem(LS.plan)||"null"); } catch{}
  if(st && Array.isArray(st.plan) && typeof st.doneDay==="number") return st;

  const books = state.bible.books;
  const OT = books.slice(0, 39);
  const NT = books.slice(39);
  const toChaps = (arr) => arr.flatMap(bm => {
    const bMap = state.bible.data.get(bm.nr);
    const bi = books.findIndex(x=>x.nr===bm.nr);
    return bMap ? [...bMap.keys()].map(c => ({ bi, c, label:`${bm.name} ${c}` })) : [];
  });
  const otChaps = toChaps(OT); const ntChaps = toChaps(NT);
  const plan = []; let oi=0, ni=0;
  for(let d=1; d<=365; d++){
    const refs = [];
    if(ni < ntChaps.length) refs.push(ntChaps[ni++]);
    const rem = 365-d+1;
    const otDay = ((otChaps.length-oi)/rem > 2.2) ? 3 : 2;
    for(let k=0; k<otDay && oi<otChaps.length; k++) refs.push(otChaps[oi++]);
    plan.push({ day:d, refs });
  }
  st = { createdAt: Date.now(), doneDay:0, plan };
  localStorage.setItem(LS.plan, JSON.stringify(st));
  return st;
}

function planDayFrom(createdAt){ return clamp(Math.floor((Date.now()-createdAt)/86400000)+1,1,365); }

async function renderPlan(){
  const st = await ensurePlan();
  const day = planDayFrom(st.createdAt);
  const entry = st.plan[day-1];
  const pt = $("#planTodayText");
  pt.innerHTML = "";
  pt.appendChild(document.createTextNode(`Jour ${day} \u2014 `));
  entry.refs.forEach((r, i) => {
    const a = document.createElement("a");
    a.href = "#";
    a.textContent = r.label;
    a.style.cssText = "color:inherit;text-decoration:underline;text-underline-offset:3px;cursor:pointer;font-weight:600";
    a.addEventListener("click", async (e) => { e.preventDefault(); await openReference({ bi:r.bi, c:r.c, v:null }); });
    pt.appendChild(a);
    if(i < entry.refs.length - 1) pt.appendChild(document.createTextNode(" \u00b7 "));
  });
  $("#planTodayMeta").textContent = st.doneDay >= day ? "✅ Déjà marqué." : `Progression : jour ${st.doneDay} terminé.`;
  const pct = Math.round((st.doneDay/365)*100);
  $("#progressFill").style.width = `${pct}%`;
  $("#progressText").textContent = `${pct}%`;
  $("#btnOpenToday").onclick = async () => { const r0 = entry.refs[0]; if(!r0) return; await openReference({ bi:r0.bi, c:r0.c, v:null }); };
  $("#btnMarkDone").onclick = async () => {
    const st2 = await ensurePlan(); const today = planDayFrom(st2.createdAt);
    if(st2.doneDay >= today){ toast("Déjà fait."); return; }
    st2.doneDay = today; localStorage.setItem(LS.plan, JSON.stringify(st2)); await renderPlan(); toast("Lecture marquée ✅");
  };
  $("#btnResetPlan").onclick = async () => { localStorage.removeItem(LS.plan); await renderPlan(); toast("Plan réinitialisé."); };
  $("#btnJumpDay").onclick = async () => {
    const input = prompt("Aller à quel jour ? (1–365)"); if(!input) return;
    const d = clamp(parseInt(input,10)||1,1,365); const st2 = await ensurePlan();
    toast(`Jour ${d} : ${st2.plan[d-1].refs.map(r=>r.label).join(" · ")}`);
  };
}

/* ---------- bibliothèque ---------- */
function renderLibrary(){
  const favs = getFavs(); const hist = getHistory();
  const renderItems = (containerId, items, limit=30) => {
    const box = $(containerId);
    box.innerHTML = items.length ? "" : `<div class="muted small">Aucun élément.</div>`;
    items.slice(0, limit).forEach(f => {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `<div class="itemTop"><div><div class="itemRef">${escapeHtml(f.ref||"")}</div><div class="itemMeta">${escapeHtml(new Date(f.at||Date.now()).toLocaleString("fr-FR"))}</div></div></div>${f.text?`<div class="itemMeta" style="margin-top:8px">${escapeHtml(f.text).slice(0,200)}${f.text.length>200?"…":""}</div>`:""}<div class="itemBtns"><button class="chip" data-open="${escapeHtml(f.ref)}">📖 Ouvrir</button><button class="chip" data-copy="${escapeHtml(f.ref)}">📎 Copier</button><button class="chip" data-share="${escapeHtml(f.ref)}">🔗 Partager</button></div>`;
      box.appendChild(div);
    });
    box.querySelectorAll("[data-open]").forEach(btn => btn.addEventListener("click", async () => { const r = parseReference(btn.getAttribute("data-open")); if(r) await openReference(r); else toast("Référence non reconnue."); }));
    box.querySelectorAll("[data-copy]").forEach(btn => btn.addEventListener("click", () => {
      const refStr = btn.getAttribute("data-copy"); const parsed = parseReference(refStr);
      const bookMap = parsed ? getBookData(parsed.bi) : null; const verses = bookMap?.get(parsed?.c) || [];
      const text = parsed?.v ? String(verses[parsed.v-1]||"") : ""; const bName = parsed ? state.bible.books[parsed.bi].name : "";
      if(parsed?.v && text){ copyText(buildVerseShareText(bName, parsed.c, parsed.v, text)); }
      else { copyText(parsed ? `https://labible.app/#${bName}-${parsed.c}` : refStr); }
    }));
    box.querySelectorAll("[data-share]").forEach(btn => btn.addEventListener("click", async () => {
      const refStr = btn.getAttribute("data-share"); const parsed = parseReference(refStr);
      const bookMap = parsed ? getBookData(parsed.bi) : null; const verses = bookMap?.get(parsed?.c) || [];
      const text = parsed?.v ? String(verses[parsed.v-1]||"") : ""; const bName = parsed ? state.bible.books[parsed.bi].name : "";
      await shareVerse(bName, parsed?.c, parsed?.v, text);
    }));
  };
  renderItems("#favList", favs);
  renderItems("#historyList", hist);
}

function bindLibraryButtons(){
  $("#btnClearFav")?.addEventListener("click", () => { if(confirm("Supprimer tous les favoris ?")){ localStorage.removeItem(LS.fav); renderLibrary(); toast("Favoris supprimés."); } });
  $("#btnClearHistory")?.addEventListener("click", () => { if(confirm("Supprimer l'historique ?")){ localStorage.removeItem(LS.hist); renderLibrary(); toast("Historique supprimé."); } });
  $("#btnOpenVDD")?.addEventListener("click", async () => { if(!state.vddRef) await computeVerseOfDay(true); if(state.vddRef) await openReference(state.vddRef); });
  $("#btnCopyVDD")?.addEventListener("click", () => copyText($("#vddBox")?.textContent||""));
}

/* ---------- PWA ---------- */
function bindInstall(){
  const btn = $("#btnInstall");
  if(!btn) return;
  function checkInstalled(){ return window.matchMedia("(display-mode: standalone)").matches || window.matchMedia("(display-mode: minimal-ui)").matches || window.navigator.standalone === true || document.referrer.includes("android-app://") || localStorage.getItem("pwa:installed") === "1"; }
  if(checkInstalled()){ btn.hidden = true; return; }
  btn.hidden = false; // toujours visible si l'app n'est pas installée
  // On laisse le navigateur proposer l'installation automatiquement (bannière native).
  // Le bouton mène aux instructions (utile sur iPhone et si la bannière a été fermée).
  btn.addEventListener("click", () => { window.location.href = "/installer.html"; });
  window.addEventListener("appinstalled", () => { state.deferredPrompt = null; localStorage.setItem("pwa:installed","1"); btn.hidden = true; toast("Installée ✅"); });
  window.addEventListener("focus", () => { if(checkInstalled()) btn.hidden = true; });
}

function bindHeaderActions(){
  $("#btnHome")?.addEventListener("click", () => { setView("read"); window.scrollTo({top:0, behavior:"smooth"}); });
  $("#btnTheme")?.addEventListener("click", () => { const cur = document.documentElement.getAttribute("data-theme")||"dark"; applyTheme(cur==="dark" ? "light" : "dark"); });
}

/* ---------- init ---------- */
async function init(){
  const y = $("#year"); if(y) y.textContent = String(new Date().getFullYear());
  loadTheme(); loadFont(); bindTabs(); bindHeaderActions(); bindSwipe(); bindLibraryButtons(); bindInstall();
  try{ await loadBible(); toast("Bible chargée ✅"); }
  catch(err){ console.error(err); $("#pageHeader").textContent = "Erreur"; $("#verses").innerHTML = `<p class="verse"><span class="vnum">!</span><span>${escapeHtml(err.message||String(err))}</span></p>`; toast(String(err.message||err)); }
}

init();
