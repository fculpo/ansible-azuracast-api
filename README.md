# AzuraCast API Authority

An Ansible collection for managing AzuraCast application configuration through
the supported AzuraCast REST API.

This collection is intended for operators who want AzuraCast settings, storage
locations, stations, mounts, playlists, remotes, and webhooks to be described in
Ansible variables and reconciled against a live AzuraCast instance.

## What This Collection Manages

The collection provides these roles:

- `fculpo.azuracast_api.api`: shared API preflight, authentication checks,
  OpenAPI endpoint validation, and read-only discovery.
- `fculpo.azuracast_api.settings`: instance-wide AzuraCast settings.
- `fculpo.azuracast_api.storage`: AzuraCast storage locations.
- `fculpo.azuracast_api.stations`: stations.
- `fculpo.azuracast_api.station_resources`: station-scoped mounts, playlists,
  remotes, and webhooks.

It also provides resource-level modules for direct tasks:

- `fculpo.azuracast_api.storage_location`: one storage location matched by
  `type`.
- `fculpo.azuracast_api.station`: one station matched by `short_name`.
- `fculpo.azuracast_api.station_mount`: one station mount matched by `name`
  under a resolved station.
- `fculpo.azuracast_api.station_playlist`: one station playlist matched by
  `name` under a resolved station.
- `fculpo.azuracast_api.station_remote`: one station remote matched by
  `display_name` under a resolved station.
- `fculpo.azuracast_api.station_webhook`: one station webhook matched by `name`
  under a resolved station.

It does not install AzuraCast, manage Docker, manage the host operating system,
upload media, create users, create API keys, or edit the AzuraCast database
directly.

## Requirements

- Ansible Core 2.16 or newer.
- An AzuraCast instance with `/api/openapi.yml` enabled.
- An AzuraCast API key with permission to manage the resources you declare.

## Installation

From Galaxy:

```yaml
---
collections:
  - name: fculpo.azuracast_api
    version: "0.1.0"
```

From GitHub:

```yaml
---
collections:
  - name: https://github.com/fculpo/ansible-azuracast-api.git
    type: git
    version: main
```

Install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Basic Playbook

Run the API foundation role first. The resource roles depend on the shared
defaults and preflight facts it establishes.

```yaml
---
- name: Converge AzuraCast API-managed configuration
  hosts: azuracast
  gather_facts: false

  roles:
    - role: fculpo.azuracast_api.api
      tags: [api, preflight]
    - role: fculpo.azuracast_api.settings
      tags: [api, settings]
    - role: fculpo.azuracast_api.storage
      tags: [api, storage]
    - role: fculpo.azuracast_api.stations
      tags: [api, stations]
    - role: fculpo.azuracast_api.station_resources
      tags: [api, station_resources]
```

Provide the API key through the `AZURACAST_API_KEY` environment variable, or
override `azuracast_api_key` from your own secret management workflow.

```bash
export AZURACAST_API_KEY=your-api-key
ansible-playbook -i inventory.yml playbook.yml --check --diff
```

## Core Variables

```yaml
azuracast_api:
  base_url: "https://radio.example.com"
  timeout: 30
  validate_certs: true
  openapi_path: /api/openapi.yml
  required_endpoints:
    - /admin/settings
    - /admin/storage_locations
    - /admin/station/{id}
    - /admin/stations
    - /station/{station_id}/mounts
    - /station/{station_id}/playlists
    - /station/{station_id}/remotes
    - /station/{station_id}/webhooks

azuracast_api_key: "{{ lookup('ansible.builtin.env', 'AZURACAST_API_KEY') }}"
azuracast_api_hide_sensitive_logs: true
```

`azuracast_api.base_url` is required. Trailing slashes are removed internally.

`azuracast_api.required_endpoints` is optional, but recommended. The API role
fetches the live OpenAPI document from your AzuraCast instance and asserts that
the endpoints this collection needs exist on the version you are actually
running.

## Desired State Shape

The collection intentionally uses AzuraCast API field names for desired state.
That makes it easy to compare Ansible variables with the live OpenAPI contract
and avoids inventing a second schema.

### Settings

```yaml
azuracast_settings:
  base_url: "https://radio.example.com"
  instance_name: Example Radio
  always_use_ssl: true
  backup_enabled: true
  backup_storage_location:
    type: backup
```

Only fields you declare are managed. Live settings outside your desired shape
are ignored by the settings role.

### Storage Locations

```yaml
azuracast_storage_locations:
  - type: backup
    adapter: s3
    path: ""
    s3Bucket: example-azcast-backups
    s3CredentialKey: "{{ lookup('ansible.builtin.env', 'S3_ACCESS_KEY') }}"
    s3CredentialSecret: "{{ lookup('ansible.builtin.env', 'S3_SECRET_KEY') }}"
    s3Endpoint: "https://s3.example.com"
    s3Region: auto
    s3UsePathStyle: false
    s3Version: latest
    stations: []
```

Storage locations are matched by `type`.

### Stations And Station Resources

```yaml
azuracast_stations:
  - name: Main Station
    short_name: main
    timezone: UTC
    is_enabled: true
    frontend_type: icecast
    backend_type: liquidsoap
    media_storage_location:
      type: station_media
    recordings_storage_location:
      type: station_recordings
    podcasts_storage_location:
      type: station_podcasts
    mounts:
      - name: /radio.mp3
        display_name: MP3
        autodj_format: mp3
        autodj_bitrate: 128
        enable_autodj: true
        is_default: true
    playlists:
      - name: Default
        type: default
        source: songs
        order: shuffle
        is_enabled: true
    remotes: []
    webhooks: []
```

Stations are matched by `short_name`.

Station resources are matched by:

- mounts: `name`
- playlists: `name`
- remotes: `display_name`
- webhooks: `name`

Storage references can be written as `{type: ...}` objects. The collection
fetches live storage locations and replaces those references with the API IDs
AzuraCast expects before sending create or update payloads.

## How Reconciliation Works

Each resource role follows the same pattern:

1. Fetch the live AzuraCast API resource with `ansible.builtin.uri`.
2. Normalize desired and live data.
3. Strip read-only API metadata such as IDs, links, timestamps, listener counts,
   art URLs, and other operational fields.
4. Ignore sensitive write-only fields during normal drift detection.
5. Build a plan with four buckets:
   - `create`: desired resources missing from AzuraCast.
   - `update`: desired resources that differ from live API state.
   - `noop`: desired resources already matching live API state.
   - `unmanaged`: live resources absent from desired state.
6. Print the plan with sensitive values redacted.
7. Apply creates, updates, and allowed deletes only when not running in check
   mode.

The normal `--check --diff` workflow is therefore a read-only planning run. It
uses API `GET` requests and local data transformations, then skips mutation
tasks because `ansible_check_mode` is true.

## Safety Model

### Check Mode First

Use check mode before every real convergence:

```bash
ansible-playbook -i inventory.yml playbook.yml --check --diff
```

A clean plan has empty `create`, `update`, and `unmanaged` lists for the
families you expect to be fully managed.

### Guarded Deletes

Deletes require two gates:

```yaml
azuracast_destructive_sync: false
azuracast_destructive_allow: []
```

Set `azuracast_destructive_sync: true` only after reviewing check-mode output.
Then add families to `azuracast_destructive_allow` deliberately:

```yaml
azuracast_destructive_sync: true
azuracast_destructive_allow:
  - mounts
  - playlists
```

Supported delete families are:

- `storage_locations`
- `stations`
- `mounts`
- `playlists`
- `remotes`
- `webhooks`

Start with station-scoped resources and leave `stations` and
`storage_locations` for last. Deleting those can have wider impact.

### Sensitive Fields

AzuraCast does not reliably round-trip write-only credentials such as S3
secrets. Normal drift detection ignores fields whose names look sensitive, such
as keys containing `authorization`, `api_key`, `token`, `secret`, `password`, or
`credential`.

To intentionally push storage credentials, run the storage credential rotation
tag:

```bash
ansible-playbook -i inventory.yml playbook.yml --tags storage_rotate_credentials --check --diff
ansible-playbook -i inventory.yml playbook.yml --tags storage_rotate_credentials
```

The first command reports which existing storage locations would receive the
credential payload. The second command performs the update.

## The Filter Plugin

`plugins/filter/azuracast_api.py` contains pure Python data transformations used
by the roles. It does not call the network and it does not mutate AzuraCast by
itself.

The filters exist because the hard part of API-based desired state is not the
HTTP request. The hard part is converting noisy live API responses and partial
desired variables into deterministic plans that are safe to review.

Key filters:

- `azuracast_plan_actions`: compares desired and live resource lists and returns
  `create`, `update`, `noop`, and `unmanaged` buckets.
- `azuracast_compare_shape`: removes read-only and sensitive fields before drift
  comparison.
- `azuracast_desired_shape`: narrows live data to the fields declared in desired
  state, so undeclared settings are not managed accidentally.
- `azuracast_sensitive_update_plan`: builds explicit credential rotation plans
  for existing resources.
- `azuracast_destructive_deletes`: applies the delete safety gates.
- `azuracast_redact`: redacts sensitive values before debug output.
- `azuracast_resolve_storage_references`: turns storage references such as
  `{type: backup}` into the live numeric ID required by the API.
- `azuracast_station_api_payloads`: removes station-scoped resource lists from
  station create/update payloads.
- `azuracast_station_resource_plans`: creates per-station plans for mounts,
  playlists, remotes, and webhooks.

Using a filter plugin for this is idiomatic Ansible: filters are meant for data
manipulation in templates, variables, and playbooks. Keeping this logic in
Python also makes it unit-testable without contacting AzuraCast.

The roles still use these filters for whole-instance planning. Stable
resource-level modules reuse the same planning helpers so direct module tasks
and role convergence do not drift apart.

## Resource Modules

Use roles when you want whole-instance convergence from collection variables.
Use modules when a playbook needs to manage one resource directly and receive
native module results.

```yaml
- name: Ensure backup storage exists
  fculpo.azuracast_api.storage_location:
    base_url: "https://radio.example.com"
    api_key: "{{ azuracast_api_key }}"
    type: backup
    resource:
      adapter: local
      path: /var/azuracast/backups

- name: Ensure station exists
  fculpo.azuracast_api.station:
    base_url: "https://radio.example.com"
    api_key: "{{ azuracast_api_key }}"
    short_name: main
    resource:
      name: Main Radio
      media_storage_location:
        type: station_media

- name: Ensure station mount exists
  fculpo.azuracast_api.station_mount:
    base_url: "https://radio.example.com"
    api_key: "{{ azuracast_api_key }}"
    station_short_name: main
    name: /radio.mp3
    resource:
      display_name: MP3
      autodj_format: mp3
      autodj_bitrate: 128

- name: Ensure station playlist exists
  fculpo.azuracast_api.station_playlist:
    base_url: "https://radio.example.com"
    api_key: "{{ azuracast_api_key }}"
    station_short_name: main
    name: Default
    resource:
      type: default
      source: songs
      order: shuffle
      is_enabled: true

- name: Ensure station remote exists
  fculpo.azuracast_api.station_remote:
    base_url: "https://radio.example.com"
    api_key: "{{ azuracast_api_key }}"
    station_short_name: main
    display_name: Relay
    resource:
      url: https://relay.example.com/live
      is_visible_on_public_pages: true

- name: Ensure station webhook exists
  fculpo.azuracast_api.station_webhook:
    base_url: "https://radio.example.com"
    api_key: "{{ azuracast_api_key }}"
    station_short_name: main
    name: Notify
    resource:
      type: generic
      url: https://hooks.example.com/azuracast
      is_enabled: true
```

Normal updates compare only safe fields. Sensitive write-only fields can be
provided through `sensitive_resource`; they are used for create payloads but are
excluded from normal drift comparison and diff output. OpenAPI documents can be
passed through `openapi_contract` to validate endpoint methods and payload
fields before mutation.

## Discovery

You can export sanitized live API state for adoption review by including the
`discover` task file from the API role:

```yaml
---
- name: Discover AzuraCast API-managed state
  hosts: azuracast
  gather_facts: false

  roles:
    - role: fculpo.azuracast_api.api
      tags: [api, preflight]

  tasks:
    - name: Export live API state for adoption review
      ansible.builtin.include_role:
        name: fculpo.azuracast_api.api
        tasks_from: discover
      tags: [api, discover]
```

The discovery task writes `generated/api-discovery.json` next to the playbook
directory. Sensitive-looking fields are redacted.

## Recommended Adoption Flow

1. Install the collection.
2. Create an API key in AzuraCast and expose it to Ansible as
   `AZURACAST_API_KEY`.
3. Configure `azuracast_api.base_url` and `azuracast_api.required_endpoints`.
4. Run the preflight tag:

   ```bash
   ansible-playbook -i inventory.yml playbook.yml --check --diff --tags preflight
   ```

5. Run discovery and review the sanitized live state.
6. Declare settings, storage locations, stations, and station resources in
   variables.
7. Run one check-mode slice at a time:

   ```bash
   ansible-playbook -i inventory.yml playbook.yml --check --diff --tags settings
   ansible-playbook -i inventory.yml playbook.yml --check --diff --tags storage
   ansible-playbook -i inventory.yml playbook.yml --check --diff --tags stations
   ansible-playbook -i inventory.yml playbook.yml --check --diff --tags station_resources
   ```

8. Apply non-destructive changes first.
9. Enable destructive sync only after every unmanaged resource is either adopted
   into desired state or intentionally removed.

## Development

Run the unit tests:

```bash
mise install
uv sync --group dev
uv run pytest -q
```

Build the collection:

```bash
source .venv/bin/activate
ansible-galaxy collection build . --output-path dist --force
```

Run Ansible sanity tests from a collection layout:

```bash
mkdir -p /tmp/ansible-test-layout/ansible_collections/fculpo
rsync -a --exclude .git --exclude .serena --exclude .venv --exclude .pytest_cache --exclude dist \
  ./ /tmp/ansible-test-layout/ansible_collections/fculpo/azuracast_api/
cd /tmp/ansible-test-layout/ansible_collections/fculpo/azuracast_api
source "$OLDPWD/.venv/bin/activate"
ansible-test sanity --python 3.12
```

Install the local artifact for consumer testing:

```bash
ansible-galaxy collection install dist/fculpo-azuracast_api-0.1.0.tar.gz \
  -p /tmp/azuracast-api-collections --force
```

Then run a consuming playbook with:

```bash
ANSIBLE_COLLECTIONS_PATH=/tmp/azuracast-api-collections \
  ansible-playbook -i inventory.yml playbook.yml --check --diff
```

## Current Limitations

- Dedicated resource modules exist for storage locations, stations, and
  station-scoped mounts, playlists, remotes, and webhooks; roles remain the
  primary whole-instance convergence interface.
- Desired state uses AzuraCast API field names directly.
- API coverage is focused on settings, storage locations, stations, mounts,
  playlists, remotes, and webhooks.
- User, role, API key, media, and operational broadcast actions are outside the
  current scope.
