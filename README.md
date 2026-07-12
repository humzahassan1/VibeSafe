# VibeSafe

Security agent that audits AI-generated ("vibecoded") codebases for vulnerabilities.

VibeSafe scans your project in three tiers:
- **Tier 1** — Regex pattern matching for secrets, dangerous functions, and misconfigurations
- **Tier 2** — Framework-specific config parsing (Next.js, Express)
- **Tier 3** — LLM-powered deep analysis using Claude (optional, requires API key)

## Install

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Scan a project (Tier 1 + 2 only, no API key needed)
vibesafe scan /path/to/project --skip-tier3

# Full scan with LLM analysis (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=your_key_here
vibesafe scan /path/to/project

# Output as JSON
vibesafe scan /path/to/project --skip-tier3 -f json

# Save report to file
vibesafe scan /path/to/project --skip-tier3 -o report.md

# Scan a public GitHub repository (no clone or zip needed)
vibesafe scan-github owner/repo --skip-tier3

# Scan a specific branch or private repo
vibesafe scan-github https://github.com/owner/repo --ref main -f json
export GITHUB_TOKEN=ghp_your_token_here   # required for private repos
vibesafe scan-github owner/private-repo --token "$GITHUB_TOKEN"

# Verbose logging
vibesafe scan /path/to/project --skip-tier3 -v
```

## What It Catches

VibeSafe checks for 51 security rules across 10 categories:

| Category | Examples |
|----------|----------|
| Secrets | Hardcoded API keys, leaked credentials, exposed .env files |
| Injection | SQL injection, XSS (eval, innerHTML, document.write) |
| Auth | Default credentials, missing authentication |
| Infrastructure | Missing helmet/security headers, permissive CORS |
| Trust Boundary | NEXT_PUBLIC_ secrets, source maps in production |
| Dependencies | Unpinned versions, missing audit scripts |
| Monitoring | Sensitive data in logs |
| AI Security | Prompt injection, unvalidated LLM output |
| Data Flow | Insecure data handling across boundaries |
| Scalability | Concurrency and scaling issues |

## SaaS / Web Service (optional)

VibeSafe ships an optional multi-user web service (`saas/`) built on FastAPI.
It wraps the CLI scanner with accounts, API keys, scan history, usage limits,
and Stripe billing. The core CLI works without any of this.

```bash
# Install web dependencies (already in requirements.txt)
pip install -r requirements.txt

# Run the server
uvicorn saas.app:app --reload
# Visit http://localhost:8000 to sign up and scan
```

Scan a project via the API with an API key (create one in the dashboard):

```bash
zip -r project.zip ./my-app
curl -X POST http://localhost:8000/api/scans \
  -H "Authorization: Bearer vsk_your_key" \
  -F "project=@project.zip" -F "name=my-app" -F "skip_tier3=true"

# Scan a GitHub repository via the API
curl -X POST http://localhost:8000/api/scans/github \
  -H "Authorization: Bearer vsk_your_key" \
  -F "repo=owner/repo" -F "name=my-app" -F "skip_tier3=true"
```

For private repositories, set `GITHUB_TOKEN` on the server or pass
`github_token` in the form body.

### Plans

| Plan | Scans/month | Tier 3 (AI) | Price |
|------|-------------|-------------|-------|
| Free | 10 | No | $0 |
| Pro | 500 | Yes | $29/mo |

### Configuration (environment variables)

| Variable | Purpose | Default |
|----------|---------|---------|
| `VIBESAFE_DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./vibesafe_saas.db` |
| `VIBESAFE_SECRET_KEY` | Session signing key | dev placeholder |
| `STRIPE_SECRET_KEY` | Stripe API key (enables billing) | unset (free tier only) |
| `STRIPE_PRICE_ID` | Stripe price for Pro plan | unset |
| `STRIPE_WEBHOOK_SECRET` | Webhook signature secret | unset |
| `VIBESAFE_APP_URL` | Public base URL for redirects | `http://localhost:8000` |
| `GITHUB_TOKEN` | GitHub PAT for private repo scans (CLI + SaaS) | unset (public repos only) |

Billing degrades gracefully: with no `STRIPE_SECRET_KEY`, the app runs
free-tier only and upgrade endpoints return a clear "not configured" error.

## GitHub Action

Add VibeSafe to your CI pipeline to scan every pull request:

```yaml
# .github/workflows/vibesafe.yml
name: VibeSafe Security Scan

on:
  pull_request:
    branches: [main, master]

permissions:
  contents: read
  pull-requests: write

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run VibeSafe
        uses: your-org/vibesafe@main
        with:
          path: "."
          skip-tier3: "true"
          fail-on-critical: "true"
          comment-on-pr: "true"
```

### Action Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `path` | `.` | Path to scan |
| `skip-tier3` | `true` | Skip LLM analysis |
| `anthropic-api-key` | — | API key for Tier 3 |
| `fail-on-critical` | `true` | Fail the workflow on critical findings |
| `comment-on-pr` | `true` | Post report as a PR comment |
| `format` | `markdown` | Output format |
| `budget` | `100000` | Token budget for Tier 3 |

### Action Outputs

| Output | Description |
|--------|-------------|
| `total-findings` | Total number of findings |
| `critical-findings` | Number of critical findings |
| `report` | Path to the report file |

## Docker

```bash
docker build -t vibesafe .
docker run -v $(pwd):/project vibesafe scan /project --skip-tier3
```

## Exit Codes

- `0` — No critical findings
- `1` — Critical findings detected

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Project Structure

```
vibesafe/
  cli.py              # CLI entry point (Click)
  orchestrator.py      # Pipeline runner
  scanner/
    discovery.py       # Project walker + framework detection
    tier1.py           # Pattern matching
    tier2.py           # Config analysis
    tier3.py           # LLM analysis
  agent/
    llm.py             # Claude API client
    loop.py            # Adaptive investigation loop
    tools.py           # File reading tools for agent
    context.py         # Token budget management
  models/              # Shared dataclasses (Finding, Fix, ProjectContext)
  config/
    rules.yaml         # 51 security rules
    patterns.yaml      # Regex patterns
    frameworks.yaml    # Framework detection signatures
    prompts/           # Jinja2 prompt templates
  report/
    generator.py       # Deduplication + summary
    formatter.py       # Markdown/JSON output
    templates/         # Report templates
  utils/               # File I/O, logging, git, token counting, archives, GitHub fetch
```
