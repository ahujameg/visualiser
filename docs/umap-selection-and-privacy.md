# UMAP selection and case-ID privacy

## Request contract

The visualiser must receive the real case key separately from the de-identified
label shown in the cases table. The preferred request field is:

```json
{
  "selected_case_id": "CASE-123",
  "selected": "Not available"
}
```

For compatibility, the visualiser also extracts `case_ID_paper`/`case_id` from
`selected_case`, `selectedCase`, `selected_row`, or `selectedRow`. It can also
resolve a row from `selected_index`/`selectedIndex` plus the `cases` array.

HGQN should therefore keep the DB identifier on the row model even when the
visible table cell is replaced by `Not available`. The UMAP button must pass the
hidden row identifier, not the rendered cell value.

## Display rules

The identifier is used only to match and highlight the selected point. UMAP
hover text is redacted by default.

Case IDs are retained only when one of these server-side conditions is true:

1. The visualiser request is authenticated as a Django staff/superuser account.
2. The trusted HGQN backend adds the header
   `X-HGQN-Visualiser-Admin-Token`, matching the visualiser environment variable
   `HGQN_VISUALISER_ADMIN_TOKEN`.

The shared token must never be sent to browser JavaScript. HGQN should proxy the
visualiser request and add the header only after it has verified that the current
HGQN user is an administrator.

## Deployment

Set the same strong random value in the trusted HGQN backend and the visualiser:

```text
HGQN_VISUALISER_ADMIN_TOKEN=<random secret>
```

Non-admin requests omit the header. If the environment variable is absent or
empty, the visualiser fails closed and hides case IDs.
