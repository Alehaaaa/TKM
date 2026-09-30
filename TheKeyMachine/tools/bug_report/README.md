# Ticket Manager

Open **Get in Touch → Ticket Manager** to browse every ticket in the repository,
regardless of its author. Opening the manager refreshes the full inbox.
The window supports text search, open/closed filters, ticket details, and opening
the full conversation on GitHub.

To enable the manager, authenticated repository access, and startup checks, add these settings to the local,
Git-ignored `TheKeyMachine/.env` (process environment values also work):

```dotenv
TKM_TICKETS_DEBUG=true
TKM_TICKETS_TOKEN=your_fine_grained_github_token
```

The token requires **Issues: Read and write** permission for
`Alehaaaa/TKM-bug-inbox`. It is used for authenticated GitHub reads and explicit status changes, never
stored in the ticket cache or sent to the bug-report relay.

With the flag enabled, startup fetches all pages of issues in the background.
Previously unseen open issues display a notification whose **Open ticket** button
selects that ticket in the manager. **Refetch Issues** is available in Get in Touch
and in the manager. Successful fetches are cached locally; failed fetches retain
the previous cache and show an error. Pull requests are excluded.

With the flag disabled (the default), Ticket Manager and Refetch Issues are hidden.
Direct manager, refresh, and edit calls are also disabled. Existing sent-report
status checks still run.

Select a ticket, choose **Reported**, **In progress**, **Completed**, or
**Cancelled**, then click **Apply status**. Reported and In progress open/reopen
the issue; Completed closes it as completed; Cancelled closes it as not planned.
The matching `status:*` label is updated while other labels are preserved.
Edits run in the background, disable duplicate actions while pending, and update
the cache only after GitHub confirms success. Editing requires a token with Issues read/write access.

On macOS, ticket API reads and writes try normal certificate verification first.
If Maya's Python cannot verify the server certificate, that request is retried
once with an unverified SSL context. Other failures and platforms do not use
this compatibility fallback.

Ticket descriptions render as Markdown, with relay bookkeeping comments hidden.
The Report tab contains the narrative and formatted tracebacks; System details
has its own tab. Status colors and action hints explain each workflow state.
