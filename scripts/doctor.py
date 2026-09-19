#!/usr/bin/env python3
"""
doctor.py — Pre-flight environment & model connectivity diagnostic.

Run this before anything else to verify your environment is ready.

Checks:
  1. Python version >= 3.10
  2. Required packages installed (pydantic, pytest)
  3. .env exists (if using real LLM mode)
  4. LLM_MODE setting
  5. SQLite works
  6. Import smoke test for all modules
"""
import importlib
import os
import sqlite3
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK, BAD, WARN, SKIP = "  ok  ", " FAIL ", " warn ", " skip "
fails = skips = 0


def line(state, what, detail=""):
    global fails, skips
    if state is BAD:
        fails += 1
    elif state is SKIP:
        skips += 1
    print(f"[{state}] {what}" + (f"\n         {detail}" if detail else ""))


print("\nAdaptTutor doctor\n" + "-" * 60)

# 1. Python version
v = sys.version_info
if v >= (3, 10):
    line(OK, f"Python {v.major}.{v.minor}.{v.micro}")
else:
    line(BAD, f"Python {v.major}.{v.minor}.{v.micro}", "Requires Python >= 3.10")

# 2. Required packages
for pkg in ("pydantic", "pytest"):
    try:
        m = importlib.import_module(pkg)
        ver = getattr(m, "__version__", getattr(m, "VERSION", "?"))
        line(OK, f"{pkg} {ver}")
    except ImportError:
        line(BAD, f"{pkg} not installed", f"Run: pip install {pkg}")

# 3. Optional packages
for pkg in ("httpx", "fastapi", "uvicorn"):
    try:
        m = importlib.import_module(pkg)
        ver = getattr(m, "__version__", getattr(m, "VERSION", "?"))
        line(OK, f"{pkg} {ver}")
    except ImportError:
        line(WARN, f"{pkg} not installed (optional for mock mode)",
             f"Run: pip install {pkg}")

# 4. .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    line(OK, ".env found")
    from slice.config import load_env
    load_env(env_path)
else:
    line(WARN, ".env not found", "Not needed for LLM_MODE=mock. Copy .env.example for real mode.")

# 5. LLM_MODE
mode = os.environ.get("LLM_MODE", "mock").strip().lower()
line(OK, f"LLM_MODE={mode}")
if mode == "real":
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        line(OK, "OPENROUTER_API_KEY is set")
    else:
        line(BAD, "OPENROUTER_API_KEY is empty",
             "Required for LLM_MODE=real. Paste it in .env.")

# 6. SQLite
try:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    db.execute("INSERT INTO test VALUES (1)")
    assert db.execute("SELECT id FROM test").fetchone()[0] == 1
    db.close()
    line(OK, "SQLite works")
except Exception as e:
    line(BAD, "SQLite broken", str(e)[:120])

# 7. Import smoke test
for mod in ("slice.records", "slice.store", "slice.runner", "slice.budget",
            "slice.callback", "slice.config",
            "remediation.schema", "remediation.questions",
            "remediation.provider", "remediation.flow", "remediation.stub"):
    try:
        importlib.import_module(mod)
        line(OK, f"import {mod}")
    except Exception as e:
        line(BAD, f"import {mod} failed", str(e)[:120])

print("-" * 60)
if fails:
    print(f"{fails} problem(s) above" + (f", {skips} check(s) skipped" if skips else ""))
    print("Fix these BEFORE running tests or sessions.\n")
elif skips:
    print(f"no failures, {skips} check(s) skipped\n")
else:
    print("all clear — environment ready\n")
sys.exit(1 if fails else 0)
