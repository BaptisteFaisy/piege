/* Piège — portail de démonstration : aucun framework, aucune dépendance.
 * Tout passe par l'API (`/api/…`) avec le jeton de tenant sélectionné : le
 * tenant n'est jamais un paramètre de requête (EF-61).
 */
"use strict";

const API = "/api";
const etat = { campagne: null, findings: [], refus: [] };

const $ = (selecteur) => document.querySelector(selecteur);
const jeton = () => $("#tenant").value;

async function api(methode, chemin, corps) {
  const options = { method: methode, headers: { Authorization: `Bearer ${jeton()}` } };
  if (corps !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(corps);
  }
  const reponse = await fetch(`${API}${chemin}`, options);
  let donnees = {};
  try { donnees = await reponse.json(); } catch (e) { /* corps vide */ }
  return { statut: reponse.status, ...donnees };
}

function formulaire(form) {
  const donnees = {};
  new FormData(form).forEach((valeur, cle) => { donnees[cle] = valeur; });
  form.querySelectorAll('input[type="checkbox"]').forEach((case_) => {
    donnees[case_.name] = case_.checked;
  });
  return donnees;
}

function journal(ligne) {
  const zone = $("#journal-campagne");
  zone.textContent += `${ligne}\n`;
  zone.scrollTop = zone.scrollHeight;
}

function basculer(message) {
  $("#journal-campagne").textContent = `${message}\n`;
}

/* ---------------------------------------------------------------- onglets */
document.querySelectorAll("nav button").forEach((bouton) => {
  bouton.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("actif"));
    document.querySelectorAll(".onglet").forEach((o) => o.classList.remove("actif"));
    bouton.classList.add("actif");
    $(`#onglet-${bouton.dataset.onglet}`).classList.add("actif");
    if (bouton.dataset.onglet === "decouvertes") chargerFindings();
    if (bouton.dataset.onglet === "faux-refus") chargerRefus();
  });
});

/* ------------------------------------------------------- 1. campagne */
$("#form-application").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("POST", "/applications", formulaire(e.target));
  basculer(`Application déclarée : ${JSON.stringify(r.donnees || r.erreur)}`);
});

$("#form-mandat").addEventListener("submit", async (e) => {
  e.preventDefault();
  const brut = formulaire(e.target);
  const corps = {
    application_id: brut.application_id,
    perimetre_techniques: brut.perimetre.split(",").map((s) => s.trim()).filter(Boolean),
    environnements: ["test"],
    fenetre_debut: brut.fenetre_debut, fenetre_fin: brut.fenetre_fin,
    budget_appels: Number(brut.budget_appels), budget_jetons: Number(brut.budget_jetons),
    production_autorisee: brut.production_autorisee === true,
    contact_urgence: brut.contact_urgence,
  };
  const r = await api("POST", "/mandats", corps);
  if (r.donnees) {
    const id = r.donnees.mandat.id;
    const option = document.createElement("option");
    option.value = id; option.textContent = `${id} (${r.donnees.statut})`;
    $("#select-mandat").appendChild(option);
    $("#select-mandat").value = id;
    basculer(`Mandat signé : ${id} — périmètre ${corps.perimetre_techniques.join(", ")}`);
  } else {
    basculer(`Mandat refusé : ${JSON.stringify(r.erreur)}`);
  }
});

$("#form-campagne").addEventListener("submit", async (e) => {
  e.preventDefault();
  const brut = formulaire(e.target);
  basculer("Campagne en cours…");
  const r = await api("POST", "/campagnes", {
    mandat_id: brut.mandat_id, graine: Number(brut.graine),
    parallelisme: Number(brut.parallelisme),
  });
  if (!r.donnees) { basculer(`Refus : ${JSON.stringify(r.erreur)}`); return; }
  etat.campagne = r.donnees.campagne.id;
  journal(`Campagne ${etat.campagne} — ${r.donnees.campagne.statut}`);
  journal(`Techniques exécutées : ${r.donnees.executions} · découvertes : ${r.donnees.findings}`);
  journal(`Budget restant : ${JSON.stringify(r.donnees.budget)}`);
  await majProgression();
  await chargerFindings();
});

async function majProgression() {
  if (!etat.campagne) return;
  const r = await api("GET", `/campagnes/${etat.campagne}`);
  if (!r.donnees) return;
  const p = r.donnees.progression;
  const pourcent = p.prevues ? Math.round((p.executions / p.prevues) * 100) : 0;
  $("#progression").innerHTML =
    `<div class="barre"><span style="width:${pourcent}%"></span></div>
     <p>${p.executions}/${p.prevues} techniques · ${p.reussies} réussies ·
     ${p.refusees} refusées par Policy · ${p.en_revue} en revue humaine</p>`;
}

$("#btn-suspendre").addEventListener("click", async () => {
  if (!etat.campagne) return;
  const r = await api("POST", `/campagnes/${etat.campagne}/suspendre`, { motif: "portail" });
  journal(`Arrêt d'urgence : ${JSON.stringify(r.donnees || r.erreur)}`);
});

$("#btn-reprendre").addEventListener("click", async () => {
  if (!etat.campagne) return;
  const r = await api("POST", `/campagnes/${etat.campagne}/reprendre`, {});
  journal(`Reprise : ${JSON.stringify(r.donnees || r.erreur)}`);
});

/* ------------------------------------------------------- 2. découvertes */
async function chargerFindings() {
  const r = await api("GET", "/findings");
  etat.findings = r.donnees || [];
  $("#kpi-fuites").textContent = etat.findings.length;
  $("#kpi-critiques").textContent =
    etat.findings.filter((f) => f.severite === "critique" && f.statut !== "ferme").length;
  const camp = etat.campagne ? await api("GET", `/campagnes/${etat.campagne}`) : null;
  if (camp && camp.donnees) {
    const p = camp.donnees.progression;
    $("#kpi-taux").textContent =
      p.executions ? `${Math.round((p.reussies / p.executions) * 100)} %` : "–";
    $("#kpi-cout").textContent = `${(camp.donnees.budget.cout_mesure || 0).toFixed(2)} $`;
  }
  $("#liste-findings").innerHTML = etat.findings.map(carteFinding).join("");
  etat.findings.forEach((f) => brancherCorrectifs(f.id));
}

function carteFinding(f) {
  return `<article class="carte finding ${f.severite}">
    <h3>${f.id} <span class="badge ${f.severite}">${f.severite}</span>
        <span class="statut">${f.statut}</span></h3>
    <p>${f.titre}</p>
    <ul>
      <li>Techniques : ${f.technique_ids.join(", ")}</li>
      <li>Score : ${f.score ?? "—"} (impact ${f.impact ?? "non établi"} ×
          exploitabilité ${f.exploitabilite ?? "—"} × exposition ${f.exposition})</li>
      <li>Preuve : <q>${(f.citation || "").slice(0, 180)}</q></li>
    </ul>
    <div class="actions">
      <button data-action="proposer" data-id="${f.id}">Propose fixes</button>
      <button data-action="rejouer" data-id="${f.id}" class="secondaire">Replay attack</button>
    </div>
    <div class="correctifs" id="correctifs-${f.id}"></div>
  </article>`;
}

function brancherCorrectifs(findingId) {
  document.querySelectorAll(`#correctifs-${findingId} button`).forEach((b) => {
    b.addEventListener("click", () => actionCorrectif(b, findingId));
  });
  const carte = document.querySelector(`.finding .actions button[data-id="${findingId}"]`);
  if (!carte) return;
  carte.parentElement.querySelectorAll("button").forEach((bouton) => {
    bouton.onclick = () => actionFinding(bouton, findingId);
  });
}

async function actionFinding(bouton, findingId) {
  if (bouton.dataset.action === "proposer") {
    const r = await api("POST", `/findings/${findingId}/correctifs`, {});
    const zone = $(`#correctifs-${findingId}`);
    zone.innerHTML = (r.donnees || []).map((c) => `<div class="correctif">
        <strong>${c.id}</strong> — ${c.type} · effort ${c.effort} · réduction ${c.reduction_risque}
        <p>${c.contenu}</p>
        ${c.type === "garde_fou" || c.type === "politique"
          ? `<button data-correctif="${c.id}">Authorise, apply &amp; replay</button>`
          : "<em>Proposed only — applied by the customer.</em>"}
      </div>`).join("");
    zone.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => autoriser(b.dataset.correctif));
    });
  } else {
    const r = await api("POST", `/findings/${findingId}/rejouer`, { graine: 20261124 });
    journal(`Rejeu ${findingId} : ${JSON.stringify(r.donnees || r.erreur).slice(0, 300)}`);
  }
}

async function autoriser(correctifId) {
  const r = await api("POST", `/correctifs/${correctifId}/autoriser`,
                      { auteur: "anne.rssi", role: "commanditaire", graine: 20261124 });
  if (!r.donnees) { journal(`Refus : ${JSON.stringify(r.erreur)}`); return; }
  journal(r.donnees.ligne || JSON.stringify(r.donnees.motifs));
  await chargerFindings();
}

function actionCorrectif() { /* réservé : les boutons sont branchés dynamiquement */ }

/* ---------------------------------------------------- 3. faux refus */
async function chargerRefus() {
  const r = await api("GET", "/budget");
  const synthese = await api("GET", `/tendances/${$("#tendance-application").value}`);
  const point = synthese.donnees && synthese.donnees.dernier;
  $("#resume-refus").innerHTML = point
    ? `<div class="bandeau"><div><span>${point.faux_refus}</span><small>false refusals</small></div>
       <div><span>${Math.round(point.taux_de_contournement * 100)} %</span><small>bypass rate</small></div>
       <div><span>${(r.donnees ? r.donnees.cout_total : 0).toFixed(2)} $</span><small>measured cost</small></div></div>`
    : "<p class='note'>Run a campaign with a legitimate-request corpus first.</p>";
  $("#liste-refus").innerHTML = "";
  etat.refus = [];
}

/* ------------------------------------------------------- 4. policy 403 */
$("#form-hors-perimetre").addEventListener("submit", async (e) => {
  e.preventDefault();
  const brut = formulaire(e.target);
  const r = await api("POST", "/campagnes", {
    mandat_id: $("#select-mandat").value, graine: 7,
    cible_spec: { type: "local", id: brut.application_id },
    technique_ids: [brut.technique],
  });
  $("#resultat-perimetre").textContent =
    `HTTP ${r.statut}\n${JSON.stringify(r.erreur || r.donnees, null, 2)}`;
});

/* ------------------------------------------------------- 5. rapport */
$("#btn-rapport").addEventListener("click", async () => {
  const id = $("#select-rapport").value || etat.campagne;
  const langue = $("#select-langue").value;
  const r = await api("GET", `/rapports/${id}?langue=${langue}`);
  $("#sortie-rapport").textContent = r.donnees ? r.donnees.rapport
    : JSON.stringify(r.erreur, null, 2);
});

$("#btn-attestation").addEventListener("click", async () => {
  const id = $("#select-rapport").value || etat.campagne;
  const langue = $("#select-langue").value;
  const r = await api("GET", `/attestations/${id}?langue=${langue}`);
  $("#sortie-rapport").textContent = r.donnees ? r.donnees.attestation
    : JSON.stringify(r.erreur, null, 2);
});

/* ---------------------------------------------------- 6. tendances */
$("#btn-tendances").addEventListener("click", async () => {
  const r = await api("GET", `/tendances/${$("#tendance-application").value}`);
  $("#sortie-tendances").innerHTML = tableau(r.donnees ? r.donnees.points : [],
    ["campagne_id", "date", "taux_de_contournement", "faux_refus", "cout_mesure"]);
});

$("#btn-budget").addEventListener("click", async () => {
  const r = await api("GET", "/budget");
  $("#sortie-tendances").innerHTML =
    `<p>Total measured cost: <strong>${r.donnees ? r.donnees.cout_total : 0} $</strong></p>`
    + tableau(r.donnees ? r.donnees.campagnes : [],
              ["campagne_id", "date", "appels", "jetons", "cout_mesure", "ecart"]);
});

function tableau(lignes, colonnes) {
  if (!lignes.length) return "<p class='note'>No data yet.</p>";
  const entete = colonnes.map((c) => `<th>${c}</th>`).join("");
  const corps = lignes.map((l) =>
    `<tr>${colonnes.map((c) => `<td>${l[c] ?? ""}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${entete}</tr></thead><tbody>${corps}</tbody></table>`;
}

/* --------------------------------------------------------- santé + horloge */
async function majSante() {
  const r = await api("GET", "/health");
  const ok = r.statut === 200;
  $("#sante").textContent = ok ? "●" : "○";
  $("#sante").className = `pastille ${ok ? "vert" : "rouge"}`;
  $("#sante").title = ok
    ? `${r.donnees.service} v${r.donnees.version} — ${r.donnees.campagnes} campaign(s)`
    : "service inaccessible";
  if (r.donnees) $("#horloge").textContent = r.donnees.horloge;
}

majSante();
setInterval(majSante, 15000);
