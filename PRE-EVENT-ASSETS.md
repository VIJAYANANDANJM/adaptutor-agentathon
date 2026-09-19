# PRE-EVENT-ASSETS.md — Mandatory Day 1 Declaration

**Team:** uniCode
**Members:** Abhijith M, Vijay Anandan J M
**Institution:** B.E. CSE, College of Engineering Guindy, Anna University
**Date:** 19 September 2026

---

## Pre-existing Assets Used in AdaptTutor

### 1. Agentic Slice Kit Core Spine

The following modules are reused from the `agentic-slice-kit` starter engine,
provided as the hackathon's foundation framework:

- `slice/store.py` — Append-only SQLite durable persistence
- `slice/runner.py` — Deterministic state machine (advance loop)
- `slice/llm.py` — Single model choke point with Pydantic validation
- `slice/budget.py` — Hard fences: tokens per run & attempts per step
- `slice/callback.py` — Suspension on human expert, sweep timeouts, resume
- `slice/config.py` — Settings & environment variables
- `slice/records.py` — RunState, Version, Question dataclasses

Minor modifications made:
- Added `all_versions_by_kind()` method to `store.py` for population-level queries
- Added `llm_mode` field to `config.py` for mock/real provider switching
- Removed `retrieve.py` (vector/RAG not used in this domain)

### 2. Product Specification

`AgentSpec-uniCode.md` — Pre-submitted on **15 September 2026** as the team's
product specification and source of truth for AdaptTutor.


