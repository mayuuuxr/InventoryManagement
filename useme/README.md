# useme — Change / Bug / Report Log

Single folder for everything an agent (or human) needs after coming back to
this repo cold: what changed, what broke, what tests did/didn't pass, and
which commit was HEAD at the time. **Update it every working session, and
always record the git HEAD hash of the run.**

## Structure

| File / folder | What goes here |
|---|---|
| `change-log.md` | Every code/doc/migration change. New entries at the TOP. Tag version + git HEAD. |
| `bug-log.md` | Bugs found, chosen fixes, watch items. New entries at the TOP. |
| `test-reports/` | One file per test-run: `YYYY-MM-DD_<suite>_run.md` — pass/fail count, duration, failures verbatim. |
| (adhoc) | Full reports (audits, sweeps, migration notes) can live as dated `.md` files right here. |

## Rules

1. Always include, per entry: date, git HEAD hash, working-tree state
   (clean / which files were deliberately left uncommitted), VERSION.
2. If a change is made but NOT committed, say so loudly — that's the
   state future sessions most often need to reconstruct.
3. Bugs: log even minor ones closed instantly (pattern value > archive ones).
4. Never paste secrets (e.g. `.env` contents) into these files.
5. These files are safe to commit — they contain no data from `db.sqlite3`
   except counts, never customer/entry personal data.
