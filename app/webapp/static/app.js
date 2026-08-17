// Client-side logica: upload (drag&drop), stappenbalk, en de live matrix-editor.
(function () {
  const container = document.querySelector(".container[data-project-id]");
  if (!container || !document.getElementById("paneel-upload")) return; // niet op de hoofd-projectpagina
  const projectId = container.dataset.projectId;

  // ---------------------------------------------------------------- stappenbalk
  const stappen = document.querySelectorAll(".stap:not(.uitgeschakeld):not(.stap-link)");
  const panelen = {
    upload: document.getElementById("paneel-upload"),
    matrix: document.getElementById("paneel-matrix"),
    offertes: document.getElementById("paneel-offertes"),
  };
  function toonFase(naam) {
    Object.entries(panelen).forEach(([k, el]) => { if (el) el.classList.toggle("verborgen", k !== naam); });
    document.querySelectorAll(".stap").forEach(s => s.classList.toggle("actief", s.dataset.stap === naam));
  }
  stappen.forEach(s => s.addEventListener("click", () => toonFase(s.dataset.stap)));
  const gaNaarMatrixBtn = document.getElementById("ga-naar-matrix");
  if (gaNaarMatrixBtn) gaNaarMatrixBtn.addEventListener("click", () => toonFase("matrix"));
  const gaNaarOffertesBtn = document.getElementById("ga-naar-offertes");
  if (gaNaarOffertesBtn) gaNaarOffertesBtn.addEventListener("click", () => toonFase("offertes"));

  // ---------------------------------------------------------------- upload
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const docTableBody = document.getElementById("doc-table-body");

  function docRowHtml(d) {
    const types = ["offerte-aanvraag", "SLA", "contractvoorwaarden", "PvE", "overig"];
    const opties = types.map(t => `<option value="${t}" ${d.type === t ? "selected" : ""}>${t}</option>`).join("");
    const fout = d.foutmelding ? `<div class="fout-melding">${escapeHtml(d.foutmelding)}</div>` : "";
    return `<tr data-doc-id="${d.id}">
      <td>${escapeHtml(d.bestandsnaam)}</td>
      <td><select class="doc-type-select" data-doc-id="${d.id}">${opties}</select></td>
      <td><span class="status status-${d.status}">${d.status}</span>${fout}</td>
      <td><button class="btn-link doc-delete" data-doc-id="${d.id}">verwijderen</button></td>
    </tr>`;
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : s;
    return div.innerHTML;
  }

  async function uploadFiles(files) {
    if (!files.length) return;
    const fd = new FormData();
    [...files].forEach(f => fd.append("bestanden", f));
    const resp = await fetch(`/project/${projectId}/upload`, { method: "POST", body: fd });
    const data = await resp.json();
    if (data.documenten) {
      docTableBody.innerHTML = data.documenten.map(docRowHtml).join("");
      bindDocTableEvents();
    }
  }

  if (dropzone) {
    ["dragenter", "dragover"].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add("dragover"); }));
    ["dragleave", "drop"].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
    dropzone.addEventListener("drop", e => uploadFiles(e.dataTransfer.files));
  }
  if (fileInput) fileInput.addEventListener("change", e => uploadFiles(e.target.files));

  function bindDocTableEvents() {
    document.querySelectorAll(".doc-type-select").forEach(sel => {
      sel.onchange = () => {
        const fd = new FormData();
        fd.append("type", sel.value);
        fetch(`/project/${projectId}/documents/${sel.dataset.docId}/type`, { method: "POST", body: fd });
      };
    });
    document.querySelectorAll(".doc-delete").forEach(btn => {
      btn.onclick = async () => {
        await fetch(`/project/${projectId}/documents/${btn.dataset.docId}/delete`, { method: "POST" });
        btn.closest("tr").remove();
      };
    });
  }
  bindDocTableEvents();

  // ---------------------------------------------------------------- matrix-editor
  let matrix = window.INITIAL_MATRIX || [];
  const matrixContainer = document.getElementById("matrix-container");
  const matrixTotaalEl = document.getElementById("matrix-totaal");
  const genereerBtn = document.getElementById("genereer-matrix");
  const onzekerhedenBlok = document.getElementById("onzekerheden-blok");
  const voegCategorieBtn = document.getElementById("voeg-categorie-toe");
  const vaststellenBtn = document.getElementById("matrix-vaststellen");
  const statusLabel = document.getElementById("matrix-status-label");

  function herberekenTotaal() {
    let totaal = 0;
    matrix.forEach(cat => {
      let catTotaal = 0;
      (cat.criteria || []).forEach(c => { if (c.type !== "knock-out") catTotaal += Number(c.weging) || 0; });
      cat.weging = catTotaal;
      totaal += catTotaal;
    });
    const afgerond = Math.round(totaal * 100) / 100;
    matrixTotaalEl.textContent = `Totaal weging: ${afgerond}% ${afgerond === 100 ? "✓" : "(moet 100% zijn)"}`;
    matrixTotaalEl.classList.toggle("fout", afgerond !== 100);
    document.querySelectorAll(".cat-weging").forEach(el => {
      const cat = matrix.find(c => c.id === el.dataset.catId);
      if (cat) el.value = cat.weging;
    });
  }

  function renderMatrix() {
    if (!matrix.length) {
      matrixContainer.innerHTML = `<p class="empty-state">Nog geen matrix. Klik op "Genereer conceptmatrix met AI" of voeg handmatig een categorie toe.</p>`;
      matrixTotaalEl.textContent = "";
      return;
    }
    matrixContainer.innerHTML = matrix.map(cat => `
      <div class="categorie-blok" data-cat-id="${cat.id}">
        <div class="categorie-kop">
          <input class="cat-naam" data-cat-id="${cat.id}" value="${escapeHtml(cat.naam)}">
          <input class="cat-weging" data-cat-id="${cat.id}" value="${cat.weging}" readonly>
          <span class="cat-weging-suffix">% (som van criteria)</span>
          <button class="btn-link cat-delete" data-cat-id="${cat.id}">categorie verwijderen</button>
        </div>
        <table class="criteria-table">
          <thead><tr><th>Criterium</th><th>Type</th><th>Schaal</th><th>Weging %</th><th>Bron</th><th>Toelichting</th><th></th></tr></thead>
          <tbody>
            ${(cat.criteria || []).map(c => `
              <tr data-crit-id="${c.id}">
                <td><input class="crit-naam" data-crit-id="${c.id}" value="${escapeHtml(c.naam)}"></td>
                <td>
                  <select class="crit-type" data-crit-id="${c.id}">
                    <option value="score" ${c.type === "score" ? "selected" : ""}>Score</option>
                    <option value="knock-out" ${c.type === "knock-out" ? "selected" : ""}>Knock-out</option>
                  </select>
                </td>
                <td><input class="crit-schaal" data-crit-id="${c.id}" value="${escapeHtml(c.schaal || "0-10")}" ${c.type === "knock-out" ? "disabled" : ""}></td>
                <td><input class="crit-weging" data-crit-id="${c.id}" type="number" step="1" value="${c.weging || 0}" ${c.type === "knock-out" ? "disabled" : ""}></td>
                <td><span class="bron-tekst">${escapeHtml(c.bron || "")}</span></td>
                <td><textarea class="crit-toelichting" data-crit-id="${c.id}">${escapeHtml(c.toelichting || "")}</textarea></td>
                <td><button class="btn-link crit-delete" data-crit-id="${c.id}">✕</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
        <div class="categorie-footer">
          <button class="btn-link crit-add" data-cat-id="${cat.id}">+ criterium toevoegen</button>
        </div>
      </div>
    `).join("");
    herberekenTotaal();
    bindMatrixEvents();
  }

  function findCrit(critId) {
    for (const cat of matrix) {
      const c = (cat.criteria || []).find(x => x.id === critId);
      if (c) return { cat, c };
    }
    return null;
  }

  function bindMatrixEvents() {
    document.querySelectorAll(".cat-naam").forEach(el => {
      el.onchange = () => {
        const cat = matrix.find(c => c.id === el.dataset.catId);
        cat.naam = el.value;
        fetch(`/project/${projectId}/matrix/categorie/${cat.id}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ naam: cat.naam }),
        });
      };
    });
    document.querySelectorAll(".cat-delete").forEach(el => {
      el.onclick = async () => {
        if (!confirm("Categorie en alle bijbehorende criteria verwijderen?")) return;
        await fetch(`/project/${projectId}/matrix/categorie/${el.dataset.catId}`, { method: "DELETE" });
        matrix = matrix.filter(c => c.id !== el.dataset.catId);
        renderMatrix();
      };
    });
    document.querySelectorAll(".crit-add").forEach(el => {
      el.onclick = async () => {
        const resp = await fetch(`/project/${projectId}/matrix/categorie/${el.dataset.catId}/criterium`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ naam: "Nieuw criterium", type: "score", weging: 0 }),
        });
        const data = await resp.json();
        matrix = data.matrix;
        renderMatrix();
      };
    });
    document.querySelectorAll(".crit-delete").forEach(el => {
      el.onclick = async () => {
        await fetch(`/project/${projectId}/matrix/criterium/${el.dataset.critId}`, { method: "DELETE" });
        const found = findCrit(el.dataset.critId);
        if (found) found.cat.criteria = found.cat.criteria.filter(c => c.id !== el.dataset.critId);
        renderMatrix();
      };
    });

    function bindField(selector, veld, transform) {
      document.querySelectorAll(selector).forEach(el => {
        el.onchange = () => {
          const found = findCrit(el.dataset.critId);
          if (!found) return;
          const waarde = transform ? transform(el.value) : el.value;
          found.c[veld] = waarde;
          fetch(`/project/${projectId}/matrix/criterium/${el.dataset.critId}`, {
            method: "PATCH", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ [veld]: waarde }),
          });
          if (veld === "weging" || veld === "type") herberekenTotaal();
          if (veld === "type") renderMatrix();
        };
      });
    }
    bindField(".crit-naam", "naam");
    bindField(".crit-type", "type");
    bindField(".crit-schaal", "schaal");
    bindField(".crit-weging", "weging", v => Number(v) || 0);
    bindField(".crit-toelichting", "toelichting");
  }

  if (genereerBtn) {
    genereerBtn.onclick = async () => {
      genereerBtn.disabled = true;
      genereerBtn.textContent = "Bezig met analyseren…";
      onzekerhedenBlok.classList.add("verborgen");
      try {
        const resp = await fetch(`/project/${projectId}/matrix/genereren`, { method: "POST" });
        const data = await resp.json();
        if (data.error) {
          alert("Fout bij genereren: " + data.error);
        } else {
          matrix = data.matrix;
          renderMatrix();
          if (data.onzekerheden && data.onzekerheden.length) {
            onzekerhedenBlok.innerHTML = "<strong>Let op — onzekerheden gevonden door de AI:</strong><ul>" +
              data.onzekerheden.map(o => `<li>${escapeHtml(o)}</li>`).join("") + "</ul>";
            onzekerhedenBlok.classList.remove("verborgen");
          }
        }
      } finally {
        genereerBtn.disabled = false;
        genereerBtn.textContent = "Genereer conceptmatrix met AI";
      }
    };
  }

  if (voegCategorieBtn) {
    voegCategorieBtn.onclick = async () => {
      const resp = await fetch(`/project/${projectId}/matrix/categorie`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ naam: "Nieuwe categorie" }),
      });
      const data = await resp.json();
      matrix = data.matrix;
      renderMatrix();
    };
  }

  if (vaststellenBtn) {
    vaststellenBtn.onclick = async () => {
      const afgerond = Math.round(matrix.reduce((s, c) => s + (Number(c.weging) || 0), 0) * 100) / 100;
      if (afgerond !== 100 && !confirm(`Let op: het totaal is ${afgerond}%, niet 100%. Toch vaststellen?`)) return;
      await fetch(`/project/${projectId}/matrix/vaststellen`, { method: "POST" });
      statusLabel.textContent = "Status: vastgesteld";
    };
  }

  renderMatrix();

  // ---------------------------------------------------------------- leveranciers (fase 4/5)
  const nieuweLeverancierForm = document.getElementById("nieuwe-leverancier-form");
  const leveranciersLijst = document.getElementById("leveranciers-lijst");

  function leverancierBlokHtml(lev) {
    const statusKlasse = lev.uitgesloten ? "fout" : (["gescoord", "handmatig gecontroleerd"].includes(lev.status) ? "klaar" : (lev.status === "bezig" ? "bezig" : "wachten"));
    const statusTekst = lev.uitgesloten ? "uitgesloten (knock-out)" : lev.status;
    return `<div class="leverancier-blok" data-supplier-id="${lev.id}">
      <div class="leverancier-kop">
        <span class="leverancier-naam">${escapeHtml(lev.naam)}</span>
        <span class="status status-${statusKlasse}">${escapeHtml(statusTekst)}</span>
        <a class="btn-secondary" href="/project/${projectId}/leverancier/${lev.id}">Scores bekijken/controleren →</a>
        <button class="btn-link leverancier-delete" data-supplier-id="${lev.id}">verwijderen</button>
      </div>
      <div class="dropzone dropzone-klein" data-supplier-id="${lev.id}">
        <p>Sleep offerte(s) hierheen, of <label class="upload-label">kies bestanden<input type="file" class="leverancier-file-input" data-supplier-id="${lev.id}" multiple accept=".pdf,.docx,.xlsx,.xls,.txt"></label></p>
      </div>
      <ul class="leverancier-doc-lijst" data-supplier-id="${lev.id}"></ul>
      <button class="btn-primary scoor-leverancier" data-supplier-id="${lev.id}" ${window.AI_GECONFIGUREERD ? "" : "disabled"}>Scoor deze offerte met AI</button>
    </div>`;
  }

  function docLijstItemHtml(d, supplierId) {
    const fout = d.foutmelding ? `<span class="fout-melding">${escapeHtml(d.foutmelding)}</span>` : "";
    return `<li data-doc-id="${d.id}">${escapeHtml(d.bestandsnaam)} — <span class="status status-${d.status}">${d.status}</span>${fout}
      <button class="btn-link lev-doc-delete" data-doc-id="${d.id}" data-supplier-id="${supplierId}">✕</button></li>`;
  }

  function bindLeverancierBlokEvents(blok) {
    const supplierId = blok.dataset.supplierId;
    const dz = blok.querySelector(".dropzone-klein");
    const input = blok.querySelector(".leverancier-file-input");
    async function uploadLeverancierFiles(files) {
      if (!files.length) return;
      const fd = new FormData();
      [...files].forEach(f => fd.append("bestanden", f));
      const resp = await fetch(`/project/${projectId}/leveranciers/${supplierId}/upload`, { method: "POST", body: fd });
      const data = await resp.json();
      const ul = blok.querySelector(".leverancier-doc-lijst");
      ul.innerHTML = data.documenten.map(d => docLijstItemHtml(d, supplierId)).join("");
      bindDocLijstEvents(blok);
    }
    if (dz) {
      ["dragenter", "dragover"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("dragover"); }));
      ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("dragover"); }));
      dz.addEventListener("drop", e => uploadLeverancierFiles(e.dataTransfer.files));
    }
    if (input) input.addEventListener("change", e => uploadLeverancierFiles(e.target.files));

    const deleteBtn = blok.querySelector(".leverancier-delete");
    if (deleteBtn) deleteBtn.onclick = async () => {
      if (!confirm(`Leverancier "${blok.querySelector(".leverancier-naam").textContent}" en alle scores verwijderen?`)) return;
      await fetch(`/project/${projectId}/leveranciers/${supplierId}/delete`, { method: "POST" });
      blok.remove();
    };

    const scoorBtn = blok.querySelector(".scoor-leverancier");
    if (scoorBtn) scoorBtn.onclick = async () => {
      scoorBtn.disabled = true;
      const origTekst = scoorBtn.textContent;
      scoorBtn.textContent = "Bezig met scoren…";
      try {
        const resp = await fetch(`/project/${projectId}/leveranciers/${supplierId}/scoren`, { method: "POST" });
        const data = await resp.json();
        if (data.error) {
          alert("Fout bij scoren: " + data.error);
        } else {
          const statusSpan = blok.querySelector(".status");
          statusSpan.textContent = data.uitgesloten ? "uitgesloten (knock-out)" : data.status;
          statusSpan.className = "status status-" + (data.uitgesloten ? "fout" : "klaar");
        }
      } finally {
        scoorBtn.disabled = false;
        scoorBtn.textContent = origTekst;
      }
    };
    bindDocLijstEvents(blok);
  }

  function bindDocLijstEvents(blok) {
    const supplierId = blok.dataset.supplierId;
    blok.querySelectorAll(".lev-doc-delete").forEach(btn => {
      btn.onclick = async () => {
        await fetch(`/project/${projectId}/leveranciers/${supplierId}/documenten/${btn.dataset.docId}/delete`, { method: "POST" });
        btn.closest("li").remove();
      };
    });
  }

  document.querySelectorAll(".leverancier-blok").forEach(bindLeverancierBlokEvents);

  if (nieuweLeverancierForm) {
    nieuweLeverancierForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("nieuwe-leverancier-naam");
      const naam = input.value.trim();
      if (!naam) return;
      const fd = new FormData();
      fd.append("naam", naam);
      const resp = await fetch(`/project/${projectId}/leveranciers`, { method: "POST", body: fd });
      const lev = await resp.json();
      if (lev.error) { alert(lev.error); return; }
      const legeTekst = document.getElementById("geen-leveranciers-tekst");
      if (legeTekst) legeTekst.remove();
      const div = document.createElement("div");
      div.innerHTML = leverancierBlokHtml(lev);
      const blok = div.firstElementChild;
      leveranciersLijst.appendChild(blok);
      bindLeverancierBlokEvents(blok);
      input.value = "";
    });
  }
})();
