# AzuraCast Module Architecture

Roles remain the supported whole-instance convergence interface. Resource
modules provide a direct Ansible task interface for one resource at a time when
callers want native `changed` status, check-mode behavior, diffs, and structured
return values.

## Layers

- `plugins/module_utils/azuracast_client.py` owns authenticated JSON HTTP
  transport and generic path-template helpers.
- `plugins/module_utils/azuracast_openapi.py` reads saved or live OpenAPI
  documents for endpoint and payload metadata.
- `plugins/module_utils/azuracast_planning.py` owns normalization, comparable
  desired shapes, sensitive-field redaction, storage reference resolution, and
  role planning helpers.
- `plugins/module_utils/azuracast_resources.py` owns private resource metadata,
  OpenAPI capability validation, one-resource reconciliation, result shaping,
  check mode, and sanitized diffs.
- `plugins/modules/*.py` stays thin: parse Ansible parameters, build the desired
  payload, pass resource metadata to the shared reconciler, and translate
  planning or API errors to `fail_json`.

## Resource Contract

Each public resource module declares a private `ResourceSpec` with:

- resource family label;
- collection path;
- item path;
- stable key;
- optional scope fields such as `station_id`;
- supported create, update, and delete operations.

The shared result shape is:

- `changed`;
- `action`;
- `before`;
- `after`;
- optional `diff`;
- `resource`.

`before`, `after`, and `diff` are comparable safe shapes. Sensitive-looking
fields are omitted from normal update comparisons and redacted from returned API
resources.

## OpenAPI Validation

OpenAPI documents are validation input, not code generation. When a module
receives an `openapi_contract`, the shared resource layer checks that required
endpoints and methods exist, payload fields are declared, read-only fields are
not sent, required fields are present, and enum values are valid.

Tests use saved fixtures under `tests/fixtures/`. Unit tests do not fetch live
AzuraCast OpenAPI documents.

## Current Modules

- `storage_location` manages one admin storage location matched by `type`.
- `station` manages one admin station matched by `short_name`; station-scoped
  child arrays are excluded from station payloads.
- `station_mount` manages one station mount matched by `name` under a resolved
  station ID.
- `station_playlist` manages one station playlist matched by `name` under a
  resolved station ID.
- `station_remote` manages one station remote matched by `display_name` under a
  resolved station ID.
- `station_webhook` manages one station webhook matched by `name` under a
  resolved station ID.

Station-scoped resources use explicit public modules because each resource
family has a distinct user-facing concept and stable key.

The current managed inventory scope is complete at the resource-module layer:
storage locations, stations, station mounts, station playlists, station
remotes, and station webhooks all have direct modules. Additional AzuraCast API
surfaces are not a module backlog by default; new modules should be added only
when a managed inventory need meets the criteria in `docs/module-feasibility.md`.

## URI-Retained Surfaces

Some role paths intentionally remain `ansible.builtin.uri` orchestration rather
than resource modules:

- `roles/settings` manages a singleton partial-update surface. It fetches live
  settings, resolves declared storage references, compares only declared
  fields, and PUTs only when those fields differ. There is no stable resource
  identity or delete lifecycle for a module to own.
- `roles/api` performs authentication preflight, live OpenAPI validation, and
  sanitized discovery exports. Those are checks and exports, not resource
  reconciliation.
- Storage credential rotation remains the explicit
  `storage_rotate_credentials` tagged path. Sensitive write-only fields are
  excluded from normal module drift, so credential pushes stay opt-in and
  auditable.

## Collection-Local Verification

Run unit tests from the collection checkout:

```bash
python -m pytest -q
```

Render module docs from an installed or collection-layout checkout:

```bash
ansible-doc fculpo.azuracast_api.storage_location
ansible-doc fculpo.azuracast_api.station
ansible-doc fculpo.azuracast_api.station_mount
ansible-doc fculpo.azuracast_api.station_playlist
ansible-doc fculpo.azuracast_api.station_remote
ansible-doc fculpo.azuracast_api.station_webhook
```

Build and sanity-check from a collection layout:

```bash
ansible-galaxy collection build . --output-path dist --force
ansible-test sanity --python 3.13
```

Example playbooks in `examples/` are intended to syntax-check against a
temporary collection install. Consumer-repo integration is a final smoke test,
not a routine development dependency, and no verification step requires
`git push`.
