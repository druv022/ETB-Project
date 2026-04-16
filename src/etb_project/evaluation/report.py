from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Template

from etb_project.evaluation.schemas import EvalRow, RunArtifacts

_REPORT_TEMPLATE = Template("""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ETB RAGAS Eval - {{ run_id }}</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }
    code, pre { background: #f6f6f6; padding: 2px 4px; border-radius: 4px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    th { background: #fafafa; text-align: left; position: sticky; top: 0; }
    .muted { color: #666; }
  </style>
</head>
<body>
  <h2>ETB RAGAS Evaluation</h2>
  <div class="muted">run_id: <code>{{ run_id }}</code> • timestamp: <code>{{ iso_timestamp }}</code></div>

  <h3>Aggregate metrics</h3>
  <pre>{{ aggregate_json }}</pre>

  <h3>Per-row</h3>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Question</th>
        <th>Answer</th>
        <th>Metrics</th>
      </tr>
    </thead>
    <tbody>
    {% for r in rows %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ r.question }}</td>
        <td>{{ r.answer }}</td>
        <td><pre>{{ r.metrics_json }}</pre></td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</body>
</html>""")


def write_metrics_json(path: Path, *, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_run_report_html(
    artifacts: RunArtifacts,
    *,
    iso_timestamp: str,
    rows: list[EvalRow],
    per_row_metrics: list[dict[str, Any]],
    aggregate_metrics: dict[str, float],
) -> None:
    merged_rows: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        m = per_row_metrics[i] if i < len(per_row_metrics) else {}
        merged_rows.append(
            {
                "question": row.question,
                "answer": row.answer or "",
                "metrics_json": json.dumps(m, indent=2, ensure_ascii=False),
            }
        )

    html = _REPORT_TEMPLATE.render(
        run_id=artifacts.run_id,
        iso_timestamp=iso_timestamp,
        aggregate_json=json.dumps(aggregate_metrics, indent=2, ensure_ascii=False),
        rows=merged_rows,
    )
    artifacts.report_html.parent.mkdir(parents=True, exist_ok=True)
    artifacts.report_html.write_text(html, encoding="utf-8")
