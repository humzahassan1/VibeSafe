"""Tier 2 — Config parsing scanner (framework-specific, no LLM)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from models.context import ProjectContext
from models.finding import Finding, Severity
from models.fix import Fix
from utils.files import read_file_safe
from utils.logger import get_logger

_log = get_logger("tier2")


def scan_tier2(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Run all Tier 2 checks against the project.

    Args:
        context: Project context from discovery.
        rules: Rule definitions keyed by rule_id.

    Returns:
        List of findings from config analysis.
    """
    findings: list[Finding] = []

    _log.info("Running Tier 2 scan (framework: %s)", context.framework)

    if context.framework == "nextjs":
        findings.extend(_parse_nextjs_config(context, rules))
    elif context.framework == "express":
        findings.extend(_parse_express_middleware(context, rules))
    elif context.framework == "django":
        findings.extend(_parse_django_settings(context, rules))
    elif context.framework == "flask":
        findings.extend(_parse_flask_config(context, rules))
    elif context.framework == "fastapi":
        findings.extend(_parse_fastapi_config(context, rules))

    findings.extend(_parse_database_config(context, rules))
    findings.extend(_check_tenant_isolation(context, rules))
    findings.extend(_check_dependencies(context, rules))
    findings.extend(_check_security_headers(context, rules))

    _log.info("Tier 2 found %d issues", len(findings))
    return findings


def _parse_nextjs_config(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check Next.js configuration for security issues.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings from Next.js config analysis.
    """
    findings: list[Finding] = []

    config_path = None
    for name in ("next.config.js", "next.config.ts", "next.config.mjs"):
        candidate = os.path.join(context.project_path, name)
        if os.path.isfile(candidate):
            config_path = candidate
            break

    if config_path is None:
        return findings

    content = read_file_safe(config_path)
    if content is None:
        return findings

    if "productionBrowserSourceMaps" in content and "true" in content.lower():
        if re.search(r'productionBrowserSourceMaps\s*:\s*true', content):
            findings.append(Finding(
                rule_id="SEC-034",
                severity=Severity.WARNING,
                category="trust_boundary",
                title="Source maps enabled in production",
                description="productionBrowserSourceMaps is true, exposing source code to users.",
                file_path=config_path,
                tier=2,
                fix=Fix(
                    description="Disable production source maps.",
                    code="productionBrowserSourceMaps: false,",
                    file_path=config_path,
                    fix_type="replace",
                ),
            ))

    has_headers = bool(re.search(r'headers\s*[:(]', content))
    security_headers = [
        "Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options",
        "Strict-Transport-Security", "Referrer-Policy",
    ]
    if not has_headers:
        findings.append(Finding(
            rule_id="SEC-038",
            severity=Severity.WARNING,
            category="infrastructure",
            title="Missing security headers in Next.js config",
            description="next.config.js does not configure security headers.",
            file_path=config_path,
            tier=2,
            fix=Fix(
                description="Add security headers to next.config.js.",
                code=_NEXTJS_HEADERS_FIX,
                file_path=config_path,
                fix_type="insert",
            ),
        ))

    for env_path in context.env_files:
        env_content = read_file_safe(env_path)
        if env_content is None:
            continue
        for line in env_content.splitlines():
            if re.match(r'NEXT_PUBLIC_\w*(?:SECRET|KEY|TOKEN|PASSWORD)', line, re.IGNORECASE):
                findings.append(Finding(
                    rule_id="SEC-033",
                    severity=Severity.CRITICAL,
                    category="trust_boundary",
                    title="Secret exposed via NEXT_PUBLIC_ variable",
                    description=f"Environment variable exposes a secret to the browser: {line.split('=')[0]}",
                    file_path=env_path,
                    tier=2,
                    fix=Fix(
                        description="Remove NEXT_PUBLIC_ prefix so this value stays server-side.",
                        code=line.split("=")[0].replace("NEXT_PUBLIC_", "", 1),
                        file_path=env_path,
                        fix_type="replace",
                    ),
                ))

    return findings


def _parse_express_middleware(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check Express middleware configuration for security issues.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings from Express middleware analysis.
    """
    findings: list[Finding] = []

    main_files = []
    for name in ("app.js", "app.ts", "server.js", "server.ts", "index.js", "index.ts"):
        candidate = os.path.join(context.project_path, name)
        if os.path.isfile(candidate):
            main_files.append(candidate)

    if not main_files:
        return findings

    combined_content = ""
    primary_file = main_files[0]
    for fp in main_files:
        content = read_file_safe(fp)
        if content:
            combined_content += content + "\n"

    if not combined_content:
        return findings

    if "helmet" not in combined_content:
        findings.append(Finding(
            rule_id="SEC-038",
            severity=Severity.WARNING,
            category="infrastructure",
            title="Missing helmet middleware",
            description="Express app does not use helmet for security headers.",
            file_path=primary_file,
            tier=2,
            fix=Fix(
                description="Install and use helmet middleware.",
                code='const helmet = require("helmet");\napp.use(helmet());',
                file_path=primary_file,
                fix_type="insert",
            ),
        ))

    cors_match = re.search(r'cors\s*\(\s*\)', combined_content)
    origin_star = re.search(r"origin\s*:\s*['\"]?\*['\"]?", combined_content)
    origin_true = re.search(r"origin\s*:\s*true", combined_content)
    if cors_match or origin_star or origin_true:
        findings.append(Finding(
            rule_id="SEC-039",
            severity=Severity.WARNING,
            category="infrastructure",
            title="Permissive CORS configuration",
            description="CORS is configured to allow all origins.",
            file_path=primary_file,
            tier=2,
            fix=Fix(
                description="Restrict CORS to specific trusted origins.",
                code='app.use(cors({ origin: "https://yourdomain.com" }));',
                file_path=primary_file,
                fix_type="replace",
            ),
        ))

    if "rate" not in combined_content.lower() and "limiter" not in combined_content.lower():
        findings.append(Finding(
            rule_id="SEC-028",
            severity=Severity.WARNING,
            category="ai_security",
            title="Missing rate limiting",
            description="Express app does not use rate limiting middleware.",
            file_path=primary_file,
            tier=2,
            fix=Fix(
                description="Add express-rate-limit middleware.",
                code=(
                    'const rateLimit = require("express-rate-limit");\n'
                    'app.use(rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }));'
                ),
                file_path=primary_file,
                fix_type="insert",
            ),
        ))

    session_match = re.search(r'session\s*\(', combined_content)
    if session_match:
        if "secure" not in combined_content or "httpOnly" not in combined_content:
            findings.append(Finding(
                rule_id="SEC-016",
                severity=Severity.WARNING,
                category="auth",
                title="Insecure session cookies",
                description="Session middleware may not have secure or httpOnly flags set.",
                file_path=primary_file,
                tier=2,
                fix=Fix(
                    description="Set secure cookie options.",
                    code='cookie: { secure: true, httpOnly: true, sameSite: "strict" }',
                    file_path=primary_file,
                    fix_type="replace",
                ),
            ))

    return findings


def _parse_django_settings(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check Django settings for security issues."""
    findings: list[Finding] = []

    settings_paths = []
    for fi in context.file_manifest:
        if fi.path.endswith("settings.py") or "/settings/" in fi.path.replace("\\", "/"):
            settings_paths.append(fi.path)

    if not settings_paths:
        return findings

    for settings_path in settings_paths:
        content = read_file_safe(settings_path)
        if not content:
            continue

        if re.search(r'DEBUG\s*=\s*True', content):
            findings.append(Finding(
                rule_id="SEC-036",
                severity=Severity.WARNING,
                category="infrastructure",
                title="Django DEBUG=True",
                description="DEBUG is set to True. Must be False in production to hide stack traces and sensitive info.",
                file_path=settings_path,
                tier=2,
                fix=Fix(
                    description="Set DEBUG to False in production.",
                    code='DEBUG = os.environ.get("DEBUG", "False").lower() == "true"',
                    file_path=settings_path,
                    fix_type="replace",
                ),
            ))

        secret_match = re.search(r'SECRET_KEY\s*=\s*["\x27]([^"\x27]{1,})["\x27]', content)
        if secret_match:
            key_val = secret_match.group(1)
            if not key_val.startswith("os.environ") and "getenv" not in key_val:
                findings.append(Finding(
                    rule_id="SEC-017",
                    severity=Severity.CRITICAL,
                    category="auth",
                    title="Hardcoded Django SECRET_KEY",
                    description="SECRET_KEY is hardcoded in settings. It should be loaded from an environment variable.",
                    file_path=settings_path,
                    tier=2,
                    fix=Fix(
                        description="Load SECRET_KEY from environment.",
                        code='SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]',
                        file_path=settings_path,
                        fix_type="replace",
                    ),
                ))

        if re.search(r'ALLOWED_HOSTS\s*=\s*\[\s*["\x27]\*["\x27]', content):
            findings.append(Finding(
                rule_id="SEC-039",
                severity=Severity.WARNING,
                category="infrastructure",
                title="Django ALLOWED_HOSTS allows all",
                description="ALLOWED_HOSTS = ['*'] allows requests from any hostname.",
                file_path=settings_path,
                tier=2,
                fix=Fix(
                    description="Restrict ALLOWED_HOSTS to your domain(s).",
                    code='ALLOWED_HOSTS = ["yourdomain.com"]',
                    file_path=settings_path,
                    fix_type="replace",
                ),
            ))

        middleware_section = re.search(r'MIDDLEWARE\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if middleware_section:
            middleware_content = middleware_section.group(1)
            if "CsrfViewMiddleware" not in middleware_content:
                findings.append(Finding(
                    rule_id="SEC-023",
                    severity=Severity.CRITICAL,
                    category="injection",
                    title="Django CSRF middleware disabled",
                    description="CsrfViewMiddleware is missing from MIDDLEWARE, leaving forms vulnerable to CSRF attacks.",
                    file_path=settings_path,
                    tier=2,
                    fix=Fix(
                        description="Add CsrfViewMiddleware to MIDDLEWARE.",
                        code='"django.middleware.csrf.CsrfViewMiddleware",',
                        file_path=settings_path,
                        fix_type="insert",
                    ),
                ))
            if "SecurityMiddleware" not in middleware_content:
                findings.append(Finding(
                    rule_id="SEC-038",
                    severity=Severity.WARNING,
                    category="infrastructure",
                    title="Django SecurityMiddleware missing",
                    description="SecurityMiddleware is missing from MIDDLEWARE. It provides HSTS, SSL redirect, and other security headers.",
                    file_path=settings_path,
                    tier=2,
                    fix=Fix(
                        description="Add SecurityMiddleware to MIDDLEWARE.",
                        code='"django.middleware.security.SecurityMiddleware",',
                        file_path=settings_path,
                        fix_type="insert",
                    ),
                ))

        if re.search(r'SESSION_COOKIE_SECURE\s*=\s*False', content) or (
            "SESSION_COOKIE_SECURE" not in content and "session" in content.lower()
        ):
            if "SESSION_COOKIE_SECURE = True" not in content:
                findings.append(Finding(
                    rule_id="SEC-016",
                    severity=Severity.WARNING,
                    category="auth",
                    title="Django session cookies not secure",
                    description="SESSION_COOKIE_SECURE is not set to True. Cookies may be sent over HTTP.",
                    file_path=settings_path,
                    tier=2,
                    fix=Fix(
                        description="Enable secure session cookies.",
                        code="SESSION_COOKIE_SECURE = True\nCSRF_COOKIE_SECURE = True",
                        file_path=settings_path,
                        fix_type="insert",
                    ),
                ))

    return findings


def _parse_flask_config(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check Flask configuration for security issues."""
    findings: list[Finding] = []

    app_files = []
    for name in ("app.py", "wsgi.py", "config.py", "__init__.py"):
        candidate = os.path.join(context.project_path, name)
        if os.path.isfile(candidate):
            app_files.append(candidate)
    for fi in context.file_manifest:
        if fi.path.endswith("__init__.py") and "app" in fi.path.replace("\\", "/").lower():
            app_files.append(fi.path)

    combined = ""
    primary = app_files[0] if app_files else None
    for fp in app_files:
        content = read_file_safe(fp)
        if content:
            combined += content + "\n"

    if not combined or not primary:
        return findings

    if re.search(r'debug\s*=\s*True', combined, re.IGNORECASE) or re.search(r'app\.run\s*\([^)]*debug\s*=\s*True', combined):
        findings.append(Finding(
            rule_id="SEC-036",
            severity=Severity.WARNING,
            category="infrastructure",
            title="Flask debug mode enabled",
            description="Debug mode exposes an interactive debugger that allows code execution.",
            file_path=primary,
            tier=2,
            fix=Fix(
                description="Disable debug mode in production.",
                code='app.run(debug=False)',
                file_path=primary,
                fix_type="replace",
            ),
        ))

    secret_match = re.search(r'SECRET_KEY["\x27\]]*\s*=\s*["\x27]([^"\x27]+)["\x27]', combined)
    if secret_match:
        key_val = secret_match.group(1)
        if "os.environ" not in key_val and "getenv" not in combined[max(0,combined.find(key_val)-50):combined.find(key_val)]:
            findings.append(Finding(
                rule_id="SEC-017",
                severity=Severity.CRITICAL,
                category="auth",
                title="Hardcoded Flask SECRET_KEY",
                description="SECRET_KEY is hardcoded. It should be loaded from an environment variable.",
                file_path=primary,
                tier=2,
                fix=Fix(
                    description="Load SECRET_KEY from environment.",
                    code='app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]',
                    file_path=primary,
                    fix_type="replace",
                ),
            ))

    if "WTF_CSRF" not in combined and "CSRFProtect" not in combined and "csrf" not in combined.lower():
        if "form" in combined.lower() or "POST" in combined:
            findings.append(Finding(
                rule_id="SEC-023",
                severity=Severity.WARNING,
                category="injection",
                title="No CSRF protection in Flask",
                description="Flask app handles forms/POST but has no CSRF protection (Flask-WTF).",
                file_path=primary,
                tier=2,
                fix=Fix(
                    description="Install and configure Flask-WTF for CSRF protection.",
                    code='from flask_wtf.csrf import CSRFProtect\ncsrf = CSRFProtect(app)',
                    file_path=primary,
                    fix_type="insert",
                ),
            ))

    return findings


def _parse_fastapi_config(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check FastAPI configuration for security issues."""
    findings: list[Finding] = []

    app_files = []
    for name in ("main.py", "app.py"):
        candidate = os.path.join(context.project_path, name)
        if os.path.isfile(candidate):
            app_files.append(candidate)

    combined = ""
    primary = app_files[0] if app_files else None
    for fp in app_files:
        content = read_file_safe(fp)
        if content:
            combined += content + "\n"

    if not combined or not primary:
        return findings

    if "CORSMiddleware" in combined:
        if re.search(r'allow_origins\s*=\s*\[\s*["\x27]\*["\x27]', combined):
            findings.append(Finding(
                rule_id="SEC-039",
                severity=Severity.WARNING,
                category="infrastructure",
                title="FastAPI CORS allows all origins",
                description="CORSMiddleware is configured with allow_origins=['*'].",
                file_path=primary,
                tier=2,
                fix=Fix(
                    description="Restrict CORS to specific origins.",
                    code='allow_origins=["https://yourdomain.com"]',
                    file_path=primary,
                    fix_type="replace",
                ),
            ))

    if "RateLimit" not in combined and "slowapi" not in combined and "rate" not in combined.lower():
        findings.append(Finding(
            rule_id="SEC-028",
            severity=Severity.WARNING,
            category="ai_security",
            title="No rate limiting in FastAPI",
            description="FastAPI app has no rate limiting middleware configured.",
            file_path=primary,
            tier=2,
            fix=Fix(
                description="Add slowapi for rate limiting.",
                code='from slowapi import Limiter\nlimiter = Limiter(key_func=get_remote_address)',
                file_path=primary,
                fix_type="insert",
            ),
        ))

    return findings


def _parse_database_config(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check database configuration for security issues.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings from database config analysis.
    """
    findings: list[Finding] = []

    for fp in context.config_files + [
        os.path.join(context.project_path, f)
        for f in ("supabase.js", "supabase.ts", "lib/supabase.js", "lib/supabase.ts")
    ]:
        if not os.path.isfile(fp):
            continue
        content = read_file_safe(fp)
        if not content:
            continue

        if "supabase" in content.lower() and "createClient" in content:
            if "service_role" in content or "serviceRole" in content:
                findings.append(Finding(
                    rule_id="SEC-007",
                    severity=Severity.CRITICAL,
                    category="database",
                    title="Supabase service role key in client code",
                    description="Service role key bypasses RLS. It must stay server-side.",
                    file_path=fp,
                    tier=2,
                    fix=Fix(
                        description="Use the anon key for client code; keep service role server-side.",
                        code="createClient(url, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)",
                        file_path=fp,
                        fix_type="replace",
                    ),
                ))

    firebase_paths = [
        os.path.join(context.project_path, f)
        for f in ("firebase.rules", "firestore.rules", "database.rules.json")
    ]
    for fp in firebase_paths:
        if not os.path.isfile(fp):
            continue
        content = read_file_safe(fp)
        if not content:
            continue

        open_read = re.search(r'["\']\.read["\']?\s*:\s*["\']?true', content)
        open_write = re.search(r'["\']\.write["\']?\s*:\s*["\']?true', content)
        allow_all = re.search(r'allow\s+read\s*,\s*write\s*:\s*if\s+true', content)

        if open_read or open_write or allow_all:
            findings.append(Finding(
                rule_id="SEC-009",
                severity=Severity.CRITICAL,
                category="database",
                title="Firebase security rules are wide open",
                description="Firebase rules allow unrestricted read/write access.",
                file_path=fp,
                tier=2,
                fix=Fix(
                    description="Restrict Firebase rules to authenticated users.",
                    code='allow read, write: if request.auth != null;',
                    file_path=fp,
                    fix_type="replace",
                ),
            ))

    return findings


def _check_dependencies(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check dependency hygiene.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings from dependency analysis.
    """
    findings: list[Finding] = []

    findings.extend(_check_python_dependencies(context, rules))

    pkg_json_path = os.path.join(context.project_path, "package.json")
    if os.path.isfile(pkg_json_path):
        content = read_file_safe(pkg_json_path)
        if content:
            try:
                pkg = json.loads(content)
            except json.JSONDecodeError:
                return findings

            scripts = pkg.get("scripts", {})
            has_audit = any("audit" in v for v in scripts.values()) if isinstance(scripts, dict) else False
            if not has_audit:
                findings.append(Finding(
                    rule_id="SEC-047",
                    severity=Severity.WARNING,
                    category="dependencies",
                    title="No dependency audit script",
                    description="package.json has no npm audit or similar script configured.",
                    file_path=pkg_json_path,
                    tier=2,
                    fix=Fix(
                        description="Add an audit script to package.json.",
                        code='"audit": "npm audit"',
                        file_path=pkg_json_path,
                        fix_type="insert",
                    ),
                ))

            for dep_key in ("dependencies", "devDependencies"):
                deps = pkg.get(dep_key, {})
                if not isinstance(deps, dict):
                    continue
                for name, version in deps.items():
                    if version in ("*", "latest") or version.startswith(">="):
                        findings.append(Finding(
                            rule_id="SEC-049",
                            severity=Severity.WARNING,
                            category="dependencies",
                            title=f"Unpinned dependency: {name}",
                            description=f"Dependency '{name}' uses version '{version}' which is too permissive.",
                            file_path=pkg_json_path,
                            tier=2,
                            fix=Fix(
                                description=f"Pin {name} to a specific version.",
                                code=f'"{name}": "^x.y.z"  // pin to a specific version',
                                file_path=pkg_json_path,
                                fix_type="replace",
                            ),
                        ))

    return findings


def _check_tenant_isolation(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check for common tenant isolation issues in route/view files."""
    findings: list[Finding] = []

    route_keywords = {"views", "routes", "controllers", "api", "routers", "endpoints"}

    for fi in context.file_manifest:
        basename = os.path.basename(fi.path).lower()
        path_parts = fi.path.replace("\\", "/").lower().split("/")
        name_no_ext = os.path.splitext(basename)[0]

        is_route_file = (
            name_no_ext in route_keywords
            or any(p in route_keywords for p in path_parts)
            or fi.relevance_score >= 0.8
        )
        if not is_route_file:
            continue

        ext = os.path.splitext(fi.path)[1]
        if ext not in (".py", ".js", ".ts", ".jsx", ".tsx"):
            continue

        content = read_file_safe(fi.path)
        if not content:
            continue

        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            _PYTHON_OWNER_FILTER = re.compile(
                r'(?:request\.user|current_user|\.filter\s*\(.*(?:user|owner|tenant|created_by)\s*=)',
                re.IGNORECASE,
            )
            _JS_OWNER_CHECK = re.compile(
                r'(?:req\.user|currentUser|session\.user|\.userId|\.user_id|\.ownerId|\.owner_id|auth\()',
                re.IGNORECASE,
            )

            if ext == ".py":
                if re.search(r'\.objects\.get\s*\(\s*(?:id|pk)\s*=', line):
                    context_window = "\n".join(lines[max(0, i-4):min(len(lines), i+3)])
                    if not _PYTHON_OWNER_FILTER.search(context_window):
                        findings.append(Finding(
                            rule_id="SEC-010",
                            severity=Severity.CRITICAL,
                            category="database",
                            title="Possible broken tenant isolation",
                            description="Record fetched by ID without user/owner filter. Verify the requesting user owns this record.",
                            file_path=fi.path,
                            line_start=i,
                            tier=2,
                            code_snippet=stripped,
                            fix=Fix(
                                description="Add user ownership check to the query.",
                                code="Model.objects.get(id=pk, user=request.user)",
                                file_path=fi.path,
                                fix_type="replace",
                            ),
                        ))
            else:
                if re.search(r'findById\s*\(\s*(?:req\.params|req\.query|params)', line):
                    context_window = "\n".join(lines[max(0, i-4):min(len(lines), i+3)])
                    if not _JS_OWNER_CHECK.search(context_window):
                        findings.append(Finding(
                            rule_id="SEC-010",
                            severity=Severity.CRITICAL,
                            category="database",
                            title="Possible broken tenant isolation",
                            description="Record fetched by ID from request params without user ownership check.",
                            file_path=fi.path,
                            line_start=i,
                            tier=2,
                            code_snippet=stripped,
                            fix=Fix(
                                description="Verify the requesting user owns the record.",
                                code="const record = await Model.findById(id);\nif (record.userId !== req.user.id) return res.status(403).json({error: 'forbidden'});",
                                file_path=fi.path,
                                fix_type="replace",
                            ),
                        ))

    return findings


def _check_python_dependencies(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check Python dependency files for security issues."""
    findings: list[Finding] = []

    req_path = os.path.join(context.project_path, "requirements.txt")
    if os.path.isfile(req_path):
        content = read_file_safe(req_path)
        if content:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                pkg_name = re.split(r'[=<>!~\[]', line)[0].strip()
                if not pkg_name:
                    continue
                if "==" not in line and ">=" not in line and "<" not in line and "~=" not in line:
                    findings.append(Finding(
                        rule_id="SEC-049",
                        severity=Severity.WARNING,
                        category="dependencies",
                        title=f"Unpinned Python dependency: {pkg_name}",
                        description=f"Dependency '{pkg_name}' has no version pin in requirements.txt.",
                        file_path=req_path,
                        tier=2,
                        fix=Fix(
                            description=f"Pin {pkg_name} to a specific version.",
                            code=f'{pkg_name}==x.y.z',
                            file_path=req_path,
                            fix_type="replace",
                        ),
                    ))

    pyproject_path = os.path.join(context.project_path, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        content = read_file_safe(pyproject_path)
        if content:
            dep_section = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if dep_section:
                for dep_line in dep_section.group(1).splitlines():
                    dep_line = dep_line.strip().strip('",\' ')
                    if not dep_line:
                        continue
                    pkg_name = re.split(r'[=<>!~\[]', dep_line)[0].strip()
                    if not pkg_name:
                        continue
                    if "==" not in dep_line and ">=" not in dep_line and "<" not in dep_line and "~=" not in dep_line:
                        findings.append(Finding(
                            rule_id="SEC-049",
                            severity=Severity.WARNING,
                            category="dependencies",
                            title=f"Unpinned Python dependency: {pkg_name}",
                            description=f"Dependency '{pkg_name}' has no version pin in pyproject.toml.",
                            file_path=pyproject_path,
                            tier=2,
                            fix=Fix(
                                description=f"Pin {pkg_name} to a specific version.",
                                code=f'"{pkg_name}==x.y.z"',
                                file_path=pyproject_path,
                                fix_type="replace",
                            ),
                        ))

    return findings


def _check_security_headers(
    context: ProjectContext,
    rules: dict[str, dict[str, Any]],
) -> list[Finding]:
    """Check for security headers in generic projects.

    Args:
        context: Project context.
        rules: Rule definitions.

    Returns:
        Findings from security header checks.
    """
    if context.framework in ("nextjs", "express"):
        return []

    findings: list[Finding] = []

    for fi in context.file_manifest:
        content = read_file_safe(fi.path)
        if content and ("createServer" in content or "app.listen" in content):
            if "helmet" not in content and "Content-Security-Policy" not in content:
                findings.append(Finding(
                    rule_id="SEC-038",
                    severity=Severity.WARNING,
                    category="infrastructure",
                    title="Missing security headers",
                    description="Server does not appear to set security headers.",
                    file_path=fi.path,
                    tier=2,
                ))
            break

    return findings


_NEXTJS_HEADERS_FIX = """async headers() {
  return [
    {
      source: "/(.*)",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
      ],
    },
  ];
},"""
