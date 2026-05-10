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

Future station-scoped modules should stay explicit public modules unless the
implemented family proves that a generic public resource module would be
clearer for users.

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
