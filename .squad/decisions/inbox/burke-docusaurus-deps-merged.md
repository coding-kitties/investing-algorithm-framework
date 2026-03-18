### 2026-03-18T12:00:00Z: Docusaurus Dependabot PRs — merge results
**By:** Burke (Docs/DevRel)
**Requested by:** marcvanduyn

**Merged (1):**
- PR #368 — Bump ajv from 6.12.6 to 6.14.0 in /docusaurus ✅ (CI green, merged with admin override for branch protection)

**NOT merged — merge conflicts (6):**
- PR #315 — Bump serialize-javascript from 6.0.1 to 6.0.2 in /docs (CONFLICTING + failing CI)
- PR #314 — Bump prismjs from 1.29.0 to 1.30.0 in /docs (CONFLICTING + failing CI)
- PR #313 — Bump @babel/runtime from 7.22.6 to 7.27.3 in /docs (CONFLICTING + failing CI)
- PR #312 — Bump http-proxy-middleware from 2.0.6 to 2.0.9 in /docs (CONFLICTING + failing CI)
- PR #311 — Bump @babel/runtime-corejs3 from 7.22.6 to 7.27.3 in /docs (CONFLICTING + failing CI)
- PR #310 — Bump nanoid from 3.3.6 to 3.3.11 in /docs (CONFLICTING + failing CI)

**Why:** PRs #310-315 all target `/docs` (the Docusaurus build output) and have merge conflicts with the current main branch. They also use an older CI workflow (`test/linting`, `test/test`) that fails. PR #368 targets `/docusaurus` (the source) and uses the current Squad CI workflow, which passes.

**Recommendation:** The 6 conflicting PRs target build output files under `/docs`. Consider closing them since build output shouldn't be tracked in version control, or rebasing them if the lockfile changes are still needed.
