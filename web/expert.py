"""
The page an instructor answers on.

When a student exhausts both explanation styles, the system suspends and parks
a question for the instructor. This web interface shows those pending flags
and lets the instructor submit a hint or note.

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


PAGE = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{color-scheme:light dark}}
body{{font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;max-width:38rem;
margin:0 auto;padding:2rem 1.2rem 4rem}}
h1{{font-size:1.35rem;margin:0 0 .3rem}}
.sub{{color:#6b7280;font-size:.9rem;margin:0 0 1.8rem}}
.card{{border:1px solid #d4d4d8;border-radius:8px;padding:1.1rem 1.2rem;margin:0 0 1rem}}
.q{{font-size:1.1rem;font-weight:600;margin:0 0 .8rem}}
.ctx{{background:rgba(127,127,127,.09);border-radius:6px;padding:.8rem 1rem;
font-size:.9rem;margin:0 0 1.2rem;white-space:pre-wrap;overflow-wrap:anywhere}}
.ctx b{{display:block;font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;
color:#6b7280;margin-bottom:.35rem;font-weight:600}}
textarea{{width:100%;min-height:9rem;font:inherit;padding:.7rem;border:1px solid #a1a1aa;
border-radius:6px;background:transparent;color:inherit}}
button{{font:inherit;font-weight:600;padding:.6rem 1.4rem;margin-top:.8rem;
border:0;border-radius:6px;background:#0d5c5f;color:#fff;cursor:pointer}}
a{{color:#0d5c5f}} .empty{{color:#6b7280}}
.note{{font-size:.85rem;color:#6b7280;margin-top:1.2rem}}
</style>
{body}"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(PAGE.format(title=html.escape(title), body=body))


@app.get("/", response_class=HTMLResponse)
def index():
    s = _store()
    callback.sweep(s)
    open_qs = callback.pending(s)
    if not open_qs:
        return _page("AdaptTutor — No flags waiting",
                     "<h1>No flags waiting</h1>"
                     "<p class='sub'>No student is currently waiting for instructor help.</p>"
                     "<p class='empty'>This page will show flags when a student fails both "
                     "explanation styles and needs your direct guidance.</p>")
    items = "".join(
        f"<div class='card'><p class='q'>{html.escape(q.question)}</p>"
        f"<a href='/q/{q.id}'>Respond &rarr;</a></div>" for q in open_qs)
    return _page("AdaptTutor — Flags waiting",
                 f"<h1>{len(open_qs)} student(s) need your help</h1>"
                 "<p class='sub'>These students could not demonstrate understanding after "
                 "two automated explanation attempts. Your guidance resumes their session.</p>"
                 + items)


@app.get("/q/{qid}", response_class=HTMLResponse)
def show(qid: str):
    q = _store().get_question(qid)
    if q is None:
        return _page("Not found", "<h1>Not found</h1><p class='sub'>No such flag.</p>")
    if q.is_answered:
        return _page("Already responded",
                     "<h1>Already responded</h1><p class='sub'>This flag has been handled.</p>"
                     f"<div class='ctx'><b>Response</b>{html.escape(q.answer or '')}</div>"
                     "<p><a href='/'>Back</a></p>")
    ctx = ""
    for k, v in (q.context or {}).items():
        if k == "resume_state":
            continue
        ctx += (f"<div class='ctx'><b>{html.escape(str(k).replace('_',' '))}</b>"
                f"{html.escape(str(v))}</div>")
    return _page("Student needs help",
                 f"<h1>Student needs help</h1>"
                 "<p class='sub'>Provide a hint, suggest a 1-on-1 session, or note your "
                 "guidance. Your response resumes the student's session.</p>"
                 f"<p class='q'>{html.escape(q.question)}</p>{ctx}"
                 f"<form method='post' action='/q/{q.id}'>"
                 "<textarea name='answer' autofocus placeholder='Your hint or guidance&hellip;'></textarea>"
                 "<input type='hidden' name='who' value='instructor'>"
                 "<button type='submit'>Send</button></form>"
                 "<p class='note'>Your response is recorded as instructor guidance and kept "
                 "separate from automated explanations.</p>")


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
    return _page("Thank you",
                 "<h1>Thank you</h1><p class='sub'>The student's session has resumed "
                 "with your guidance.</p>"
                 "<p><a href='/'>Any other flags?</a></p>")
