from pathlib import Path

import yaml


ROLE_TASKS = (
    Path(__file__).resolve().parents[1]
    / "roles"
    / "station_resources"
    / "tasks"
    / "main.yml"
)

MODULES_BY_FAMILY = {
    "mounts": {
        "module": "fculpo.azuracast_api.station_mount",
        "option": "name",
    },
    "playlists": {
        "module": "fculpo.azuracast_api.station_playlist",
        "option": "name",
    },
    "remotes": {
        "module": "fculpo.azuracast_api.station_remote",
        "option": "display_name",
    },
    "webhooks": {
        "module": "fculpo.azuracast_api.station_webhook",
        "option": "name",
    },
}


def load_tasks():
    return yaml.safe_load(ROLE_TASKS.read_text())


def task_by_name(name):
    for task in load_tasks():
        if task.get("name") == name:
            return task
    raise AssertionError(f"missing task: {name}")


def test_station_resources_role_uses_modules_for_safe_create_update_delete_paths():
    for family, module_config in MODULES_BY_FAMILY.items():
        create = task_by_name(f"Create missing station {family}")
        update = task_by_name(f"Update changed station {family}")
        delete = task_by_name(
            f"Delete unmanaged station {family} only when explicitly allowed"
        )
        module_name = module_config["module"]
        option = module_config["option"]

        assert module_name in create
        assert module_name in update
        assert module_name in delete

        assert create[module_name]["state"] == "present"
        assert create[module_name]["station_short_name"] == "{{ item.0.station }}"
        assert create[module_name][option] == f"{{{{ item.1.{option} }}}}"
        assert create[module_name]["resource"] == "{{ item.1 }}"

        assert update[module_name]["state"] == "present"
        assert update[module_name]["station_short_name"] == "{{ item.0.station }}"
        assert update[module_name][option] == "{{ item.1.key }}"
        assert update[module_name]["resource"] == "{{ item.1.after }}"

        assert delete[module_name]["state"] == "absent"
        assert delete[module_name]["station_short_name"] == "{{ item.0.station }}"
        assert delete[module_name][option] == f"{{{{ item.1.{option} }}}}"


def test_station_resources_role_keeps_destructive_gates_per_family():
    for family in MODULES_BY_FAMILY:
        delete = task_by_name(
            f"Delete unmanaged station {family} only when explicitly allowed"
        )

        assert delete["when"] == [
            "azuracast_destructive_sync",
            f"'{family}' in azuracast_destructive_allow",
        ]
