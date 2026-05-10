#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, fculpo
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r'''
---
module: station
short_description: Manage one AzuraCast station
version_added: "0.2.0"
description:
  - Manages a single AzuraCast station through the supported REST API.
options:
  base_url:
    description:
      - Base URL for the AzuraCast instance.
    required: true
    type: str
  api_key:
    description:
      - AzuraCast API key with permission to manage stations.
    required: true
    type: str
  short_name:
    description:
      - Stable station short name to manage.
    required: true
    type: str
  resource:
    description:
      - Desired AzuraCast station payload.
      - Station-scoped child resources are ignored by this module.
    type: dict
    default: {}
  sensitive_resource:
    description:
      - Sensitive desired payload fields. These values are excluded from normal drift comparison and diff output.
    type: dict
    default: {}
  openapi_contract:
    description:
      - Optional AzuraCast OpenAPI document used to validate station endpoint capabilities.
    type: raw
  state:
    description:
      - Whether the station should exist.
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
- name: Ensure station exists
  fculpo.azuracast_api.station:
    base_url: https://radio.example.com
    api_key: "{{ lookup('ansible.builtin.env', 'AZURACAST_API_KEY') }}"
    short_name: main
    resource:
      name: Main Radio
      media_storage_location:
        type: station_media
'''

RETURN = r'''
action:
  description: Planned or applied action.
  returned: always
  type: str
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


def station_spec():
    return ResourceSpec(
        family="station",
        collection_path="/api/admin/stations",
        item_path="/api/admin/station/{id}",
        key="short_name",
    )


def build_desired_station(resource, sensitive_resource=None, short_name=None):
    desired = dict(resource or {})
    desired.update(sensitive_resource or {})
    if short_name is not None:
        if "short_name" in desired and desired["short_name"] != short_name:
            raise planning.AzuraCastPlanningError(
                "Station resource short_name must match the module short_name option"
            )
        desired["short_name"] = short_name
    return planning.azuracast_station_api_payloads([desired])[0]


def _has_storage_reference(value, parent_key=None):
    if isinstance(value, list):
        return any(_has_storage_reference(item, parent_key) for item in value)
    if isinstance(value, dict):
        if str(parent_key).endswith("_storage_location") and "type" in value:
            return True
        return any(_has_storage_reference(item, key) for key, item in value.items())
    return False


def apply_station(
    client,
    desired,
    state="present",
    check_mode=False,
    openapi_contract=None,
):
    desired = build_desired_station(desired)
    if state == "present" and _has_storage_reference(desired):
        desired = planning.azuracast_resolve_storage_references(
            desired,
            client.list_storage_locations(),
        )

    return reconcile_resource(
        client,
        station_spec(),
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
            "short_name": {"type": "str", "required": True},
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
        desired = build_desired_station(
            module.params["resource"],
            module.params["sensitive_resource"],
            module.params["short_name"],
        )
        client = AzuraCastClient(
            module.params["base_url"],
            module.params["api_key"],
            validate_certs=module.params["validate_certs"],
            timeout=module.params["timeout"],
        )
        result = apply_station(
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
