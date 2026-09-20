# Run AdaptTutor

```bash
export OPENROUTER_API_KEY=your-openrouter-api-key
python run.py demo
```

*(Note: An active key is already configured in `.env`, so you can directly run `python run.py demo`)*

### What You Will Watch
This executes the live adaptive tutoring demo across 3 distinct student personas using the real OpenRouter LLM:
1. **Ananya (`ananya_analogy`)**: Resolves knowledge gap on first attempt with Analogy style.
2. **Bharat (`bharat_trace`)**: Retest failure triggers targeted mistake feedback, adapts teaching style to Trace, and succeeds.
3. **Karthik (`karthik_stuck`)**: Demonstrates retest pool exhaustion detection, transitions into 3-step interactive Guided Practice, and validates via fresh independent retest.

---

### Instructor Web Dashboard (Browser)
To inspect real-time student mastery profiles, weak/strong concept tags, and escalated flags:

1. Start the server:
   ```bash
   python -m uvicorn web.expert:app --host 127.0.0.1 --port 8000
   ```
2. Open your browser at:
   ```
   http://127.0.0.1:8000/students
   ```

---

### Interactive Student Mode (Alternative)
To take the diagnostic assessment and experience the adaptive tutor interactively:

```bash
python run.py session judge_demo
```
