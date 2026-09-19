"""
The spine.

This package is the durable engine reused from agentic-slice-kit.
It provides: append-only SQLite store, deterministic runner,
single LLM choke point, budget fences, and callback suspension.

    records.py   what a run is made of          (stdlib)
    store.py     durable append-only state      (stdlib)
    budget.py    the fences                     (stdlib)
    llm.py       the one place model calls happen
    runner.py    the state machine
    callback.py  suspend, resume, time out
"""
__version__ = "0.1.0"
