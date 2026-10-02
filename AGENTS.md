# Agent working agreement

Use the repository's code, configuration, README, and implementation plan for project facts. Keep this file about how to work; do not copy the current architecture, commands, versions, or roadmap into it.

## Scope

- Keep changes focused on the user's request. Avoid unrelated refactors, new dependencies, or architectural changes unless they are necessary to complete the work; explain the reason when they are.

## Commits

- Create commits only when the user explicitly requests them. A request to implement or edit something does not authorize a commit. Otherwise, leave the changes uncommitted for review.
- Use Conventional Commits for commit subjects and PR titles: `type(scope): imperative summary` (or `type: imperative summary` when a scope adds no clarity). Common types are `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, and `chore`.
- Make each commit atomic: one coherent change that can be understood and reviewed on its own. Include the tests and documentation needed for that change in the same commit. Do not split work into artificial commits to increase the count.
- Keep unrelated formatting or cleanup out of a feature or fix commit. Do not rewrite published history or force-push a shared branch unless the user explicitly asks.

## Pull requests

- Create a PR only when the user explicitly requests one. Permission to commit or push does not by itself authorize a PR. Push changes only when requested or necessary for an explicitly requested PR.
- When a PR is requested, use a short-lived branch and keep the PR focused. Explain why the change is needed, what changed, how it was verified, and any material limitation. Link an existing issue when there is one.
- Check CI and address failures caused by the change. Merge only when the user explicitly requests it.

## Before handing off

- Review the diff, including `git diff --check`. Inspect new files as well as tracked changes for secrets and generated artifacts.
- Run the smallest set of checks needed to verify the change. Documentation-only changes usually need a diff review, not application tests. For code changes, start with the tests related to the affected behavior.
- After checks pass, do not repeat them unless relevant code changes, a failure, or an unresolved concern justifies it. Run larger sets of tests only when the change affects multiple components or a required CI gate demands them.
- State which checks ran and their results. If a check could not run, say why rather than presenting it as passed.
- Update existing documentation when behavior or setup changes, and keep the documentation accurate for the current repository state.
