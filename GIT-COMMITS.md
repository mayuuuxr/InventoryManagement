# Clean Commits Plan — nibba (template 07)

nibba is not a git repo yet (`.git` was excluded on copy). Run once in `C:\Users\mayuuuxr\Downloads\nibba`:

```
git init
git add .gitignore
git commit -m "chore(repo): init nibba PC-only project from app copy"
```

Then atomic commits in this order (repo builds + `manage.py check` passes each step):

```
git add entries/forms.py entries/admin.py
git commit -m "feat(entries): make photo proof optional for PC-only use

Inward/Outward save with 0-2 photos; only max-2 enforced.
Why: owner runs single PC, no photo entry; legacy rows keep showing."

git add requirements-pc.txt run_pc.bat
git commit -m "feat(pc): add lean requirements plus waitress launcher with backup

waitress serves 0.0.0.0:8000; run_pc.bat backs up db.sqlite3 keeping 30.
Why: stable always-on Windows server, one-file backup, data stays on PC."

git add PRD-PC.md DESIGN-PC.md
git commit -m "docs(pc): add PC-only PRD and design brief

Locks owner-PC-full plus staff-phone-entry scope, no-photo MVP.
Why: every future prompt stays scoped to PC build."

git add SECURITY-AUDIT.md CLEANUP-AUDIT.md DEBUG-PROCESS.md
git commit -m "docs(pc): add security audit, cleanup audit, debug process

Report-only; no code changed. Orders CRITICAL-1 key rotation first.
Why: pre-tunnel review trail before phones connect."

git add e2e/ .github/workflows/e2e.yml
git commit -m "test(e2e): add Playwright journeys for login, inward, outward

Auth fixture, seeded isolated data, CI on PR with traces.
Why: verify phone-entry-hits-PC acceptance without manual retests."
```

Never use `fix stuff` / `wip` / `changes`. Types: feat, fix, refactor, perf, docs, test, chore.
