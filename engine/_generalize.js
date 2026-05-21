// ===== pointcloud-atlas generalization layer (v0.1) =========================
// Injected at the end of the atlas module by build_engine.py.
// Drives the whole UI from manifest.config: title/labels, color-by ANY
// categorical or continuous attribute, legend (swatches or gradient), and the
// View dropdown. Categorical subset-by-legend and a generic filter rail are v0.2.
// Relies on module globals: data, docs, deck, currentViewState, buildLayers,
// colorMode (let), getColor / buildLegend / renderHoverContent (fn decls),
// currentZoomAlpha.
(function generalize() {
  const cfg = data && data.manifest && data.manifest.config;
  if (!cfg) return;  // legacy data with no config block -> keep original behavior

  // ---- continuous colormaps (stops, 0..1) ---------------------------------
  const CM = {
    viridis: [[68,1,84],[59,82,139],[33,145,140],[94,201,98],[253,231,37]],
    magma:   [[0,0,4],[81,18,124],[183,55,121],[252,137,97],[252,253,191]],
    inferno: [[0,0,4],[87,16,110],[188,55,84],[249,142,9],[252,255,164]],
    plasma:  [[13,8,135],[126,3,168],[204,71,120],[248,149,64],[240,249,33]],
  };
  const ramp = (stops, t) => {
    t = Math.min(1, Math.max(0, t));
    const f = t * (stops.length - 1), i = Math.floor(f), g = f - i;
    const a = stops[i], b = stops[Math.min(i + 1, stops.length - 1)];
    return [a[0]+(b[0]-a[0])*g, a[1]+(b[1]-a[1])*g, a[2]+(b[2]-a[2])*g];
  };

  // ---- attribute access ---------------------------------------------------
  docs.forEach((d, i) => { d._i = i; });
  const num = {}, cat = {};
  const spec = Object.fromEntries(cfg.color_by.map(c => [c.key, c]));
  const base = (data.manifest.__dataBase) || '/data/';
  async function loadSidecars() {
    await Promise.all(cfg.color_by.map(async c => {
      try {
        if (c.source.startsWith('num:')) {
          const r = await fetch(base + 'num_' + c.key + '.bin');
          if (r.ok) num[c.key] = new Float32Array(await r.arrayBuffer());
        } else if (c.source.startsWith('cat:')) {
          const r = await fetch(base + 'cat_' + c.key + '.bin');
          if (r.ok) cat[c.key] = new Uint16Array(await r.arrayBuffer());
        }
      } catch (e) { /* sidecar optional */ }
    }));
  }
  const codeOf = (d, c) => {
    if (c.source === 'struct:s0') return d.ds;
    if (c.source === 'struct:s1') return d.year;
    if (c.source.startsWith('cat:')) return cat[c.key] ? cat[c.key][d._i] : 0;
    return 0;
  };
  const valOf = (d, c) => (num[c.key] ? num[c.key][d._i] : 0);

  // ---- filtering: categorical (legend chips) + continuous (range rail) ----
  // Per-attribute state: categorical -> {codes:Set}, continuous -> {min,max}.
  // All active filters AND together into one 'filter' constraint that composes
  // with search + lasso via the engine's constraint stack.
  const filt = {};
  function computeFilterMatch() {
    const preds = [];
    for (const c of cfg.color_by) {
      const st = filt[c.key];
      if (!st) continue;
      if (c.kind === 'categorical' && st.codes && st.codes.size)
        preds.push(d => st.codes.has(codeOf(d, c)));
      else if (c.kind === 'continuous' && (st.min != null || st.max != null))
        preds.push(d => { const v = valOf(d, c);
          return (st.min == null || v >= st.min) && (st.max == null || v <= st.max); });
    }
    if (!preds.length) { setSingularConstraint('filter', null); recomputeComposite(); return; }
    const m = new Set();
    for (const d of docs) if (preds.every(p => p(d))) m.add(d.nid);
    setSingularConstraint('filter', { label: 'filters', glyph: '▦', matchSet: m });
    recomputeComposite();
  }

  // ---- color override -----------------------------------------------------
  // feat = a lazily-fetched continuous feature (e.g. a gene from the backend)
  let feat = null;   // {vals:Float32Array, lo, hi, label}
  getColor = function (d, mode) {
    let col = [150, 150, 150];
    if (mode === '__feature' && feat) {
      col = ramp(CM.inferno, feat.hi > feat.lo ? (feat.vals[d._i] - feat.lo) / (feat.hi - feat.lo) : 0);
    } else {
      const c = spec[mode];
      if (c) {
        if (c.kind === 'categorical') col = (c.palette && c.palette[codeOf(d, c)]) || [150, 150, 150];
        else { const [lo, hi] = c.range;
          col = ramp(CM[c.colormap] || CM.viridis, hi > lo ? (valOf(d, c) - lo) / (hi - lo) : 0); }
      }
    }
    return [col[0], col[1], col[2], (typeof currentZoomAlpha === 'number' ? currentZoomAlpha : 200)];
  };

  // ---- legend override ----------------------------------------------------
  const gradLegend = (label, lo, hi, stops) => {
    const grad = stops.map((s, i) => `rgb(${s.join(',')}) ${Math.round(100*i/(stops.length-1))}%`).join(',');
    return `<div style="font-size:11px;color:var(--muted);margin-bottom:4px;">${label}</div>` +
      `<div style="height:12px;border-radius:3px;background:linear-gradient(to right,${grad});"></div>` +
      `<div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:2px;"><span>${(+lo).toPrecision(3)}</span><span>${(+hi).toPrecision(3)}</span></div>`;
  };
  buildLegend = function () {
    const el = document.getElementById('legend');
    if (!el) return;
    if (colorMode === '__feature' && feat) { el.innerHTML = gradLegend(feat.label, feat.lo, feat.hi, CM.inferno); return; }
    const c = spec[colorMode];
    if (!c) { el.innerHTML = ''; return; }
    if (c.kind === 'categorical') {
      const sel = (filt[c.key] && filt[c.key].codes) || null;
      el.innerHTML = c.vocab.map((lab, code) => {
        const col = (c.palette && c.palette[code]) || [150, 150, 150];
        const on = !sel || sel.has(code);
        return `<div class="row clickable" data-code="${code}" title="click to filter to ${lab}" `
          + `style="opacity:${on ? 1 : 0.35};cursor:pointer">`
          + `<div class="swatch" style="background:rgb(${col.join(',')})"></div>${lab}</div>`;
      }).join('') + (sel && sel.size
        ? '<div class="row clickable" id="legend-clear" style="cursor:pointer;color:var(--muted)">↺ clear</div>' : '');
      el.querySelectorAll('.row.clickable[data-code]').forEach(row => row.addEventListener('click', () => {
        const code = +row.dataset.code;
        const st = filt[c.key] || (filt[c.key] = { codes: new Set() });
        if (st.codes.has(code)) st.codes.delete(code); else st.codes.add(code);
        if (!st.codes.size) delete filt[c.key];
        computeFilterMatch(); buildLegend();
      }));
      const clr = document.getElementById('legend-clear');
      if (clr) clr.addEventListener('click', () => { delete filt[c.key]; computeFilterMatch(); buildLegend(); });
    } else {
      const [lo, hi] = c.range, stops = CM[c.colormap] || CM.viridis;
      const grad = stops.map((s, i) => `rgb(${s.join(',')}) ${Math.round(100*i/(stops.length-1))}%`).join(',');
      el.innerHTML =
        `<div style="font-size:11px;color:var(--muted);margin-bottom:4px;">${c.label}</div>` +
        `<div style="height:12px;border-radius:3px;background:linear-gradient(to right,${grad});"></div>` +
        `<div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:2px;"><span>${(+lo).toPrecision(3)}</span><span>${(+hi).toPrecision(3)}</span></div>`;
    }
  };

  // ---- hover override (id + configured fields; no PDF thumbnail) -----------
  const labelFor = (d, c) => c.kind === 'categorical'
    ? (c.vocab[codeOf(d, c)] ?? '?')
    : (+valOf(d, c)).toPrecision(3);
  const fillTpl = (tpl, id) => tpl.replace(/\{id\}/g, encodeURIComponent(id));
  renderHoverContent = function (obj) {
    const nidEl = document.getElementById('hover-nid');
    const t = document.getElementById('hover-title');
    const m = document.getElementById('hover-meta');
    if (nidEl) nidEl.textContent = `${cfg.id_label || 'id'}: ${obj.nid}`;
    if (t) t.style.display = 'none';
    if (m) {
      m.innerHTML = (cfg.hover || []).map(k => spec[k]
        ? `<div><span style="color:var(--muted)">${spec[k].label}:</span> ${labelFor(obj, spec[k])}</div>`
        : '').join('');
    }
    // optional source thumbnail + link-out, driven by config templates
    const thumb = document.getElementById('hover-thumb');
    if (thumb) {
      if (cfg.thumb_template) {
        thumb.innerHTML = `<img src="${fillTpl(cfg.thumb_template, obj.nid)}" alt="" `
          + `style="max-width:100%;border-radius:4px;" onerror="this.style.display='none'">`;
        thumb.style.display = '';
      } else { thumb.style.display = 'none'; }
    }
    const open = document.getElementById('hover-open');
    if (open) {
      if (cfg.link_template) { open.href = fillTpl(cfg.link_template, obj.nid); open.style.display = ''; }
      else open.style.display = 'none';
    }
  };

  // ---- chrome: labels, hide v0.1-unsupported widgets ----------------------
  document.title = cfg.title;
  const titleEl = document.querySelector('.topbar .title');
  if (titleEl) titleEl.textContent = cfg.title;
  // (#filterbar is repopulated as a generic numeric-range rail by buildFilterRail)
  // make the lasso ellipse clearly visible (the default fill/stroke are very faint)
  const lst = document.createElement('style');
  lst.textContent = '#lasso-ellipse{fill:rgba(122,176,255,0.14)!important;stroke:#9ec1ff!important;'
    + 'stroke-width:2.5!important;stroke-dasharray:6 4!important;}';
  document.head.appendChild(lst);

  // ---- color-by dropdown from config --------------------------------------
  const cb = document.getElementById('color-by');
  if (cb) {
    cb.innerHTML = cfg.color_by.map(c => `<option value="${c.key}">${c.label}</option>`).join('');
    colorMode = cfg.color_by[0].key;
    cb.value = colorMode;
  }

  // ---- View dropdown: keep only options whose embedding exists ------------
  const viewOf = { umap:'umap', tsne:'tsne', pacmap:'pacmap', consensus:'consensus',
                   '3d':'umap', tsne3d:'tsne', pacmap3d:'pacmap', consensus3d:'consensus' };
  const have2d = new Set(cfg.views_2d || []), have3d = new Set(cfg.views_3d || []);
  const pm = document.getElementById('pos-mode');
  if (pm) [...pm.options].forEach(o => {
    const v = viewOf[o.value], is3d = /3d|^3d$/.test(o.value) || o.value === '3d';
    const ok = is3d ? have3d.has(v) : have2d.has(v);
    if (!ok) o.remove();
  });

  // ---- meta counter relabel ("docs" -> node_label) ------------------------
  const meta = document.getElementById('meta-counter');
  if (meta) meta.textContent = meta.textContent.replace(/\bdocs\b/, cfg.node_label || 'nodes');

  const rerender = () => { if (typeof deck !== 'undefined' && deck)
    deck.setProps({ layers: buildLayers(currentViewState) }); };

  // ---- Display panel: better defaults + generic "Size by" ------------------
  function setSlider(id, v) {
    const s = document.getElementById(id), vEl = document.getElementById(id + '-v');
    if (s) s.value = v; if (vEl) vEl.textContent = (id === 't-abase') ? String(v) : (+v).toFixed(2);
  }
  function tuneDefaults() {            // points are sparse vs the 1.3M corpus — bump size+alpha for visibility
    if (typeof tune === 'object') { tune.aBase = 175; tune.rBase = 2.2; tune.rBaseMax = Math.max(tune.rBaseMax || 0, 2.2); }
    setSlider('t-abase', 175); setSlider('t-rbase', 2.2);
  }
  function installSizeBy() {
    const row = document.getElementById('t-sizebylen');
    if (!row) return;
    const num = cfg.color_by.filter(c => c.kind === 'continuous');
    const sel = document.createElement('select');
    sel.id = 't-sizeby'; sel.style.cssText = 'width:100%;font-size:10px;';
    sel.innerHTML = '<option value="">uniform</option>' +
      num.map(c => `<option value="${c.key}">${c.label}</option>`).join('');
    const lbl = row.previousElementSibling; if (lbl) lbl.textContent = 'size by';
    row.replaceWith(sel);
    sel.addEventListener('change', () => {
      const key = sel.value;
      if (!key) { window.__sizeVals = null; sizeByLen = false; }
      else {
        const a = sizeArr[key];
        if (a) {
          let lo = Infinity, hi = -Infinity;
          for (const v of a) { if (v < lo) lo = v; if (v > hi) hi = v; }
          const span = hi > lo ? hi - lo : 1;
          window.__sizeVals = Float32Array.from(a, v => 1 + ((v - lo) / span) * 63); // -> [1,64]
          sizeByLen = true;
        }
      }
      window.__sizeVersion = (window.__sizeVersion || 0) + 1;
      activeDataCache = null; rerender();
    });
  }

  // ---- Continuous filter rail (numeric range per continuous attribute) ----
  const debounce = (fn, ms = 250) => { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; };
  function buildFilterRail() {
    const bar = document.getElementById('filterbar');
    if (!bar) return;
    const cont = cfg.color_by.filter(c => c.kind === 'continuous');
    if (!cont.length) { bar.style.display = 'none'; document.body.classList.remove('has-filterbar'); return; }
    bar.removeAttribute('hidden'); bar.style.display = ''; bar.className = 'filterbar';
    document.body.classList.add('has-filterbar');
    bar.innerHTML = '<span style="color:var(--muted);font-size:11px;margin-right:2px">filter range:</span>' +
      cont.map(c => `<span class="group" data-key="${c.key}" style="gap:3px">`
        + `<label style="color:var(--muted);font-size:10px">${c.label}</label>`
        + `<input type="number" class="f-min" step="any" placeholder="${(+c.range[0]).toPrecision(3)}" style="width:62px">`
        + `<span style="color:var(--muted)">–</span>`
        + `<input type="number" class="f-max" step="any" placeholder="${(+c.range[1]).toPrecision(3)}" style="width:62px"></span>`).join('') +
      '<button class="clear" id="f-clear-all">clear</button>';
    bar.querySelectorAll('.group[data-key]').forEach(g => {
      const key = g.dataset.key;
      const upd = debounce(() => {
        const mn = g.querySelector('.f-min').value, mx = g.querySelector('.f-max').value;
        if (mn === '' && mx === '') delete filt[key];
        else filt[key] = { min: mn === '' ? null : +mn, max: mx === '' ? null : +mx };
        computeFilterMatch();
      });
      g.querySelectorAll('input').forEach(i => i.addEventListener('input', upd));
    });
    document.getElementById('f-clear-all').addEventListener('click', () => {
      bar.querySelectorAll('input').forEach(i => i.value = '');
      for (const c of cont) delete filt[c.key];
      computeFilterMatch();
    });
  }

  // ---- Generic metadata search (subsets the cloud; results link to source) ─
  const catSpecs = cfg.color_by.filter(c => c.kind === 'categorical');
  const docText = d => {
    let s = String(d.nid).toLowerCase();
    for (const c of catSpecs) s += ' ' + String((c.vocab[codeOf(d, c)] ?? '')).toLowerCase();
    return s;
  };
  function wireSearch() {
    const box = document.getElementById('search');
    const res = document.getElementById('search-results');
    if (!box) return;
    box.placeholder = 'Search ' + (cfg.id_label || 'id') + ' or metadata…';
    let deb;
    box.addEventListener('input', () => { clearTimeout(deb); deb = setTimeout(run, 200); });
    function run() {
      const q = box.value.trim().toLowerCase();
      if (!q) { setSingularConstraint('search', null); recomputeComposite();
                if (res) { res.innerHTML = ''; res.style.display = 'none'; } return; }
      const match = new Set(); const rows = [];
      for (const d of docs) if (docText(d).includes(q)) {
        match.add(d.nid); if (rows.length < 50) rows.push(d);
      }
      setSingularConstraint('search', { label: 'search: ' + q, glyph: '🔍', matchSet: match });
      recomputeComposite();
      if (res) {
        res.innerHTML = rows.map(d => `<div class="row" data-id="${d.nid}">`
          + `<span class="id">${d.nid}</span></div>`).join('')
          || '<div class="row" style="color:var(--muted)">no matches</div>';
        res.style.display = '';
        res.querySelectorAll('.row[data-id]').forEach(r =>
          r.addEventListener('click', () => { if (window.atlasPin) window.atlasPin(r.dataset.id); }));
      }
    }
  }

  // ---- Interactive backend: color-by-any-gene + lasso→DE (if endpoints set) ─
  function selectedIndices() {
    const out = [];
    if (typeof searchMatchSet !== 'undefined' && searchMatchSet)
      for (const d of docs) if (searchMatchSet.has(d.nid)) out.push(d._i);
    return out;
  }
  function panel() {
    let p = document.getElementById('sc1-analysis');
    if (!p) {
      p = document.createElement('div'); p.id = 'sc1-analysis';
      p.style.cssText = 'position:fixed;right:12px;top:140px;width:240px;max-height:60vh;overflow:auto;'
        + 'background:rgba(20,22,30,.96);border:1px solid #2a2e3a;border-radius:8px;padding:10px;'
        + 'font-size:11px;color:#cdd3e0;z-index:50;display:none;';
      document.body.appendChild(p);
    }
    return p;
  }
  function wireInteractive() {
    const controls = document.querySelector('.topbar .controls') || document.querySelector('.topbar');
    if (cfg.feature_endpoint && controls) {
      const inp = document.createElement('input');
      inp.placeholder = 'color by gene…'; inp.title = 'type a gene/feature name + Enter';
      inp.style.cssText = 'width:110px;margin-left:6px;background:#11141c;color:#cdd3e0;border:1px solid #2a2e3a;border-radius:4px;padding:2px 6px;';
      controls.insertBefore(inp, controls.firstChild);
      inp.addEventListener('keydown', async e => {
        if (e.key !== 'Enter' || !inp.value.trim()) return;
        const g = inp.value.trim();
        try {
          const r = await fetch(cfg.feature_endpoint.replace('{id}', encodeURIComponent(g)));
          if (!r.ok) { inp.style.borderColor = '#e0533b'; return; }
          inp.style.borderColor = '#2a2e3a';
          const v = new Float32Array(await r.arrayBuffer());
          let lo = Infinity, hi = -Infinity; for (const x of v) { if (x < lo) lo = x; if (x > hi) hi = x; }
          feat = { vals: v, lo, hi, label: g + ' (feature)' };
          colorMode = '__feature';
          const cb2 = document.getElementById('color-by'); if (cb2) cb2.selectedIndex = -1;
          buildLegend(); activeDataCache = null; rerender();
        } catch (_) { inp.style.borderColor = '#e0533b'; }
      });
    }
    if (cfg.de_endpoint && controls) {
      const btn = document.createElement('button');
      btn.textContent = '⚲ analyze selection'; btn.className = 'help-btn';
      btn.title = 'DE of the lassoed/searched selection vs the rest';
      btn.style.marginLeft = '6px';
      controls.appendChild(btn);
      btn.addEventListener('click', async () => {
        const idx = selectedIndices(); const p = panel(); p.style.display = '';
        if (idx.length < 5) { p.innerHTML = 'Select ≥5 cells first (Shift-drag a lasso, or search), then click again.'; return; }
        p.innerHTML = `Running DE on ${idx.length} selected cells…`;
        try {
          const r = await fetch(cfg.de_endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ indices: idx }) });
          const j = await r.json();
          if (j.error) { p.innerHTML = 'Error: ' + j.error; return; }
          const genes = j.up || [];
          p.innerHTML = `<div style="font-weight:600;margin-bottom:4px;">DE: ${j.n_selected} cells vs rest</div>`
            + `<div style="color:var(--muted);margin-bottom:4px;">top up-regulated genes:</div>`
            + genes.map(g => `<span style="display:inline-block;background:#1c2030;border-radius:3px;padding:1px 5px;margin:1px;">${g}</span>`).join('')
            + (cfg.enrich_endpoint ? `<div style="margin-top:8px;"><button id="sc1-enrich" class="help-btn">enrich these →</button></div><div id="sc1-enrich-out" style="margin-top:6px;"></div>` : '');
          const eb = document.getElementById('sc1-enrich');
          if (eb) eb.addEventListener('click', async () => {
            const out = document.getElementById('sc1-enrich-out'); out.textContent = 'enriching…';
            const er = await fetch(cfg.enrich_endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ genes }) });
            const ej = await er.json();
            out.innerHTML = (ej.terms || []).slice(0, 8).map(t =>
              `<div>• ${t.name} <span style="color:var(--muted)">(${(+t.p_value).toExponential(1)})</span></div>`).join('')
              || ('error: ' + (ej.error || '?'));
          });
        } catch (e) { p.innerHTML = 'Request failed: ' + e; }
      });
    }
  }

  // ---- apply ---------------------------------------------------------------
  let sizeArr = num;  // alias the continuous-sidecar map for installSizeBy
  loadSidecars().then(() => {
    tuneDefaults();
    installSizeBy();
    buildFilterRail();
    wireSearch();
    wireInteractive();
    buildLegend();
    rerender();
  });
})();
