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
  fb: null,                // índice de grupos de FishBase
  fbGroup: null,           // tabla del grupo abierto
  fbBusy: false,
  matrix: null,            // tabla completa especie × parámetro
  mx: { group: '', q: '', verPendientes: true, soloConDato: false },
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
  // El avance se mide SÓLO sobre la cola. `decisions.json` guarda además las
  // celdas resueltas fuera de ella —FishBase tiene su propia página— y contarlas
  // contra el tamaño de la cola daba porcentajes por encima de 100.
  const enCola = new Set(state.queue.items.map((i) => i.id));
  const resueltas = Object.entries(state.decisions)
    .filter(([, d]) => ['accepted', 'rejected'].includes(d.status));
  const reviewed = resueltas.filter(([id]) => enCola.has(id)).length;
  const fuera = resueltas.length - reviewed;
  const flagged = Object.entries(state.decisions)
    .filter(([id, d]) => enCola.has(id) && d.status === 'needs_more_evidence').length;
  const pct = t.conflicts ? Math.round(reviewed / t.conflicts * 100) : 0;

  const kpis = el('div', { class: 'kpis' },
    kpi(t.cells_with_value, 'Celdas con dato', `unión de ${q.searches.join(' · ')}`),
    kpi((t.by_tipo || {}).conflicto || 0, 'Discrepan', 'dos o más búsquedas, valores distintos'),
    kpi((t.by_tipo || {}).sin_respaldo || 0, 'Sin respaldo', 'B6 no halló evidencia en el corpus'),
    kpi((t.by_tipo || {}).sugerencia_ia || 0, 'Sugerencias IA', `${t.ai_contradicts || 0} contradicen a las búsquedas`),
    quoteKpi(t),
    conflictKpi(t, reviewed, pct, fuera),
    kpi(flagged, 'Marcadas', 'requieren más evidencia'),
  );

  const groups = q.groups.filter((g) => groupLoad(g) > 0)
    .sort((a, b) => b.critical - a.critical || groupLoad(b) - groupLoad(a));
  const quiet = q.groups.filter((g) => groupLoad(g) === 0);

  // replaceChildren convierte null en el texto "null": hay que filtrarlo.
  const show = (...nodes) => $('#view').replaceChildren(...nodes.filter(Boolean));
  show(
    kpis,
    el('h2', {}, 'Grupos con celdas por revisar ', el('span', {}, `(${groups.length} de ${q.groups.length})`),
      el('button', { class: 'ghost', style: 'float:right;font-size:13px',
                     onclick: () => go({ view: 'group', group: '__all__' }) },
        'Ver la cola completa →'),
      el('button', { class: 'ghost', style: 'float:right;font-size:13px;margin-right:8px',
                     onclick: () => go({ view: 'fb', group: null }) },
        'Parámetros de FishBase →'),
      el('button', { class: 'ghost', style: 'float:right;font-size:13px;margin-right:8px',
                     onclick: () => go({ view: 'matrix', group: null }) },
        'Todos los parámetros →')),
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

// Las celdas con cita verbatim de B6 son el subconjunto que puede resolverse sin
// volver al PDF, así que el resumen tiene que decir cuántas quedan. `cells_with_quote`
// es un total congelado al construir la cola: se recuenta contra las decisiones
// vivas o el tablero seguiría anunciando trabajo pendiente que ya está hecho.
function quoteKpi(t) {
  const total = t.cells_with_quote || 0;
  const conCita = state.queue.items.filter((i) => i.evidence_b6?.quote);
  const done = conCita.filter((i) => isDecided(i.id)).length;
  const pct = total ? Math.round(done / total * 100) : 0;
  const node = kpi(total, 'Con cita textual',
    done ? `${done} resueltas · ${total - done} por revisar` : 'respaldadas por B6 con fragmento verbatim');
  node.append(el('div', { class: 'progress' }, el('i', { style: `width:${pct}%` })));
  return node;
}

function conflictKpi(t, reviewed, pct, fuera) {
  const node = kpi(t.conflicts, 'En revisión', `${reviewed} resueltas · ${pct}%`);
  node.append(el('div', { class: 'progress' }, el('i', { style: `width:${pct}%` })));
  // Las resueltas fuera de la cola no caben en esta barra, pero tampoco pueden
  // desaparecer del resumen: son trabajo hecho, y quien lo hizo tiene que verlo.
  if (fuera) {
    node.append(el('div', { class: 'sub' },
      `+${fuera.toLocaleString('es-MX')} resueltas fuera de esta cola `
      + '(casi todas, en la página de FishBase)'));
  }
  return node;
}

// Celdas que este grupo pone en la cola de revisión. Las sugerencias de IA
// cuentan: son la mayor parte de la cola y también piden decisión humana.
// Omitirlas hacía que un grupo lleno de sugerencias se mostrara como vacío.
// Lo mismo vale para peso-talla y NotebookLM: si no se cuentan, un grupo cuya
// cola sea sólo de esos canales se pinta como si no tuviera nada que revisar.
function groupLoad(g) {
  return (g.conflicts || 0) + (g.unsupported || 0) + (g.ai_suggested || 0)
    + (g.reclasificado || 0) + (g.peso_talla || 0) + (g.notebooklm || 0);
}

function groupCard(g) {
  const done = state.queue.items.filter((i) => i.group === g.group && isDecided(i.id)).length;
  const total = groupLoad(g);
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
    el('div', { class: 'big' }, total,
      el('small', {}, 'celdas por revisar')),
    el('div', { class: 'meta' },
      el('span', {}, `${g.conflicts || 0} discrepan`),
      el('span', {}, `${g.unsupported || 0} sin respaldo`),
      g.ai_suggested ? el('span', {}, `${g.ai_suggested} sugerencias`) : null,
      g.reclasificado ? el('span', {}, `${g.reclasificado} reclasificadas`) : null,
      g.peso_talla ? el('span', {}, `${g.peso_talla} peso-talla`) : null,
      g.notebooklm ? el('span', {}, `${g.notebooklm} NotebookLM`) : null),
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
    ['reclasificado', 'Reclasificadas'],
    ['peso_talla', 'Peso-talla'],
    ['notebooklm', 'NotebookLM'],
  ].map(([key, label]) => {
    const n = all.filter((i) => (i.tipo || 'conflicto') === key).length;
    return el('button', {
      class: 'chip', 'aria-pressed': f.tipo === key,
      title: key === 'sin_respaldo'
        ? 'Otra búsqueda afirma un valor que la corrida con evidencia (B6) no encontró en el corpus'
        : (key === 'sugerencia_ia'
            ? 'Inferencia taxonómica del modelo, sin respaldo documental: hipótesis a validar'
            : key === 'reclasificado'
            ? 'Valor que ya existía, repartido desde Von_bertalanffy_a/b a la columna que le corresponde'
            : key === 'peso_talla'
            ? 'li_a / li_b extraídos del corpus con cita textual, después de corregir la definición que las búsquedas recibieron mal'
            : key === 'notebooklm'
            ? 'Leído por NotebookLM en dos notebooks con literatura que el índice FAISS no tiene. Corpus externo: no reproducible desde el repo'
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
    el('div', { class: 'pl', title: item.param_hint || null },
      el('b', {}, item.param_label), item.unit ? ` (${item.unit})` : '',
      item.critical_param ? el('div', { class: 'fam' }, '★ parámetro clave para Atlantis') : null),
    valueChips(item),
    el('div', { style: 'display:flex;gap:6px;align-items:center' },
      item.tipo === 'sugerencia_ia'
        ? el('span', { class: 'badge ia', title: 'Inferencia taxonómica, sin respaldo documental' }, 'sugerencia IA')
        : item.tipo === 'reclasificado'
        ? el('span', { class: 'badge rc', title: 'Valor existente, movido a su columna real' }, 'reclasificada')
        : item.tipo === 'peso_talla'
        ? el('span', { class: 'badge lw', title: 'Extraído del corpus con cita textual' }, 'peso-talla')
        : item.tipo === 'notebooklm'
        ? el('span', {
            class: `badge nb${item.nblm_suggestion?.discrepancia ? ' crit' : ''}`,
            title: item.nblm_suggestion?.discrepancia
              ? 'Los dos notebooks dan valores distintos'
              : 'Leído por NotebookLM en un corpus externo al repo',
          }, item.nblm_suggestion?.discrepancia ? 'NotebookLM · discrepan' : 'NotebookLM')
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

  // ── reparto de esquema ───────────────────────────────────────────────
  // Aquí no hay valor nuevo: es el mismo número que ya estaba en el CSV, sólo
  // que en la columna equivocada. Lo que se revisa no es el dato, es la lectura
  // de a qué cantidad corresponde.
  const rc = item.reclass_suggestion;
  if (rc) {
    body.append(
      el('h4', {}, 'Reparto de esquema ',
        el('span', { class: `conf conf-${rc.confidence}` }, `confianza ${rc.confidence}`)),
      el('div', { class: 'rc-box' },
        el('div', {}, el('b', {}, fmt(rc.value, item.kind)),
          el('span', { class: 'hint' }, ` · ${rc.scope}`)),
        el('div', { class: 'paper-grid', style: 'margin-top:8px' },
          el('span', { class: 'pk' }, 'Columna de origen'),
          el('span', { class: 'pv' }, rc.from_column),
          el('span', { class: 'pk' }, 'Búsquedas que lo aportaron'),
          el('span', { class: 'pv' }, Object.entries(rc.from_searches || {})
            .map(([k, v]) => `${k}=${v}`).join(' · ') || '—')),
        el('p', { style: 'margin:8px 0 0;font-size:13px;line-height:1.55' }, rc.rationale),
        el('div', { class: 'hint', style: 'margin-top:10px' },
          'El número ya existía: ', el('b', {}, 'lo que se propone es la columna, no el valor'),
          '. La causa fue la definición que recibió el extractor —«Von Bertalanffy '
          + 'coefficient a», que no existe: la ecuación tiene L∞, K y t₀—, así que cada '
          + 'búsqueda la resolvió a su manera. Confirma que la cantidad es la que dice.'),
        el('button', { class: 'chip', style: 'margin-top:10px',
          onclick: () => fillDecision(item.id, rc.value, 'reclasificado') }, 'Usar este valor')));
  }

  // ── peso-talla extraído del corpus ───────────────────────────────────
  // A diferencia del reparto de esquema, aquí sí hay dato nuevo: un número que
  // estaba en los papers y que la extracción original tiró por no tener dónde
  // ponerlo. Lo que se revisa es la cita — que sea de esta especie y que traiga
  // las unidades de W y L, sin las cuales una «a» no significa nada.
  const lw = item.lw_suggestion;
  if (lw) {
    body.append(
      el('h4', {}, 'Peso-talla extraído del corpus ',
        el('span', { class: `conf conf-${lw.confidence}` }, `confianza ${lw.confidence}`)),
      el('div', { class: 'lw-box' },
        el('div', {}, el('b', {}, fmt(lw.value, 'num')),
          el('span', { class: 'hint' }, ` · ${lw.scope}`),
          lw.unit ? null : el('span', { class: 'badge crit', style: 'margin-left:8px' }, 'sin unidades')),
        el('div', { class: 'paper-grid', style: 'margin-top:8px' },
          el('span', { class: 'pk' }, 'Unidades'),
          el('span', { class: 'pv' }, lw.unit || '— el paper no las declara'),
          el('span', { class: 'pk' }, 'Fuente'),
          el('span', { class: 'pv' }, (lw.citations || []).map((c) => c.ref).join(' · ') || '—'),
          lw.n_records ? el('span', { class: 'pk' }, 'n') : null,
          lw.n_records ? el('span', { class: 'pv' }, String(lw.n_records)) : null),
        lw.quote ? el('blockquote', { class: 'quote' }, lw.quote) : null,
        el('p', { style: 'margin:8px 0 0;font-size:13px;line-height:1.55' }, lw.rationale),
        el('div', { class: 'hint', style: 'margin-top:10px' },
          'Extraído del corpus, ', el('b', {}, 'no inferido'),
          '. Comprueba dos cosas en la cita: que hable de ', el('i', {}, item.species),
          ' y no de otra especie con el mismo epíteto, y que declare en qué unidades '
          + 'van W y L — el mismo pez tiene una «a» mil veces distinta según si el '
          + 'peso va en gramos o kilos.'),
        el('button', { class: 'chip', style: 'margin-top:10px',
          onclick: () => fillDecision(item.id, lw.value, 'peso_talla') }, 'Usar este valor')));
  }

  // ── NotebookLM ───────────────────────────────────────────────────────
  // El canal más externo: su corpus no está en este repo y la respuesta no se
  // puede reproducir desde aquí. Por eso la tarjeta no muestra un número, sino
  // lo que dijo CADA notebook con su frase y su documento. Si discrepan, se ve
  // primero: esa discrepancia es la información, no un estorbo que promediar.
  const nb = item.nblm_suggestion;
  if (nb) {
    body.append(
      el('h4', {}, 'NotebookLM ',
        el('span', { class: `conf conf-${nb.confidence}` }, `confianza ${nb.confidence}`),
        nb.discrepancia
          ? el('span', { class: 'badge crit', style: 'margin-left:8px' },
              `los notebooks discrepan ${Math.round(nb.acuerdo_pct)}%`)
          : null),
      el('div', { class: 'nb-box' },
        el('div', {}, el('b', {}, fmt(nb.value, item.kind)),
          nb.unit ? el('span', { class: 'hint' }, ` ${nb.unit}`) : null,
          el('span', { class: 'hint' }, ` · ${nb.scope}`)),
        el('div', { style: 'margin-top:10px;display:grid;gap:8px' },
          (nb.notebooks || []).map((src) => el('div', { class: 'nb-src' },
            el('div', {},
              el('span', { class: 'nb-alias' }, src.alias),
              el('b', { style: 'margin-left:8px' }, fmt(src.value, item.kind)),
              src.unit ? el('span', { class: 'hint' }, ` ${src.unit}`) : null,
              src.n ? el('span', { class: 'hint' }, ` · n = ${src.n}`) : null,
              src.scope ? el('span', { class: 'hint' }, ` · ${src.scope}`) : null),
            el('div', { class: 'hint', style: 'margin-top:4px' },
              src.source_title
                ? ['Fuente: ', el('b', {}, src.source_title)]
                : el('span', { class: 'badge crit' }, 'sin fuente identificada')),
            src.quote ? el('blockquote', { class: 'quote' }, src.quote) : null))),
        el('p', { style: 'margin:10px 0 0;font-size:13px;line-height:1.55' }, nb.rationale),
        el('div', { class: 'hint', style: 'margin-top:10px' },
          'Corpus externo a este repositorio: ', el('b', {}, 'la respuesta no es reproducible desde aquí'),
          ' y la librería que la obtiene no es oficial de Google. Lo único '
          + 'comprobable es la cita — léela antes de aceptar. Un valor «sin fuente '
          + 'identificada» es una afirmación del asistente, no un dato de la literatura.'),
        el('button', { class: 'chip', style: 'margin-top:10px',
          onclick: () => fillDecision(item.id, nb.value, 'NotebookLM') }, 'Usar este valor')));
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
                   ...(item.ai_suggestion ? ['IA'] : []),
                   ...(item.lw_suggestion ? ['peso_talla'] : []),
                   ...(item.nblm_suggestion ? ['NotebookLM'] : []), 'manual', 'ninguna'];

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

  // La matriz se calcula en el servidor a partir de las decisiones: acabamos de
  // cambiar una, así que la copia en memoria ya no vale.
  state.matrix = null;
  if (status === 'pending') delete state.decisions[item.id];
  else state.decisions[item.id] = { ...payload, updated_at: new Date().toISOString().slice(0, 19) };
  toast(status === 'pending' ? 'Celda reabierta' : `Guardado: ${STATUS_LABEL[status]}`);
  state.open.delete(item.id);
  render();
}

// ── exportación y navegación ───────────────────────────────────────────

// Ambos botones regeneran el export y bajan uno de los dos CSV. La matriz es lo
// que consume Atlantis; la procedencia es la tabla larga con una fila por celda
// —valor, estado, búsquedas de respaldo, revisor y referencia— que es la que
// permite auditar de dónde salió cada número.
async function exportCsv(kind = 'consolidado') {
  const esProv = kind === 'procedencia';
  const btn = $(esProv ? '#btn-export-prov' : '#btn-export');
  const etiqueta = esProv ? 'Tabla completa' : 'Exportar CSV';
  btn.disabled = true; btn.textContent = esProv ? 'Generando…' : 'Exportando…';
  try {
    const res = await fetch('/api/export', { method: 'POST' });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    const parts = Object.entries(data.by_status || {}).map(([k, v]) => `${k}: ${v}`).join(' · ');
    const archivo = esProv ? data.provenance_csv : data.csv;
    toast(`${data.cells} celdas → ${archivo}  (${parts})`, 6000);
    window.open(`/api/export/download?kind=${kind}`, '_blank');
  } catch (err) {
    toast('Error al exportar');
  } finally {
    btn.disabled = false; btn.textContent = etiqueta;
  }
}

function go(route) {
  state.route = route;
  state.open.clear();
  location.hash = route.view === 'group' ? `#g=${encodeURIComponent(route.group)}`
    : route.view === 'fbGroup' ? `#fb=${encodeURIComponent(route.group)}`
    : route.view === 'fb' ? '#fb'
    : route.view === 'matrix' ? '#m' : '';
  render();
  window.scrollTo(0, 0);
}

function readHash() {
  const g = location.hash.match(/^#g=(.*)$/);
  const f = location.hash.match(/^#fb=(.*)$/);
  if (f) state.route = { view: 'fbGroup', group: decodeURIComponent(f[1]) };
  else if (location.hash === '#fb') state.route = { view: 'fb', group: null };
  else if (location.hash === '#m') state.route = { view: 'matrix', group: null };
  else if (g) state.route = { view: 'group', group: decodeURIComponent(g[1]) };
  else state.route = { view: 'home', group: null };
}

function render() {
  if (!state.queue) return;
  const t = state.queue.totals;
  $('#subtitle').textContent =
    `${t.conflicts} celdas en conflicto · ${t.species} especies · ${state.queue.searches.join('/')} · cola del ${state.queue.generated_at.slice(0, 10)}`;
  if (state.route.view === 'matrix') renderMatrix();
  else if (state.route.view === 'fb') renderFishbase();
  else if (state.route.view === 'fbGroup') renderFishbaseGroup();
  else if (state.route.view === 'group') renderGroup();
  else renderHome();
}

// ── arranque ───────────────────────────────────────────────────────────

$('#btn-export').addEventListener('click', () => exportCsv('consolidado'));
$('#btn-export-prov').addEventListener('click', () => exportCsv('procedencia'));
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

// ── página de FishBase ─────────────────────────────────────────────────
// Separada de la cola de revisión. La cola dirime celda a celda —qué búsqueda
// tiene razón, si el corpus lo respalda—, y con FishBase esa pregunta no
// aplica: son valores curados y coherentes entre sí. Lo que hace falta aquí es
// ver la especie completa de un vistazo y decidir por lotes.

async function loadFishbase() {
  const r = await fetch('/api/fishbase');
  if (!r.ok) {
    // 404 aquí casi siempre significa lo mismo: el proceso del servidor lleva
    // días arrancado y no tiene estas rutas. Los estáticos sí se releen del
    // disco, así que se ve el botón nuevo contra una API vieja. Decirlo ahorra
    // buscar el fallo en el sitio equivocado.
    fbError = r.status === 404
      ? 'El servidor no conoce /api/fishbase. Reinícialo para que cargue las rutas nuevas:\n'
        + '  ./scripts/phase_7_review/run_review.sh 8600'
      : `El servidor respondió ${r.status} al pedir /api/fishbase.`;
    return;
  }
  fbError = null;
  state.fb = await r.json();
}

let fbError = null;

// Un fallo de carga tiene que verse en la página, no sólo en un aviso que se
// desvanece: si no, el síntoma es «no pasa nada al pulsar» y no se sabe dónde
// mirar.
function fbErrorView(volverA) {
  return el('div', {},
    el('div', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:16px' },
      el('button', { class: 'ghost', onclick: () => go(volverA) }, '← Volver'),
      el('h2', { style: 'margin:0;font-size:18px' }, 'No se pudo cargar FishBase')),
    el('div', { class: 'warn-note' },
      el('b', {}, 'La página no está disponible en este servidor. '),
      el('pre', { style: 'white-space:pre-wrap;margin:8px 0 0;font-size:12px' }, fbError)));
}

async function renderFishbase() {
  if (!state.fb) {
    await loadFishbase();
    if (!state.fb) { $('#view').replaceChildren(fbErrorView({ view: 'home' })); return; }
  }
  const f = state.fb;
  const t = f.totals;
  const pct = t.cells ? Math.round(t.accepted / t.cells * 100) : 0;

  const cabecera = el('div', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:16px' },
    el('button', { class: 'ghost', onclick: () => go({ view: 'home' }) }, '← Revisión'),
    el('h2', { style: 'margin:0;font-size:18px' }, 'Parámetros de FishBase'),
    el('span', { class: 'hint' }, `${t.accepted} de ${t.cells} celdas aceptadas · ${pct}%`));

  const kpis = el('div', { class: 'kpis' },
    kpi(t.cells, 'Celdas propuestas', `${f.groups.length} grupos · ${t.species} especies`),
    kpi(t.region || 0, 'Medidas en la región',
        'Golfo de California, Pacífico mexicano u oriental'),
    kpi(t.accepted, 'Aceptadas', 'ya son dato al exportar'),
    kpi(t.rejected, 'Descartadas', 'no se escriben en el CSV'),
    kpi(t.cells - t.accepted - t.rejected - (t.locked || 0), 'Sin revisar', 'la celda queda vacía'),
    t.locked ? kpi(t.locked, 'Decididas en la cola',
                   'ya resueltas con otra fuente · FishBase no las toca') : null);

  // El aprobado por procedencia. Vive aquí arriba y no dentro de cada grupo
  // porque la regla es la misma para todos: si el número se midió en el
  // sistema que se está modelando, revisarlo celda a celda no añade nada.
  const panelRegion = el('div', { class: 'region-panel' },
    el('div', {},
      el('b', {}, 'Validación por procedencia'),
      el('div', { class: 'hint', style: 'margin-top:4px;max-width:70ch' },
        'FishBase guarda dónde se midió cada registro. Cuando hay registros del '
        + 'Golfo de California, del Pacífico mexicano o del Pacífico oriental, el '
        + 'valor propuesto se calcula sólo con ellos y la celda se puede aprobar '
        + 'como validada sin ir al paper: la procedencia ya contesta la pregunta '
        + 'que hacía falta contestar.')),
    el('div', { class: 'spacer', style: 'flex:1' }),
    el('button', {
      class: 'primary', disabled: state.fbBusy || !t.region_pending,
      onclick: () => validarRegion({},
        `¿Aprobar como validadas las ${t.region_pending} celdas medidas en la región?\n\n`
        + 'Sólo las que traen localidad de medición; las clasificadas por el título '
        + 'del estudio se quedan pendientes. Las ya resueltas en la cola no se tocan.\n\n'
        + 'Se puede revertir en bloque con «Deshacer».'),
    }, `Validar ${t.region_pending || 0} celda(s) por región`),
    el('button', {
      class: 'ghost', disabled: state.fbBusy,
      onclick: () => validarRegion({ deshacer: true },
        '¿Reabrir todas las celdas aprobadas por procedencia?\n\n'
        + 'No toca las que aceptaste a mano.'),
    }, 'Deshacer'));

  const filas = f.groups.map((g) => {
    const revisado = g.accepted + g.rejected + (g.locked || 0);
    return el('tr', {},
      el('td', {}, el('b', {}, g.group)),
      el('td', { class: 'num' }, g.n_species),
      el('td', { class: 'num' }, g.cells),
      el('td', { class: 'num' }, g.region
        ? el('span', { class: 'badge region',
              title: `${g.region} celdas medidas en la región`
                   + (g.region_pending ? ` · ${g.region_pending} sin aprobar` : ' · todas resueltas') },
            g.region)
        : '—'),
      el('td', { class: 'num' }, g.accepted ? el('span', { class: 'badge done' }, g.accepted) : '—'),
      el('td', { class: 'num' }, g.rejected || '—'),
      el('td', { class: 'num' }, g.locked
        ? el('span', { class: 'badge', title: 'Resueltas en la cola de revisión con otra fuente' }, g.locked)
        : '—'),
      el('td', {},
        el('div', { class: 'progress', style: 'margin:0' },
          el('i', { style: `width:${g.cells ? Math.round(revisado / g.cells * 100) : 0}%` }))),
      el('td', {}, el('button', { class: 'chip',
        onclick: () => go({ view: 'fbGroup', group: g.group }) }, 'Ver tabla →')));
  });

  $('#view').replaceChildren(
    cabecera,
    kpis,
    el('div', { class: 'warn-note', style: 'margin:16px 0' },
      el('b', {}, 'Estos valores no salen del corpus ni los dedujo el modelo. '),
      f.warning || ''),
    panelRegion,
    el('div', { class: 'tablewrap' },
      el('table', { class: 'fbtable' },
        el('thead', {}, el('tr', {},
          el('th', {}, 'Grupo'), el('th', { class: 'num' }, 'Especies'),
          el('th', { class: 'num' }, 'Celdas'),
          el('th', { class: 'num', title: 'Con localidad de medición en la región modelada' }, 'Regionales'),
          el('th', { class: 'num' }, 'Aceptadas'),
          el('th', { class: 'num' }, 'Descartadas'),
          el('th', { class: 'num' }, 'En la cola'),
          el('th', {}, 'Avance'), el('th', {}, ''))),
        el('tbody', {}, filas))),
    el('p', { class: 'hint', style: 'margin-top:14px' },
      `Fuente: ${f.source || 'FishBase'} · generado el ${(f.generated_at || '').slice(0, 10)}`));
}

async function renderFishbaseGroup() {
  const group = state.route.group;
  if (!state.fbGroup || state.fbGroup.group !== group) {
    const r = await fetch(`/api/fishbase/group/${encodeURIComponent(group)}`);
    if (!r.ok) {
      if (r.status === 404 && state.fb) { toast('Ese grupo no tiene sugerencias de FishBase'); go({ view: 'fb' }); return; }
      fbError = `El servidor respondió ${r.status} al pedir la tabla de «${group}».`
        + (r.status === 404 ? ' Si acabas de actualizar el código, reinicia el servidor.' : '');
      $('#view').replaceChildren(fbErrorView({ view: 'fb', group: null }));
      return;
    }
    state.fbGroup = await r.json();
  }
  const d = state.fbGroup;
  const celdas = d.species.flatMap((sp) => Object.values(sp.cells));
  const bloqueadas = celdas.filter((c) => c.locked).length;
  const aceptadas = celdas.filter((c) => c.status === 'accepted' && !c.locked).length;
  const descartadas = celdas.filter((c) => c.status === 'rejected' && !c.locked).length;
  const pendientes = celdas.length - aceptadas - descartadas - bloqueadas;
  const regPend = celdas.filter((c) => c.region && c.region_origin === 'localidad'
                                    && !c.status && !c.locked).length;

  const cabecera = el('div', { style: 'display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px' },
    el('button', { class: 'ghost', onclick: () => go({ view: 'fb' }) }, '← FishBase'),
    el('h2', { style: 'margin:0;font-size:18px' }, group),
    el('span', { class: 'hint' },
      `${d.species.length} especies · ${celdas.length} celdas · ${aceptadas} aceptadas`
      + (bloqueadas ? ` · ${bloqueadas} ya resueltas en la cola` : '')),
    el('div', { class: 'spacer', style: 'flex:1' }),
    el('button', {
      class: 'primary', disabled: state.fbBusy || !regPend,
      title: 'Sólo las celdas cuyo registro se midió en el Golfo de California, '
           + 'el Pacífico mexicano o el Pacífico oriental',
      onclick: () => validarRegion({ group },
        `¿Validar las ${regPend} celdas de «${group}» medidas en la región?\n\n`
        + 'El valor de cada una ya está calculado sólo con sus registros regionales.'),
    }, `Validar por región (${regPend})`),
    el('button', {
      class: 'ghost', disabled: state.fbBusy || !pendientes,
      onclick: () => decidirFB({ group }, 'accepted',
        `¿Aceptar las ${pendientes} celdas sin revisar de «${group}»?\n\n`
        + 'Se escribirán en el CSV al exportar, cada una con su SpecCode y su '
        + 'referencia primaria. Puedes revertirlo célula a célula después.'
        + (bloqueadas ? `\n\nLas ${bloqueadas} celdas ya resueltas en la cola de revisión `
           + 'no se tocan.' : '')),
    }, `Aceptar el grupo (${pendientes})`),
    el('button', {
      class: 'ghost', disabled: state.fbBusy || !(aceptadas + descartadas),
      onclick: () => decidirFB({ group }, 'pending',
        `¿Reabrir las ${aceptadas + descartadas} celdas ya revisadas de «${group}»?`),
    }, 'Reabrir el grupo'));

  const encabezados = [el('th', {}, 'Especie')]
    .concat(d.params.map((p) => el('th', { class: 'num', title: p.hint || null },
      p.label, p.unit ? el('small', {}, ` (${p.unit})`) : null)))
    .concat([el('th', {}, '')]);

  const filas = d.species.map((sp) => {
    const suyas = Object.values(sp.cells);
    const pend = suyas.filter((c) => !c.status && !c.locked).length;
    return el('tr', {},
      el('td', { class: 'sp' }, sp.species,
        sp.speccode ? el('div', { class: 'fam' }, `SpecCode ${sp.speccode}`) : null),
      ...d.params.map((p) => celdaFB(sp.cells[p.key])),
      el('td', {}, el('button', {
        class: 'chip', disabled: state.fbBusy || !pend,
        onclick: () => decidirFB({ ids: suyas.filter((c) => !c.status && !c.locked).map((c) => c.id) },
          'accepted', null),
      }, pend ? `Aceptar ${pend}` : '✓')));
  });

  $('#view').replaceChildren(
    cabecera,
    el('div', { class: 'tablewrap' },
      el('table', { class: 'fbtable fbparams' },
        el('thead', {}, el('tr', {}, ...encabezados)),
        el('tbody', {}, filas))),
    el('p', { class: 'hint', style: 'margin-top:14px' },
      'Cada celda muestra el valor propuesto. Si viene de varios registros, el '
      + 'número pequeño es cuántos: pasa el cursor para ver el rango observado y '
      + 'la referencia primaria. Verde = aceptada; tachada = descartada.'));
}

// Marca corta de procedencia en la celda. El nivel importa: un t₀ del Golfo
// describe el sistema modelado; uno de Perú, el mismo océano bajo otro régimen.
const SIGLA_REGION = {
  golfo_california: 'GC', pacifico_mexicano: 'PM', pacifico_oriental: 'PO',
};

// Una celda de la tabla: valor, cuántos registros lo sostienen y su estado.
function celdaFB(c) {
  if (!c) return el('td', { class: 'num vacia' }, '—');
  if (c.locked) {
    // Resuelta en la cola con otra fuente. Se muestra lo que se decidió allí,
    // no lo que propone FishBase, y no se ofrece ningún botón: deshacer una
    // decisión humana desde aquí sería justo lo que no debe poder hacerse.
    return el('td', { class: 'num lock',
      title: `Resuelta en la cola de revisión por ${c.reviewer || '—'} `
           + `(fuente ${c.source}). FishBase proponía ${c.value}${c.unit ? ' ' + c.unit : ''}.` },
      el('span', {}, fmt(c.decided_value, 'num')), el('span', { class: 'lockicon' }, '🔒'));
  }
  const clase = `num${c.status === 'accepted' ? ' ok' : c.status === 'rejected' ? ' no' : ''}`;
  const evid = (c.region_evidence || [])
    .map((e) => `    ${e.locality || '(sin localidad)'}${e.origen === 'referencia'
                 ? ` — por el título del estudio: «${e.fragmento}»` : ''}`);
  const detalle = [
    `${c.value}${c.unit ? ' ' + c.unit : ''}`,
    c.observed_range ? `rango observado: ${c.observed_range[0]} – ${c.observed_range[1]}` : null,
    `${c.n_records} registro(s) · confianza ${c.confidence}`,
    c.region ? `procedencia: ${c.region_label} (${c.region_n} de ${c.region_of} registros)`
             : 'FishBase no dice dónde se midió',
    ...evid,
    c.region && c.value_global != null && c.value_global !== c.value
      ? `mediana mundial (no se usa): ${c.value_global}` : null,
    ...(c.citations || []).map((x) => x.ref),
  ].filter(Boolean).join('\n');
  return el('td', { class: clase, title: detalle },
    el('span', { class: `fbval conf-${c.confidence}` }, fmt(c.value, 'num')),
    c.n_records > 1 ? el('sup', { class: 'nrec' }, c.n_records) : null,
    c.region ? el('span', {
      class: `reg reg-${c.region}${c.region_origin === 'referencia' ? ' weak' : ''}`,
    }, SIGLA_REGION[c.region] || '·') : null,
    el('div', { class: 'cellbtns' },
      el('button', {
        class: 'mini', title: 'Aceptar esta celda', disabled: state.fbBusy,
        onclick: (e) => { e.stopPropagation(); decidirFB({ ids: [c.id] }, 'accepted', null); },
      }, '✓'),
      el('button', {
        class: 'mini', title: 'Descartar esta celda', disabled: state.fbBusy,
        onclick: (e) => { e.stopPropagation(); decidirFB({ ids: [c.id] }, 'rejected', null); },
      }, '✕')));
}

// Aprobación por procedencia: la regla la aplica el servidor, aquí sólo se
// pide y se cuenta. Deshacer sólo alcanza a lo que aprobó esta regla.
async function validarRegion(objetivo, confirmacion) {
  const reviewer = $('#reviewer').value.trim();
  if (!objetivo.deshacer && !reviewer) {
    toast('Escribe tu nombre de revisor arriba'); $('#reviewer').focus(); return;
  }
  if (confirmacion && !window.confirm(confirmacion)) return;
  state.fbBusy = true;
  try {
    const r = await fetch('/api/fishbase/validate-region', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...objetivo, reviewer }),
    });
    if (!r.ok) {
      toast(r.status === 404
        ? 'El servidor no conoce esta ruta todavía: reinícialo'
        : 'No se pudo validar');
      return;
    }
    const res = await r.json();
    if (res.undone) {
      toast(`${res.cells} celda(s) reabiertas`);
    } else {
      const detalle = Object.entries(res.by_level || {})
        .map(([k, v]) => `${SIGLA_REGION[k] || k}=${v}`).join(' · ');
      toast(`${res.cells} celda(s) validadas por procedencia`
            + (detalle ? ` (${detalle})` : '')
            + (res.skipped ? ` · ${res.skipped} intactas (ya resueltas en la cola)` : ''));
      localStorage.setItem('reviewer', reviewer);
    }
    state.fb = null;
    state.fbGroup = null;
    state.matrix = null;
  } finally {
    state.fbBusy = false;
  }
  render();
}

async function decidirFB(objetivo, status, confirmacion) {
  const reviewer = $('#reviewer').value.trim();
  if (status !== 'pending' && !reviewer) {
    toast('Escribe tu nombre de revisor arriba'); $('#reviewer').focus(); return;
  }
  if (confirmacion && !window.confirm(confirmacion)) return;
  state.fbBusy = true;
  try {
    const r = await fetch('/api/fishbase/decide', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...objetivo, status, reviewer }),
    });
    if (!r.ok) { toast('No se pudo guardar'); return; }
    const res = await r.json();
    const verbo = status === 'accepted' ? 'aceptadas'
                : status === 'rejected' ? 'descartadas' : 'reabiertas';
    toast(`${res.cells} celda(s) ${verbo}`
          + (res.skipped ? ` · ${res.skipped} intactas (ya resueltas en la cola)` : ''));
    localStorage.setItem('reviewer', reviewer);
    state.fb = null;            // los contadores del índice cambiaron
    state.fbGroup = null;       // y la tabla también
    state.matrix = null;        // y lo que se exportaría
  } finally {
    state.fbBusy = false;
  }
  render();
}

// ── página de todos los parámetros ─────────────────────────────────────
// Las otras vistas miran una celda a la vez: son para decidir. Ésta es para
// ver. Una fila por especie, una columna por parámetro, y el estado de
// procedencia en el color — que es la pregunta que el modelador se hace antes
// de alimentar Atlantis: ¿de dónde salió cada número, y cuánto falta?
//
// El valor y su estado salen de la MISMA consolidate() que escribe el CSV, así
// que esta tabla no es un resumen aparte que pueda desincronizarse: es lo que
// se exportaría si se pulsara «Exportar CSV» ahora mismo.

// Estado de procedencia → cómo se pinta y qué significa. El orden es el de la
// leyenda, de más respaldado a menos.
const ESTADOS = {
  acuerdo:                  { cls: 'st-ok',     lbl: 'Acuerdo entre búsquedas' },
  validado_region:          { cls: 'st-ok',     lbl: 'Validado · medido en la región' },
  validado_region_cita:     { cls: 'st-rev',    lbl: 'Validado · literatura de la región' },
  revisado:                 { cls: 'st-rev',    lbl: 'Revisado' },
  revisado_fuente_externa:  { cls: 'st-rev',    lbl: 'Revisado · fuente externa' },
  revisado_fishbase:        { cls: 'st-rev',    lbl: 'Revisado · FishBase' },
  revisado_sugerencia_ia:   { cls: 'st-rev',    lbl: 'Revisado · sugerencia de IA' },
  revisado_reclasificacion: { cls: 'st-rev',    lbl: 'Revisado · reparto de esquema' },
  revisado_peso_talla:      { cls: 'st-rev',    lbl: 'Revisado · peso-talla del corpus' },
  revisado_notebooklm:      { cls: 'st-rev',    lbl: 'Revisado · NotebookLM' },
  sin_corroborar:           { cls: 'st-solo',   lbl: 'Una sola búsqueda' },
  conflicto_pendiente:      { cls: 'st-confl',  lbl: 'Discrepan · consenso provisional' },
  sin_respaldo_b6:          { cls: 'st-norsp',  lbl: 'Sin respaldo de B6' },
  conflicto_sin_consenso:   { cls: 'st-vacia',  lbl: 'Empate: requiere decisión' },
  descartado:               { cls: 'st-vacia',  lbl: 'Descartado por el revisor' },
  fishbase_pendiente:       { cls: 'st-pend',   lbl: 'Propuesto · FishBase' },
  fishbase_rechazado:       { cls: 'st-vacia',  lbl: 'FishBase rechazado' },
  sugerencia_ia_pendiente:  { cls: 'st-pend',   lbl: 'Propuesto · IA' },
  reclasificado_pendiente:  { cls: 'st-pend',   lbl: 'Propuesto · reparto de esquema' },
  peso_talla_pendiente:     { cls: 'st-pend',   lbl: 'Propuesto · peso-talla del corpus' },
  notebooklm_pendiente:     { cls: 'st-pend',   lbl: 'Propuesto · NotebookLM' },
};
const estadoDe = (s) => ESTADOS[s] || { cls: 'st-pend', lbl: s };
const esPendiente = (s) => estadoDe(s).cls === 'st-pend';

let matrixError = null;

async function loadMatrix() {
  const r = await fetch('/api/matrix');
  if (!r.ok) {
    matrixError = r.status === 404
      ? 'El servidor no conoce /api/matrix. Reinícialo para que cargue las rutas nuevas:\n'
        + '  ./scripts/phase_7_review/run_review.sh 8600'
      : `El servidor respondió ${r.status} al pedir /api/matrix.`;
    return;
  }
  matrixError = null;
  state.matrix = await r.json();
}

function filasMatrix() {
  const f = state.mx;
  const needle = f.q.trim().toLowerCase();
  return state.matrix.rows.filter((r) => {
    if (f.group && r.group !== f.group) return false;
    if (f.soloConDato && !Object.values(r.cells).some((c) => c.value !== null)) return false;
    if (needle) {
      const hay = `${r.species} ${r.group} ${r.family} ${r.genus} ${r.order} ${r.class}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
}

async function renderMatrix() {
  if (!state.matrix) {
    $('#view').replaceChildren(el('p', { class: 'hint' }, 'Construyendo la tabla…'));
    await loadMatrix();
    if (!state.matrix) {
      $('#view').replaceChildren(el('div', {},
        el('div', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:16px' },
          el('button', { class: 'ghost', onclick: () => go({ view: 'home' }) }, '← Volver'),
          el('h2', { style: 'margin:0;font-size:18px' }, 'No se pudo cargar la tabla')),
        el('div', { class: 'warn-note' },
          el('pre', { style: 'white-space:pre-wrap;margin:0;font-size:12px' }, matrixError))));
      return;
    }
  }

  const m = state.matrix;
  const params = Object.entries(m.params);
  const filas = filasMatrix();
  const visibles = filas.flatMap((r) => Object.values(r.cells));
  const conDato = visibles.filter((c) => c.value !== null).length;
  const pendientes = visibles.filter((c) => esPendiente(c.status)).length;
  const cobertura = filas.length * params.length;

  const cabecera = el('div', { style: 'display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px' },
    el('button', { class: 'ghost', onclick: () => go({ view: 'home' }) }, '← Portada'),
    el('h2', { style: 'margin:0;font-size:18px' }, 'Todos los parámetros encontrados'),
    el('span', { class: 'hint' },
      `${filas.length} especies · ${conDato} celdas con dato de ${cobertura} posibles `
      + `(${cobertura ? Math.round(conDato / cobertura * 100) : 0} %)`
      + (state.mx.verPendientes ? ` · ${pendientes} propuestas sin aceptar` : '')));

  const grupos = [...new Set(m.rows.map((r) => r.group))].sort();
  const filtros = el('div', { class: 'filters' },
    el('select', { onchange: (e) => { state.mx.group = e.target.value; renderMatrix(); } },
      el('option', { value: '', selected: !state.mx.group }, `Todos los grupos (${grupos.length})`),
      ...grupos.map((g) => el('option', { value: g, selected: state.mx.group === g }, g))),
    el('input', {
      placeholder: 'Especie, género, familia…', value: state.mx.q,
      // Repintar diecisiete mil celdas en cada tecla se siente como un tirón:
      // se espera a que el revisor deje de escribir.
      oninput: (e) => {
        state.mx.q = e.target.value;
        clearTimeout(renderMatrix._t);
        renderMatrix._t = setTimeout(() => {
          renderMatrix();
          const caja = $('.filters input[placeholder^="Especie"]');
          if (caja) { caja.focus(); caja.setSelectionRange(caja.value.length, caja.value.length); }
        }, 220);
      },
    }),
    chk('Mostrar propuestas sin aceptar', state.mx.verPendientes,
        (v) => { state.mx.verPendientes = v; renderMatrix(); }),
    chk('Sólo especies con algún dato', state.mx.soloConDato,
        (v) => { state.mx.soloConDato = v; renderMatrix(); }));

  // Leyenda: sin ella la tabla es un campo de colores sin clave, y el color es
  // justamente lo que la hace útil.
  const vistos = new Set(visibles.map((c) => c.status));
  const leyenda = el('div', { class: 'mx-leyenda' },
    ...Object.entries(ESTADOS)
      .filter(([k]) => vistos.has(k) && (state.mx.verPendientes || !esPendiente(k)))
      .map(([k, v]) => el('span', { class: 'mx-lg' },
        el('i', { class: `mx-sw ${v.cls}` }), v.lbl)));

  const encabezados = [
    el('th', { class: 'mx-sticky mx-g' }, 'Grupo'),
    el('th', { class: 'mx-sticky mx-s' }, 'Especie'),
    ...params.map(([key, p]) => el('th', { class: 'num', title: p.hint || key },
      p.label, p.unit ? el('small', {}, ` (${p.unit})`) : null)),
  ];

  const cuerpo = filas.map((r) => el('tr', {},
    el('td', { class: 'mx-sticky mx-g' },
      el('button', {
        class: 'linkish', title: `Ir a la cola de revisión de «${r.group}»`,
        onclick: () => go({ view: 'group', group: r.group }),
      }, r.group)),
    el('td', { class: 'mx-sticky mx-s sp' }, r.species,
      r.family ? el('div', { class: 'fam' }, r.family) : null),
    ...params.map(([key, p]) => celdaMx(r.cells[key], p))));

  $('#view').replaceChildren(
    cabecera, filtros, leyenda,
    filas.length
      ? el('div', { class: 'tablewrap mx-wrap' },
          el('table', { class: 'fbtable mxtable' },
            el('thead', {}, el('tr', {}, ...encabezados)),
            el('tbody', {}, cuerpo)))
      : el('p', { class: 'hint' }, 'Ninguna especie coincide con el filtro.'),
    el('p', { class: 'hint', style: 'margin-top:14px' },
      'El valor y su color salen de la misma consolidación que escribe el CSV: '
      + 'esto es lo que se exportaría ahora mismo. Las propuestas sin aceptar van '
      + 'en gris y entre paréntesis — no están en el CSV, y no lo estarán hasta '
      + 'que alguien las revise. Pasa el cursor sobre una celda para ver de dónde '
      + 'sale.'));
}

function chk(label, valor, onchange) {
  const input = el('input', { type: 'checkbox', checked: valor || null,
                              onchange: (e) => onchange(e.target.checked) });
  return el('label', { class: 'mx-chk' }, input, label);
}

function celdaMx(c, meta) {
  if (!c) return el('td', { class: 'num vacia' }, '·');
  const est = estadoDe(c.status);
  const pend = esPendiente(c.status);

  if (pend && !state.mx.verPendientes) return el('td', { class: 'num vacia' }, '·');

  const detalle = [
    `${meta.label}${meta.unit ? ` (${meta.unit})` : ''}`,
    meta.hint || null,
    est.lbl,
    c.value !== null ? `valor: ${c.value}` : (c.proposed !== null ? `propuesto: ${c.proposed}` : null),
    c.searches ? `búsquedas: ${c.searches}` : null,
    c.reviewer ? `revisor: ${c.reviewer}` : null,
    c.note || null,
  ].filter(Boolean).join('\n');

  if (c.value === null) {
    const texto = c.proposed === null || c.proposed === undefined ? '—' : `(${fmt(c.proposed, meta.type)})`;
    return el('td', { class: `num ${est.cls}`, title: detalle }, texto);
  }
  return el('td', { class: `num ${est.cls}`, title: detalle }, fmt(c.value, meta.type));
}
