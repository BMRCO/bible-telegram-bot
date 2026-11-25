// labible-horloge v2 : Worker Cloudflare qui lance les publications du bot a l'heure.
//
// Pourquoi : le planificateur de GitHub Actions arrive 4 a 8 h en retard
// (9 novembre 2026). Les Cron Triggers de Cloudflare partent a la minute.
// Le Worker ne publie rien lui-meme : il demande a GitHub de lancer le
// workflow (workflow_dispatch), et le bot fait le reste.
//
// v2 (21 novembre 2026, regle de BC : tout passe par l'horloge de Cloudflare) :
// le plan est lu dans le depot, horloge/plan.json, a chaque passage. Changer
// une heure ou ajouter une publication = modifier plan.json, sans redeployer.
// Si le fichier est illisible, le Worker prend la copie PLAN_SECOURS ci-dessous.
//
// Un seul Cron Trigger (*/15 * * * *). Heures en UTC.
// Secret requis : GH_TOKEN (jeton GitHub fine-grained, depot
// BMRCO/bible-telegram-bot seulement, Actions en lecture/ecriture).
// Il se pose dans le tableau de bord Cloudflare, jamais dans ce fichier.
// Fichier volontairement sans accents : il peut etre colle depuis un telephone.

const DEPOT = "BMRCO/bible-telegram-bot";
const PLAN_URL = "https://raw.githubusercontent.com/" + DEPOT + "/main/horloge/plan.json";

// Copie de secours de horloge/plan.json (21 nov. 2026).
const PLAN_SECOURS = {
  "04:45": [{ workflow: "horloge_v2.yml" }],
  "05:30": [{ workflow: "meditation.yml" }],
  "05:45": [{ workflow: "holy_week.yml", condition: "semaine_sainte" }],
  "06:30": [{ workflow: "publish.yml", inputs: { mode: "auto", creneau: "matin" } }],
  "08:15": [{ workflow: "bible_audio.yml", inputs: { testament: "at" } }],
  "10:15": [{ workflow: "bible_audio.yml", inputs: { testament: "nt" } }],
  "11:00": [{ workflow: "quiz_du_jour.yml" }],
  "11:45": [{ workflow: "horloge_v2.yml" }],
  "12:00": [{ workflow: "derniers_temps.yml", si_actif: true }],
  "12:15": [{ workflow: "tutoriels.yml", si_actif: true }],
  "14:15": [{ workflow: "bible_audio.yml", inputs: { testament: "at" } }],
  "16:15": [{ workflow: "bible_audio.yml", inputs: { testament: "nt" } }],
  "16:45": [{ workflow: "horloge_v2.yml" }],
  "17:00": [{ workflow: "thematic_meditation.yml" }],
  "18:45": [{ workflow: "horloge_v2.yml" }],
  "19:00": [{ workflow: "publish.yml", inputs: { mode: "auto", creneau: "soir" } }],
  "19:30": [{ workflow: "compilation_audio.yml", jours: [0, 3] }],
  "20:15": [{ workflow: "bible_audio.yml", inputs: { testament: "at" } }],
};

function creneau(ms) {
  const d = new Date(ms);
  const m = Math.floor(d.getUTCMinutes() / 15) * 15;
  return String(d.getUTCHours()).padStart(2, "0") + ":" + String(m).padStart(2, "0");
}

// Paques (calendrier gregorien, algorithme de Meeus/Butcher), en UTC.
function paques(annee) {
  const a = annee % 19, b = Math.floor(annee / 100), c = annee % 100;
  const d = Math.floor(b / 4), e = b % 4;
  const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const n = h + l - 7 * m + 114;
  return Date.UTC(annee, Math.floor(n / 31) - 1, (n % 31) + 1);
}

function semaineSainte(ms) {
  const d = new Date(ms);
  const jour = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  const ecart = (paques(d.getUTCFullYear()) - jour) / 86400000;
  return ecart >= 0 && ecart <= 7;      // du dimanche des Rameaux au dimanche de Paques
}

async function lirePlan() {
  try {
    const r = await fetch(PLAN_URL + "?t=" + Date.now(), {
      headers: { "User-Agent": "labible-horloge" },
      cf: { cacheTtl: 0 },
    });
    if (r.ok) {
      const p = await r.json();
      if (p && typeof p === "object") return p;
    }
    console.error("plan.json illisible (HTTP " + r.status + ") : copie de secours");
  } catch (e) {
    console.error("plan.json injoignable : copie de secours (" + e + ")");
  }
  return PLAN_SECOURS;
}

function entetes(env) {
  return {
    "Authorization": "Bearer " + env.GH_TOKEN,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "labible-horloge",
    "Content-Type": "application/json",
  };
}

async function estActif(env, workflow) {
  const r = await fetch("https://api.github.com/repos/" + DEPOT + "/actions/workflows/" + workflow,
                        { headers: entetes(env) });
  if (!r.ok) return true;               // dans le doute, on tente le lancement
  const w = await r.json();
  return w.state === "active";
}

async function lancer(env, workflow, inputs) {
  const url = "https://api.github.com/repos/" + DEPOT + "/actions/workflows/" + workflow + "/dispatches";
  for (let essai = 1; essai <= 3; essai++) {
    const r = await fetch(url, {
      method: "POST",
      headers: entetes(env),
      body: JSON.stringify({ ref: "main", inputs: inputs || {} }),
    });
    if (r.status === 204) {
      console.log("lance : " + workflow + " " + JSON.stringify(inputs || {}));
      return;
    }
    const txt = (await r.text()).slice(0, 300);
    console.error("echec " + essai + "/3 " + workflow + " : HTTP " + r.status + " " + txt);
    if (r.status < 500 && r.status !== 429) break;   // jeton ou workflow : inutile d'insister
    await new Promise((ok) => setTimeout(ok, 5000 * essai));
  }
  throw new Error(workflow + " non lance");
}

async function tache(env, t, ms) {
  if (Array.isArray(t)) t = { workflow: t[0], inputs: t[1] };       // ancien format
  if (t.jours && !t.jours.includes(new Date(ms).getUTCDay())) return;
  if (t.condition === "semaine_sainte" && !semaineSainte(ms)) return;
  if (t.si_actif && !(await estActif(env, t.workflow))) {
    console.log("saute : " + t.workflow + " desactive");
    return;
  }
  await lancer(env, t.workflow, t.inputs);
}

export default {
  async scheduled(event, env, ctx) {
    const cle = creneau(event.scheduledTime);
    if (!env.GH_TOKEN) throw new Error("secret GH_TOKEN absent");
    const plan = await lirePlan();
    const taches = Array.isArray(plan[cle]) ? plan[cle] : [];
    if (!taches.length) return;
    const res = await Promise.allSettled(taches.map((t) => tache(env, t, event.scheduledTime)));
    const ko = res.filter((x) => x.status === "rejected");
    if (ko.length) throw new Error(cle + " : " + ko.length + " lancement(s) en echec");
  },
  // Aucune page publique : personne ne peut declencher une publication par l'URL.
  async fetch() {
    return new Response("Not found", { status: 404 });
  },
};
