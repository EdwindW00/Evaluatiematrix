// Eigen lichte SVG-grafieken (geen externe CDN-dependency) + categorie-filter.
(function () {
  const data = window.DASHBOARD_DATA;
  if (!data || !data.leveranciers.length) return;

  const KLEUREN = ["#2E6DB4", "#1A4E8C", "#5FA8D3", "#8FBFE0", "#0F3460", "#4A90C2"];

  // ---------------------------------------------------------------- gestapelde staafgrafiek
  function tekenStaafgrafiek() {
    const el = document.getElementById("staafgrafiek");
    const breedte = 320, hoogte = 260, margeOnder = 40, margeBoven = 10;
    const barBreedte = Math.min(60, (breedte - 40) / data.leveranciers.length - 10);
    const schaal = (hoogte - margeOnder - margeBoven) / 100;

    let svg = `<svg viewBox="0 0 ${breedte} ${hoogte}" width="100%" style="max-width:${breedte}px">`;
    svg += `<line x1="30" y1="${hoogte - margeOnder}" x2="${breedte - 10}" y2="${hoogte - margeOnder}" stroke="#dbe4ee"/>`;
    data.leveranciers.forEach((naam, i) => {
      const x = 40 + i * (barBreedte + 20);
      let y = hoogte - margeOnder;
      (data.punten[i] || []).forEach((cat, ci) => {
        const h = cat.punten * schaal;
        y -= h;
        svg += `<rect x="${x}" y="${y}" width="${barBreedte}" height="${h}" fill="${KLEUREN[ci % KLEUREN.length]}"><title>${naam} — ${cat.categorie_naam}: ${cat.punten}</title></rect>`;
      });
      const opacity = data.uitgesloten[i] ? "0.4" : "1";
      svg += `<text x="${x + barBreedte / 2}" y="${hoogte - 22}" font-size="9" text-anchor="middle" fill="#374151" opacity="${opacity}">${naam.length > 10 ? naam.slice(0, 9) + "…" : naam}</text>`;
      svg += `<text x="${x + barBreedte / 2}" y="${hoogte - margeOnder - (data.eindtotalen[i] * schaal) - 4}" font-size="10" font-weight="700" text-anchor="middle" fill="#1A4E8C">${data.eindtotalen[i]}</text>`;
    });
    svg += `</svg>`;
    el.innerHTML = svg;
  }

  // ---------------------------------------------------------------- radargrafiek per categorie
  function tekenRadar() {
    const el = document.getElementById("radargrafiek");
    const n = data.categorieen.length;
    if (n < 3) {
      el.innerHTML = `<p class="muted">Minstens 3 categorieën nodig voor een radarweergave. Zie de staafgrafiek en tabel hiernaast.</p>`;
      return;
    }
    const size = 300, cx = size / 2, cy = size / 2, r = size / 2 - 40;
    const angle = (i) => (Math.PI * 2 * i) / n - Math.PI / 2;
    const puntOp = (i, waarde) => {
      const a = angle(i);
      const radius = r * Math.max(0, Math.min(1, waarde));
      return [cx + radius * Math.cos(a), cy + radius * Math.sin(a)];
    };

    let svg = `<svg viewBox="0 0 ${size} ${size}" width="100%" style="max-width:${size}px">`;
    // rasterringen
    [0.25, 0.5, 0.75, 1].forEach(f => {
      const pts = Array.from({ length: n }, (_, i) => puntOp(i, f).join(",")).join(" ");
      svg += `<polygon points="${pts}" fill="none" stroke="#e5e7eb"/>`;
    });
    // assen + labels
    data.categorieen.forEach((naam, i) => {
      const [x, y] = puntOp(i, 1.08);
      const a = angle(i);
      svg += `<line x1="${cx}" y1="${cy}" x2="${cx + r * Math.cos(a)}" y2="${cy + r * Math.sin(a)}" stroke="#e5e7eb"/>`;
      svg += `<text x="${x}" y="${y}" font-size="9" text-anchor="middle" fill="#374151">${naam.length > 14 ? naam.slice(0, 13) + "…" : naam}</text>`;
    });
    // per leverancier een lijn (waarde = punten / weging van die categorie, dus 0-1 schaal)
    data.leveranciers.forEach((naam, li) => {
      if (data.uitgesloten[li]) return;
      const cats = data.punten[li] || [];
      const pts = cats.map((c, i) => puntOp(i, c.weging ? c.punten / c.weging : 0).join(",")).join(" ");
      const kleur = KLEUREN[li % KLEUREN.length];
      svg += `<polygon points="${pts}" fill="${kleur}22" stroke="${kleur}" stroke-width="2"><title>${naam}</title></polygon>`;
    });
    svg += `</svg>`;
    el.innerHTML = svg;

    let legenda = '<div style="margin-top:8px;font-size:0.8rem">';
    data.leveranciers.forEach((naam, i) => {
      if (data.uitgesloten[i]) return;
      legenda += `<span style="display:inline-block;margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:${KLEUREN[i % KLEUREN.length]};border-radius:2px;margin-right:4px"></span>${naam}</span>`;
    });
    legenda += "</div>";
    el.innerHTML += legenda;
  }

  tekenStaafgrafiek();
  tekenRadar();

  // ---------------------------------------------------------------- categorie-filter op detailtabel
  const filter = document.getElementById("categorie-filter");
  if (filter) {
    filter.addEventListener("change", () => {
      document.querySelectorAll("#detail-tabel tbody tr").forEach(tr => {
        tr.style.display = !filter.value || tr.dataset.catId === filter.value ? "" : "none";
      });
    });
  }
})();
