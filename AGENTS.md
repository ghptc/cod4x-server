# Repository governance

This is ghptc's maintained fork of callofduty4x/CoD4x_Server. Preserve upstream
Git history, source layout, licenses, copyright notices, and attribution.

- Target pull requests at `master`; use feature branches and Conventional Commits.
- The owner reviews and merges manually. Never merge, force-push, rewrite history,
  publish a release, deploy, or change running services without explicit approval.
- Priorities: Promod AI gameplay, stability, Auto-Fill, human admission priority,
  and bot administration. General administration work follows stable bots.
- Do not add/configure GitHub Actions, CI/CD, image publishing, deployments,
  infrastructure management, or monitoring stacks under the current scope.
- Keep integrity changes independent of bot changes. Preserve `sv_pure=1` and
  the eight administrative headers; do not add temporary PURE_DIAG logging.
- Never commit credentials, proprietary game/Promod assets, extracted game scripts,
  downloaded dependencies, generated binaries, build caches, or full runtime logs.
- Keep local runtimes isolated. Do not touch production, AWS, or Bard.
- Preserve the known-working PoC and its evidence before modifying it.
- Document exact dependency revisions, meaningful gameplay evidence, test limits,
  and rollback. CS_ACTIVE alone is not proof of AI gameplay.
- Prefer existing engine/GSC capabilities and small focused changes over frameworks.

Remotes: `origin` is `https://github.com/ghptc/cod4x-server.git`; `upstream` is
`https://github.com/callofduty4x/CoD4x_Server.git`. Inspect before changing them.
