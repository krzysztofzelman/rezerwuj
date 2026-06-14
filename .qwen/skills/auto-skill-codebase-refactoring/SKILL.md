---
name: codebase-refactoring
description: Large-scale multi-file refactoring with class renames, model changes, and comprehensive rebranding across a whole codebase
source: auto-skill
extracted_at: '2026-06-14T10:17:49.712Z'
---

# Large-Scale Codebase Refactoring

Use when the user wants to rename classes across an entire project, add/modify model fields, rebrand the application, or perform any refactoring that touches 10+ files with interdependent changes.

## When to use this

- Renaming ORM model classes (e.g., `Provider`→`ServiceProvider`, `Booking`→`Order`)
- Adding new fields to models that ripple through schemas, routers, templates, and tests
- Rebranding an entire application (name, logo, domain references, landing page)
- Changing enums and status systems that affect routing logic and template rendering
- Any refactoring where changes must be applied in a specific dependency order

## Process

### 1. Understand the full scope first

Read the user's specification carefully. Map every file that needs changes and note the dependency order between them:

1. **Models** (no internal deps) — always first
2. **Migrations** (depends on models) — second
3. **Schemas / Pydantic models** (depends on models) — third
4. **Core utility files** (utils, config, auth, csrf, ratelimit) — fourth
5. **Business logic modules** (payments, scheduler, metrics, email_mock, sms_mock, ics_export) — fifth
6. **Router files** (depend on schemas and models) — sixth
7. **Templates** (display router data) — seventh
8. **Tests** — eighth
9. **Documentation / README** — ninth
10. **Config / env files** — last (defaults only)

### 2. Create a state snapshot

Before starting, record the full state in your context: every file, its importance, current status, and any pending/known issues. Update this as you go. This is critical for multi-hour refactoring sessions.

Structure each file entry as:

```
{file, importance: HIGH|MEDIUM|LOW, status: COMPLETED|IN_PROGRESS|PENDING, notes: "..."}
```

### 3. Track progress with a todo list

Use `todo_write` to maintain a numbered phase list. Group logically:

```json
[
  {"id":"1","content":"Phase 1: Refactor models.py (class renames + new fields)","status":"completed"},
  {"id":"2","content":"Phase 2: Create migration file","status":"completed"},
  {"id":"3","content":"Phase 3: Update schemas","status":"in_progress"},
  ...
]
```

### 4. Read before you edit

The `edit` tool requires a `read_file` call in the same session before it can modify a file. Follow this pattern for batch editing:

```python
# Step A: Read all files in a phase
read_file("file1.py", limit=5)
read_file("file2.py", limit=5)
# Step B: Edit each one
edit("file1.py", old="...", new="...")
edit("file2.py", old="...", new="...")
```

### 5. Use background agents for parallelizable router files

When you have multiple router files that all need the same type of change (import updates, query renames), launch background agents to handle them in parallel while you continue with templates or other work.

```python
# Launch agent for file
# Continue working on templates while agent runs
```

**Caveat**: Background agents may not be able to use worktree isolation if there are uncommitted changes — launch without isolation in that case.

### 6. Apply changes in dependency order

Always respect the dependency order. Example:
- **Models first**: because schemas, routers, and templates reference model classes/fields.
- **Migration second**: because the DB must match the new models before the app boots.
- **Schemas third**: because they validate API input/output for the new model shapes.
- **Routers fourth**: because they use both models and schemas.
- **Templates last**: because they display data from routers.

### 7. Keep backward compatibility when possible

If the spec allows it:
- Keep existing table names with `__tablename__` so existing data survives the migration
- Add a legacy property alias (e.g., `bookings = orders` on ServiceProvider) so the router code can be migrated gradually
- Use new columns with `nullable=True` initially
- Keep old status fields as nullable for data migration

### 8. Comprehensive grep-based verification at the end

After all edits are applied, run grep searches to verify no old references remain:

```bash
# Old class names
grep -r "class Provider\|class Booking" app/

# Old imports
grep -r "from app.models import Provider" app/

# Old queries
grep -r "db.query(Provider)" app/

# Old branding
grep -r "Rezerwuj" app/templates/

# Old logger names
grep -r '"rezerwuj"' app/

# Old domain references
grep -r "rezerwuj\.pl" app/
grep -r "rezerwuj\.kzelman" app/
```

Each hit should be a false positive (variable name, template context variable, element ID) — not an actual class reference.

### 9. Update or create migration file

Always create a SQL migration for:
- New tables
- ALTER TABLE statements for new columns
- New indexes on frequently-queried columns

Use IF NOT EXISTS / IF EXISTS guards when possible.

### 10. Update documentation last

Only update README and config examples after all code changes are verified. This avoids documenting something that isn't yet implemented.

## Key invariants to maintain

- **Read → Edit**: Never call `edit` without a prior `read_file` of the same file in the same session.
- **One file, one responsibility**: Don't mix model changes with template changes in the same edit.
- **Verify as you go**: After each phase, do a quick sanity check (import test, grep check) before moving to the next.
- **State tracking**: Keep your state snapshot and todos up-to-date so you can resume after interruptions.
