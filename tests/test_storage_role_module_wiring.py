from pathlib import Path

import yaml


ROLE_TASKS = (
    Path(__file__).resolve().parents[1]
    / "roles"
    / "storage"
    / "tasks"
    / "main.yml"
)


def load_tasks():
    return yaml.safe_load(ROLE_TASKS.read_text())


def task_by_name(name):
    for task in load_tasks():
        if task.get("name") == name:
            return task
    raise AssertionError(f"missing task: {name}")


def test_storage_role_uses_module_for_safe_create_update_delete_paths():
    create = task_by_name("Create missing storage locations")
    update = task_by_name("Update changed storage locations")
    delete = task_by_name("Delete unmanaged storage locations only when explicitly allowed")

    assert "fculpo.azuracast_api.storage_location" in create
    assert "fculpo.azuracast_api.storage_location" in update
    assert "fculpo.azuracast_api.storage_location" in delete
    assert create["fculpo.azuracast_api.storage_location"]["state"] == "present"
    assert update["fculpo.azuracast_api.storage_location"]["resource"] == "{{ item.after }}"
    assert delete["fculpo.azuracast_api.storage_location"]["state"] == "absent"


def test_storage_role_keeps_credential_rotation_as_explicit_tagged_uri_path():
    rotation = task_by_name("Rotate storage location credentials only when explicitly tagged")

    assert "ansible.builtin.uri" in rotation
    assert rotation["tags"] == ["never", "storage_rotate_credentials"]
    assert rotation["no_log"] == "{{ azuracast_api_hide_sensitive_logs }}"


def test_storage_role_module_delete_keeps_destructive_gates():
    delete = task_by_name("Delete unmanaged storage locations only when explicitly allowed")

    expected_loop = (
        "{{ azuracast_storage_plan | "
        "fculpo.azuracast_api.azuracast_destructive_deletes("
        "azuracast_destructive_sync, azuracast_destructive_allow, "
        "'storage_locations') }}"
    )
    assert (
        delete["loop"]
        == expected_loop
    )
