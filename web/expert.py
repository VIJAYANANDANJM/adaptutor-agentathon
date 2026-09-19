"""
The page an instructor answers on + student roster dashboard.

When a student exhausts both explanation styles, the system suspends and parks
a question for the instructor. This web interface shows those pending flags
and lets the instructor submit a hint or note.

The /students route provides a full student roster with mastery breakdowns,
strong/weak concept tags, and style efficacy pills.

Run it:
    uvicorn web.expert:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import html
import os

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import FastAPI

from slice import callback
from slice.config import settings
from slice.store import Store

DB = os.environ.get("SLICE_DB", "run.db")
app = FastAPI(title="AdaptTutor — Instructor Panel")


def _store() -> Store:
    return Store(DB)


# ── CSS Design System ──────────────────────────────────────────────────────

CSS = """
:root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface-2: #232736;
    --border: #2d3148;
    --text: #e4e6ef;
    --text-dim: #8b8fa8;
    --accent: #4f8cff;
    --accent-dim: #2d5aa0;
    --success: #34d399;
    --success-dim: #065f46;
    --warning: #fbbf24;
    --warning-dim: #78350f;
    --danger: #f87171;
    --danger-dim: #7f1d1d;
    --gradient-1: linear-gradient(135deg, #4f8cff 0%, #9333ea 100%);
    --gradient-2: linear-gradient(135deg, #0f1117 0%, #1a1d27 100%);
    --radius: 12px;
    --radius-sm: 8px;
    --shadow: 0 4px 24px rgba(0,0,0,0.3);
    color-scheme: dark;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font: 15px/1.6 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}
.container {
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1rem 0;
    margin-bottom: 2rem;
}
.header-inner {
    max-width: 960px;
    margin: 0 auto;
    padding: 0 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.logo {
    font-size: 1.2rem;
    font-weight: 700;
    background: var(--gradient-1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.nav { display: flex; gap: 1.5rem; }
.nav a {
    color: var(--text-dim);
    font-size: 0.9rem;
    font-weight: 500;
    transition: color 0.2s;
}
.nav a:hover, .nav a.active { color: var(--accent); text-decoration: none; }

/* Cards */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow);
    transition: transform 0.15s, box-shadow 0.15s;
}
.card:hover { transform: translateY(-1px); box-shadow: 0 6px 32px rgba(0,0,0,0.4); }

/* Headings */
h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.3rem; }
h2 { font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem; }
.sub { color: var(--text-dim); font-size: 0.9rem; margin-bottom: 1.5rem; }

/* Mastery bars */
.mastery-bar {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
}
.bar-track {
    width: 120px;
    height: 8px;
    background: var(--surface-2);
    border-radius: 4px;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}
.bar-fill.high { background: var(--success); }
.bar-fill.mid { background: var(--warning); }
.bar-fill.low { background: var(--danger); }

/* Pills / tags */
.pill {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 0.15rem 0.2rem;
}
.pill-strong { background: var(--success-dim); color: var(--success); }
.pill-weak { background: var(--danger-dim); color: var(--danger); }
.pill-style {
    background: var(--surface-2);
    color: var(--text-dim);
    border: 1px solid var(--border);
}
.pill-style.good { color: var(--success); border-color: var(--success-dim); }
.pill-style.bad { color: var(--danger); border-color: var(--danger-dim); }

/* Context blocks */
.ctx {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.8rem 1rem;
    font-size: 0.88rem;
    margin-bottom: 0.8rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.ctx b {
    display: block;
    font-size: 0.72rem;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 0.3rem;
    font-weight: 600;
}

/* Forms */
textarea {
    width: 100%;
    min-height: 9rem;
    font: inherit;
    padding: 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface-2);
    color: var(--text);
    resize: vertical;
}
textarea:focus { outline: none; border-color: var(--accent); }
button, .btn {
    font: inherit;
    font-weight: 600;
    padding: 0.6rem 1.6rem;
    margin-top: 0.8rem;
    border: 0;
    border-radius: var(--radius-sm);
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    transition: background 0.2s;
}
button:hover, .btn:hover { background: var(--accent-dim); }

/* Student roster grid */
.student-grid { display: flex; flex-direction: column; gap: 1rem; }
.student-card { display: flex; flex-direction: column; gap: 0.6rem; }
.concept-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0;
    border-bottom: 1px solid var(--border);
}
.concept-row:last-child { border-bottom: none; }
.concept-name { flex: 0 0 180px; font-weight: 500; font-size: 0.9rem; }
.style-efficacy { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.5rem; }

/* Empty state */
.empty { color: var(--text-dim); text-align: center; padding: 3rem 1rem; }
.note { font-size: 0.85rem; color: var(--text-dim); margin-top: 1rem; }

/* Question card link */
.q { font-size: 1.05rem; font-weight: 600; margin-bottom: 0.8rem; }
.flag-link {
    display: inline-block;
    padding: 0.4rem 1rem;
    background: var(--accent);
    color: #fff;
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
    font-weight: 600;
    transition: background 0.2s;
}
.flag-link:hover { background: var(--accent-dim); text-decoration: none; }
"""

HEADER = """
<div class="header">
  <div class="header-inner">
    <div class="logo">🧠 AdaptTutor — Instructor Panel</div>
    <nav class="nav">
      <a href="/" class="{esc_cls}">Escalations</a>
      <a href="/students" class="{stu_cls}">Student Roster</a>
    </nav>
  </div>
</div>
"""


def _page(title: str, body: str, active: str = "escalations") -> HTMLResponse:
    esc_cls = "active" if active == "escalations" else ""
    stu_cls = "active" if active == "students" else ""
    header = HEADER.format(esc_cls=esc_cls, stu_cls=stu_cls)
    full = (
        f"<!doctype html><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap' rel='stylesheet'>"
        f"<title>{html.escape(title)}</title>"
        f"<style>{CSS}</style>"
        f"{header}"
        f"<div class='container'>{body}</div>"
    )
    return HTMLResponse(full)


def _mastery_bar_html(pct: float) -> str:
    """Render a mastery bar as HTML."""
    cls = "high" if pct >= 75 else ("mid" if pct >= 40 else "low")
    return (
        f"<span class='mastery-bar'>"
        f"<span class='bar-track'><span class='bar-fill {cls}' style='width:{pct}%'></span></span>"
        f"<strong>{int(pct)}%</strong>"
        f"</span>"
    )


# ── Escalations Page (/): pending flags with enriched context ──────────────

@app.get("/", response_class=HTMLResponse)
def index():
    s = _store()
    callback.sweep(s)
    open_qs = callback.pending(s)
    if not open_qs:
        return _page(
            "AdaptTutor — No flags waiting",
            "<h1>No flags waiting</h1>"
            "<p class='sub'>No student is currently waiting for instructor help.</p>"
            "<p class='empty'>This page will show flags when a student fails both "
            "explanation styles and needs your direct guidance.</p>",
        )

    items = ""
    for q in open_qs:
        ctx = q.context or {}
        sid = ctx.get("student_id", "Unknown")
        concept = ctx.get("concept", "Unknown")
        styles = ctx.get("styles_tried", [])
        mastery_pct = ctx.get("mastery_pct", 0)
        wrong_ans = ctx.get("wrong_answers", {})
        budget = ctx.get("budget_remaining", "N/A")

        # Build enriched card
        concept_display = concept.replace("_", " ").title() if isinstance(concept, str) else str(concept)
        styles_html = ", ".join(f"<span class='pill pill-style bad'>{s.title()}</span>" for s in styles) if styles else "None"
        wrong_html = ""
        if wrong_ans:
            wrong_html = "<div class='ctx'><b>Wrong Answers</b>"
            for qid, ans in wrong_ans.items():
                wrong_html += f"{qid}: answered '{html.escape(str(ans))}'<br>"
            wrong_html += "</div>"

        items += (
            f"<div class='card'>"
            f"<h2>🚨 {html.escape(sid)} — {html.escape(concept_display)}</h2>"
            f"<div style='display:flex;align-items:center;gap:1rem;margin:0.5rem 0'>"
            f"<span>Mastery:</span>{_mastery_bar_html(mastery_pct)}"
            f"</div>"
            f"<div style='margin:0.5rem 0'>Styles tried: {styles_html}</div>"
            f"{wrong_html}"
            f"<div style='font-size:0.85rem;color:var(--text-dim)'>Budget remaining: {budget} tokens</div>"
            f"<div style='margin-top:0.8rem'><a class='flag-link' href='/q/{q.id}'>Respond →</a></div>"
            f"</div>"
        )

    return _page(
        "AdaptTutor — Flags waiting",
        f"<h1>{len(open_qs)} student(s) need your help</h1>"
        "<p class='sub'>These students could not demonstrate understanding after "
        "two automated explanation attempts. Your guidance resumes their session.</p>"
        + items,
    )


@app.get("/q/{qid}", response_class=HTMLResponse)
def show(qid: str):
    q = _store().get_question(qid)
    if q is None:
        return _page("Not found", "<h1>Not found</h1><p class='sub'>No such flag.</p>")
    if q.is_answered:
        return _page(
            "Already responded",
            "<h1>Already responded</h1><p class='sub'>This flag has been handled.</p>"
            f"<div class='ctx'><b>Response</b>{html.escape(q.answer or '')}</div>"
            "<p><a href='/'>Back</a></p>",
        )

    ctx_html = ""
    for k, v in (q.context or {}).items():
        if k == "resume_state":
            continue
        label = str(k).replace("_", " ").title()
        value = str(v)
        if k == "mastery_pct":
            value = f"{v}%"
        elif k == "wrong_answers" and isinstance(v, dict):
            value = ", ".join(f"{qid}: '{ans}'" for qid, ans in v.items())
        elif k == "styles_tried" and isinstance(v, list):
            value = ", ".join(s.title() for s in v)
        ctx_html += f"<div class='ctx'><b>{html.escape(label)}</b>{html.escape(value)}</div>"

    return _page(
        "Student needs help",
        f"<h1>Student needs help</h1>"
        "<p class='sub'>Provide a hint, suggest a 1-on-1 session, or note your "
        "guidance. Your response resumes the student's session.</p>"
        f"<p class='q'>{html.escape(q.question)}</p>{ctx_html}"
        f"<form method='post' action='/q/{q.id}'>"
        "<textarea name='answer' autofocus placeholder='Your hint or guidance…'></textarea>"
        "<input type='hidden' name='who' value='instructor'>"
        "<button type='submit'>Send Guidance</button></form>"
        "<p class='note'>Your response is recorded as instructor guidance and kept "
        "separate from automated explanations.</p>",
    )


@app.post("/q/{qid}")
async def submit(qid: str, request: Request):
    raw_body = (await request.body()).decode("utf-8")
    import urllib.parse
    params = urllib.parse.parse_qs(raw_body)
    text = params.get("answer", [""])[0].strip()
    who = params.get("who", ["instructor"])[0].strip()
    if not text:
        return RedirectResponse(f"/q/{qid}", status_code=303)
    callback.answer(_store(), qid, text, who=who)
    return RedirectResponse("/thanks", status_code=303)


@app.get("/thanks", response_class=HTMLResponse)
def thanks():
    return _page(
        "Thank you",
        "<h1>Thank you</h1><p class='sub'>The student's session has resumed "
        "with your guidance.</p>"
        "<p><a href='/'>Any other flags?</a></p>",
    )


# ── Student Roster Dashboard (/students) ───────────────────────────────────

@app.get("/students", response_class=HTMLResponse)
def student_roster():
    s = _store()
    student_ids = s.get_all_student_ids()

    if not student_ids:
        return _page(
            "AdaptTutor — Student Roster",
            "<h1>Student Roster</h1>"
            "<p class='sub'>No student data yet. Run a session or demo first.</p>"
            "<p class='empty'>Student profiles appear here after students take the quiz.</p>",
            active="students",
        )

    cards = ""
    for sid in student_ids:
        profile = s.get_learner_profile(sid)
        mastery = profile["mastery"]
        weak = profile["weak_concepts"]
        strong = profile["strong_concepts"]
        eff = profile["style_efficacy"]

        # Overall mastery
        if mastery:
            overall = sum(mastery.values()) / len(mastery) * 100
        else:
            overall = 0

        # Concept rows
        concept_rows = ""
        for concept, m in sorted(mastery.items()):
            pct = m * 100
            tag = ""
            if concept in strong:
                tag = "<span class='pill pill-strong'>Strong</span>"
            elif concept in weak:
                tag = "<span class='pill pill-weak'>Weak</span>"
            concept_rows += (
                f"<div class='concept-row'>"
                f"<span class='concept-name'>{concept.replace('_', ' ').title()}</span>"
                f"{_mastery_bar_html(pct)} {tag}"
                f"</div>"
            )

        # Style efficacy pills
        eff_pills = ""
        for style, data in eff.items():
            pct = int(data["rate"] * 100)
            cls = "good" if pct >= 50 else "bad"
            eff_pills += (
                f"<span class='pill pill-style {cls}'>"
                f"{style.title()}: {data['wins']}/{data['total']} ({pct}%)"
                f"</span>"
            )
        if not eff_pills:
            eff_pills = "<span class='pill pill-style'>No interventions yet</span>"

        cards += (
            f"<div class='card student-card'>"
            f"<div style='display:flex;align-items:center;justify-content:space-between'>"
            f"<h2>👤 {html.escape(sid)}</h2>"
            f"<div>Overall: {_mastery_bar_html(overall)}</div>"
            f"</div>"
            f"<div>{concept_rows}</div>"
            f"<div class='style-efficacy'>"
            f"<span style='font-size:0.8rem;color:var(--text-dim);margin-right:0.3rem'>Style Efficacy:</span>"
            f"{eff_pills}"
            f"</div>"
            f"</div>"
        )

    return _page(
        "AdaptTutor — Student Roster",
        f"<h1>Student Roster</h1>"
        f"<p class='sub'>{len(student_ids)} student(s) tracked. "
        f"Showing mastery breakdown, concept tags, and style efficacy.</p>"
        f"<div class='student-grid'>{cards}</div>",
        active="students",
    )
