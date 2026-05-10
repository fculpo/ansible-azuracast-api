import importlib.util
from pathlib import Path

import pytest
import yaml


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "modules"
    / "station_mount.py"
)
spec = importlib.util.spec_from_file_location("station_mount", MODULE_PATH)
station_mount = importlib.util.module_from_spec(spec)
spec.loader.exec_module(station_mount)


OPENAPI_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "station_mounts_openapi.yml"


class FakeMountClient:
    def __init__(self, stations=None, mounts=None):
        self.stations = stations or []
        self.mounts = mounts or []
        self.created = []
        self.updated = []
        self.deleted = []

    def list_resources(self, path, scope=None):
        if path == "/api/admin/stations":
            return self.stations
        assert path == "/api/station/{station_id}/mounts"
        assert scope == {"station_id": 7}
        return self.mounts

    def create_resource(self, path, payload, scope=None):
        self.created.append((path, payload, scope))
        return {"id": 10, **payload}

    def update_resource(self, path, resource_id, payload, scope=None):
        self.updated.append((path, resource_id, payload, scope))
        return {"id": resource_id, **payload}

    def delete_resource(self, path, resource_id, scope=None):
        self.deleted.append((path, resource_id, scope))
        return {"deleted": resource_id}


def test_station_mount_noops_when_name_matches_live_state():
    desired = {"name": "/radio.mp3", "display_name": "MP3"}
    client = FakeMountClient(
        stations=[{"id": 7, "short_name": "main"}],
        mounts=[{"id": 3, **desired}],
    )

    result = station_mount.apply_station_mount(
        client,
        desired,
        station_short_name="main",
    )

    assert result["changed"] is False
    assert result["action"] == "noop"
    assert result["before"] == desired


def test_station_mount_creates_missing_mount_under_resolved_station():
    desired = {"name": "/radio.mp3", "display_name": "MP3"}
    client = FakeMountClient(stations=[{"id": 7, "short_name": "main"}])

    result = station_mount.apply_station_mount(
        client,
        desired,
        station_short_name="main",
    )

    assert result["action"] == "create"
    assert client.created == [
        ("/api/station/{station_id}/mounts", desired, {"station_id": 7})
    ]


def test_station_mount_updates_changed_mount_by_station_and_mount_id():
    desired = {"name": "/radio.mp3", "display_name": "MP3"}
    client = FakeMountClient(
        stations=[{"id": 7, "short_name": "main"}],
        mounts=[{"id": 3, "name": "/radio.mp3", "display_name": "Old"}],
    )

    result = station_mount.apply_station_mount(
        client,
        desired,
        station_short_name="main",
    )

    assert result["action"] == "update"
    assert client.updated == [
        ("/api/station/{station_id}/mount/{id}", 3, desired, {"station_id": 7})
    ]


def test_station_mount_absent_deletes_by_station_and_mount_id():
    client = FakeMountClient(
        stations=[{"id": 7, "short_name": "main"}],
        mounts=[{"id": 3, "name": "/radio.mp3"}],
    )

    result = station_mount.apply_station_mount(
        client,
        {"name": "/radio.mp3"},
        station_short_name="main",
        state="absent",
    )

    assert result["action"] == "delete"
    assert client.deleted == [("/api/station/{station_id}/mount/{id}", 3, {"station_id": 7})]


def test_station_mount_check_mode_reports_without_mutation():
    client = FakeMountClient(stations=[{"id": 7, "short_name": "main"}])

    result = station_mount.apply_station_mount(
        client,
        {"name": "/radio.mp3"},
        station_short_name="main",
        check_mode=True,
    )

    assert result["changed"] is True
    assert result["action"] == "create"
    assert client.created == []


def test_station_mount_fails_for_unknown_station_short_name():
    client = FakeMountClient(stations=[])

    with pytest.raises(station_mount.planning.AzuraCastPlanningError) as exc:
        station_mount.apply_station_mount(
            client,
            {"name": "/radio.mp3"},
            station_short_name="main",
        )

    assert str(exc.value) == "Unknown AzuraCast station short_name: main"


def test_station_mount_openapi_validation_uses_scoped_paths():
    client = FakeMountClient(stations=[{"id": 7, "short_name": "main"}])

    result = station_mount.apply_station_mount(
        client,
        {"name": "/radio.mp3", "display_name": "MP3"},
        station_short_name="main",
        openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
    )

    assert result["action"] == "create"


def test_station_mount_openapi_rejects_unsupported_field():
    client = FakeMountClient(stations=[{"id": 7, "short_name": "main"}])

    with pytest.raises(station_mount.planning.AzuraCastPlanningError) as exc:
        station_mount.apply_station_mount(
            client,
            {"name": "/radio.mp3", "unexpected": True},
            station_short_name="main",
            openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        )

    assert str(exc.value) == (
        "Station mount payload contains fields not declared by OpenAPI: unexpected"
    )
