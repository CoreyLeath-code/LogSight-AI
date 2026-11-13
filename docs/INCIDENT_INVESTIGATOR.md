# Incident investigator

The incident investigator retrieves evidence from approved local Markdown runbooks. It is deliberately retrieval-grounded: it returns ranked excerpts and provenance, rather than generating root-cause claims or executing remediation.

## Runbook contract

Each runbook must be a UTF-8 `.md` file below the selected directory and start with bounded front matter:

```markdown
---
id: database-timeout
title: Database timeout response
version: 1.0.0
---
# Response steps
...
```

At investigation time, operators must provide an immutable source-control revision for the complete runbook set. The result records:

- runbook ID, version, and relative source path;
- supplied repository commit revision;
- SHA-256 digest of the exact runbook file;
- deterministic relevance score and a bounded matching excerpt.

This lets an incident record show exactly which approved guidance was retrieved. The command never downloads runbooks, calls a hosted model, modifies infrastructure, or presents its response as an authorization to act.

## CLI usage

Pin the runbooks to the revision checked out by your deployment or incident workspace:

```bash
logsight investigate "database timeout during checkout" \
  --runbooks ./runbooks \
  --revision "$(git rev-parse HEAD)" \
  --evidence "ERROR connection pool timeout" \
  --evidence "trace_id=abc123"
```

Alternatively, provide the revision through deployment configuration:

```bash
export LOGSIGHT_RUNBOOK_REVISION="$(git rev-parse HEAD)"
logsight investigate "queue consumer lag" --runbooks ./runbooks
```

Review cited excerpts and the surrounding versioned runbook before any production action. A result with no citations is intentionally inconclusive; it should prompt human triage or authoring of an approved runbook, not an invented recommendation.

## Promotion controls

- Store runbooks with code review and immutable release/commit history.
- Require incident responders to include the returned revision and digest in an incident record.
- Review changes to runbook wording as operational changes, including rollback implications.
- Use access-controlled repositories and deployment-owned checkout paths for production runbooks.
