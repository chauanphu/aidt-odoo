# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fork of the **Odoo 19** source tree (`odoo/`, `addons/`, `odoo-bin`) used as a
platform. **All project work happens in `custom-addons/`** — the `aidt_*` modules
that implement a Vietnamese government document-management / office-automation
system (văn bản đến/đi, nhiệm vụ, ký số, họp, tìm kiếm). `extra-addons/dms` is
vendored OCA DMS. Touch `odoo/` or `addons/` only when patching upstream is the
only option, and say so explicitly.

Everything user-facing — field labels, menus, error messages, module READMEs,
`docs/` — is written in **Vietnamese**. Code comments in `custom-addons/` are
mostly Vietnamese too, and they carry hard-won operational detail (see the
comment blocks in `docker-compose.ai.yml`); read them before changing behaviour
they describe.

## Running things

Everything runs in Docker. The dev stack bind-mounts the repo at `/opt/odoo`, so
host edits are live.

```bash
docker network create aidt-ai-net                     # once, before first up
docker compose -f docker-compose.dev.yml up --build   # http://localhost:8069
docker compose -f docker-compose.ai.yml  up -d --build # GPU tier (see below)
```

Container names: `aidt-odoo-dev-odoo-1`, `aidt-odoo-dev-db-1`.

`--dev=reload,qweb` is the default. Adding `xml` (read view arch from file, no
`-u` needed) disables three server caches and costs ~3.5 s per webclient load —
opt in only while iterating on view XML:
`ODOO_DEV=reload,qweb,xml docker compose -f docker-compose.dev.yml up`.

**Container start auto-upgrades `aidt_demo`.** The `dev` Dockerfile stage bakes
`ODOO_UPDATE_MODULES` (a comma-separated list of every `aidt_*` module) and
`docker/entrypoint.sh` runs `-u` (or `-i` on a fresh DB) before launching. So a
restart already registers Python/view/data changes — you rarely need a manual
`-u`. **When you add a new module, add it to that ENV list in the `Dockerfile`**,
or it will never be installed in dev.

## Tests

Two suites, two runners.

**Pure-Python engine libraries** (`aidt_format_engine/`, `aidt_search_engine/` —
no `__manifest__.py`, no `import odoo`) run under pytest, no database:

```bash
docker exec aidt-odoo-dev-odoo-1 bash -lc \
  'cd /opt/odoo && PYTHONPATH=custom-addons /opt/venv/bin/python3 -m pytest \
     custom-addons/aidt_search_engine/tests -q'
# single file / single test:
#   ... -m pytest custom-addons/aidt_format_engine/tests/test_rules.py -q
#   ... -m pytest custom-addons/aidt_format_engine/tests/test_rules.py::TestX::test_y
```

pytest is only in the `dev` image (`/opt/venv/bin/python3`), not on the host and
not on the container's `/usr/local/bin/python3`. `tests/` directories in these
packages deliberately have **no `__init__.py`** — adding one breaks the bare
`import fixtures` used by the format-engine tests.

**Odoo module tests** (everything under `custom-addons/*/tests/`, plus OWL/hoot
suites under `static/tests/`) need a database:

```bash
docker exec aidt-odoo-dev-odoo-1 /opt/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d aidt_demo -u aidt_search \
  --test-enable --test-tags /aidt_search --stop-after-init
```

`--test-tags /<module>` scopes to one module, `.TestClass` / `.test_method` to
one case. Most suites are `@tagged('post_install', '-at_install')`.

JS tests run through `HttpCase.browser_js`, which **skips rather than fails**
when chromium or `websocket-client` is missing — that once hid three broken hoot
suites for eleven tasks. If a JS suite reports zero assertions, check for a skip
before believing it passed.

Lint config is Odoo upstream's `ruff.toml` (`ruff check`); ruff is not installed
in the image, so it is not part of the normal loop.

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

`reset_db.sh` predates this convention — it drops `aidt_demo` and rebuilds a
database named `aidt`. Don't run it without reading it.

## Architecture

### `aidt.document` is the spine

`aidt.document` is defined once in **`aidt_org`** (with `department_id`,
secrecy level, sharing) and then **extended by `_inherit` in almost every other
module**: `aidt_dms` adds the DMS directory, `aidt_format` the format check,
`aidt_search` the index hooks, `aidt_task` the derived tasks, `aidt_vanban_den`
/ `aidt_vanban_di` the incoming/outgoing lifecycles. Before adding a field or
changing behaviour, grep `_inherit = 'aidt.document'` across `custom-addons/` —
the model's real shape is the union of those files, not `aidt_org` alone.

`aidt_org` also owns the permission model: organisation tree on `hr.department`,
role RBAC on `res.users`, and secrecy levels (`thuong` → `tuyet_mat`) that scope
record access. Permissions on files are **inherited, not duplicated**:
`aidt_dms` hard-constrains the AIDT `dms.storage` to
`save_type='attachment'` + `inherit_access_from_parent_record=True`, so every
`dms.file` defers to its parent `aidt.document`. Turning either off silently
collapses secrecy enforcement — hence the `@api.constrains` guard in
`aidt_dms/models/dms_storage.py`.

### Engine / addon split

Two features use a deliberate two-package pattern; follow it for new heavy logic:

| Package | Shape |
|---|---|
| `aidt_format_engine/`, `aidt_search_engine/` | Pure Python. No `__manifest__.py`, no `import odoo`. Table-driven unit tests under pytest, no DB. |
| `aidt_format/`, `aidt_search/` | Thin Odoo addons: models, views, security, data, OWL assets. |

`aidt_search_engine/_compat.py` is the **only** file in that package allowed to
mention `odoo` — it bridges the two import paths (`odoo.addons.X` inside Odoo,
bare `X` under pytest with `custom-addons` on `sys.path`).

### `*_demo` modules

`aidt_org_demo`, `aidt_vanban_demo`, `aidt_calendar_demo`, … carry seed data
only. Keep demo records out of feature modules and put them here.

### AI tier (`docker-compose.ai.yml`)

Three GPU services on the shared external network `aidt-ai-net`, deliberately
split from the web stack: `aidt-embed` (vLLM, Vietnamese embeddings, used by
`aidt_search`), `aidt-asr` (vLLM Whisper, used by `aidt_meeting_minutes`),
`aidt-llm` (Ollama `gemma3:12b-it-qat`, summaries). They share one 16 GB card,
so **startup order is load-bearing**: vLLM preallocates a fixed fraction, Ollama
sizes itself against whatever is free, so Ollama must start last
(`depends_on: service_healthy`). `docker compose restart <one-vllm-service>`
bypasses that and will OOM — stop `aidt-llm` first, or recreate the whole stack.
The long comment blocks in that file record measured VRAM numbers and the
failures behind each decision; read them before changing images, flags, or model
tags.

Odoo reaches these by container name over `aidt-ai-net`. If the network is
missing, calls fail as "Connection refused" written into a field
(`summary_error`) rather than surfacing — i.e. silently.

`aidt_meeting.llm_model` in `aidt_meeting_minutes/data/ir_config_parameter.xml`
must match the Ollama tag **verbatim**; a one-character drift is a silent 404.

## Documentation obligations

### End-user manual (`docs/GUIDANCE.md`)

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

### Module `README.md`

`aidt_search`, `aidt_meeting_minutes` and `aidt_dashboard_builder` carry a
module README that documents the pipeline, the design trade-offs, and — in a
dedicated section — **what has and has not been verified end-to-end**, with
dates. When you change one of those pipelines, update that verification section
rather than leaving a stale claim standing.

Design/plan documents live in `docs/superpowers/{specs,plans}/` and
`.superpowers/sdd/`. They describe intent at the time of writing and drift from
what shipped — never document behaviour from them; read the code.

`docs/DESIGN.md` is the shared UI design system (tokens, colours, typography)
extracted from `aidt_dashboard_builder`; follow it for new OWL/SCSS work.

## graphify

This project can keep a knowledge graph at `graphify-out/`, with god nodes,
community structure, and cross-file relationships. It is **not currently
generated** — run `graphify update .` (AST-only, no API cost) to create it.

Rules:
- For codebase questions, first run `graphify query "<question>"` when `graphify-out/graph.json` exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current.
