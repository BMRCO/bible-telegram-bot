// labible-horloge : Worker Cloudflare qui lance les publications du bot a l'heure.
//
// Pourquoi : le planificateur de GitHub Actions arrive 4 a 8 h en retard
// (9 novembre 2026 : le verset de 03h37 sortait vers 10h40). Les Cron Triggers
// de Cloudflare partent a la minute. Le Worker ne publie rien lui-meme : il
// demande a GitHub de lancer le workflow (workflow_dispatch), et le bot
// fait le reste comme avant.
//
// Un seul Cron Trigger (*/15 * * * *, le plan gratuit en permet 5 par compte) :
// a chaque quart d'heure, le Worker regarde dans PLAN s'il y a quelque chose
// a lancer. Les heures sont en UTC (France en hiver = UTC+1, en ete = UTC+2).
//
// Secret requis : GH_TOKEN (jeton GitHub « fine-grained », depot
// BMRCO/bible-telegram-bot seulement, permission Actions en lecture/ecriture).
// Il se pose dans le tableau de bord Cloudflare, jamais dans ce fichier.

const DEPOT = "BMRCO/bible-telegram-bot";

// "HH:MM" UTC (multiple de 15 minutes) -> [workflow, inputs]
const PLAN = {
  "05:30": [["meditation.yml", {}]],                   // Psaume narre
  "06:30": [["publish.yml", { mode: "auto", creneau: "matin" }]],    // verset du matin
  "08:15": [["bible_audio.yml", {}]],                  // Bible audio 1/3
  "11:00": [["quiz_du_jour.yml", {}]],                 // quiz
  "14:15": [["bible_audio.yml", {}]],                  // Bible audio 2/3
  "17:00": [["thematic_meditation.yml", {}]],          // meditation thematique
  "19:00": [["publish.yml", { mode: "auto", creneau: "soir" }]],     // verset du soir
  "20:15": [["bible_audio.yml", {}]],                  // Bible audio 3/3
};

function creneau(ms) {
  const d = new Date(ms);
  const m = Math.floor(d.getUTCMinutes() / 15) * 15;
  return String(d.getUTCHours()).padStart(2, "0") + ":" + String(m).padStart(2, "0");
}

async function lancer(env, workflow, inputs) {
  const url = `https://api.github.com/repos/${DEPOT}/actions/workflows/${workflow}/dispatches`;
  for (let essai = 1; essai <= 3; essai++) {
    const r = await fetch(url, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GH_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "labible-horloge",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    });
    if (r.status === 204) {
      console.log(`lance : ${workflow} ${JSON.stringify(inputs)}`);
      return;
    }
    const txt = (await r.text()).slice(0, 300);
    console.error(`echec ${essai}/3 ${workflow} : HTTP ${r.status} ${txt}`);
    if (r.status < 500 && r.status !== 429) break;   // erreur de jeton ou de workflow : inutile d'insister
    await new Promise((ok) => setTimeout(ok, 5000 * essai));
  }
  throw new Error(`${workflow} non lance`);
}

export default {
  async scheduled(event, env, ctx) {
    const cle = creneau(event.scheduledTime);
    const taches = PLAN[cle] || [];
    if (!taches.length) return;
    if (!env.GH_TOKEN) throw new Error("secret GH_TOKEN absent");
    const res = await Promise.allSettled(taches.map(([w, i]) => lancer(env, w, i)));
    const ko = res.filter((x) => x.status === "rejected");
    if (ko.length) throw new Error(`${cle} : ${ko.length} lancement(s) en echec`);
  },
  // Aucune page publique : personne ne peut declencher une publication par l'URL.
  async fetch() {
    return new Response("Not found", { status: 404 });
  },
};
