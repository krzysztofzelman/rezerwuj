---
name: gap-audit
description: Audit and fill missing features in a project — systematically verify claimed gaps, prioritize, implement step by step, then verify.
source: auto-skill
extracted_at: '2026-06-14T09:27:55.976Z'
---

# Gap Audit & Fill

Use when the user presents a list of "what's missing" in a project and wants them all implemented.

## Process

### 0. Check memory first

Before starting, check relevant memories — the user may have saved:
- Feedback about fix priorities (e.g. "backend/Docker first, VPS later")
- User preferences (e.g. language, working style)
- Reference pointers (e.g. Linear tickets, Grafana dashboards)

Align with those before diving in.

### 1. Verify every claim against actual code

Do NOT trust the user's assessment blindly. Read the actual source files for every item on their list:

- **Existing function claims**: grep for the exact function name.
- **File claims**: read the file to see what functions actually exist.
- **Route claims**: check the router files — does the handler exist? What does it call?
- **Feature claims**: search for related patterns (imports, config vars, templates).

Document what's real, what's missing, and what's partially done (e.g. "email_mock.py exists but has no provider notification").

### 2. Categorize and prioritize

Map each item to the user's priority (or use this default):

| Priority | Label | Action |
|----------|-------|--------|
| 🔴 Critical | Blocks functionality | Fix first |
| 🟡 Important | Competitive edge | Fix second |
| 🟢 Nice-to-have | Polish / future | Fix last |

### 3. Todo-driven step-by-step implementation

Create a todo list (`todo_write`) with one item per logical change. Work through them sequentially:

```
[{"id":"1","content":"🔴 Add function X to module.py","status":"in_progress"},
 {"id":"2","content":"🔴 Wire function X into route Y","status":"pending"},
 ...]
```

Key rules:
- **One concern per commit-ish step**: don't mix the email function and the ICS export in one step.
- **Read before you edit**: always `read_file` the full file before any `edit` call.
- **Keep existing patterns**: use the same import style, error handling, logging, and HTML patterns already in the project.
- **Template changes**: if the feature needs a UI button/link, add it to the template in the same step as the backend endpoint.

### 4. Verify at the end

1. Run existing tests (`pytest tests/ -v`).
2. Test new module imports (`python -c "from app.new_module import new_function"`).
3. Test app boots (`python -c "from app.main import app"`).
4. For generated content (ICS, CSV etc.), test a sample output programmatically.

All existing tests must still pass. If not, fix regressions before declaring done.

### 5. Commit, push, and verify live deployment

1. **Commit** with a structured multi-line message using the same priority emoji system (🔴 🟡 🟢).
2. **Push** to origin.
3. **Verify deployment** if the project has CI/CD:
   - Check GitHub Actions (or equivalent) ran successfully.
   - Test the **new** endpoints on the live domain to confirm the new code is deployed:
     ```bash
     # Endpoint should respond differently than 404
     curl -s -o /dev/null -w "HTTP %{http_code}" "https://example.com/new-endpoint"
     # HTTP 302 (redirect to login) or 403 (CSRF) = route exists = new code is live
     # HTTP 404 = old code still running = deployment pending/failed
     ```
   - Test existing critical paths too (home page, health check).

## When to use this

- User says "what's missing" or "add everything" or gives a list of features to implement.
- User has a competitive analysis ("this is what Booksy has") and wants parity.
- User presents a priority-ordered wish list (critical → important → nice-to-have).

## Example workflow

```
1. Explore codebase → verify each claim
2. todo_write with ordered steps
3. For each step: read_file → implement → mark done
4. pytest tests/ -v
5. Import smoke tests
```
