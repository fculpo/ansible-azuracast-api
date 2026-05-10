from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_tasks(path):
    return yaml.safe_load((ROOT / path).read_text())


def task_by_name(path, name):
    for task in load_tasks(path):
        if task.get("name") == name:
            return task
    raise AssertionError(f"missing task in {path}: {name}")


def test_settings_role_keeps_uri_fetch_drift_and_update_path():
    fetch = task_by_name("roles/settings/tasks/main.yml", "Fetch current AzuraCast settings")
    drift = task_by_name("roles/settings/tasks/main.yml", "Build settings drift")
    before = task_by_name(
        "roles/settings/tasks/main.yml",
        "Select desired AzuraCast settings fields from live state",
    )
    update = task_by_name("roles/settings/tasks/main.yml", "Update AzuraCast settings")
    expected_before = (
        "{{ azuracast_settings_live_response.json | "
        "fculpo.azuracast_api.azuracast_compare_shape | "
        "fculpo.azuracast_api.azuracast_desired_shape("
        "azuracast_settings_after) }}"
    )

    assert fetch["ansible.builtin.uri"]["method"] == "GET"
    assert fetch["ansible.builtin.uri"]["url"] == (
        "{{ azuracast_api_base_url }}/api/admin/settings"
    )
    assert fetch["check_mode"] is False

    assert (
        drift["ansible.builtin.set_fact"]["azuracast_settings_after"]
        == "{{ azuracast_settings_resolved | fculpo.azuracast_api.azuracast_compare_shape }}"
    )
    assert (
        before["ansible.builtin.set_fact"]["azuracast_settings_before"]
        == expected_before
    )

    assert "ansible.builtin.uri" in update
    assert update["ansible.builtin.uri"]["method"] == "PUT"
    assert update["ansible.builtin.uri"]["body"] == "{{ azuracast_settings_resolved }}"
    assert update["when"] == [
        "not ansible_check_mode",
        "azuracast_settings_after | length > 0",
        "azuracast_settings_before != azuracast_settings_after",
    ]


def test_settings_role_resolves_storage_references_before_put_body():
    storage_fetch = task_by_name(
        "roles/settings/tasks/main.yml",
        "Fetch current AzuraCast storage locations for settings references",
    )
    resolve = task_by_name(
        "roles/settings/tasks/main.yml",
        "Resolve settings storage references",
    )
    update = task_by_name("roles/settings/tasks/main.yml", "Update AzuraCast settings")

    assert storage_fetch["ansible.builtin.uri"]["url"] == (
        "{{ azuracast_api_base_url }}/api/admin/storage_locations"
    )
    assert storage_fetch["check_mode"] is False
    assert (
        resolve["ansible.builtin.set_fact"]["azuracast_settings_resolved"]
        == "{{ azuracast_settings | fculpo.azuracast_api.azuracast_resolve_storage_references(azuracast_settings_storage_live_response.json) }}"
    )
    assert update["ansible.builtin.uri"]["body"] == "{{ azuracast_settings_resolved }}"


def test_api_preflight_keeps_uri_authentication_and_assertion_failure_path():
    auth = task_by_name("roles/api/tasks/main.yml", "Check AzuraCast API authentication")
    fail = task_by_name(
        "roles/api/tasks/main.yml",
        "Fail when API authentication is not successful",
    )

    assert "ansible.builtin.uri" in auth
    assert auth["ansible.builtin.uri"]["method"] == "GET"
    assert auth["ansible.builtin.uri"]["url"] == (
        "{{ azuracast_api_base_url }}/api/admin/settings"
    )
    assert auth["check_mode"] is False
    assert auth["failed_when"] is False

    assert "ansible.builtin.assert" in fail
    assert fail["ansible.builtin.assert"]["that"] == [
        "azuracast_api_auth_response.status == 200"
    ]


def test_openapi_validation_keeps_live_uri_fetch_and_assertions():
    fetch = task_by_name(
        "roles/api/tasks/openapi.yml",
        "Fetch live AzuraCast OpenAPI document",
    )
    unavailable = task_by_name(
        "roles/api/tasks/openapi.yml",
        "Fail when live OpenAPI document is unavailable",
    )
    verify = task_by_name(
        "roles/api/tasks/openapi.yml",
        "Verify required AzuraCast API endpoints exist",
    )

    assert "ansible.builtin.uri" in fetch
    assert fetch["ansible.builtin.uri"]["url"] == "{{ azuracast_api_openapi_url }}"
    assert fetch["check_mode"] is False
    assert fetch["failed_when"] is False

    assert unavailable["ansible.builtin.assert"]["that"] == [
        "azuracast_openapi_response.status == 200"
    ]
    assert verify["ansible.builtin.assert"]["that"] == [
        "azuracast_openapi_response.content is search(item)"
    ]


def test_api_discovery_keeps_uri_fetch_and_sanitized_export():
    fetch = task_by_name("roles/api/tasks/discover.yml", "Fetch API discovery resources")
    export = task_by_name("roles/api/tasks/discover.yml", "Write sanitized discovery export")

    assert "ansible.builtin.uri" in fetch
    assert fetch["ansible.builtin.uri"]["method"] == "GET"
    assert fetch["check_mode"] is False
    assert fetch["register"] == "azuracast_discovery_responses"
    assert fetch["loop"] == [
        {"name": "settings", "path": "/api/admin/settings"},
        {"name": "storage_locations", "path": "/api/admin/storage_locations"},
        {"name": "stations", "path": "/api/admin/stations"},
    ]

    assert "ansible.builtin.copy" in export
    assert "azuracast_redact" in export["vars"]["export_payload"]["resources"]
