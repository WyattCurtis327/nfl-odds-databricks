"""Email helpers for Monte Carlo prediction summaries."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import requests

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def format_predictions_email_html(
    picks: pd.DataFrame,
    *,
    season: int,
    week: int,
    prediction_run_id: str,
    run_page_url: str | None = None,
) -> str:
    """Render predictions as an HTML table for email clients."""
    display_cols = [
        "away_abbr",
        "home_abbr",
        "away_spread",
        "total_line",
        "spread_pick",
        "spread_confidence",
        "total_pick",
        "total_confidence",
        "proj_away_score",
        "proj_home_score",
    ]
    available = [col for col in display_cols if col in picks.columns]
    table_df = picks[available].copy()

    for col in ("spread_confidence", "total_confidence"):
        if col in table_df.columns:
            table_df[col] = (
                pd.to_numeric(table_df[col], errors="coerce") * 100
            ).round(1).astype(str) + "%"

    headers = "".join(f"<th>{escape(col)}</th>" for col in available)
    rows: list[str] = []
    for row in table_df.itertuples(index=False):
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in row)
        rows.append(f"<tr>{cells}</tr>")

    link_html = ""
    if run_page_url:
        link_html = (
            f'<p><a href="{escape(run_page_url)}">View Databricks run</a></p>'
        )

    return f"""
<html>
  <body>
    <h2>NFL Monte Carlo Picks — Season {season}, Week {week}</h2>
    <p><strong>prediction_run_id:</strong> {escape(prediction_run_id)}</p>
    <p><strong>games:</strong> {len(picks)}</p>
    {link_html}
    <table border="1" cellpadding="6" cellspacing="0">
      <thead><tr>{headers}</tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </body>
</html>
"""


def send_email_sendgrid(
    *,
    api_key: str,
    to_email: str,
    subject: str,
    html_content: str,
    from_email: str,
) -> dict[str, Any]:
    """Send HTML email via SendGrid REST API."""
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}],
    }
    response = requests.post(
        SENDGRID_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"SendGrid request failed ({response.status_code}): {response.text}"
        )
    return {"status_code": response.status_code}