// Client-side logica voor de leverancier-detailpagina: score-overschrijven met live totaal-update.
(function () {
  const container = document.querySelector(".container[data-supplier-id]");
  if (!container) return;
  const projectId = container.dataset.projectId;
  const supplierId = container.dataset.supplierId;

  const eindtotaalBlok = document.getElementById("eindtotaal-blok");

  function verwerkTotalen(totalen) {
    eindtotaalBlok.textContent = `Eindtotaal (gewogen): ${totalen.eindtotaal} / 100`;
    totalen.categorieen.forEach(c => {
      const el = document.querySelector(`.cat-subtotaal[data-cat-id="${c.categorie_id}"]`);
      if (el) el.textContent = `(subtotaal: ${c.punten})`;
    });
    if (totalen.uitgesloten && !document.querySelector(".warning-blok")) {
      location.reload(); // toon de uitsluitingsbanner bovenaan alsnog
    }
  }

  async function stuurOverride(critId, veld, waarde) {
    const row = document.querySelector(`tr[data-crit-id="${critId}"]`);
    const commentaarEl = row.querySelector(".commentaar-input");
    if (!commentaarEl.value.trim()) {
      commentaarEl.style.borderColor = "#b91c1c";
      commentaarEl.placeholder = "Verplicht: leg kort uit waarom je de AI-score aanpast";
    }
    const body = { [veld]: waarde, gebruiker_commentaar: commentaarEl.value };
    const resp = await fetch(`/project/${projectId}/leverancier/${supplierId}/score/${critId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (data.totalen) verwerkTotalen(data.totalen);
    const badge = row.querySelector(".score-ai, .score-overschreven");
    if (badge) { badge.textContent = "door Edwin aangepast"; badge.className = "score-overschreven"; }
  }

  document.querySelectorAll(".score-input").forEach(el => {
    el.addEventListener("change", () => stuurOverride(el.dataset.critId, "score", el.value === "" ? null : Number(el.value)));
  });
  document.querySelectorAll(".voldaan-select").forEach(el => {
    el.addEventListener("change", () => stuurOverride(el.dataset.critId, "voldaan", el.value === "" ? null : Number(el.value)));
  });
  document.querySelectorAll(".commentaar-input").forEach(el => {
    el.addEventListener("change", () => {
      fetch(`/project/${projectId}/leverancier/${supplierId}/score/${el.dataset.critId}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gebruiker_commentaar: el.value }),
      });
    });
  });
  document.querySelectorAll(".nader-verifieren-check").forEach(el => {
    el.addEventListener("change", () => {
      fetch(`/project/${projectId}/leverancier/${supplierId}/score/${el.dataset.critId}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nader_verifieren: el.checked }),
      });
    });
  });
})();
