# API Authority Design

This collection treats each AzuraCast installation's own OpenAPI document as the contract.

For your deployment, use the API documentation and OpenAPI document exposed by
your own AzuraCast instance:

- API docs: `https://radio.example.com/docs/api/`
- OpenAPI YAML: `https://radio.example.com/api/openapi.yml`

## Credential Rotation

Normal convergence ignores sensitive fields when detecting drift because the
AzuraCast API does not reliably round-trip write-only credentials. To push
storage credentials intentionally, use the targeted rotation tag:

```bash
export AZURACAST_API_KEY=your-api-key
ansible-playbook -i inventory.yml playbook.yml --tags storage_rotate_credentials --check --diff
ansible-playbook -i inventory.yml playbook.yml --tags storage_rotate_credentials
```

This tag runs API preflight, fetches live storage locations, reports the storage
locations that will receive the desired credential payload, and then updates
only those locations on a non-check run.

## Destructive Authority Rollout

Destructive sync uses two gates:

- `azuracast_destructive_sync`: global delete authority switch.
- `azuracast_destructive_allow`: explicit family allow-list.

Enable delete authority one family at a time. Start with families whose check
output shows `unmanaged: []`, then run a full `--check --diff` before any real
converge.

Recommended order:

1. `remotes`
2. `webhooks`
3. `mounts`
4. `playlists`
5. `stations`
6. `storage_locations`

Keep `stations` and `storage_locations` as the last families in the allow-list.
Before any real run after adding them, verify that both plans still show
`unmanaged: []`; otherwise, stop and adopt or intentionally remove the unmanaged
resource before converging.
