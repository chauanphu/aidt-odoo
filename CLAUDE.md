## Database convention (dev/staging)

There is exactly **one** persistent Odoo database in the dev stack: **`aidt_demo`**.
It is the single source of truth for demo state — every feature that needs
demo/seed data installs into `aidt_demo`, not a new database.

Rules:
- Never create a new named database for a feature, module install, or demo
  session (no `aidt_poc`, `aidt_<feature>_demo`, `db`, etc.). Install into
  `aidt_demo`: `-d aidt_demo -i <module>` / `-u <module>`.
- Automated tests may use a throwaway database (e.g. `aidt_test`), but **you
  must drop it (and its filestore dir under `/var/lib/odoo/filestore/`) when
  the test run finishes** — `DROP DATABASE aidt_test;` plus `rm -rf` the
  filestore dir. Don't leave `aidt_test_*`, `*_tmp`, `*_tmp_<timestamp>`, or
  similar scratch databases lying around.
- If you must inspect state destructively (e.g. a risky migration), duplicate
  `aidt_demo` first, work on the copy, then drop the copy when done — don't
  fork the "canonical" name.
- Before ending a work session, verify only `aidt_demo` remains:
  `docker exec aidt-odoo-dev-db-1 psql -U odoo -d postgres -c "\l"` and
  `docker exec aidt-odoo-dev-odoo-1 ls /var/lib/odoo/filestore/` should both
  show a single `aidt_demo` entry (aside from Postgres system databases).

## End-user documentation (`docs/GUIDANCE.md`)

`docs/GUIDANCE.md` is the **living end-user manual** — written in Vietnamese
for văn thư / chuyên viên / lãnh đạo, not for developers or admins. It evolves
with the product: every shipped feature gets a section, and every change to an
existing feature's user-visible behaviour updates the section it belongs to.

Rules:
- **A feature is not finished until `docs/GUIDANCE.md` covers it.** Treat this
  as part of the definition of done, alongside tests passing — not a follow-up
  task. Add a numbered section and a row in the index table at the top.
- Write in **Vietnamese**, matching the UI language. A guide in English forces
  the reader to translate menu names as they read.
- Describe **what the user sees on screen**: exact menu paths, button labels,
  banner text. Verify every one of them against the actual view XML / OWL
  templates before writing it down — never from memory, and never from a spec
  or plan document (those describe intent, which drifts from what shipped).
- Explain the behaviours users will otherwise **misread**, and say why. Two
  similar-looking messages that mean opposite things deserve a paragraph, not
  a mention.
- **Flag what is unverified.** A feature whose code path has never run
  end-to-end is documented with a warning, not described as working. Same for
  thresholds calibrated on toy data.
- Keep admin-only material in the clearly separated trailing section so end
  users never wander into it. Deep technical detail belongs in the module's
  `README.md`; link to it rather than inlining it.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
