from pathlib import Path

import yaml


ROLE_TASKS = (
    Path(__file__).resolve().parents[1]
    / "roles"
    / "stations"
    / "tasks"
    / "main.yml"
)

STATION_MODULE = "fculpo.azuracast_api.station"


def load_tasks():
    return yaml.safe_load(ROLE_TASKS.read_text())


def task_by_name(name):
    for task in load_tasks():
        if task.get("name") == name:
            return task
    raise AssertionError(f"missing task: {name}")


def test_station_role_uses_module_for_safe_create_update_delete_paths():
    create = task_by_name("Create missing stations")
    update = task_by_name("Update changed stations")
    delete = task_by_name("Delete unmanaged stations only when explicitly allowed")

    assert STATION_MODULE in create
    assert STATION_MODULE in update
    assert STATION_MODULE in delete

    assert create[STATION_MODULE]["short_name"] == "{{ item.short_name }}"
    assert create[STATION_MODULE]["resource"] == "{{ item }}"
    assert create[STATION_MODULE]["state"] == "present"

    assert update[STATION_MODULE]["short_name"] == "{{ item.key }}"
    assert update[STATION_MODULE]["resource"] == "{{ item.after }}"
    assert update[STATION_MODULE]["state"] == "present"

    assert delete[STATION_MODULE]["short_name"] == "{{ item.short_name }}"
    assert delete[STATION_MODULE]["state"] == "absent"


def test_station_role_module_tasks_keep_common_connection_options():
    for task_name in (
        "Create missing stations",
        "Update changed stations",
        "Delete unmanaged stations only when explicitly allowed",
    ):
        module_options = task_by_name(task_name)[STATION_MODULE]

        assert module_options["base_url"] == "{{ azuracast_api_base_url }}"
        assert module_options["api_key"] == "{{ azuracast_api_key }}"
        assert module_options["validate_certs"] == (
            "{{ azuracast_api.validate_certs | default(true) }}"
        )
        assert module_options["timeout"] == "{{ azuracast_api.timeout | default(30) }}"


def test_station_role_module_tasks_do_not_skip_check_mode():
    for task_name in (
        "Create missing stations",
        "Update changed stations",
        "Delete unmanaged stations only when explicitly allowed",
    ):
        task = task_by_name(task_name)

        assert task.get("when") != "not ansible_check_mode"


def test_station_role_keeps_storage_resolution_and_payload_planning():
    tasks = load_tasks()
    task_names = [task["name"] for task in tasks]
    expected_resolved = (
        "{{ azuracast_stations | "
        "fculpo.azuracast_api.azuracast_resolve_storage_references("
        "azuracast_stations_storage_live_response.json) }}"
    )
    expected_plan = (
        "{{ azuracast_stations_resolved | "
        "fculpo.azuracast_api.azuracast_station_api_payloads | "
        "fculpo.azuracast_api.azuracast_plan_actions("
        "azuracast_stations_live_response.json, 'short_name') }}"
    )

    assert "Fetch current AzuraCast storage locations for station references" in task_names
    assert "Resolve station storage references" in task_names
    assert "Plan station actions" in task_names

    resolve = task_by_name("Resolve station storage references")
    plan = task_by_name("Plan station actions")

    assert (
        resolve["ansible.builtin.set_fact"]["azuracast_stations_resolved"]
        == expected_resolved
    )
    assert (
        plan["ansible.builtin.set_fact"]["azuracast_stations_plan"]
        == expected_plan
    )


def test_station_role_module_delete_keeps_destructive_gates():
    delete = task_by_name("Delete unmanaged stations only when explicitly allowed")

    expected_loop = (
        "{{ azuracast_stations_plan | "
        "fculpo.azuracast_api.azuracast_destructive_deletes("
        "azuracast_destructive_sync, azuracast_destructive_allow, "
        "'stations') }}"
    )
    assert delete["loop"] == expected_loop
