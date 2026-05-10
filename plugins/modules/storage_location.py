#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, fculpo
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r'''
---
module: storage_location
short_description: Manage one AzuraCast storage location
version_added: "0.2.0"
description:
  - Manages a single AzuraCast storage location through the supported REST API.
  - This is a proof-of-concept resource module for the collection's module direction.
options:
  base_url:
    description:
      - Base URL for the AzuraCast instance.
      - Trailing slashes are ignored.
    required: true
    type: str
  api_key:
    description:
      - AzuraCast API key with permission to manage storage locations.
    required: true
    type: str
  type:
    description:
      - Stable AzuraCast storage location type to manage.
    required: true
    type: str
  resource:
    description:
      - Desired AzuraCast storage location payload.
      - The C(type) option is added to this payload automatically.
    type: dict
    default: {}
  sensitive_resource:
    description:
      - Sensitive desired payload fields, such as write-only credentials.
      - These values are sent when needed but are excluded from normal drift comparison and diff output.
    type: dict
    default: {}
  openapi_contract:
    description:
      - Optional AzuraCast OpenAPI document used to validate storage endpoint capabilities.
      - When provided, the module checks endpoint methods, declared request fields, read-only fields, and enum values before mutating.
      - The contract is used for capability discovery only; module behavior is not generated from it.
    type: raw
  state:
    description:
      - Whether the storage location should exist.
    type: str
    choices:
      - present
      - absent
    default: present
  validate_certs:
    description:
      - Whether to validate TLS certificates for HTTPS requests.
    type: bool
    default: true
  timeout:
    description:
      - HTTP request timeout in seconds.
    type: int
    default: 30
author:
  - fculpo (@fculpo)
'''

EXAMPLES = r'''
- name: Ensure backup storage exists
  fculpo.azuracast_api.storage_location:
    base_url: https://radio.example.com
    api_key: "{{ lookup('ansible.builtin.env', 'AZURACAST_API_KEY') }}"
    type: backup
    resource:
      adapter: local
      path: /var/azuracast/backups

- name: Remove backup storage
  fculpo.azuracast_api.storage_location:
    base_url: https://radio.example.com
    api_key: "{{ lookup('ansible.builtin.env', 'AZURACAST_API_KEY') }}"
    type: backup
    state: absent
'''

RETURN = r'''
action:
  description: Planned or applied action.
  returned: always
  type: str
  sample: update
before:
  description: Comparable live state before the change.
  returned: always
  type: dict
after:
  description: Comparable desired state after the change.
  returned: always
  type: dict
resource:
  description: API resource returned by the applied change, or the live resource for no-op present state.
  returned: always
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils.azuracast_client import (
        AzuraCastApiError,
        AzuraCastClient,
    )
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils import (
        azuracast_planning as planning,
    )
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils.azuracast_resources import (
        ResourceSpec,
        reconcile_resource,
        validate_resource_openapi,
    )
except ImportError:
    import importlib.util
    import sys
    from pathlib import Path

    def _load_module_util(name):
        if name in sys.modules:
            return sys.modules[name]
        module_path = Path(__file__).resolve().parents[1] / "module_utils" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    azuracast_client = _load_module_util("azuracast_client")
    planning = _load_module_util("azuracast_planning")
    azuracast_resources = _load_module_util("azuracast_resources")
    AzuraCastApiError = azuracast_client.AzuraCastApiError
    AzuraCastClient = azuracast_client.AzuraCastClient
    ResourceSpec = azuracast_resources.ResourceSpec
    reconcile_resource = azuracast_resources.reconcile_resource
    validate_resource_openapi = azuracast_resources.validate_resource_openapi


def storage_location_spec():
    return ResourceSpec(
        family="storage location",
        collection_path="/api/admin/storage_locations",
        item_path="/api/admin/storage_location/{id}",
        key="type",
    )


def build_desired_storage_location(storage_type, resource, sensitive_resource=None):
    desired = dict(resource or {})
    desired.update(sensitive_resource or {})
    if "type" in desired and desired["type"] != storage_type:
        raise planning.AzuraCastPlanningError(
            "Storage location resource type must match the module type option"
        )
    desired["type"] = storage_type
    return desired


def changed_result(action, before, after, resource):
    return {
        "changed": True,
        "action": action,
        "before": before,
        "after": after,
        "diff": {"before": before, "after": after},
        "resource": planning.azuracast_redact(resource),
    }


def validate_storage_location_openapi(openapi_contract, desired, state):
    validate_resource_openapi(storage_location_spec(), openapi_contract, desired, state)


class StorageLocationResourceClient:
    def __init__(self, client):
        self.client = client

    def list_resources(self, path, scope=None):
        if hasattr(self.client, "list_resources"):
            return self.client.list_resources(path, scope)
        return self.client.list_storage_locations()

    def create_resource(self, path, payload, scope=None):
        if hasattr(self.client, "create_resource"):
            return self.client.create_resource(path, payload, scope)
        return self.client.create_storage_location(payload)

    def update_resource(self, path, resource_id, payload, scope=None):
        if hasattr(self.client, "update_resource"):
            return self.client.update_resource(path, resource_id, payload, scope)
        return self.client.update_storage_location(resource_id, payload)

    def delete_resource(self, path, resource_id, scope=None):
        if hasattr(self.client, "delete_resource"):
            return self.client.delete_resource(path, resource_id, scope)
        return self.client.delete_storage_location(resource_id)


def apply_storage_location(
    client,
    desired,
    state="present",
    check_mode=False,
    openapi_contract=None,
):
    return reconcile_resource(
        StorageLocationResourceClient(client),
        storage_location_spec(),
        desired,
        state=state,
        check_mode=check_mode,
        openapi_contract=openapi_contract,
    )


def main():
    module = AnsibleModule(
        argument_spec={
            "base_url": {"type": "str", "required": True},
            "api_key": {"type": "str", "required": True, "no_log": True},
            "type": {"type": "str", "required": True},
            "resource": {"type": "dict", "default": {}},
            "sensitive_resource": {"type": "dict", "default": {}, "no_log": True},
            "state": {
                "type": "str",
                "default": "present",
                "choices": ["present", "absent"],
            },
            "validate_certs": {"type": "bool", "default": True},
            "timeout": {"type": "int", "default": 30},
            "openapi_contract": {"type": "raw", "default": None},
        },
        supports_check_mode=True,
    )

    try:
        desired = build_desired_storage_location(
            module.params["type"],
            module.params["resource"],
            module.params["sensitive_resource"],
        )
        client = AzuraCastClient(
            module.params["base_url"],
            module.params["api_key"],
            validate_certs=module.params["validate_certs"],
            timeout=module.params["timeout"],
        )
        result = apply_storage_location(
            client,
            desired,
            state=module.params["state"],
            check_mode=module.check_mode,
            openapi_contract=module.params["openapi_contract"],
        )
    except (AzuraCastApiError, planning.AzuraCastPlanningError, KeyError) as exc:
        module.fail_json(msg=str(exc))

    module.exit_json(**result)


if __name__ == "__main__":
    main()
