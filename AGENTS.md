# Agent working agreement

Use the repository's code, configuration, README, and implementation plan for project facts. Keep this file about how to work; do not copy the current architecture, commands, versions, or roadmap into it.

## Commits

- Use Conventional Commits for commit subjects and PR titles: `type(scope): imperative summary` (or `type: imperative summary` when a scope adds no clarity). Common types are `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, and `chore`.
- Make each commit atomic: one coherent change that can be understood and reviewed on its own. Include the tests and documentation needed for that change in the same commit. Do not split work into artificial commits to increase the count.
- Keep unrelated formatting or cleanup out of a feature or fix commit. Do not rewrite published history or force-push a shared branch unless the user explicitly asks.

## Pull requests

- Work on a short-lived branch and open a PR for a coherent change. Push directly to the default branch only when the user explicitly requests it.
- Keep the PR focused. Explain why the change is needed, what changed, how it was verified, and any material limitation. Link an existing issue when there is one.
- Check CI and address failures caused by the change. Treat merging as a review step; follow the user's instruction about when to merge.

## Before handing off

- Review the diff and run the relevant checks, including `git diff --check`. Inspect tracked files for secrets and generated artifacts.
- State which checks ran and their results. If a check could not run, say why rather than presenting it as passed.
- Update existing documentation when behavior or setup changes, and keep the documentation accurate for the current repository state.
