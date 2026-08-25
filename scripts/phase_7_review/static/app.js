/* Tablero de revisión manual de parámetros · Atlantis GOC */

const SEV = {
  critical: { label: 'Crítica', hint: 'discrepancia >100% o empate categórico' },
  serious:  { label: 'Alta',    hint: 'discrepancia 50-100%, empate o parámetro clave' },
  warning:  { label: 'Media',   hint: 'discrepancia 10-50%' },
};
const STATUS_LABEL = {
  accepted: 'Aceptado',
  rejected: 'Descartado',
  needs_more_evidence: 'Falta evidencia',
};

const state = {
  queue: null,
  decisions: {},
  rag: {},                 // "item_id|motor" -> respuesta RAG
  ragView: {},             // item_id -> motor que se está mostrando
  route: { view: 'home', group: null },
  filters: { param: '', sev: new Set(), status: new Set(), q: '', onlyCritical: false,
             tipo: 'conflicto' },
  open: new Set(),
};

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, String(v));   // true → "true" (lo exige [aria-pressed="true"])
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
};
function toast(msg, ms = 2600) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('show'), ms);
}

// ── Markdown mínimo ────────────────────────────────────────────────────
// El LLM responde en Markdown (negritas, títulos, listas, tablas y citas en
// blockquote). Se escapa el HTML primero y sólo después se aplican las marcas,
// así que nada de lo que devuelva el modelo puede inyectar etiquetas.

const escHtml = (s) => String(s).replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function inlineMd(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // No perezoso sobre [^*]: las negritas suelen envolver cursivas —los nombres
    // científicos van en *cursiva*— y también saltos de línea.
    .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/(^|[\s(])_([^_\n]+)_/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function md(src) {
  const text = escHtml(src ?? '').replace(/\r\n/g, '\n');
  const out = [];

  for (const block of text.split(/\n{2,}/)) {
    const lines = block.split('\n').filter((l) => l.trim() !== '');
    if (!lines.length) continue;

    // Tabla con pipes: | a | b |  /  |---|---|
    if (lines.length >= 2 && /^\s*\|/.test(lines[0]) && /^\s*\|?[\s:|-]+\|/.test(lines[1])) {
      const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
      const head = cells(lines[0]).map((c) => `<th>${inlineMd(c)}</th>`).join('');
      const body = lines.slice(2)
        .map((r) => '<tr>' + cells(r).map((c) => `<td>${inlineMd(c)}</td>`).join('') + '</tr>').join('');
      out.push(`<div class="tbl-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`);
      continue;
    }

    // Título
    const heading = lines[0].match(/^(#{1,6})\s+(.*)$/);
    if (heading && lines.length === 1) {
      const level = Math.min(heading[1].length + 2, 6);   // # → h3, para no competir con la página
      out.push(`<h${level}>${inlineMd(heading[2])}</h${level}>`);
      continue;
    }

    // Cita (los fragmentos textuales del corpus vienen así). Ojo: el escapado ya
    // convirtió el «>» inicial en «&gt;».
    if (lines.every((l) => /^\s*(&gt;|>)/.test(l))) {
      const quoted = lines.map((l) => l.replace(/^\s*(&gt;|>)\s?/, '')).join('\n');
      out.push('<blockquote>' + inlineMd(quoted).replace(/\n/g, '<br>') + '</blockquote>');
      continue;
    }

    // Listas
    if (/^\s*([-*+]|\d+[.)])\s+/.test(lines[0])) {
      const ordered = /^\s*\d+[.)]\s+/.test(lines[0]);
      const items = [];
      for (const line of lines) {
        const m = line.match(/^\s*(?:[-*+]|\d+[.)])\s+(.*)$/);
        if (m) items.push(m[1]);
        else if (items.length) items[items.length - 1] += ' ' + line.trim();
      }
      const tag = ordered ? 'ol' : 'ul';
      out.push(`<${tag}>` + items.map((i) => `<li>${inlineMd(i)}</li>`).join('') + `</${tag}>`);
      continue;
    }

    // Párrafo, con títulos sueltos intercalados. Las marcas en línea se aplican
    // al párrafo completo, no línea a línea: una negrita puede abrirse en una
    // línea y cerrarse en la siguiente.
    const buffer = [];
    const flush = () => {
      if (!buffer.length) return;
      out.push('<p>' + inlineMd(buffer.join('\n')).replace(/\n/g, '<br>') + '</p>');
      buffer.length = 0;
    };
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        flush();
        const level = Math.min(h[1].length + 2, 6);
        out.push(`<h${level}>${inlineMd(h[2])}</h${level}>`);
        continue;
      }
      // Viñetas que arrancan sin línea en blanco delante (muy común en el LLM).
      if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
        flush();
        const ordered = /^\s*\d+[.)]\s+/.test(line);
        const items = [];
        while (i < lines.length) {
          const m = lines[i].match(/^\s*(?:[-*+]|\d+[.)])\s+(.*)$/);
          if (m) items.push(m[1]);
          else if (items.length && /^\s{2,}\S/.test(lines[i])) items[items.length - 1] += ' ' + lines[i].trim();
          else break;
          i++;
        }
        i--;
        const tag = ordered ? 'ol' : 'ul';
        out.push(`<${tag}>` + items.map((it) => `<li>${inlineMd(it)}</li>`).join('') + `</${tag}>`);
        continue;
      }
      buffer.push(line);
    }
    flush();
  }
  return out.join('').replace(/<p><\/p>/g, '');
}

const fmt = (v, kind) => {
  if (v === null || v === undefined || v === '') return '—';
  if (kind === 'cat') return v;
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  if (Math.abs(n) >= 1000) return n.toLocaleString('es-MX', { maximumFractionDigits: 0 });
  return String(Math.round(n * 1000) / 1000);
};

// ── carga ──────────────────────────────────────────────────────────────

async function load() {
  const res = await fetch('/api/queue');
  if (!res.ok) { $('#view').innerHTML = '<p class="empty">No se pudo cargar la cola.</p>'; return; }
  const data = await res.json();
  state.queue = data;
  state.decisions = data.decisions || {};
  render();
}

const decisionOf = (id) => state.decisions[id];
const isDecided = (id) => ['accepted', 'rejected'].includes(decisionOf(id)?.status);

// ── vista general ──────────────────────────────────────────────────────

function renderHome() {
  const q = state.queue;
  const t = q.totals;
  const reviewed = Object.values(state.decisions).filter((d) => ['accepted', 'rejected'].includes(d.status)).length;
  const flagged = Object.values(state.decisions).filter((d) => d.status === 'needs_more_evidence').length;
  const pct = t.conflicts ? Math.round(reviewed / t.conflicts * 100) : 0;

  const kpis = el('div', { class: 'kpis' },
    kpi(t.cells_with_value, 'Celdas con dato', `unión de ${q.searches.join(' · ')}`),
    kpi((t.by_tipo || {}).conflicto || 0, 'Discrepan', 'dos o más búsquedas, valores distintos'),
    kpi((t.by_tipo || {}).sin_respaldo || 0, 'Sin respaldo', 'B6 no halló evidencia en el corpus'),
    kpi((t.by_tipo || {}).sugerencia_ia || 0, 'Sugerencias IA', `${t.ai_contradicts || 0} contradicen a las búsquedas`),
    kpi(t.cells_with_quote || 0, 'Con cita textual', 'respaldadas por B6 con fragmento verbatim'),
    conflictKpi(t, reviewed, pct),
    kpi(flagged, 'Marcadas', 'requieren más evidencia'),
  );

  const load = (g) => (g.conflicts || 0) + (g.unsupported || 0);
  const groups = q.groups.filter((g) => load(g) > 0)
    .sort((a, b) => b.critical - a.critical || load(b) - load(a));
  const quiet = q.groups.filter((g) => load(g) === 0);

  // replaceChildren convierte null en el texto "null": hay que filtrarlo.
  const show = (...nodes) => $('#view').replaceChildren(...nodes.filter(Boolean));
  show(
    kpis,
    el('h2', {}, 'Grupos con celdas por revisar ', el('span', {}, `(${groups.length} de ${q.groups.length})`),
      el('button', { class: 'ghost', style: 'float:right;font-size:13px',
                     onclick: () => go({ view: 'group', group: '__all__' }) },
        'Ver la cola completa →')),
    el('div', { class: 'cards' }, groups.map(groupCard)),
    quiet.length ? el('h2', {}, 'Sin celdas por revisar ', el('span', {}, `(${quiet.length} grupos)`)) : null,
    quiet.length ? el('div', { class: 'cards' }, quiet.map(groupCard)) : null,
  );
}

function kpi(val, label, sub) {
  return el('div', { class: 'kpi' },
    el('div', { class: 'val' }, typeof val === 'number' ? val.toLocaleString('es-MX') : val),
    el('div', { class: 'lbl' }, label),
    sub ? el('div', { class: 'sub' }, sub) : null);
}

function conflictKpi(t, reviewed, pct) {
  const node = kpi(t.conflicts, 'En revisión', `${reviewed} resueltas · ${pct}%`);
  node.append(el('div', { class: 'progress' }, el('i', { style: `width:${pct}%` })));
  return node;
}

function groupCard(g) {
  const done = state.queue.items.filter((i) => i.group === g.group && isDecided(i.id)).length;
  const total = (g.conflicts || 0) + (g.unsupported || 0);
  const pending = total - done;
  // Composición por severidad de la cola del grupo (bruta) + lo ya revisado.
  const bar = el('div', { class: 'sevbar' });
  for (const [name, n] of [['done', done], ['critical', g.critical],
                           ['serious', g.serious], ['warning', g.warning]]) {
    if (n > 0) bar.append(el('i', { class: `sev-${name}`, style: `flex:${n}` }));
  }
  return el('button', {
    class: `card${total ? '' : ' quiet'}`,
    onclick: () => go({ view: 'group', group: g.group }),
  },
    el('span', { class: 'code' }, g.code || '—'),
    el('div', { class: 'name' }, g.group),
    el('div', { class: 'big' }, (g.conflicts || 0) + (g.unsupported || 0),
      el('small', {}, 'celdas por revisar')),
    el('div', { class: 'meta' },
      el('span', {}, `${g.conflicts || 0} discrepan`),
      el('span', {}, `${g.unsupported || 0} sin respaldo`)),
    total ? bar : null,
    el('div', { class: 'meta' },
      el('span', {}, `${g.n_species} especies`),
      el('span', {}, `${g.cells_with_value} con dato`),
      pending > 0 ? el('span', {}, `${pending} pendientes`) : (total ? el('span', {}, '✓ completo') : null)),
  );
}

// ── vista de grupo ─────────────────────────────────────────────────────

function itemsOfGroup(group) {
  return state.queue.items.filter((i) => group === '__all__' || i.group === group);
}

function applyFilters(items) {
  const f = state.filters;
  const needle = f.q.trim().toLowerCase();
  return items.filter((i) => {
    if (f.tipo && (i.tipo || 'conflicto') !== f.tipo) return false;
    if (f.param && i.param !== f.param) return false;
    if (f.sev.size && !f.sev.has(i.severity)) return false;
    if (f.onlyCritical && !i.critical_param) return false;
    if (f.status.size) {
      const d = decisionOf(i.id);
      const st = d ? d.status : 'pending';
      if (!f.status.has(st)) return false;
    }
    if (needle) {
      const hay = `${i.species} ${i.family} ${i.genus} ${i.order} ${i.param_label} ${i.param}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
}

function renderGroup() {
  const group = state.route.group;
  const all = itemsOfGroup(group);
  const items = applyFilters(all).sort((a, b) => {
    const rank = { critical: 0, serious: 1, warning: 2 };
    return (isDecided(a.id) - isDecided(b.id)) || (rank[a.severity] - rank[b.severity])
      || b.spread_pct - a.spread_pct || a.species.localeCompare(b.species);
  });
  const done = all.filter((i) => isDecided(i.id)).length;

  const head = el('div', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:16px' },
    el('button', { class: 'ghost', onclick: () => go({ view: 'home' }) }, '← Grupos'),
    el('h2', { style: 'margin:0;font-size:18px' }, group === '__all__' ? 'Todas las celdas en conflicto' : group),
    el('span', { class: 'hint' }, `${done}/${all.length} revisadas`));

  $('#view').replaceChildren(head, filtersBar(all),
    items.length
      ? el('div', {}, items.map((i) => conflictCard(i)))
      : el('p', { class: 'empty' }, 'Ninguna celda coincide con los filtros.'));
}

function filtersBar(all) {
  const f = state.filters;
  const params = [...new Set(all.map((i) => i.param))].sort();
  const paramSel = el('select', { onchange: (e) => { f.param = e.target.value; render(); } },
    el('option', { value: '' }, `Todos los parámetros (${params.length})`),
    params.map((p) => {
      const n = all.filter((i) => i.param === p).length;
      const opt = el('option', { value: p }, `${state.queue.params[p].label} · ${n}`);
      if (f.param === p) opt.selected = true;
      return opt;
    }));

  const sevChips = el('div', { class: 'chips' }, Object.entries(SEV).map(([key, meta]) => {
    const n = all.filter((i) => i.severity === key).length;
    return el('button', {
      class: 'chip', title: meta.hint, 'aria-pressed': f.sev.has(key),
      onclick: () => { f.sev.has(key) ? f.sev.delete(key) : f.sev.add(key); render(); },
    }, el('span', { class: 'dot', style: `background:var(--${key})` }), `${meta.label} ${n}`);
  }));

  const statusChips = el('div', { class: 'chips' }, [
    ['pending', 'Pendientes'], ['accepted', 'Aceptadas'],
    ['rejected', 'Descartadas'], ['needs_more_evidence', 'Marcadas'],
  ].map(([key, label]) => {
    const n = all.filter((i) => (decisionOf(i.id)?.status || 'pending') === key).length;
    return el('button', {
      class: 'chip', 'aria-pressed': f.status.has(key),
      onclick: () => { f.status.has(key) ? f.status.delete(key) : f.status.add(key); render(); },
    }, `${label} ${n}`);
  }));

  // Al teclear se redibuja la lista, así que hay que devolver el foco y el cursor.
  const search = el('input', {
    id: 'flt-q', placeholder: 'Especie, familia o parámetro…', value: f.q, style: 'min-width:220px',
    oninput: (e) => {
      f.q = e.target.value;
      const pos = e.target.selectionStart;
      renderGroup();
      const again = $('#flt-q');
      if (again) { again.focus(); again.setSelectionRange(pos, pos); }
    },
  });

  const tipoChips = el('div', { class: 'chips' }, [
    ['conflicto', 'Discrepan'],
    ['sin_respaldo', 'Sin respaldo de B6'],
    ['sugerencia_ia', 'Sugerencia IA'],
  ].map(([key, label]) => {
    const n = all.filter((i) => (i.tipo || 'conflicto') === key).length;
    return el('button', {
      class: 'chip', 'aria-pressed': f.tipo === key,
      title: key === 'sin_respaldo'
        ? 'Otra búsqueda afirma un valor que la corrida con evidencia (B6) no encontró en el corpus'
        : (key === 'sugerencia_ia'
            ? 'Inferencia taxonómica del modelo, sin respaldo documental: hipótesis a validar'
            : 'Dos o más búsquedas dan valores distintos'),
      onclick: () => { f.tipo = key; render(); },
    }, `${label} ${n}`);
  }));

  return el('div', { class: 'filters' },
    el('label', {}, 'Tipo'), tipoChips,
    el('label', {}, 'Parámetro'), paramSel,
    el('label', {}, 'Severidad'), sevChips,
    el('label', {}, 'Estado'), statusChips,
    el('button', {
      class: 'chip', 'aria-pressed': f.onlyCritical,
      title: 'Solo parámetros que Atlantis necesita con urgencia',
      onclick: () => { f.onlyCritical = !f.onlyCritical; render(); },
    }, '★ Parámetros clave'),
    el('div', { class: 'spacer' }), search,
    (f.param || f.sev.size || f.status.size || f.q || f.onlyCritical)
      ? el('button', { class: 'ghost', onclick: () => { state.filters = { param: '', sev: new Set(), status: new Set(), q: '', onlyCritical: false, tipo: f.tipo }; render(); } }, 'Limpiar')
      : null);
}

// ── tarjeta de celda en conflicto ──────────────────────────────────────

const rangeText = (r, kind) => `${fmt(r[0], kind)}–${fmt(r[1], kind)}`;

function valueChips(item) {
  return el('div', { class: 'vals' }, Object.entries(item.values).map(([k, v]) =>
    el('span', { class: `vchip${k === 'B6' ? ' evid' : ''}` },
      el('span', { class: `dot dot-${k}` }),
      el('span', { class: 'k' }, k), fmt(v, item.kind),
      (k === 'B6' && item.range_b6)
        ? el('span', { class: 'rng' }, ` (${rangeText(item.range_b6, item.kind)})`) : null)));
}

function conflictCard(item) {
  const d = decisionOf(item.id);
  const open = state.open.has(item.id);
  const card = el('div', { class: `conflict s-${item.severity}${isDecided(item.id) ? ' decided' : ''}` });

  const head = el('div', {
    class: 'chead',
    onclick: () => { state.open.has(item.id) ? state.open.delete(item.id) : state.open.add(item.id); renderGroup(); },
  },
    el('div', { class: 'sp' }, item.species, el('div', { class: 'fam' }, [item.family, item.order].filter(Boolean).join(' · '))),
    el('div', { class: 'pl' }, el('b', {}, item.param_label), item.unit ? ` (${item.unit})` : '',
      item.critical_param ? el('div', { class: 'fam' }, '★ parámetro clave para Atlantis') : null),
    valueChips(item),
    el('div', { style: 'display:flex;gap:6px;align-items:center' },
      item.tipo === 'sugerencia_ia'
        ? el('span', { class: 'badge ia', title: 'Inferencia taxonómica, sin respaldo documental' }, 'sugerencia IA')
        : item.tipo === 'sin_respaldo'
        ? el('span', { class: 'badge crit', title: 'B6 no encontró evidencia en el corpus' }, 'sin respaldo')
        : (item.kind === 'num'
            ? el('span', { class: `badge${item.spread_pct > 100 ? ' crit' : ''}` }, `Δ ${item.spread_pct.toFixed(0)}%`)
            : el('span', { class: 'badge crit' }, 'discrepa')),
      d ? el('span', { class: `badge${d.status === 'accepted' ? ' done' : ''}` }, STATUS_LABEL[d.status]) : null,
      el('span', { class: 'hint' }, open ? '▲' : '▼')),
  );
  card.append(head);
  if (open) card.append(cardBody(item));
  return card;
}

function cardBody(item) {
  const body = el('div', { class: 'cbody' });
  const searches = Object.keys(item.values);

  // Tabla de candidatos
  const rows = searches.map((k) => el('tr', {},
    el('td', {}, el('span', { class: `vchip${k === 'B6' ? ' evid' : ''}` },
      el('span', { class: `dot dot-${k}` }), k)),
    el('td', { class: 'num' }, fmt(item.values[k], item.kind), item.unit ? ` ${item.unit}` : '',
      (k === 'B6' && item.range_b6)
        ? el('div', { class: 'fam' }, `rango ${rangeText(item.range_b6, item.kind)}`) : null,
      (item.inside_range && k !== 'B6')
        ? el('div', { class: 'fam' }, item.inside_range[k] ? '✓ dentro del rango de B6' : '✗ fuera del rango de B6')
        : null),
    el('td', { class: 'cites' }, (item.citations?.[k] || []).join(', ') || '— sin cita en la fila —'),
    el('td', {}, el('button', {
      class: 'chip',
      onclick: () => { fillDecision(item.id, item.values[k], k); },
    }, 'Usar')),
  ));

  body.append(
    el('h4', {}, 'Valores propuestos por cada búsqueda'),
    el('table', { class: 'cand' },
      el('thead', {}, el('tr', {},
        el('th', {}, 'Búsqueda'), el('th', {}, 'Valor'),
        el('th', {}, 'Citas de la fila'), el('th', {}, ''))),
      el('tbody', {}, rows)),
    el('div', { style: 'margin-top:10px', class: 'hint' },
      `Consenso sugerido: `, el('b', {}, fmt(item.suggested, item.kind)),
      ` · método: ${item.suggested_method}`),
  );

  const sug = item.ai_suggestion;
  if (sug) {
    const contradice = Object.values(item.values).some((v) => v !== sug.value);
    body.append(
      el('h4', {}, 'Sugerencia de IA ',
        el('span', { class: `conf conf-${sug.confidence}` }, `confianza ${sug.confidence}`)),
      el('div', { class: 'ia-box' },
        el('div', {}, el('b', {}, fmt(sug.value, item.kind)),
          el('span', { class: 'hint' }, ` · ${sug.scope}`),
          contradice ? el('span', { class: 'badge crit', style: 'margin-left:8px' }, 'contradice a las búsquedas') : null),
        el('p', { style: 'margin:8px 0 0;font-size:13px;line-height:1.55' }, sug.rationale),
        citasIA(sug.citations),
        el('div', { class: 'hint', style: 'margin-top:10px' },
          'Inferencia taxonómica del modelo, ', el('b', {}, 'respaldada por literatura pero no extraída del corpus'),
          '. La cita sostiene la afirmación biológica (residencia, territorialidad, estatus '
          + 'migratorio), no la codificación del campo de Atlantis: eso lo decides tú. '
          + 'Trátala como hipótesis con fuente, no como dato del corpus.'),
        el('button', { class: 'chip', style: 'margin-top:10px',
          onclick: () => fillDecision(item.id, sug.value, 'IA') }, 'Usar la sugerencia')));
  }

  const ev = item.evidence_b6;
  if (ev) {
    body.append(
      el('h4', {}, 'Evidencia de B6'),
      el('div', { class: 'evid-box' },
        el('div', { class: 'paper-grid' },
          el('span', { class: 'pk' }, 'Unidad'),  el('span', { class: 'pv' }, ev.unit || '—'),
          el('span', { class: 'pk' }, 'Base'),    el('span', { class: 'pv' }, ev.basis || '—'),
          el('span', { class: 'pk' }, 'Fuente'),  el('span', { class: 'pv' }, ev.source || '—')),
        ev.quote ? el('blockquote', { class: 'quote' }, ev.quote) : null));
  }

  if (item.tipo === 'sin_respaldo') {
    body.append(el('div', { class: 'warn-note', style: 'margin-top:10px' },
      `B6 procesó esta especie y no encontró en el corpus ningún valor para ${item.param_label}. `
      + 'En una muestra de 12 casos así, en 10 el corpus no contenía dato alguno de la especie '
      + 'y el valor provenía del conocimiento general del modelo. Verifícalo con el RAG antes de conservarlo.'));
  }

  if (searches.includes('B5') && searches.includes('B4') && item.values.B4 === item.values.B5) {
    body.append(el('div', { class: 'warn-note', style: 'margin-top:10px' },
      'B5 partió del CSV de B4: su coincidencia no es evidencia independiente y no cuenta como voto.'));
  }
  if (item.param === 'IsMigratory') {
    body.append(el('div', { class: 'warn-note', style: 'margin-top:10px' },
      'IsMigratory es el campo con mayor riesgo de que el LLM lo dedujera del taxón sin respaldo del corpus. Exige cita explícita antes de aceptar.'));
  }

  // Panel RAG
  body.append(el('h4', {}, 'Asistencia RAG'), ragPanel(item));

  // Formulario de decisión
  body.append(el('h4', {}, 'Decisión'), decisionForm(item));

  const d = decisionOf(item.id);
  if (d && item.tipo === 'sin_respaldo' && d.status === 'accepted' && d.source !== 'externo') {
    body.append(el('div', { class: 'warn-note', style: 'margin-top:12px' },
      'Esta celda se aceptó antes de que B6 existiera. B6 no encontró respaldo en el corpus: '
      + 'conviene reabrirla y verificarla con el RAG.'));
  }
  if (d) {
    body.append(el('div', { class: 'decided-note' },
      `${STATUS_LABEL[d.status]} · valor ${fmt(d.value, item.kind)} · fuente ${d.source || '—'}`
      + `${d.reference ? ` · ref. ${d.reference}` : ''} · ${d.reviewer || 'sin revisor'} · ${d.updated_at}`
      + `${d.comment ? ` · «${d.comment}»` : ''}`));
  }
  return body;
}

// ── RAG ────────────────────────────────────────────────────────────────

const ragKey = (id, engine) => `${id}|${engine}`;
const ENGINE_LABEL = { semantic: 'semántico', hybrid: 'híbrido (BM25)' };

function ragPanel(item) {
  const box = el('div', { class: 'rag', id: `rag-${cssId(item.id)}` });
  const shown = state.ragView[item.id];
  const cached = shown ? state.rag[ragKey(item.id, shown)] : null;
  const known = state.queue.rag_cached?.includes(item.id);

  if (cached) {
    box.replaceChildren(...ragContent(item, cached));
  } else {
    box.append(
      el('div', { class: 'hint', style: 'margin-bottom:10px' },
        known
          ? 'Ya existe una consulta guardada para esta celda.'
          : 'Consulta el índice (18 080 chunks) para verificar qué sostiene la literatura.'),
      el('div', { style: 'display:flex;gap:8px;flex-wrap:wrap' },
        el('button', { class: 'primary', onclick: () => runRag(item) }, 'Consultar RAG'),
        el('button', { onclick: () => runRag(item, null, 'hybrid') }, 'Motor híbrido'),
        known ? el('button', { onclick: () => loadCachedRag(item) }, 'Ver consulta guardada') : null,
        el('button', { onclick: () => askCustom(item) }, 'Pregunta libre…')),
    );
  }
  return box;
}

function ragContent(item, data) {
  const engine = data.engine || 'semantic';
  const other = engine === 'semantic' ? 'hybrid' : 'semantic';
  const nodes = [
    el('div', { class: 'q' },
      el('span', { class: 'badge', style: 'margin-right:8px' }, `motor ${ENGINE_LABEL[engine]}`),
      '❯ ', data.question),
    el('div', { class: 'answer', html: md(data.answer) }),
  ];
  if (data.sources?.length) {
    nodes.push(el('h4', { style: 'margin-bottom:2px' }, `Fuentes (${data.sources.length})`));
    const max = Math.max(...data.sources.map((s) => s.score), 0.001);
    for (const [i, s] of data.sources.entries()) {
      const cardId = `src-${cssId(item.id)}-${i}`;
      nodes.push(el('div', { class: 'src' },
        el('div', {},
          el('div', { class: 'pid' },
            el('button', {
              class: 'pid-btn', title: 'Ver ficha del documento y abrir el PDF',
              onclick: (e) => togglePaper(e.currentTarget, cardId, s),
            }, s.paper_id, ' ▾'),
            s.year ? el('span', { class: 'hint' }, ` · ${s.year}`) : null,
            s.page ? el('span', { class: 'hint' }, ` · p. ${s.page}`) : null,
            s.doi ? el('a', { href: `https://doi.org/${s.doi}`, target: '_blank', rel: 'noopener' }, ' · DOI') : null),
          s.text ? el('div', { class: 'txt' }, s.text) : null,
          el('div', { class: 'paper-card', id: cardId })),
        el('div', {},
          el('div', { class: 'score' }, s.score.toFixed(3)),
          el('div', { class: 'meter' }, el('i', { style: `width:${Math.round(s.score / max * 100)}%` })))));
    }
  } else {
    nodes.push(el('div', { class: 'hint', style: 'margin-top:8px' }, 'Sin fuentes recuperadas.'));
  }
  const twin = state.rag[ragKey(item.id, other)];
  nodes.push(el('div', { style: 'display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;align-items:center' },
    el('span', { class: 'hint', style: 'flex:1' },
      `${data.chunks_used} chunks · ${(data.elapsed_ms / 1000).toFixed(1)} s · ${data.model || ''} · ${data.queried_at}`),
    el('button', { class: 'chip', onclick: () => runRag(item, data.question, engine) }, 'Reconsultar'),
    twin
      ? el('button', { class: 'chip', onclick: () => { state.ragView[item.id] = other; refreshRag(item); } },
          `Ver motor ${ENGINE_LABEL[other]}`)
      : el('button', { class: 'chip', onclick: () => runRag(item, null, other) },
          `Segunda opinión: motor ${ENGINE_LABEL[other]}`),
    el('button', { class: 'chip', onclick: () => askCustom(item) }, 'Pregunta libre…')));
  return nodes;
}

// ── ficha bibliográfica del documento citado ───────────────────────────

async function togglePaper(button, cardId, source) {
  const card = $(`#${cardId}`);
  if (!card) return;
  if (card.dataset.open === '1') {
    card.replaceChildren();
    card.dataset.open = '0';
    button.lastChild.textContent = ' ▾';
    return;
  }
  card.dataset.open = '1';
  button.lastChild.textContent = ' ▴';
  card.replaceChildren(el('div', { class: 'hint' }, el('span', { class: 'spin' }), 'Cargando ficha…'));

  try {
    const [paper, chunk] = await Promise.all([
      fetch(`/api/paper/${encodeURIComponent(source.paper_id)}`).then((r) => (r.ok ? r.json() : null)),
      source.chunk_id
        ? fetch(`/api/chunk/${encodeURIComponent(source.chunk_id)}`).then((r) => (r.ok ? r.json() : null))
        : Promise.resolve(null),
    ]);
    if (!paper) throw new Error('sin ficha para este documento');
    card.replaceChildren(...paperCard(paper, chunk, source));
  } catch (err) {
    card.replaceChildren(el('div', { class: 'warn-note' }, `No se pudo cargar la ficha: ${err.message}`));
  }
}

function paperCard(paper, chunk, source) {
  const page = source.page || chunk?.page;
  const doi = paper.doi || chunk?.doi || source.doi;
  const pdfUrl = `/api/pdf/${encodeURIComponent(paper.paper_id)}${page ? `#page=${page}` : ''}`;

  const rows = [
    ['Identificador', paper.paper_id],
    ['Año', paper.year ?? '—'],
    ['Fragmento', chunk
      ? `${(chunk.chunk_index ?? 0) + 1} de ${chunk.total_chunks} · página ${chunk.page ?? '—'}`
      : (page ? `página ${page}` : '—')],
    ['Extensión', `${paper.n_chunks} fragmentos indexados · ${paper.pages} páginas`],
    ['DOI', doi
      ? el('a', { href: `https://doi.org/${doi}`, target: '_blank', rel: 'noopener' }, doi)
      : 'no detectado en el texto'],
  ];

  const nodes = [
    el('div', { class: 'paper-grid' },
      rows.flatMap(([label, value]) => [
        el('span', { class: 'pk' }, label),
        el('span', { class: 'pv' }, value),
      ])),
    el('div', { class: 'hint', style: 'margin:8px 0' },
      'El índice no guarda autores ni título verificados: ',
      el('b', {}, (paper.authors_from_filename || []).join(', ') || '—'),
      ' se derivó del nombre del archivo. La portada de abajo es la fuente fiable.'),
    el('div', { style: 'display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px' },
      paper.pdf_available
        ? el('a', { class: 'btn-link', href: pdfUrl, target: '_blank', rel: 'noopener' },
            page ? `Abrir PDF en la página ${page}` : 'Abrir PDF')
        : el('span', { class: 'hint' }, 'PDF no disponible en disco'),
      doi ? el('a', { class: 'btn-link', href: `https://doi.org/${doi}`, target: '_blank', rel: 'noopener' }, 'Ir al DOI') : null),
  ];

  if (chunk?.text) {
    nodes.push(el('details', { class: 'fold' },
      el('summary', {}, 'Texto íntegro del fragmento citado'),
      el('div', { class: 'excerpt' }, chunk.text)));
  }
  if (paper.cover_text) {
    nodes.push(el('details', { class: 'fold' },
      el('summary', {}, 'Portada del documento (título, revista, DOI)'),
      el('div', { class: 'excerpt' }, paper.cover_text)));
  }
  return nodes;
}

function refreshRag(item) {
  const target = $(`#rag-${cssId(item.id)}`);
  const data = state.rag[ragKey(item.id, state.ragView[item.id])];
  if (target && data) target.replaceChildren(...ragContent(item, data));
}

const cssId = (id) => id.replace(':', '_');

async function runRag(item, question = null, engine = 'semantic') {
  const box = $(`#rag-${cssId(item.id)}`);
  if (box) box.replaceChildren(el('div', {}, el('span', { class: 'spin' }),
    `Consultando el índice con el motor ${ENGINE_LABEL[engine]}… (5-30 s)`));
  try {
    const res = await fetch('/api/rag', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_id: item.id, question, engine, include_chunks: true }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    state.rag[ragKey(item.id, engine)] = data;
    state.ragView[item.id] = engine;
    refreshRag(item);
  } catch (err) {
    const target = $(`#rag-${cssId(item.id)}`);
    if (target) target.replaceChildren(
      el('div', { class: 'warn-note' }, `No se pudo consultar el RAG: ${err.message}`),
      el('button', { style: 'margin-top:10px', onclick: () => runRag(item, question, engine) }, 'Reintentar'));
  }
}

async function loadCachedRag(item) {
  const res = await fetch(`/api/rag/cached/${encodeURIComponent(item.id)}`);
  const byEngine = await res.json();
  const engines = Object.keys(byEngine || {});
  if (!engines.length) { toast('No hay consulta guardada'); return; }
  for (const engine of engines) state.rag[ragKey(item.id, engine)] = byEngine[engine];
  state.ragView[item.id] = engines.includes('semantic') ? 'semantic' : engines[0];
  refreshRag(item);
}

function askCustom(item) {
  const engine = state.ragView[item.id] || 'semantic';
  const base = state.rag[ragKey(item.id, engine)]?.question || '';
  const q = prompt('Pregunta al RAG:', base || `What does the literature report for ${item.param} of ${item.species} in the Gulf of California?`);
  if (q && q.trim()) runRag(item, q.trim(), engine);
}

// ── decisión ───────────────────────────────────────────────────────────

function decisionForm(item) {
  const d = decisionOf(item.id);
  const sources = [...Object.keys(item.values), 'RAG', 'externo',
                   ...(item.ai_suggestion ? ['IA'] : []), 'manual', 'ninguna'];

  const valueInput = el('input', {
    id: `val-${cssId(item.id)}`,
    value: d?.value ?? (item.suggested ?? ''),
    placeholder: item.kind === 'cat' ? 'Yes / No' : 'valor numérico',
    style: 'min-width:150px',
  });
  const sourceSel = el('select', { id: `src-${cssId(item.id)}` },
    sources.map((s) => {
      const opt = el('option', { value: s }, s);
      if (d?.source === s) opt.selected = true;
      return opt;
    }));
  const commentInput = el('input', {
    id: `cmt-${cssId(item.id)}`, value: d?.comment || '',
    placeholder: 'Justificación, cita, conversión de unidades…',
  });
  // Respaldo fuera del corpus: hay parámetros que estos papers no pueden
  // sostener (la migración de un ave playera, p. ej.) y la evidencia buena
  // vive en otra fuente. Sin dónde anotarla, se perdería.
  const refInput = el('input', {
    id: `ref-${cssId(item.id)}`, value: d?.reference || '',
    placeholder: 'FishBase, Birds of the World, DOI…',
  });

  const send = (status) => saveDecision(item, status);

  return el('div', { class: 'decide' },
    el('div', { class: 'field' }, el('label', {}, 'Valor final'), valueInput),
    el('div', { class: 'field' }, el('label', {}, 'Fuente'), sourceSel),
    el('div', { class: 'field' }, el('label', {}, 'Referencia externa'), refInput),
    el('div', { class: 'field grow' }, el('label', {}, 'Comentario'), commentInput),
    el('button', { class: 'primary', onclick: () => send('accepted') }, 'Aceptar valor'),
    el('button', { onclick: () => send('needs_more_evidence') }, 'Falta evidencia'),
    el('button', { onclick: () => send('rejected') }, 'Descartar celda'),
    d ? el('button', { class: 'ghost', onclick: () => send('pending') }, 'Reabrir') : null);
}

function fillDecision(itemId, value, source) {
  const v = $(`#val-${cssId(itemId)}`);
  const s = $(`#src-${cssId(itemId)}`);
  if (v) v.value = value;
  if (s) s.value = source;
  toast(`Valor de ${source} cargado en el formulario`);
}

async function saveDecision(item, status) {
  const reviewer = $('#reviewer').value.trim();
  if (status !== 'pending' && !reviewer) { toast('Escribe tu nombre de revisor arriba'); $('#reviewer').focus(); return; }
  localStorage.setItem('reviewer', reviewer);

  const value = $(`#val-${cssId(item.id)}`)?.value ?? '';
  if (status === 'accepted' && !value.trim()) { toast('Indica el valor final'); return; }
  if (status === 'accepted' && item.kind === 'num' && isNaN(Number(value))) {
    toast('El valor debe ser numérico'); return;
  }
  const src = $(`#src-${cssId(item.id)}`)?.value;
  const ref = $(`#ref-${cssId(item.id)}`)?.value?.trim();
  if (status === 'accepted' && src === 'externo' && !ref) {
    toast('Indica la referencia externa que respalda el valor');
    $(`#ref-${cssId(item.id)}`)?.focus();
    return;
  }

  const payload = {
    item_id: item.id, status,
    value: status === 'rejected' ? null : value,
    source: $(`#src-${cssId(item.id)}`)?.value || null,
    reference: $(`#ref-${cssId(item.id)}`)?.value || '',
    reviewer, comment: $(`#cmt-${cssId(item.id)}`)?.value || '',
  };
  const res = await fetch('/api/decision', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) { toast('Error al guardar'); return; }

  if (status === 'pending') delete state.decisions[item.id];
  else state.decisions[item.id] = { ...payload, updated_at: new Date().toISOString().slice(0, 19) };
  toast(status === 'pending' ? 'Celda reabierta' : `Guardado: ${STATUS_LABEL[status]}`);
  state.open.delete(item.id);
  render();
}

// ── exportación y navegación ───────────────────────────────────────────

async function exportCsv() {
  const btn = $('#btn-export');
  btn.disabled = true; btn.textContent = 'Exportando…';
  try {
    const res = await fetch('/api/export', { method: 'POST' });
    const data = await res.json();
    const parts = Object.entries(data.by_status || {}).map(([k, v]) => `${k}: ${v}`).join(' · ');
    toast(`${data.cells} celdas → ${data.csv}  (${parts})`, 6000);
    window.open('/api/export/download', '_blank');
  } catch (err) {
    toast('Error al exportar');
  } finally {
    btn.disabled = false; btn.textContent = 'Exportar CSV';
  }
}

function go(route) {
  state.route = route;
  state.open.clear();
  location.hash = route.view === 'group' ? `#g=${encodeURIComponent(route.group)}` : '';
  render();
  window.scrollTo(0, 0);
}

function readHash() {
  const m = location.hash.match(/^#g=(.*)$/);
  state.route = m ? { view: 'group', group: decodeURIComponent(m[1]) } : { view: 'home', group: null };
}

function render() {
  if (!state.queue) return;
  const t = state.queue.totals;
  $('#subtitle').textContent =
    `${t.conflicts} celdas en conflicto · ${t.species} especies · ${state.queue.searches.join('/')} · cola del ${state.queue.generated_at.slice(0, 10)}`;
  if (state.route.view === 'group') renderGroup(); else renderHome();
}

// ── arranque ───────────────────────────────────────────────────────────

$('#btn-export').addEventListener('click', exportCsv);
$('#btn-theme').addEventListener('click', () => {
  const now = document.documentElement.getAttribute('data-theme');
  const next = now === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
});
window.addEventListener('hashchange', () => { readHash(); render(); });

document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || '');
$('#reviewer').value = localStorage.getItem('reviewer') || '';
$('#reviewer').addEventListener('change', (e) => localStorage.setItem('reviewer', e.target.value.trim()));

readHash();
load();

// Citas académicas que respaldan una sugerencia de IA. Puede haber varias, y
// una misma cita puede servir a varias familias: se enumeran completas para
// que el revisor pueda ir a comprobarlas sin salir del tablero.
function citasIA(citations) {
  if (!citations || !citations.length) {
    return el('div', { class: 'hint', style: 'margin-top:10px' }, 'Sin cita — regla no respaldada.');
  }
  return el('div', { class: 'citas-ia' },
    el('div', { class: 'citas-ia-tit' },
      citations.length === 1 ? 'Respaldo académico' : `Respaldo académico (${citations.length})`),
    ...citations.map((c) => el('div', { class: 'cita' },
      el('div', { class: 'cita-ref' }, c.ref),
      c.url ? el('a', { class: 'cita-url', href: c.url, target: '_blank', rel: 'noopener' }, c.url) : null,
      el('div', { class: 'cita-sostiene' }, 'sostiene: ', c.supports))));
}
