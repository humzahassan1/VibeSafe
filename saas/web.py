"""Server-rendered HTML for the landing page and dashboard."""

from __future__ import annotations

import html
from typing import Iterable

from saas.database import Scan, User
from saas.usage import UsageStatus

_STYLE = """
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 860px;
         margin: 0 auto; padding: 2rem; line-height: 1.5; }
  h1 { margin-bottom: 0.25rem; }
  .muted { color: #888; }
  .card { border: 1px solid #8883; border-radius: 10px; padding: 1.25rem; margin: 1rem 0; }
  .row { display: flex; gap: 1rem; flex-wrap: wrap; }
  .pill { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
          font-size: 0.8rem; font-weight: 600; }
  .crit { background: #e5484d22; color: #e5484d; }
  .warn { background: #f5a62322; color: #f5a623; }
  .ok   { background: #30a46c22; color: #30a46c; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #8882; }
  input, button { font: inherit; padding: 0.5rem 0.75rem; border-radius: 8px;
                  border: 1px solid #8886; }
  button { cursor: pointer; background: #3b82f6; color: white; border: none; }
  button.secondary { background: transparent; color: inherit; border: 1px solid #8886; }
  form.inline { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
  code { background: #8882; padding: 0.1rem 0.35rem; border-radius: 4px; }
</style>
"""


def render_landing(stripe_on: bool) -> str:
    """Render the public landing / auth page.

    Args:
        stripe_on: Whether Stripe billing is configured.

    Returns:
        Full HTML document.
    """
    billing_note = (
        "Pro plan available." if stripe_on else "Billing not configured (free tier only)."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VibeSafe — Security for vibecoded apps</title>{_STYLE}</head>
<body>
  <h1>🛡️ VibeSafe</h1>
  <p class="muted">Security scanning for AI-generated codebases. {html.escape(billing_note)}</p>

  <div class="card">
    <h2>Log in</h2>
    <form class="inline" onsubmit="return submitForm(event, '/auth/login')">
      <input name="email" type="email" placeholder="you@example.com" required>
      <input name="password" type="password" placeholder="Password" required>
      <button type="submit">Log in</button>
    </form>
  </div>

  <div class="card">
    <h2>Create an account</h2>
    <form class="inline" onsubmit="return submitForm(event, '/auth/signup')">
      <input name="email" type="email" placeholder="you@example.com" required>
      <input name="password" type="password" placeholder="Password (8+ chars)" required>
      <button type="submit">Sign up — free</button>
    </form>
    <p class="muted">Free plan: 10 scans/month, Tier 1 &amp; 2 analysis.</p>
  </div>

  <script>
    async function submitForm(e, url) {{
      e.preventDefault();
      const data = new FormData(e.target);
      const res = await fetch(url, {{ method: 'POST', body: data }});
      if (res.ok) {{ window.location = '/dashboard'; }}
      else {{ const j = await res.json().catch(() => ({{}}));
              alert(j.detail || 'Something went wrong'); }}
      return false;
    }}
  </script>
</body></html>"""


def render_dashboard(
    user: User, usage: UsageStatus, scans: Iterable[Scan], stripe_on: bool
) -> str:
    """Render the authenticated dashboard.

    Args:
        user: The logged-in user.
        usage: The user's usage status.
        scans: The user's scans (most recent first).
        stripe_on: Whether Stripe billing is configured.

    Returns:
        Full HTML document.
    """
    limit_text = "unlimited" if usage.limit < 0 else str(usage.limit)
    upgrade_block = ""
    if usage.plan_key == "free" and stripe_on:
        upgrade_block = """
      <button onclick="upgrade()">Upgrade to Pro</button>"""
    elif usage.plan_key == "pro" and stripe_on:
        upgrade_block = """
      <button class="secondary" onclick="portal()">Manage subscription</button>"""

    rows = []
    for s in scans:
        badge = _severity_badge(s.critical_findings, s.warning_findings)
        rows.append(
            f"<tr><td>{html.escape(s.project_name)}</td>"
            f"<td>{html.escape(s.framework)}</td>"
            f"<td>{badge}</td>"
            f"<td>{s.total_findings}</td>"
            f"<td class='muted'>{s.created_at.strftime('%Y-%m-%d %H:%M')}</td></tr>"
        )
    scan_rows = "".join(rows) or (
        "<tr><td colspan='5' class='muted'>No scans yet. Upload a project below.</td></tr>"
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VibeSafe — Dashboard</title>{_STYLE}</head>
<body>
  <div class="row" style="justify-content: space-between; align-items: center;">
    <h1>🛡️ VibeSafe</h1>
    <form onsubmit="return logout(event)"><button class="secondary">Log out</button></form>
  </div>
  <p class="muted">{html.escape(user.email)}</p>

  <div class="card">
    <div class="row" style="justify-content: space-between; align-items: center;">
      <div>
        <strong>{html.escape(usage.plan_name)} plan</strong><br>
        <span class="muted">{usage.used} / {limit_text} scans this month</span>
      </div>
      <div>{upgrade_block}</div>
    </div>
  </div>

  <div class="card">
    <h2>New scan</h2>
    <form class="inline" onsubmit="return runScan(event)">
      <input name="name" placeholder="Project name" required>
      <input name="project" type="file" accept=".zip" required>
      <button type="submit">Scan</button>
    </form>
    <p class="muted">Upload a <code>.zip</code> of your project. Tier 1 &amp; 2 analysis
      runs without an API key.</p>
    <pre id="result" class="muted"></pre>
  </div>

  <div class="card">
    <h2>Scan a GitHub repo</h2>
    <form class="inline" onsubmit="return runGithubScan(event)">
      <input name="repo" placeholder="owner/repo or github.com URL" required style="min-width: 14rem;">
      <input name="name" placeholder="Project name (optional)">
      <button type="submit">Scan repo</button>
    </form>
    <p class="muted">Public repos work without a token. Private repos need <code>GITHUB_TOKEN</code>
      configured on the server.</p>
    <pre id="gh-result" class="muted"></pre>
  </div>

  <div class="card">
    <h2>Scan history</h2>
    <table>
      <thead><tr><th>Project</th><th>Framework</th><th>Result</th><th>Total</th><th>When</th></tr></thead>
      <tbody>{scan_rows}</tbody>
    </table>
  </div>

  <script>
    async function runScan(e) {{
      e.preventDefault();
      const out = document.getElementById('result');
      out.textContent = 'Scanning…';
      const data = new FormData(e.target);
      const res = await fetch('/api/scans', {{ method: 'POST', body: data }});
      const j = await res.json().catch(() => ({{}}));
      if (res.ok) {{
        out.textContent = 'Done: ' + JSON.stringify(j.summary, null, 2);
        setTimeout(() => window.location.reload(), 1200);
      }} else {{ out.textContent = 'Error: ' + (j.detail || 'scan failed'); }}
      return false;
    }}
    async function runGithubScan(e) {{
      e.preventDefault();
      const out = document.getElementById('gh-result');
      out.textContent = 'Fetching and scanning…';
      const data = new FormData(e.target);
      const res = await fetch('/api/scans/github', {{ method: 'POST', body: data }});
      const j = await res.json().catch(() => ({{}}));
      if (res.ok) {{
        out.textContent = 'Done: ' + JSON.stringify(j.summary, null, 2);
        setTimeout(() => window.location.reload(), 1200);
      }} else {{ out.textContent = 'Error: ' + (j.detail || 'scan failed'); }}
      return false;
    }}
    async function logout(e) {{
      e.preventDefault();
      await fetch('/auth/logout', {{ method: 'POST' }});
      window.location = '/';
      return false;
    }}
    async function upgrade() {{
      const res = await fetch('/billing/checkout', {{ method: 'POST' }});
      const j = await res.json().catch(() => ({{}}));
      if (res.ok && j.checkout_url) {{ window.location = j.checkout_url; }}
      else {{ alert(j.detail || 'Upgrade unavailable'); }}
    }}
    async function portal() {{
      const res = await fetch('/billing/portal', {{ method: 'POST' }});
      const j = await res.json().catch(() => ({{}}));
      if (res.ok && j.portal_url) {{ window.location = j.portal_url; }}
      else {{ alert(j.detail || 'Portal unavailable'); }}
    }}
  </script>
</body></html>"""


def _severity_badge(critical: int, warning: int) -> str:
    """Return an HTML badge summarizing a scan's severity.

    Args:
        critical: Number of critical findings.
        warning: Number of warnings.

    Returns:
        An HTML snippet.
    """
    if critical > 0:
        return f"<span class='pill crit'>{critical} critical</span>"
    if warning > 0:
        return f"<span class='pill warn'>{warning} warning</span>"
    return "<span class='pill ok'>clean</span>"
