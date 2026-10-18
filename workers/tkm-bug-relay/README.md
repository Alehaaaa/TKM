# TKM bug-report relay

This Cloudflare Worker accepts bug reports from TheKeyMachine and creates
or groups issues in `Alehaaaa/TKM`. No GitHub credential is distributed with TKM.
The supported write path is Maya toolbar → Worker → GitHub.

## Required configuration

- KV binding: `REPORTS`
- Plain variables: `GITHUB_OWNER`, `GITHUB_REPO`
- Encrypted secrets: `GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID`,
  `GITHUB_PRIVATE_KEY`, `RATE_LIMIT_SALT`

The GitHub App needs only repository metadata read access and Issues read/write
access, and should be installed only on `Alehaaaa/TKM`.

## Labels

The relay self-heals the labels it applies in `Alehaaaa/TKM`:

- `bug`
- `suggestion`
- `enhancement`
- `source:auto-detected`
- `source:user-reported`
- `frequent`
- `regression`
- `area:*` labels as they appear

GitHub downloads App keys as PKCS#1 PEM files. Convert the key to unencrypted
PKCS#8 before storing it as `GITHUB_PRIVATE_KEY`:

```sh
openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt \
  -in downloaded.private-key.pem -out worker.private-key.pem
```

Never commit either key. The relay returns health information at `/health` and
accepts reports at `/report`. Deploy from this directory with `npm run deploy`.

The repository's issue chooser intentionally offers no GitHub issue form. A
workflow closes and locks issues that do not carry one of the trusted
`source:*` labels applied atomically by this Worker.

The Worker requires `public_issue_disclosure_shown: true`. Updated toolbar
clients set it only alongside UI copy that explains reports become public
GitHub issues. Older clients are rejected and retain their existing local-file
fallback instead of silently publishing a report they described as private.

KV report, cluster, label, and installation-token caches are namespaced by
their repository or installation. This is required when reusing the original
`REPORTS` namespace: records containing issue numbers from `TKM-bug-inbox`
must never be applied to same-numbered issues in `TKM`.
