# AzuraCast API Authority

An Ansible collection for managing AzuraCast application configuration through the supported REST API.

The collection is built around a shared API foundation role and focused resource-family roles:

- `fculpo.azuracast_api.api`
- `fculpo.azuracast_api.settings`
- `fculpo.azuracast_api.storage`
- `fculpo.azuracast_api.stations`
- `fculpo.azuracast_api.station_resources`

## Requirements

- Ansible Core 2.16 or newer.
- An AzuraCast API key with permission to manage application settings and stations.

## Basic Usage

Set the AzuraCast base URL in inventory or play variables:

```yaml
azuracast_api:
  base_url: "https://radio.example.com"
  openapi_path: /api/openapi.yml
```

Provide the API key through the `AZURACAST_API_KEY` environment variable, or
override `azuracast_api_key` from your own secret management workflow.

```bash
export AZURACAST_API_KEY=your-api-key
ansible-playbook -i inventory.yml playbook.yml --check --diff
```

The collection redacts sensitive values in its own plan output and requires an
explicit allow-list before deleting unmanaged resources.
