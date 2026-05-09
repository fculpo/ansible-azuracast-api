import importlib.util
from pathlib import Path

from ansible.errors import AnsibleFilterError


PLUGIN_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "filter"
    / "azuracast_api.py"
)
spec = importlib.util.spec_from_file_location("azuracast_api", PLUGIN_PATH)
azuracast_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(azuracast_api)

azuracast_destructive_deletes = azuracast_api.azuracast_destructive_deletes
azuracast_desired_shape = azuracast_api.azuracast_desired_shape
azuracast_index_by = azuracast_api.azuracast_index_by
azuracast_plan_actions = azuracast_api.azuracast_plan_actions
azuracast_redact = azuracast_api.azuracast_redact
azuracast_sensitive_update_plan = azuracast_api.azuracast_sensitive_update_plan
azuracast_station_api_payloads = azuracast_api.azuracast_station_api_payloads
azuracast_station_resource_plans = azuracast_api.azuracast_station_resource_plans
azuracast_strip_readonly = azuracast_api.azuracast_strip_readonly


def test_strip_readonly_removes_api_metadata_recursively():
    payload = {
        "id": 10,
        "name": "Main",
        "links": {"self": "/api/item/10"},
        "nested": [{"id": 99, "name": "Child", "created_at": "2026-05-08"}],
    }

    assert azuracast_strip_readonly(payload) == {
        "name": "Main",
        "nested": [{"name": "Child"}],
    }


def test_index_by_rejects_duplicate_keys():
    resources = [{"name": "music", "id": 1}, {"name": "music", "id": 2}]

    try:
        azuracast_index_by(resources, "name")
    except AnsibleFilterError as exc:
        assert "Duplicate AzuraCast resource key: music" in str(exc)
    else:
        raise AssertionError("duplicate keys must fail")


def test_plan_actions_splits_create_update_noop_and_unmanaged():
    desired = [
        {"name": "music", "type": "station_media"},
        {"name": "records", "type": "station_recordings"},
        {"name": "podcasts", "type": "station_podcasts"},
    ]
    live = [
        {"id": 1, "name": "music", "type": "station_media"},
        {"id": 2, "name": "records", "type": "station_media"},
        {"id": 3, "name": "legacy", "type": "station_media"},
    ]

    plan = azuracast_plan_actions(desired, live, "name")

    assert plan["create"] == [{"name": "podcasts", "type": "station_podcasts"}]
    assert plan["update"] == [
        {
            "id": 2,
            "key": "records",
            "before": {"name": "records", "type": "station_media"},
            "after": {"name": "records", "type": "station_recordings"},
        }
    ]
    assert plan["noop"] == [{"id": 1, "key": "music"}]
    assert plan["unmanaged"] == [{"id": 3, "name": "legacy", "type": "station_media"}]


def test_plan_actions_ignores_station_resource_operational_metadata():
    desired = [
        {
            "name": "/radio.mp3",
            "display_name": "MP3",
            "autodj_format": "mp3",
            "autodj_bitrate": 128,
            "enable_autodj": True,
            "fallback_mount": "/error.mp3",
            "is_default": False,
            "is_public": False,
            "is_visible_on_public_pages": True,
            "max_listener_duration": 0,
        }
    ]
    live = [
        {
            "id": 3,
            "name": "/radio.mp3",
            "display_name": "MP3",
            "autodj_format": "mp3",
            "autodj_bitrate": 128,
            "enable_autodj": True,
            "fallback_mount": "/error.mp3",
            "is_default": False,
            "is_public": False,
            "is_visible_on_public_pages": True,
            "links": {"self": "/api/station/1/mount/3"},
            "listeners_total": 0,
            "listeners_unique": 0,
            "max_listener_duration": 0,
            "station_id": 1,
        }
    ]

    assert azuracast_plan_actions(desired, live, "name") == {
        "create": [],
        "update": [],
        "noop": [{"id": 3, "key": "/radio.mp3"}],
        "unmanaged": [],
    }


def test_plan_actions_compares_live_resources_using_desired_shape():
    desired = [
        {
            "short_name": "main",
            "frontend_config": {
                "banned_countries": [],
                "port": 8000,
            },
        }
    ]
    live = [
        {
            "id": 1,
            "short_name": "main",
            "api_history_items": 10,
            "frontend_config": {
                "admin_pw": "secret",
                "banned_countries": [],
                "port": 8000,
                "source_pw": "secret",
            },
        }
    ]

    assert azuracast_plan_actions(desired, live, "short_name") == {
        "create": [],
        "update": [],
        "noop": [{"id": 1, "key": "main"}],
        "unmanaged": [],
    }


def test_plan_actions_ignores_sensitive_field_drift():
    desired = [
        {
            "type": "backup",
            "adapter": "s3",
            "s3Bucket": "example-azcast-backups",
            "s3CredentialKey": "desired-key",
            "s3CredentialSecret": "desired-secret",
        }
    ]
    live = [
        {
            "id": 8,
            "type": "backup",
            "adapter": "s3",
            "s3Bucket": "example-azcast-backups",
            "s3CredentialKey": "masked-or-different-key",
            "s3CredentialSecret": "masked-or-different-secret",
        }
    ]

    assert azuracast_plan_actions(desired, live, "type") == {
        "create": [],
        "update": [],
        "noop": [{"id": 8, "key": "backup"}],
        "unmanaged": [],
    }


def test_sensitive_update_plan_targets_existing_desired_resources_with_sensitive_fields():
    desired = [
        {
            "type": "backup",
            "adapter": "s3",
            "s3Bucket": "example-azcast-backups",
            "s3CredentialKey": "desired-key",
            "s3CredentialSecret": "desired-secret",
        },
        {
            "type": "station_media",
            "adapter": "s3",
            "s3Bucket": "example-azcast-music",
            "s3CredentialKey": "desired-key",
            "s3CredentialSecret": "desired-secret",
        },
        {
            "type": "station_podcasts",
            "adapter": "s3",
            "s3Bucket": "example-azcast-podcasts",
            "s3CredentialKey": "desired-key",
            "s3CredentialSecret": "desired-secret",
        },
    ]
    live = [
        {"id": 8, "type": "backup"},
        {"id": 11, "type": "station_media"},
    ]

    assert azuracast_sensitive_update_plan(desired, live, "type") == [
        {
            "id": 8,
            "key": "backup",
            "after": desired[0],
        },
        {
            "id": 11,
            "key": "station_media",
            "after": desired[1],
        },
    ]


def test_sensitive_update_plan_ignores_resources_without_sensitive_fields():
    desired = [{"type": "backup", "adapter": "local"}]
    live = [{"id": 8, "type": "backup"}]

    assert azuracast_sensitive_update_plan(desired, live, "type") == []


def test_desired_shape_keeps_only_desired_keys_recursively():
    live = {
        "backup_keep_copies": 30,
        "backup_last_run": 1778227946,
        "nested": {"managed": True, "transient": "ignored"},
    }
    desired = {
        "backup_keep_copies": 30,
        "nested": {"managed": True},
    }

    assert azuracast_desired_shape(live, desired) == {
        "backup_keep_copies": 30,
        "nested": {"managed": True},
    }


def test_destructive_deletes_require_global_and_family_allow_flags():
    plan = {"unmanaged": [{"id": 3, "name": "legacy"}]}

    assert azuracast_destructive_deletes(plan, False, ["storage_locations"], "storage_locations") == []
    assert azuracast_destructive_deletes(plan, True, [], "storage_locations") == []
    assert azuracast_destructive_deletes(plan, True, ["storage_locations"], "storage_locations") == [
        {"id": 3, "name": "legacy"}
    ]


def test_redact_hides_nested_sensitive_values():
    payload = {
        "Authorization": "Bearer secret",
        "s3CredentialSecret": "secret",
        "nested": {"api_key": "secret", "safe": "visible"},
    }

    assert azuracast_redact(payload) == {
        "Authorization": "********",
        "s3CredentialSecret": "********",
        "nested": {"api_key": "********", "safe": "visible"},
    }


def test_station_api_payloads_remove_station_scoped_resources():
    stations = [
        {
            "short_name": "main",
            "name": "Main Station",
            "mounts": [{"name": "/radio.mp3"}],
            "playlists": [{"name": "Default"}],
            "remotes": [{"display_name": "Relay"}],
            "webhooks": [{"name": "Notify"}],
        }
    ]

    assert azuracast_station_api_payloads(stations) == [
        {"short_name": "main", "name": "Main Station"}
    ]


def test_resolve_storage_references_replaces_type_objects_with_live_ids():
    payload = {
        "backup_storage_location": {"type": "backup"},
        "stations": [
            {
                "short_name": "main",
                "media_storage_location": {"type": "station_media"},
                "recordings_storage_location": {"type": "station_recordings"},
                "podcasts_storage_location": 10,
            }
        ],
    }
    storage_locations = [
        {"id": 8, "type": "backup"},
        {"id": 9, "type": "station_recordings"},
        {"id": 11, "type": "station_media"},
    ]

    assert azuracast_api.azuracast_resolve_storage_references(payload, storage_locations) == {
        "backup_storage_location": 8,
        "stations": [
            {
                "short_name": "main",
                "media_storage_location": 11,
                "recordings_storage_location": 9,
                "podcasts_storage_location": 10,
            }
        ],
    }


def test_resolve_storage_references_rejects_unknown_types():
    payload = {"media_storage_location": {"type": "missing"}}

    try:
        azuracast_api.azuracast_resolve_storage_references(payload, [{"id": 11, "type": "station_media"}])
    except AnsibleFilterError as exc:
        assert "Unknown AzuraCast storage location type: missing" in str(exc)
    else:
        raise AssertionError("unknown storage types must fail")


def test_station_resource_plans_create_update_unmanaged_per_station_and_family():
    stations = [
        {
            "short_name": "main",
            "mounts": [{"name": "/radio.mp3", "bitrate": 192}],
        }
    ]
    live_results = [
        {
            "station": "main",
            "family": "mounts",
            "key": "name",
            "resources": [
                {"id": 1, "name": "/radio.mp3", "bitrate": 128},
                {"id": 2, "name": "/legacy.mp3", "bitrate": 128},
            ],
        }
    ]

    plans = azuracast_station_resource_plans(stations, live_results)

    assert plans == [
        {
            "station": "main",
            "family": "mounts",
            "key": "name",
            "create": [],
            "update": [
                {
                    "id": 1,
                    "key": "/radio.mp3",
                    "before": {"name": "/radio.mp3", "bitrate": 128},
                    "after": {"name": "/radio.mp3", "bitrate": 192},
                }
            ],
            "noop": [],
            "unmanaged": [{"id": 2, "name": "/legacy.mp3", "bitrate": 128}],
        }
    ]
