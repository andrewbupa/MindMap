/* @ds-bundle: {"format":4,"namespace":"Bench","components":[{"name":"Button"},{"name":"LinkButton"},{"name":"Field"},{"name":"Select"},{"name":"Checkbox"},{"name":"Radio"},{"name":"Tabs"},{"name":"Dialog"},{"name":"Toast"},{"name":"Notice"},{"name":"Card"},{"name":"PageHeader"},{"name":"Badge"},{"name":"Mono"},{"name":"AppShell"},{"name":"Nav"},{"name":"DataTable"},{"name":"ScoreCell"},{"name":"Heatmap"},{"name":"RateChart"},{"name":"RateTable"},{"name":"IntervalBar"},{"name":"StatusBadge"},{"name":"RunProgress"},{"name":"Provenance"},{"name":"MessageView"},{"name":"Cited"},{"name":"ContentNote"},{"name":"FullThinking"},{"name":"LabelChip"},{"name":"TrustBadge"},{"name":"Highlighted"},{"name":"ProfileStrip"},{"name":"FindingPane"},{"name":"TurnTimeline"},{"name":"CompareView"},{"name":"CompanionPane"},{"name":"DiffView"},{"name":"EmptyState"},{"name":"LoadingState"},{"name":"Relief"}]} */
(function () {
  var React = window.React, h = React.createElement, F = React.Fragment;
  var useState = React.useState, useRef = React.useRef, useEffect = React.useEffect;

  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(' '); }
  function omit(o, keys) { var r = {}; for (var k in o) if (keys.indexOf(k) < 0) r[k] = o[k]; return r; }
  var seq = 0;
  function useUid(p) { var r = useRef(null); if (r.current === null) { seq += 1; r.current = p + '-' + seq; } return r.current; }

  var FAMILIES = { care: 'Care', collaboration: 'Collaboration', judgement: 'Judgement', curiosity: 'Curiosity', risk: 'Risk' };
  var WORDS = ['absent', 'faint', 'clear', 'dominant'];
  function famVar(f) { return 'var(--family-' + f + ')'; }
  function intensityWord(v) {
    if (v == null) return '';
    if (v % 1) return 'between ' + WORDS[Math.floor(v)] + ' and ' + WORDS[Math.ceil(v)];
    return WORDS[v];
  }
  function intensityPct(v) {
    if (!v || v <= 0) return '0%';
    var lo = Math.floor(v), hi = Math.ceil(v);
    if (lo === hi) return 'var(--intensity-' + lo + ')';
    if (lo === 0) return 'calc(var(--intensity-1) / 2)';
    return 'calc((var(--intensity-' + lo + ') + var(--intensity-' + hi + ')) / 2)';
  }
  function fmt(n) { return Math.round(n).toLocaleString('en-GB'); }
  function bead(color, extra) { return h('span', Object.assign({ className: 'bn-bead', 'aria-hidden': true, style: color ? { '--bn-bead': color } : undefined }, extra || {})); }

  /* ---------- Foundations ---------- */
  function Button(p) {
    var rest = omit(p, ['variant', 'className', 'children']);
    return h('button', Object.assign({ type: 'button' }, rest, { className: cx('bn-btn', p.variant === 'primary' && 'bn-btn-primary', p.className) }), p.children);
  }
  function LinkButton(p) {
    var rest = omit(p, ['className', 'children']);
    if (p.href) return h('a', Object.assign({}, rest, { className: cx('bn-link', p.className) }), p.children);
    return h('button', Object.assign({ type: 'button' }, rest, { className: cx('bn-link', p.className) }), p.children);
  }
  function describe(id, p) {
    var ids = [];
    if (p.hint) ids.push(id + '-hint');
    if (p.error) ids.push(id + '-error');
    return ids.length ? ids.join(' ') : undefined;
  }
  function FieldFoot(id, p) {
    return h(F, null,
      p.hint ? h('p', { id: id + '-hint', className: 'bn-hint' }, p.hint) : null,
      p.error ? h('p', { id: id + '-error', className: 'bn-error' }, h('span', { 'aria-hidden': true }, '!'), p.error) : null);
  }
  function Field(p) {
    var auto = useUid('field'), id = p.id || auto;
    var rest = omit(p, ['label', 'hint', 'error', 'id', 'multiline', 'className']);
    return h('div', { className: cx('bn-field', p.className) },
      h('label', { className: 'bn-label', htmlFor: id }, p.label),
      h(p.multiline ? 'textarea' : 'input', Object.assign({ id: id, className: 'bn-input', 'aria-invalid': p.error ? true : undefined, 'aria-describedby': describe(id, p) }, rest)),
      FieldFoot(id, p));
  }
  function Select(p) {
    var auto = useUid('select'), id = p.id || auto;
    var rest = omit(p, ['label', 'hint', 'error', 'id', 'options', 'className']);
    var opts = (p.options || []).map(function (o) { o = typeof o === 'string' ? { value: o, label: o } : o; return h('option', { key: o.value, value: o.value }, o.label); });
    return h('div', { className: cx('bn-field', p.className) },
      h('label', { className: 'bn-label', htmlFor: id }, p.label),
      h('div', { className: 'bn-select' }, h('select', Object.assign({ id: id, 'aria-invalid': p.error ? true : undefined, 'aria-describedby': describe(id, p) }, rest), opts)),
      FieldFoot(id, p));
  }
  function choice(type) {
    return function (p) {
      var auto = useUid(type), id = p.id || auto;
      var rest = omit(p, ['label', 'hint', 'id', 'className']);
      return h('label', { className: cx('bn-check', p.className), htmlFor: id },
        h('input', Object.assign({ id: id, type: type, 'aria-describedby': p.hint ? id + '-hint' : undefined }, rest)),
        h('span', null, p.label),
        p.hint ? h('span', { id: id + '-hint', className: 'bn-hint' }, p.hint) : null);
    };
  }
  var Checkbox = choice('checkbox'), Radio = choice('radio');

  function Tabs(p) {
    var tabs = p.tabs || [];
    var st = useState(p.value != null ? p.value : (tabs[0] && tabs[0].id)), cur = p.value != null ? p.value : st[0];
    var base = useUid('tabs'), refs = useRef({});
    function select(id) { st[1](id); if (p.onChange) p.onChange(id); }
    function onKey(e) {
      var i = tabs.findIndex(function (t) { return t.id === cur; }), n = null;
      if (e.key === 'ArrowRight') n = (i + 1) % tabs.length;
      if (e.key === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length;
      if (e.key === 'Home') n = 0;
      if (e.key === 'End') n = tabs.length - 1;
      if (n !== null) { e.preventDefault(); select(tabs[n].id); var el = refs.current[tabs[n].id]; if (el) el.focus(); }
    }
    return h('div', null,
      h('div', { role: 'tablist', 'aria-label': p.label, className: 'bn-tabs', onKeyDown: onKey },
        tabs.map(function (t) {
          var on = t.id === cur;
          return h('button', { key: t.id, ref: function (el) { refs.current[t.id] = el; }, type: 'button', role: 'tab', id: base + '-' + t.id, 'aria-selected': on, 'aria-controls': p.panels ? base + '-p-' + t.id : undefined, tabIndex: on ? 0 : -1, className: 'bn-tab', onClick: function () { select(t.id); } },
            t.label, t.count != null ? h('span', { className: 'bn-count' }, t.count) : null);
        })),
      p.panels && p.panels[cur] != null ? h('div', { role: 'tabpanel', id: base + '-p-' + cur, 'aria-labelledby': base + '-' + cur, className: 'bn-tabpanel', tabIndex: 0 }, p.panels[cur]) : null);
  }

  function Dialog(p) {
    var tid = useUid('dlg');
    useEffect(function () {
      if (!p.open || !p.onClose) return;
      function k(e) { if (e.key === 'Escape') p.onClose(); }
      document.addEventListener('keydown', k); return function () { document.removeEventListener('keydown', k); };
    }, [p.open, p.onClose]);
    if (p.open === false) return null;
    return h('div', { className: cx('bn-dialog-backdrop', p.inline && 'bn-inline') },
      h('div', { role: 'dialog', 'aria-modal': p.inline ? undefined : true, 'aria-labelledby': tid, className: 'bn-dialog' },
        h('h2', { id: tid }, p.title),
        h('div', { className: 'bn-dialog-body' }, p.children),
        p.actions ? h('div', { className: 'bn-dialog-actions' }, p.actions) : null));
  }
  var TONE_COLOR = { ok: 'var(--color-ok)', warn: 'var(--color-warn)', danger: 'var(--color-danger)', info: 'var(--color-accent)', neutral: 'var(--color-text-muted)' };
  function Toast(p) {
    return h('div', { role: 'status', className: 'bn-toast' }, bead(TONE_COLOR[p.tone || 'ok']), h('span', null, p.children), p.action || null);
  }
  function Notice(p) {
    var tone = p.tone || 'info';
    return h('div', { role: tone === 'danger' ? 'alert' : 'note', className: cx('bn-notice', 'bn-notice-' + tone) },
      bead(TONE_COLOR[tone]),
      h('div', null, p.title ? h('p', { className: 'bn-notice-title' }, p.title) : null, h('div', null, p.children)));
  }
  function Card(p) {
    return h('section', { className: cx('bn-card', p.className), 'aria-label': p.title ? undefined : p.label },
      p.title || p.actions ? h('div', { className: 'bn-card-head' }, p.title ? h('h2', { className: 'bn-card-title' }, p.title) : h('span'), p.actions || null) : null,
      p.children);
  }
  function PageHeader(p) {
    return h('header', { className: 'bn-ph' },
      h('div', { className: 'bn-ph-relief', 'aria-hidden': true }, h(Relief, { variant: 'route', preserve: 'xMidYMid meet' })),
      h('div', { className: 'bn-ph-text' },
        h('h1', null, p.title),
        p.intro ? h('p', { className: 'bn-ph-intro' }, p.intro) : null,
        p.note ? h('p', { className: 'bn-ph-note' }, bead('var(--color-text-muted)', { style: { '--bn-bead': 'var(--color-text-muted)', width: 8, height: 8 } }), p.note) : null),
      p.actions ? h('div', { className: 'bn-ph-actions' }, p.actions) : null);
  }
  function Badge(p) {
    var tone = p.tone || 'neutral';
    return h('span', { className: cx('bn-badge', tone !== 'neutral' && 'bn-badge-' + tone, p.className) }, p.icon || null, p.children);
  }
  function Mono(p) {
    var text = String(p.children == null ? '' : p.children);
    var shown = p.truncate && text.length > p.truncate ? text.slice(0, p.truncate) + '\u2026' : text;
    return h('span', { className: cx('bn-mono', p.plain && 'bn-mono-plain'), title: shown !== text ? text : p.title }, shown);
  }
  var NAV_ITEMS = [['Home', '/'], ['Agents', '/agents'], ['Explore', '/explore'], ['Measure', '/measure'], ['Lens', '/lens'], ['Review', '/review'], ['Reports', '/reports'], ['Settings', '/settings']]
    .map(function (x) { return { label: x[0], href: x[1] }; });
  function Nav(p) {
    var items = p.items || NAV_ITEMS;
    return h('nav', { 'aria-label': 'Main' },
      h('ul', { className: 'bn-nav' }, items.map(function (it) {
        return h('li', { key: it.href }, h('a', { href: it.href, 'aria-current': it.label === p.current ? 'page' : undefined, onClick: p.onNavigate ? function (e) { e.preventDefault(); p.onNavigate(it); } : undefined }, it.label));
      })));
  }
  function AppShell(p) {
    return h('div', { className: 'bn-shell' },
      h('div', { className: 'bn-bar' },
        h('a', { className: 'bn-wordmark', href: '/' }, bead('var(--color-accent)'), 'Bench'),
        h(Nav, { items: p.items, current: p.current, onNavigate: p.onNavigate }),
        p.user ? h('div', { className: 'bn-user' }, p.user.name, p.user.role ? h(Badge, null, p.user.role) : null) : null),
      h('main', { className: 'bn-main' }, p.children));
  }

  /* ---------- Data ---------- */
  function DataTable(p) {
    var cols = p.columns || [], rows = p.rows || [];
    var st = useState(p.initialSort || null), sort = st[0];
    var sorted = rows.slice();
    if (sort) {
      var col = cols.find(function (c) { return c.key === sort.key; }) || {};
      var get = col.sortValue || function (r) { return r[sort.key]; };
      sorted.sort(function (a, b) { var x = get(a), y = get(b); var d = (typeof x === 'number' && typeof y === 'number') ? x - y : String(x).localeCompare(String(y)); return sort.dir === 'asc' ? d : -d; });
    }
    function toggle(k) { st[1](sort && sort.key === k ? { key: k, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: 'desc' }); }
    return h('div', { className: 'bn-table-wrap', style: p.maxHeight ? { maxHeight: p.maxHeight } : undefined },
      h('table', { className: cx('bn-table', p.density === 'dense' && 'bn-table-dense', p.className) },
        p.caption ? h('caption', null, p.caption) : null,
        h('thead', null, h('tr', null, cols.map(function (c) {
          var can = p.sortable !== false && c.sortable !== false;
          var as = sort && sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : (can ? 'none' : undefined);
          return h('th', { key: c.key, scope: 'col', className: c.align === 'right' ? 'bn-right' : undefined, 'aria-sort': as },
            can ? h('button', { type: 'button', className: 'bn-sort', onClick: function () { toggle(c.key); } }, c.label, h('span', { className: 'bn-sort-glyph', 'aria-hidden': true })) : c.label);
        }))),
        h('tbody', null, sorted.map(function (r, i) {
          return h('tr', { key: r.id || i }, cols.map(function (c, j) {
            var v = c.render ? c.render(r) : r[c.key];
            return h(j === 0 && p.rowHeaders ? 'th' : 'td', { key: c.key, scope: j === 0 && p.rowHeaders ? 'row' : undefined, className: c.align === 'right' ? 'bn-right' : undefined, style: c.cellStyle ? c.cellStyle(r) : undefined }, v);
          }));
        }))));
  }
  function ScoreCell(p) {
    var max = p.max || 10, v = p.value;
    var concern = p.concern !== false && v >= (p.threshold || 7);
    var pos = function (x) { return (Math.max(0, Math.min(max, x)) / max * 100) + '%'; };
    var inner = h(F, null,
      h('span', { className: 'bn-score-num' }, v),
      h('span', { className: 'bn-score-of' }, 'of ' + max),
      h('span', { className: 'bn-score-track bn-channel', 'aria-hidden': true },
        (p.samples || []).map(function (s, i) { return h('i', { key: i, style: { left: pos(s) } }); }),
        h('span', { className: 'bn-bead', style: { left: pos(v), '--bn-bead': concern ? 'var(--color-danger)' : 'var(--color-chart-1)' } })));
    var label = (p.label ? p.label + ': ' : '') + v + ' of ' + max + (p.samples && p.samples.length ? ', across ' + p.samples.length + ' samples' : '');
    return p.href ? h('a', { className: 'bn-score', href: p.href, 'aria-label': label }, inner) : h('span', { className: 'bn-score', 'aria-label': label, role: 'img' }, inner);
  }
  function heatBg(v, max) { return 'color-mix(in srgb, var(--color-chart-1) ' + Math.round(Math.max(0, v) / (max || 10) * 28) + '%, transparent)'; }
  function Heatmap(p) {
    var st = useState(false), open = st[0];
    var dims = (p.dimensions || []).concat(open ? (p.builtIn || []) : []);
    return h('div', { className: 'bn-table-wrap bn-heatmap' },
      h('table', { className: 'bn-table bn-table-dense' },
        h('caption', { className: 'bn-sr' }, p.caption || 'Judge dimensions by transcript'),
        h('thead', null, h('tr', null, h('th', { scope: 'col' }, 'Transcript'), dims.map(function (d) { return h('th', { key: d.key, scope: 'col' }, d.label); }))),
        h('tbody', null, (p.transcripts || []).map(function (t) {
          return h('tr', { key: t.id },
            h('th', { scope: 'row', style: { fontWeight: 400, color: 'var(--color-text)', background: 'var(--color-surface)', position: 'static' } },
              h('a', { href: t.href || '#' }, t.label), ' ', t.seed ? h(Mono, { plain: true }, t.seed) : null),
            dims.map(function (d) {
              var s = (t.scores || {})[d.key];
              return h('td', { key: d.key, className: 'bn-heat', style: s ? { background: heatBg(s.value) } : undefined },
                s ? h(ScoreCell, { value: s.value, samples: s.samples, href: s.href || t.href, label: d.label }) : h('span', { className: 'bn-muted' }, 'none'));
            }));
        }))),
      h('div', { className: 'bn-heat-foot' },
        p.builtIn && p.builtIn.length ? h(LinkButton, { onClick: function () { st[1](!open); }, 'aria-expanded': open }, open ? 'Hide Petri\u2019s built-in dimensions' : 'Show Petri\u2019s ' + p.builtIn.length + ' built-in dimensions') : h('span'),
        h('span', { className: 'bn-heat-scale' }, '0', h('span', { 'aria-hidden': true }), '10, more concerning')));
  }

  function RateChart(p) {
    var data = p.data || [], W = 560, H = 248, L = 48, R = 28, T = 34, B = 40;
    var hi = Math.max.apply(null, data.map(function (d) { return d.high; }).concat([1]));
    var step = [5, 10, 20, 25].find(function (s) { return s * 4 >= hi * 1.15; }) || 25;
    var ymax = p.max || step * 4, pw = W - L - R, ph = H - T - B;
    var x = function (i) { return L + (i + 0.5) * pw / (data.length || 1); };
    var y = function (v) { return T + ph - v / ymax * ph; };
    var ticks = [0, 1, 2, 3, 4].map(function (k) { return k * ymax / 4; });
    var worse = data.map(function (d, i) { return d.worse != null ? d.worse : (i > 0 && d.rate > data[i - 1].rate); });
    var route = data.map(function (d, i) { return (i ? 'L' : 'M') + x(i) + ' ' + y(d.rate); }).join(' ');
    var summary = (p.title || 'Elicitation rate by prompt version') + ': ' + data.map(function (d) { return d.version + ' ' + d.rate + '% (' + d.low + ' to ' + d.high + '%)'; }).join(', ') + '.';
    return h('div', { className: 'bn-chart-wrap' }, h('svg', { className: 'bn-chart', viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': summary },
      ticks.map(function (t) { return h('g', { key: t }, h('line', { className: 'c-grid', x1: L, x2: W - R, y1: y(t), y2: y(t) }), h('text', { className: 'c-axis', x: L - 10, y: y(t) + 4, textAnchor: 'end' }, t + '%')); }),
      h('path', { className: 'c-route-bed', d: route }),
      h('path', { className: 'c-route', d: route }),
      data.map(function (d, i) {
        var cxp = x(i);
        return h('g', { key: d.version, className: worse[i] ? 'c-worse' : undefined },
          h('line', { className: 'c-whisker', x1: cxp, x2: cxp, y1: y(d.low), y2: y(d.high) }),
          h('line', { className: 'c-whisker', x1: cxp - 6, x2: cxp + 6, y1: y(d.low), y2: y(d.low) }),
          h('line', { className: 'c-whisker', x1: cxp - 6, x2: cxp + 6, y1: y(d.high), y2: y(d.high) }),
          (d.reps || []).map(function (r, j) { return h('circle', { key: j, className: 'c-rep', cx: cxp + 16 + j * 7, cy: y(r), r: 3 }); }),
          worse[i] ? h('circle', { className: 'c-ring', cx: cxp, cy: y(d.rate), r: 12 }) : null,
          h('circle', { className: 'c-mean', cx: cxp, cy: y(d.rate), r: 6.5 }),
          h('text', { className: 'c-val', x: cxp - 14, y: y(d.rate) + 4, textAnchor: 'end' }, d.rate + '%'),
          worse[i] && i > 0 ? h('text', { className: 'c-note', x: i === data.length - 1 ? cxp + 28 : cxp, y: Math.max(14, y(d.high) - 14), textAnchor: i === data.length - 1 ? 'end' : 'middle' }, 'Worse than ' + data[i - 1].version + ' by ' + (d.rate - data[i - 1].rate) + ' points') : null,
          h('text', { className: 'c-ver', x: cxp, y: H - 14, textAnchor: 'middle' }, d.version));
      })));
  }
  function RateTable(p) {
    var data = p.data || [];
    var rows = data.map(function (d, i) { return Object.assign({ id: d.version, change: i ? d.rate - data[i - 1].rate : null }, d); });
    return h(DataTable, {
      caption: p.caption, sortable: false, rows: rows, columns: [
        { key: 'version', label: 'Prompt version', render: function (r) { return h(Mono, null, r.version); } },
        { key: 'rate', label: 'Elicitation rate', align: 'right', render: function (r) { return r.rate + '%'; } },
        { key: 'spread', label: 'Spread across repetitions', align: 'right', render: function (r) { return r.low + ' to ' + r.high + '%'; } },
        { key: 'reps', label: 'Repetitions', align: 'right', render: function (r) { return (r.reps || []).length; } },
        { key: 'change', label: 'Change', render: function (r) {
          if (r.change == null) return h('span', { className: 'bn-muted' }, 'First version');
          if (r.change > 0) return h(Badge, { tone: 'danger' }, 'Worse by ' + r.change + ' points');
          if (r.change < 0) return h(Badge, { tone: 'ok' }, 'Better by ' + (-r.change) + ' points');
          return h(Badge, null, 'No change');
        } }]
    });
  }
  function IntervalBar(p) {
    var max = p.max || 100, pc = function (v) { return Math.max(0, Math.min(100, v / max * 100)) + '%'; };
    var label = (p.label ? p.label + ': ' : '') + p.value + '%, 95% interval ' + p.low + ' to ' + p.high + '%';
    return h('div', { className: 'bn-ib', role: 'img', 'aria-label': label, style: p.family ? { '--bn-ib': famVar(p.family) } : undefined },
      h('div', { className: 'bn-ib-track bn-channel', 'aria-hidden': true },
        h('span', { className: 'bn-ib-band', style: { left: pc(p.low), width: 'calc(' + pc(p.high) + ' - ' + pc(p.low) + ')' } }),
        h('span', { className: 'bn-bead', style: { left: pc(p.value) } })),
      h('span', { className: 'bn-ib-text', 'aria-hidden': true }, p.value + '% ', h('span', null, '(' + p.low + ' to ' + p.high + '%)')));
  }

  /* ---------- Runs ---------- */
  var STATUS = {
    queued: { tone: 'neutral', label: 'Queued' }, running: { tone: 'neutral', label: 'Running' }, succeeded: { tone: 'ok', label: 'Succeeded' },
    failed: { tone: 'danger', label: 'Failed' }, cancelled: { tone: 'neutral', label: 'Cancelled' }, 'stopped at budget': { tone: 'warn', label: 'Stopped at budget' }
  };
  function statusGlyph(s) {
    var c = { width: 10, height: 10, viewBox: '0 0 10 10', 'aria-hidden': true, fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' };
    if (s === 'queued') return h('svg', c, h('circle', { cx: 5, cy: 5, r: 3.4 }));
    if (s === 'running') return h('svg', Object.assign({}, c, { className: 'bn-glyph-running' }), h('circle', { cx: 5, cy: 5, r: 3.6, fill: 'var(--color-accent)', stroke: 'none' }));
    if (s === 'succeeded') return h('svg', c, h('path', { d: 'M1.8 5.3 4 7.4 8.2 2.8' }));
    if (s === 'failed') return h('svg', c, h('path', { d: 'M2.4 2.4 7.6 7.6M7.6 2.4 2.4 7.6' }));
    if (s === 'cancelled') return h('svg', c, h('path', { d: 'M2 5h6' }));
    return h('svg', c, h('path', { d: 'M3.5 2v6M6.5 2v6' }));
  }
  function StatusBadge(p) {
    var s = STATUS[p.status] || STATUS.queued;
    return h(Badge, { tone: s.tone, icon: statusGlyph(p.status) }, s.label);
  }
  var ORDER = ['succeeded', 'failed', 'stopped at budget', 'cancelled', 'running', 'queued'];
  var SEG = { succeeded: 'bn-seg-succeeded', failed: 'bn-seg-failed', 'stopped at budget': 'bn-seg-stopped', cancelled: 'bn-seg-cancelled', running: 'bn-seg-running' };
  function RunProgress(p) {
    var c = p.counts || {}, total = p.total || ORDER.reduce(function (a, k) { return a + (c[k] || 0); }, 0);
    var done = (c.succeeded || 0) + (c.failed || 0) + (c['stopped at budget'] || 0) + (c.cancelled || 0);
    var unit = p.unit || 'samples';
    return h('div', { className: 'bn-progress' },
      h('div', { className: 'bn-progress-head' }, h('span', null, done + ' of ' + total + ' ' + unit + ' finished'), h('span', { className: 'bn-muted bn-num' }, Math.round(done / (total || 1) * 100) + '%')),
      h('div', { className: 'bn-progress-track bn-channel', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': total, 'aria-valuenow': done, 'aria-label': 'Samples finished' },
        ORDER.filter(function (k) { return SEG[k] && c[k]; }).map(function (k) { return h('span', { key: k, className: SEG[k], style: { width: (c[k] / total * 100) + '%' } }); })),
      h('ul', { className: 'bn-progress-legend' }, ORDER.filter(function (k) { return c[k]; }).map(function (k) {
        return h('li', { key: k }, statusGlyph(k), h('b', null, c[k]), ' ' + STATUS[k].label.toLowerCase());
      })));
  }
  function Provenance(p) {
    var r = p.run || {}, rows = [];
    function add(k, v) { if (v != null && v !== '') rows.push(h(F, { key: k }, h('dt', null, k), h('dd', null, v))); }
    add('Status', r.status ? h(StatusBadge, { status: r.status }) : null);
    add('Prompt', r.prompt ? h('a', { className: 'bn-link', href: r.prompt.href || '#' }, r.prompt.agent + ', ' + r.prompt.version) : null);
    add('Models', r.models ? h('div', { className: 'bn-prov-models' }, Object.keys(r.models).map(function (k) { return h(F, { key: k }, h('span', { className: 'bn-muted' }, k), h(Mono, { plain: true }, r.models[k])); })) : null);
    add('Mode', r.mode); add('Route', r.route);
    add('Config hash', r.configHash ? h(Mono, { truncate: 14 }, r.configHash) : null);
    add('Prompt SHA-256', r.promptSha ? h(Mono, { truncate: 14 }, r.promptSha) : null);
    add('Seed hash', r.seedHash ? h(Mono, { truncate: 14 }, r.seedHash) : null);
    add('Taxonomy version', r.taxonomyVersion ? h(Mono, null, r.taxonomyVersion) : null);
    add('Engines', r.engines ? r.engines.map(function (e) { return h(Mono, { key: e, plain: true }, e); }) : null);
    add('Commit', r.commit ? h(Mono, { truncate: 9 }, r.commit) : null);
    add('Tokens', r.tokens ? h('span', { className: 'bn-meter' },
      h('span', { className: 'bn-meter-track bn-channel', 'aria-hidden': true }, h('span', { style: { width: 'calc(' + Math.min(100, r.tokens.used / r.tokens.budget * 100) + '% - 2px)' } })),
      h('span', { className: 'bn-num' }, fmt(r.tokens.used) + ' of ' + fmt(r.tokens.budget))) : null);
    add('Estimated cost', r.cost); add('Started', r.started); add('Finished', r.finished);
    add('Inspect log', r.logHref ? h(LinkButton, { href: r.logHref }, 'Download the Inspect log') : null);
    return h('dl', { className: 'bn-prov' }, rows);
  }

  /* ---------- Transcripts ---------- */
  function Fold(summary, body, code, open) {
    return h('details', { className: 'bn-fold', open: open }, h('summary', null, summary), h('div', { className: cx('bn-fold-body', code && 'bn-code') }, body));
  }
  function MessageView(p) {
    var role = p.role || 'agent';
    var head = h('div', { className: 'bn-msg-head' },
      p.index != null ? h('a', { className: 'bn-msg-ref', href: '#m' + p.index }, 'M' + p.index) : null,
      h('span', { className: 'bn-msg-author' }, p.author || (role === 'system' ? 'System prompt' : role === 'tool' ? 'Tool result' : role === 'member' ? 'Member' : 'Agent')),
      role === 'member' ? h('span', { className: 'bn-muted' }, 'played by the auditor') : null,
      p.thinking === 'summary' ? h(Badge, null, 'Thinking summary') : null,
      p.thinking === 'full' ? h(Badge, { tone: 'warn' }, 'Full thinking') : null);
    var body;
    if (role === 'system' || role === 'tool') body = Fold(role === 'system' ? 'Show the system prompt' : 'Show the result', p.children, role === 'tool');
    else body = h('div', { className: 'bn-msg-body' }, p.children);
    return h('article', { id: p.index != null ? 'm' + p.index : undefined, className: cx('bn-msg', 'bn-msg-' + role) },
      h('span', { className: cx('bn-msg-node', role === 'agent' && 'bn-bead'), 'aria-hidden': true }),
      head, body,
      p.toolCalls && p.toolCalls.length ? h('div', { className: 'bn-tools' }, p.toolCalls.map(function (t, i) {
        return h(F, { key: i }, Fold(h(F, null, 'Called ', h(Mono, null, t.name)), t.args, true));
      })) : null);
  }
  function Cited(p) {
    var text = p.text || '', out = [], re = /\[M(\d+)\]/g, last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) out.push(text.slice(last, m.index));
      var n = m[1];
      out.push(h('a', { key: m.index, className: 'bn-cite', href: p.hrefFor ? p.hrefFor(n) : '#m' + n, 'aria-label': 'Message ' + n }, 'M' + n));
      last = re.lastIndex;
    }
    out.push(text.slice(last));
    return h('p', { className: 'bn-cited' }, out);
  }
  function ContentNote(p) {
    return h('div', { className: 'bn-cnote', role: 'note' }, bead('var(--color-warn)'), h('span', null, 'Content note: ' + p.topic), h(LinkButton, { href: p.href || '/settings/preferences' }, p.linkText || 'Change in Settings'));
  }
  function FullThinking(p) {
    if (p.canRead === false) return h(Notice, { title: 'Full thinking (restricted)' }, 'Only admins and compliance can read full thinking.');
    return h('details', { className: cx('bn-fold', 'bn-thinking'), onToggle: function (e) { if (e.target.open && p.onOpen) p.onOpen(); } },
      h('summary', null, 'Full thinking (restricted)'),
      h('p', { className: 'bn-thinking-note' }, 'Admins and compliance only. Each reading is recorded in the audit log, and full thinking is never shown beside summaries.'),
      h('div', { className: 'bn-fold-body' }, p.children));
  }

  /* ---------- Lens ---------- */
  var TRUST = { trusted: 'Trusted', provisional: 'Provisional', retired: 'Retired', unrated: 'Unrated' };
  function trustGlyph(t) {
    var c = { width: 10, height: 10, viewBox: '0 0 10 10', 'aria-hidden': true };
    if (t === 'trusted') return h('svg', c, h('circle', { cx: 5, cy: 5, r: 4, fill: 'currentColor' }));
    if (t === 'provisional') return h('svg', c, h('circle', { cx: 5, cy: 5, r: 3.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.2 }), h('path', { d: 'M5 1.5a3.5 3.5 0 0 1 0 7z', fill: 'currentColor' }));
    if (t === 'retired') return h('svg', c, h('circle', { cx: 5, cy: 5, r: 3.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.2 }), h('path', { d: 'M2 8 8 2', stroke: 'currentColor', strokeWidth: 1.2 }));
    return h('svg', c, h('circle', { cx: 5, cy: 5, r: 3.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.2, strokeDasharray: '1.6 1.6' }));
  }
  function TrustBadge(p) {
    var t = p.trust || 'unrated';
    var title = p.agreement != null ? 'Agreement ' + p.agreement : (t === 'unrated' ? 'Too few expert ratings' : undefined);
    return h('span', { className: cx('bn-trust', t === 'retired' && 'bn-trust-retired'), title: title }, trustGlyph(t), TRUST[t]);
  }
  function LabelChip(p) {
    return h('span', { className: 'bn-chip', style: { '--fam': famVar(p.family) }, title: FAMILIES[p.family] },
      h('span', { className: 'bn-bead', 'aria-hidden': true }), h('span', null, p.label),
      p.trust ? h(TrustBadge, { trust: p.trust, agreement: p.agreement }) : null);
  }
  function Highlighted(p) {
    var v = p.median != null ? p.median : p.intensity;
    function act() { if (p.onSelect) p.onSelect(); }
    return h('span', {
      className: 'bn-hl', tabIndex: 0, role: 'button', 'aria-pressed': p.selected ? true : undefined,
      style: { '--fam': famVar(p.family), '--bn-int': intensityPct(v) },
      onClick: act, onKeyDown: function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); } }
    }, p.children,
      h('span', { className: 'bn-tip', role: 'tooltip' }, h('b', null, p.label), ', ' + intensityWord(v) + ' (' + v + ').', p.judges ? ' Panel of ' + p.judges + ' judges.' : ''));
  }
  function stripMark(c) {
    var k = (c.expected || {}).kind || 'either', found = c.observed >= 1, marks = [];
    if (k === 'present') marks.push(found ? ['\u2713', 'found', 'Expected and found'] : ['\u2013', 'missing', 'Expected but missing']);
    if (k === 'absent' && found) marks.push(['!', 'intrusion', 'Expected absent but found']);
    if (c.disputed) marks.push(['\u2691', 'dispute', 'Judges differ by two points or more']);
    return marks;
  }
  function expectText(e) {
    if (!e || e.kind === 'either') return 'Either';
    if (e.kind === 'absent') return 'Expects none';
    return 'Expects ' + e.min + (e.max !== e.min ? ' to ' + e.max : '');
  }
  function observedText(v) {
    if (v % 1) return 'Median ' + v;
    return WORDS[v].replace(/^./, function (s) { return s.toUpperCase(); }) + ', ' + v;
  }
  function ProfileStrip(p) {
    return h('ul', { className: 'bn-strip', 'aria-label': p.label || 'Profile against the expected profile' }, (p.cells || []).map(function (c) {
      var e = c.expected || {}, pc = function (v) { return (v / 3 * 100) + '%'; };
      var band = e.kind === 'present' ? { left: pc(e.min), width: 'calc(' + pc(e.max) + ' - ' + pc(e.min) + ')' } : (e.kind === 'absent' ? { left: 0, width: '16%' } : null);
      if (band && e.kind === 'present' && e.min === e.max) band = { left: 'calc(' + pc(e.min) + ' - 7%)', width: '14%' };
      var marks = stripMark(c);
      return h('li', { key: c.label, style: { '--fam': famVar(c.family) } },
        h('div', { className: 'bn-strip-head' }, h('span', { className: 'bn-bead', 'aria-hidden': true }), h('span', { className: 'bn-strip-name' }, c.label),
          marks.map(function (m) { return h('span', { key: m[1], className: 'bn-mark bn-mark-' + m[1], title: m[2] }, h('span', { 'aria-hidden': true }, m[0]), h('span', { className: 'bn-sr' }, m[2])); })),
        h('div', { className: 'bn-strip-track bn-channel', 'aria-hidden': true },
          band ? h('span', { className: 'bn-strip-band', style: band }) : null,
          c.observed > 0 ? h('span', { className: 'bn-strip-fill', style: { width: 'calc(' + pc(c.observed) + ' - 4px)' } }) : null,
          h('span', { className: 'bn-strip-ticks' }, h('i'), h('i'), h('i'), h('i'))),
        h('div', { className: 'bn-strip-foot' }, h('span', null, observedText(c.observed || 0)), h('span', null, expectText(e))));
    }));
  }
  function dots(v) { return h('span', { className: 'bn-dots', 'aria-hidden': true }, [1, 2, 3].map(function (i) { return h('i', { key: i, className: v >= i ? 'on' : undefined }); })); }
  function FindingPane(p) {
    return h('aside', { className: cx('bn-card', 'bn-pane'), style: { '--fam': famVar(p.family) }, 'aria-label': 'Finding: ' + p.label },
      h('div', { className: 'bn-pane-head' }, h(LabelChip, { family: p.family, label: p.label }), h(TrustBadge, { trust: p.trust, agreement: p.agreement }),
        p.onClose ? h('span', { style: { marginLeft: 'auto' } }, h(LinkButton, { onClick: p.onClose }, 'Close')) : null),
      p.definition ? h('p', { className: 'bn-pane-def' }, p.definition) : null,
      h('div', { className: 'bn-pane-median' }, h('span', { className: 'bn-muted' }, 'Panel median'), h('b', { className: 'bn-num' }, p.median), h('span', null, intensityWord(p.median))),
      h('ul', { className: 'bn-judges' }, (p.judges || []).map(function (j, i) {
        return h('li', { key: i, className: 'bn-judge' },
          h('div', { className: 'bn-judge-head' }, h(Mono, { plain: true }, j.model), h('span', { style: { display: 'inline-flex', gap: 8, alignItems: 'center' } }, dots(j.intensity), h('span', { className: 'bn-num' }, intensityWord(j.intensity) + ' (' + j.intensity + ')'))),
          (j.quotes || []).map(function (q, k) { return h('p', { key: k, className: 'bn-quote' }, '\u201C' + q + '\u201D'); }),
          (j.dropped || []).map(function (q, k) { return h('p', { key: 'd' + k, className: 'bn-dropped', title: 'Dropped: the quote is not in the reply' }, 'Dropped quote: \u201C' + q + '\u201D'); }),
          j.rationale ? h('p', { className: 'bn-pane-def' }, j.rationale) : null);
      })));
  }
  function TurnTimeline(p) {
    var n = p.replies || ((p.rows && p.rows[0] && p.rows[0].values.length) || 0), cols = [];
    for (var i = 1; i <= n; i++) cols.push('R' + i);
    return h('div', { className: 'bn-tl', role: 'table', 'aria-label': p.label || 'Labels across the conversation\u2019s replies' },
      h('div', { role: 'row', className: 'bn-row' },
        h('span', { role: 'columnheader' }, h('span', { className: 'bn-sr' }, 'Label')),
        h('div', { className: 'bn-tl-cols', role: 'presentation' }, cols.map(function (c) { return h('span', { key: c, role: 'columnheader' }, c); }))),
      (p.rows || []).map(function (r) {
        return h('div', { key: r.label, role: 'row', className: 'bn-row' },
          h('span', { role: 'rowheader' }, h(LabelChip, { family: r.family, label: r.label })),
          h('div', { className: 'bn-tl-row', role: 'presentation', style: { '--fam': famVar(r.family) } }, r.values.map(function (v, i) {
            var size = [0, 7, 11, 15][Math.round(v)] || 0;
            return v > 0
              ? h('span', { key: i, className: 'bn-bead', role: 'cell', 'aria-label': cols[i] + ': ' + intensityWord(v), style: { width: size, height: size } })
              : h('span', { key: i, className: 'bn-tl-zero', role: 'cell', 'aria-label': cols[i] + ': absent' });
          })));
      }));
  }
  function CompareView(p) {
    var span = p.span || 40, pc = function (v) { return (50 + Math.max(-span, Math.min(span, v)) / span * 50) + '%'; };
    return h('div', { className: 'bn-cmp', role: 'table', 'aria-label': 'Prompt ' + p.a.name + ' beside prompt ' + p.b.name },
      h('div', { role: 'row', className: 'bn-row' },
        h('span', { className: 'bn-cmp-h', role: 'columnheader' }, 'Label'),
        h('span', { className: 'bn-cmp-h', role: 'columnheader' }, 'A: ', h(Mono, { plain: true }, p.a.name)),
        h('span', { className: 'bn-cmp-h', role: 'columnheader' }, 'B: ', h(Mono, { plain: true }, p.b.name)),
        h('span', { className: 'bn-cmp-h', role: 'columnheader' }, 'Difference, B minus A, with 95% interval'),
        h('span', { className: 'bn-cmp-h', role: 'columnheader' }, h('span', { className: 'bn-sr' }, 'In words'))),
      (p.rows || []).map(function (r) {
        var words = (r.diff > 0 ? '+' : '') + r.diff + ' points (' + r.low + ' to ' + r.high + ')';
        return h('div', { key: r.label, role: 'row', className: 'bn-row' },
          h('span', { role: 'rowheader' }, h(LabelChip, { family: r.family, label: r.label })),
          h('span', { role: 'cell', className: 'bn-num' }, r.a + '%'), h('span', { role: 'cell', className: 'bn-num' }, r.b + '%'),
          h('div', { role: 'cell', className: 'bn-diverge bn-channel', 'aria-label': words },
            h('span', { className: 'bn-ib-band', 'aria-hidden': true, style: { left: pc(r.low), width: 'calc(' + pc(r.high) + ' - ' + pc(r.low) + ')' } }),
            h('span', { className: 'bn-bead', 'aria-hidden': true, style: { left: pc(r.diff) } })),
          h('span', { role: 'cell', className: 'bn-num' }, (r.diff > 0 ? '+' : '') + r.diff + ' points ', h('span', { className: 'bn-muted' }, '(' + r.low + ' to ' + r.high + ')')));
      }));
  }
  function CompanionPane(p) {
    var signals = p.signals || [];
    var st = useState(p.active || (signals[0] && signals[0].id)), cur = st[0];
    var sig = signals.find(function (s) { return s.id === cur; }) || {};
    var text = p.text || '', spans = (sig.spans || []).slice().sort(function (a, b) { return a.start - b.start; }), out = [], at = 0;
    spans.forEach(function (s, i) {
      if (s.start > at) out.push(text.slice(at, s.start));
      out.push(h('span', { key: i, className: 'bn-sig', style: { '--bn-sv': Math.round(s.value * 45) + '%' }, title: sig.name + ': ' + s.value.toFixed(2) }, text.slice(s.start, s.end)));
      at = s.end;
    });
    out.push(text.slice(at));
    var KIND = { probe: 'Probe', persona: 'Persona vector', autoencoder: 'Autoencoder explanation' };
    return h(Card, { title: 'Open-model signals', actions: h('span', { className: 'bn-sig-scale' }, 'Low', h('span', { 'aria-hidden': true }), 'High') },
      h('p', { className: 'bn-pane-def', style: { margin: '0 0 var(--space-4)' } }, 'These signals are ', h(Mono, { plain: true }, p.model || 'an open model'), '\u2019s reading of the text, not the agent\u2019s own internals.'),
      h(Tabs, { label: 'Signals', value: cur, onChange: st[1], tabs: signals.map(function (s) { return { id: s.id, label: s.name }; }) }),
      h('p', { className: 'bn-muted', style: { fontSize: 'var(--text-xs)', margin: 'var(--space-3) 0 var(--space-2)' } }, KIND[sig.kind] || ''),
      h('p', { className: 'bn-signal-text' }, out),
      p.explanations && p.explanations.length ? h('div', { style: { marginTop: 'var(--space-5)' } },
        h('h3', { style: { margin: '0 0 var(--space-3)', fontSize: 'var(--text-sm)', fontWeight: 600 } }, 'Autoencoder explanations'),
        h('ul', { className: 'bn-expl' }, p.explanations.map(function (x, i) { return h('li', { key: i }, h('q', null, x.quote), x.text); }))) : null);
  }

  /* ---------- Agents ---------- */
  function DiffView(p) {
    function col(side) {
      return h('div', { className: 'bn-diff-col' },
        h('div', { className: 'bn-diff-head' }, side.title),
        h('ol', null, (side.lines || []).map(function (l, i) {
          var sign = l.change === 'removed' ? '\u2212' : l.change === 'added' ? '+' : '';
          return h('li', { key: i, className: l.change ? 'is-' + l.change : undefined },
            h('span', { className: 'bn-diff-n' }, l.n), h('span', { className: 'bn-diff-sign', 'aria-hidden': true }, sign),
            h('span', null, l.change ? h('span', { className: 'bn-sr' }, l.change === 'added' ? 'Added: ' : 'Removed: ') : null, l.text));
        })));
    }
    return h('div', { className: 'bn-diff' }, col(p.left || {}), col(p.right || {}));
  }

  /* ---------- States ---------- */
  function EmptyState(p) {
    return h('div', { className: 'bn-empty' },
      h(Relief, { variant: 'hairpin', width: 240, height: 100, preserve: 'xMidYMid meet' }),
      p.title ? h('p', { className: 'bn-empty-title' }, p.title) : null,
      h('p', { className: 'bn-empty-text' }, p.children),
      p.action || null);
  }
  function LoadingState(p) {
    return h('div', { className: 'bn-loading', role: 'status', 'aria-live': 'polite' },
      h('span', null, p.label || 'Loading'),
      h('div', { className: 'bn-loading-track bn-channel', 'aria-hidden': true }));
  }

  /* ---------- Relief: the routed-ridge motif ----------
     Each route is a ridge: a crisp 1.25px crest, a lit flank tapering away toward the top left, a shaded flank tapering
     toward the bottom right, and a fine shaded lip under the crest. The flanks are stacks of strokes whose widths grow
     on a square curve, so the profile peaks sharply at the crest and tails off softly, like contour lines on slate. */
  var ROUTES = {
    route: { vb: '0 0 480 200', lit: 56, shade: 32, d: [
      'M540 30H316A124 124 0 0 0 192 154V280', 'M540 84H316A70 70 0 0 0 246 154V280', 'M540 138H316A16 16 0 0 0 300 154V280',
      'M540 184H430A30 30 0 0 0 430 244H540'] },
    hairpin: { vb: '0 0 480 200', lit: 34, shade: 20, d: [
      'M540 64H252A36 36 0 0 0 252 136H540', 'M540 100H312'] }
  };
  function Relief(p) {
    var r = ROUTES[p.variant] || ROUTES.route, id = useUid('relief');
    var vb = r.vb.split(' ').map(Number), VW = vb[2], VH = vb[3];
    function lanes(cls, sw, extra) {
      return h('g', Object.assign({ className: cls, fill: 'none', strokeWidth: sw, strokeLinecap: 'round', strokeLinejoin: 'round' }, extra || {}),
        r.d.map(function (x, i) { return h('path', { key: i, d: x }); }));
    }
    function flank(cls, width, layers, dx, dy) {
      var out = [];
      for (var i = 1; i <= layers; i++) out.push(lanes(null, +(width * (i / layers) * (i / layers)).toFixed(2), { key: i }));
      return h('g', { className: cls, filter: 'url(#' + id + '-sm)', transform: 'translate(' + dx + ' ' + dy + ')' }, out);
    }
    function fadeMask(n, x1, y1, x2, y2, stops) {
      return h(F, null,
        h('linearGradient', { id: id + '-' + n + 'g', gradientUnits: 'userSpaceOnUse', x1: x1, y1: y1, x2: x2, y2: y2 },
          stops.map(function (st, i) { return h('stop', { key: i, offset: st[0], stopColor: st[1] }); })),
        h('mask', { id: id + '-' + n, maskUnits: 'userSpaceOnUse', x: -200, y: -200, width: VW + 400, height: VH + 400 },
          h('rect', { x: -200, y: -200, width: VW + 400, height: VH + 400, fill: 'url(#' + id + '-' + n + 'g)' })));
    }
    var fade = p.fade !== false;
    return h('svg', { className: cx('bn-relief', p.className), viewBox: r.vb, width: p.width, height: p.height, preserveAspectRatio: p.preserve || 'xMaxYMid slice', 'aria-hidden': true, focusable: 'false', style: p.style },
      h('defs', null,
        h('filter', { id: id + '-sm', x: '-10%', y: '-10%', width: '120%', height: '120%' }, h('feGaussianBlur', { stdDeviation: 1.2 })),
        fadeMask('fx', 0, 0, VW, 0, [[0, '#000'], [0.12, '#fff'], [0.86, '#fff'], [1, '#000']]),
        fadeMask('fy', 0, 0, 0, VH, [[0, '#000'], [0.1, '#fff'], [0.78, '#fff'], [1, '#000']])),
      h('g', { mask: fade ? 'url(#' + id + '-fx)' : undefined }, h('g', { mask: fade ? 'url(#' + id + '-fy)' : undefined },
        flank('r-shade', r.shade, 10, 2, 2.5),
        flank('r-lit', r.lit, 20, -3, -3.5),
        lanes('r-lip', 1.4, { transform: 'translate(0.8 0.9)' }),
        lanes('r-crest', 1.25))));
  }

  var Bench = {
    Button: Button, LinkButton: LinkButton, Field: Field, Select: Select, Checkbox: Checkbox, Radio: Radio, Tabs: Tabs, Dialog: Dialog, Toast: Toast,
    Notice: Notice, Card: Card, PageHeader: PageHeader, Badge: Badge, Mono: Mono, AppShell: AppShell, Nav: Nav,
    DataTable: DataTable, ScoreCell: ScoreCell, Heatmap: Heatmap, RateChart: RateChart, RateTable: RateTable, IntervalBar: IntervalBar,
    StatusBadge: StatusBadge, RunProgress: RunProgress, Provenance: Provenance,
    MessageView: MessageView, Cited: Cited, ContentNote: ContentNote, FullThinking: FullThinking,
    LabelChip: LabelChip, TrustBadge: TrustBadge, Highlighted: Highlighted, ProfileStrip: ProfileStrip, FindingPane: FindingPane,
    TurnTimeline: TurnTimeline, CompareView: CompareView, CompanionPane: CompanionPane,
    DiffView: DiffView, EmptyState: EmptyState, LoadingState: LoadingState, Relief: Relief,
    FAMILIES: FAMILIES, intensityWord: intensityWord
  };
  window.Bench = Object.assign(window.Bench || {}, Bench);
})();
