from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Template

from etb_project.evaluation.history import evals_root, load_history

_DASHBOARD_TEMPLATE = Template("""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ETB Eval Dashboard</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
    input, select { padding: 6px 8px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    th { background: #fafafa; text-align: left; position: sticky; top: 0; }
    .muted { color: #666; }
    .notes { max-width: 720px; white-space: pre-wrap; }
    code { background: #f6f6f6; padding: 2px 4px; border-radius: 4px; }
  </style>
</head>
<body>
  <h2>ETB Evaluation Dashboard</h2>
  <div class="muted">Source: <code>data/evals/eval_history.jsonl</code></div>

  <div class="row">
    <label>Search Notes: <input id="q" placeholder="substring..." /></label>
    <label>Run ID: <input id="runId" placeholder="exact or partial..." /></label>
    <label>Metric: <select id="metricKey"></select></label>
    <label>Min: <input id="metricMin" type="number" step="0.0001" /></label>
    <label>Max: <input id="metricMax" type="number" step="0.0001" /></label>
    <button id="reset">Reset</button>
  </div>

  <div class="muted" id="count"></div>

  <table>
    <thead>
      <tr>
        <th>Timestamp</th>
        <th>Run ID</th>
        <th>Aggregate</th>
        <th>Δ vs prev</th>
        <th>Notes</th>
        <th>Links</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <script id="history" type="application/json">{{ history_json }}</script>
  <script>
    const history = JSON.parse(document.getElementById('history').textContent || '[]');
    const q = document.getElementById('q');
    const runId = document.getElementById('runId');
    const metricKey = document.getElementById('metricKey');
    const metricMin = document.getElementById('metricMin');
    const metricMax = document.getElementById('metricMax');
    const tbody = document.getElementById('tbody');
    const count = document.getElementById('count');
    const reset = document.getElementById('reset');

    function allMetricKeys() {
      const s = new Set();
      for (const r of history) {
        const m = r.aggregate_metrics || {};
        for (const k of Object.keys(m)) s.add(k);
      }
      return Array.from(s).sort();
    }

    function fmtObj(o) {
      return JSON.stringify(o || {}, null, 2);
    }

    function buildMetricSelect() {
      const keys = allMetricKeys();
      metricKey.innerHTML = '';
      const opt0 = document.createElement('option');
      opt0.value = '';
      opt0.textContent = '(any)';
      metricKey.appendChild(opt0);
      for (const k of keys) {
        const opt = document.createElement('option');
        opt.value = k;
        opt.textContent = k;
        metricKey.appendChild(opt);
      }
    }

    function passes(r) {
      const notes = (r.notes_ai || '').toLowerCase();
      const rq = (q.value || '').toLowerCase().trim();
      if (rq && !notes.includes(rq)) return false;
      const rid = (runId.value || '').trim();
      if (rid && !(r.run_id || '').includes(rid)) return false;
      const mk = (metricKey.value || '').trim();
      if (mk) {
        const v = (r.aggregate_metrics || {})[mk];
        if (typeof v !== 'number') return false;
        const mn = metricMin.value === '' ? null : Number(metricMin.value);
        const mx = metricMax.value === '' ? null : Number(metricMax.value);
        if (mn !== null && v < mn) return false;
        if (mx !== null && v > mx) return false;
      }
      return true;
    }

    function render() {
      const rows = history.filter(passes).slice().reverse(); // newest first
      count.textContent = `${rows.length} / ${history.length} runs shown`;
      tbody.innerHTML = '';
      for (const r of rows) {
        const tr = document.createElement('tr');
        const link = r.report_path ? `<a href=\"${r.report_path}\">report</a>` : '';
        tr.innerHTML = `
          <td><code>${r.iso_timestamp || ''}</code></td>
          <td><code>${r.run_id || ''}</code></td>
          <td><pre>${fmtObj(r.aggregate_metrics)}</pre></td>
          <td><pre>${fmtObj(r.metric_delta_vs_previous)}</pre></td>
          <td class=\"notes\">${(r.notes_ai || '').replaceAll('&','&amp;').replaceAll('<','&lt;')}</td>
          <td>${link}</td>
        `;
        tbody.appendChild(tr);
      }
    }

    function wire() {
      for (const el of [q, runId, metricKey, metricMin, metricMax]) {
        el.addEventListener('input', render);
        el.addEventListener('change', render);
      }
      reset.addEventListener('click', () => {
        q.value = '';
        runId.value = '';
        metricKey.value = '';
        metricMin.value = '';
        metricMax.value = '';
        render();
      });
    }

    buildMetricSelect();
    wire();
    render();
  </script>
</body>
</html>""")


def write_dashboard_html(repo_root: Path) -> Path:
    hist = load_history(repo_root)
    out_path = evals_root(repo_root) / "dashboard.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = _DASHBOARD_TEMPLATE.render(
        history_json=json.dumps([r.model_dump() for r in hist], ensure_ascii=False)
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path
