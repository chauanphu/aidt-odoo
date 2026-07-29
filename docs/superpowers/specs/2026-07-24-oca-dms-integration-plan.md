# OCA DMS Integration — Plan

**Date:** 2026-07-24
**Scope:** Bring OCA's Document Management System (`OCA/dms`) into this Odoo 19 fork as the Community replacement for Odoo Enterprise `documents`.

## Context

- This repo is a fork of Odoo **19.0** community source (`odoo/release.py` → `version_info = (19, 0, 0, FINAL, 0, '')`).
- Odoo `documents` is an Enterprise module and is not available here. `OCA/dms` is the established Community alternative.
- **`OCA/dms` branch `19.0` is empty** — a single "Initial commit" (2025-09-30) with only `.github`; no modules have been migrated yet.
- **Branch `18.0` is the newest real code** and is actively maintained (latest commit 2026-07-22). It is what we vendor.
- Running an 18.0 manifest on Odoo 19 is rejected by the addon loader, so a minimal 18→19 adaptation is unavoidable. The plan treats that adaptation as *our* patch set on top of pinned upstream, not as a fork.

### Measured size of the 18→19 gap

Grepped `OCA/dms@18.0` against this tree; the APIs it uses still exist in Odoo 19:

| Checked | Result |
|---|---|
| `@mail/core/common/attachment_model`, `@mail/core/common/link_preview` | present |
| `@web/core/file_viewer/file_viewer_hook`, kanban/list controller + renderer | present |
| `_sql_constraints` (old-style) | still used by core `lunch` → still supported |
| `<tree>` view tags | none |
| `name_get()` | none |
| `check_access_rights` / `check_access_rule` | none |

So the expected patch surface is small: manifest series bump plus whatever the loader actually complains about.

### Modules and their fate

| Module | Decision | Reason |
|---|---|---|
| `dms` | **integrate** | Core: `dms.storage` → `dms.directory` → `dms.file`, tags, categories, access groups |
| `dms_field` | **integrate** | Embeds a DMS view inside any record's form — the actual "integration" capability |
| `dms_auto_classification` | defer | Add once core is stable; rule-based auto-filing |
| `dms_field_auto_classification` | defer | Depends on both of the above |
| `hr_dms_field` | defer | Only if employee document files are needed |
| `dms_user_role` | **excluded** | Depends on `base_user_role` (OCA/server-backend), not vendored here |
| `web_editor_media_dialog_dms` | **excluded** | Depends on `web_editor`, which **does not exist in Odoo 19** (replaced by `html_editor`). Would need a real port, not a version bump. |

## Decisions

**Vendor location: `extra-addons/`, not `addons/`.**
`addons/` is upstream Odoo core; mixing third-party modules in makes future rebases against odoo/odoo painful. A separate directory keeps the boundary legible.

**Vendor method: `git subtree`.**
Code lands in-tree so a plain `git clone` is enough for any developer (no `--recursive` footgun), our 18→19 patches are ordinary commits in this repo, and `git subtree pull` still pulls upstream fixes. A submodule cannot hold our patches without forking OCA/dms first; a plain copy severs the update path entirely.

**Scope for this pass: `dms` + `dms_field`.**
Core first keeps the error surface small enough to diagnose. The deferred modules are additive and can follow once the core installs and passes tests.

## Deliverables

| File | Change |
|---|---|
| `extra-addons/dms/**` | Vendored `OCA/dms@18.0` (subtree), 5 modules present, 2 excluded ones deleted |
| `extra-addons/README.md` | Upstream URL, pinned commit, applied patch list, `git subtree pull` recipe |
| `docker/odoo.conf` | `addons_path` gains `/opt/odoo/extra-addons` |

`docker-compose.dev.yml` needs no change — it already bind-mounts the repo root at `/opt/odoo`, so `extra-addons/` appears in the container automatically.

## Steps

### Phase 0 — Addons path

1. Edit `docker/odoo.conf`: `addons_path = /opt/odoo/addons,/opt/odoo/extra-addons/dms,/opt/odoo/custom-addons`. Each vendored repo needs its own entry — modules live one level below the repo root (`extra-addons/dms/dms/`), so pointing at `extra-addons/` alone finds nothing.
2. Restart the dev stack and confirm Odoo starts and logs the new path.

### Phase 1 — Vendor

3. `git subtree add --prefix extra-addons/dms https://github.com/OCA/dms.git 18.0 --squash`.
4. Delete `dms_user_role/` and `web_editor_media_dialog_dms/` from the vendored tree (excluded above), plus repo-level lint scaffolding that conflicts with this repo's `ruff.toml`.
5. Record the pinned upstream commit SHA in `extra-addons/README.md`.

### Phase 2 — Make it install

6. Bump `"version"` in the manifests of `dms` and `dms_field` from `18.0.x.y.z` to `19.0.x.y.z` — Odoo refuses a manifest from another series.
7. Create a scratch database and install `dms`:
   `docker compose -f docker-compose.dev.yml exec odoo odoo -d dms_test -i dms --stop-after-init`
8. Fix whatever the loader reports, one error at a time, reading the actual traceback. **No speculative rewrites** — every edit must be traceable to a real failure.
9. Repeat for `dms_field`.
10. Each fix is its own commit with a `[MIG]` prefix so the patch set stays separable from upstream and is upstreamable to OCA later.

### Phase 3 — Verify

11. Run the module tests: `odoo -d dms_test -i dms,dms_field --test-enable --stop-after-init`.
12. Drive the real UI at http://localhost:8069 — create Storage → Directory → upload a file → confirm preview, tags, and the move/share wizards.
13. Add a `dms_field` embed to one model's form view and confirm files attach and list correctly.

### Phase 4 — Document

14. Write `extra-addons/README.md`: what was vendored, at which commit, which modules were dropped and why, the full list of 18→19 patches, and how to pull upstream updates.

## Risks

- **Phase 2 is the only open-ended step.** The grep evidence says the gap is small, but the true cost is unknown until the loader runs. If it turns out large, the fallback is to stop after `dms` and defer `dms_field`.
- **`web_editor_media_dialog_dms` is a genuine port, not a bump.** If media-dialog integration is required later, budget separate work to move it onto `html_editor`.
- **Upstream will eventually publish `19.0`.** Our patches should be kept as small, clearly-labelled commits so switching the subtree to the official 19.0 branch later is a `git subtree pull`, not a rewrite.

## Out of scope

- Migrating existing documents from any current storage into DMS.
- OCR / AI invoice extraction, e-signature, or Enterprise-style public share links.
- `base_user_role` and the OCA/server-backend dependency chain.
