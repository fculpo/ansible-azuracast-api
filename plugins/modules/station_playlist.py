#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, fculpo
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r'''
---
module: station_playlist
short_description: Manage one AzuraCast station playlist
version_added: "0.2.0"
description:
  - Manages a single playlist for one AzuraCast station.
options:
  base_url:
    description:
      - Base URL for the AzuraCast instance.
    required: true
    type: str
  api_key:
    description:
      - AzuraCast API key with permission to manage station playlists.
    required: true
    type: str
  station_short_name:
    description:
      - Station short name used to resolve the station ID.
    type: str
  station_id:
    description:
      - Explicit station ID. When set, no station short-name lookup is needed.
    type: int
  name:
    description:
      - Stable playlist name to manage.
    required: true
    type: str
  resource:
    description:
      - Desired playlist payload.
    type: dict
    default: {}
  sensitive_resource:
    description:
      - Sensitive desired payload fields. These values are excluded from normal drift comparison and diff output.
    type: dict
    default: {}
  openapi_contract:
    description:
      - Optional AzuraCast OpenAPI document used to validate playlist endpoint capabilities.
    type: raw
  state:
    description:
      - Whether the playlist should exist.
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
- name: Ensure default playlist exists
  fculpo.azuracast_api.station_playlist:
    base_url: https://radio.example.com
    api_key: "{{ lookup('ansible.builtin.env', 'AZURACAST_API_KEY') }}"
    station_short_name: main
    name: Default
    resource:
      type: default
      source: songs
      order: shuffle
      is_enabled: true
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
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils.azuracast_station_resources import (
        apply_station_resource,
        build_desired_station_resource,
        station_resource_spec,
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
    azuracast_station_resources = _load_module_util("azuracast_station_resources")
    AzuraCastApiError = azuracast_client.AzuraCastApiError
    AzuraCastClient = azuracast_client.AzuraCastClient
    apply_station_resource = azuracast_station_resources.apply_station_resource
    build_desired_station_resource = azuracast_station_resources.build_desired_station_resource
    station_resource_spec = azuracast_station_resources.station_resource_spec


def station_playlist_spec():
    return station_resource_spec(
        "station playlist",
        "/api/station/{station_id}/playlists",
        "/api/station/{station_id}/playlist/{id}",
        "name",
    )


def build_desired_station_playlist(name, resource, sensitive_resource=None):
    return build_desired_station_resource(
        "name",
        name,
        resource,
        sensitive_resource,
        "Station playlist",
    )


def apply_station_playlist(
    client,
    desired,
    station_short_name=None,
    station_id=None,
    state="present",
    check_mode=False,
    openapi_contract=None,
):
    return apply_station_resource(
        client,
        station_playlist_spec(),
        desired,
        station_short_name=station_short_name,
        station_id=station_id,
        state=state,
        check_mode=check_mode,
        openapi_contract=openapi_contract,
    )


def main():
    module = AnsibleModule(
        argument_spec={
            "base_url": {"type": "str", "required": True},
            "api_key": {"type": "str", "required": True, "no_log": True},
            "station_short_name": {"type": "str"},
            "station_id": {"type": "int"},
            "name": {"type": "str", "required": True},
            "resource": {"type": "dict", "default": {}},
            "sensitive_resource": {"type": "dict", "default": {}, "no_log": True},
            "state": {"type": "str", "default": "present", "choices": ["present", "absent"]},
            "validate_certs": {"type": "bool", "default": True},
            "timeout": {"type": "int", "default": 30},
            "openapi_contract": {"type": "raw", "default": None},
        },
        required_one_of=[("station_short_name", "station_id")],
        supports_check_mode=True,
    )

    try:
        desired = build_desired_station_playlist(
            module.params["name"],
            module.params["resource"],
            module.params["sensitive_resource"],
        )
        client = AzuraCastClient(
            module.params["base_url"],
            module.params["api_key"],
            validate_certs=module.params["validate_certs"],
            timeout=module.params["timeout"],
        )
        result = apply_station_playlist(
            client,
            desired,
            station_short_name=module.params["station_short_name"],
            station_id=module.params["station_id"],
            state=module.params["state"],
            check_mode=module.check_mode,
            openapi_contract=module.params["openapi_contract"],
        )
    except (AzuraCastApiError, planning.AzuraCastPlanningError, KeyError) as exc:
        module.fail_json(msg=str(exc))

    module.exit_json(**result)


if __name__ == "__main__":
    main()
