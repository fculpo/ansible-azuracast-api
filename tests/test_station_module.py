import importlib.util
from pathlib import Path

import pytest
import yaml


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "modules"
    / "station.py"
)
spec = importlib.util.spec_from_file_location("station", MODULE_PATH)
station = importlib.util.module_from_spec(spec)
spec.loader.exec_module(station)


OPENAPI_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stations_openapi.yml"


class FakeStationClient:
    def __init__(self, live_stations=None, live_storage=None):
        self.live_stations = live_stations or []
        self.live_storage = live_storage or []
        self.created = []
        self.updated = []
        self.deleted = []

    def list_resources(self, path, scope=None):
        assert path == "/api/admin/stations"
        return self.live_stations

    def create_resource(self, path, payload, scope=None):
        self.created.append(payload)
        return {"id": 10, **payload}

    def update_resource(self, path, resource_id, payload, scope=None):
        self.updated.append((resource_id, payload))
        return {"id": resource_id, **payload}

    def delete_resource(self, path, resource_id, scope=None):
        self.deleted.append(resource_id)
        return {"deleted": resource_id}

    def list_storage_locations(self):
        return self.live_storage


def test_station_present_noops_when_short_name_matches_live_state():
    desired = {"short_name": "main", "name": "Main Radio"}
    client = FakeStationClient(live_stations=[{"id": 3, **desired}])

    result = station.apply_station(client, desired)

    assert result["changed"] is False
    assert result["action"] == "noop"
    assert result["before"] == desired
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_station_present_creates_missing_station():
    desired = {"short_name": "main", "name": "Main Radio"}
    client = FakeStationClient()

    result = station.apply_station(client, desired)

    assert result["changed"] is True
    assert result["action"] == "create"
    assert result["after"] == desired
    assert client.created == [desired]


def test_station_present_updates_changed_station():
    desired = {"short_name": "main", "name": "Main Radio"}
    client = FakeStationClient(live_stations=[{"id": 3, "short_name": "main", "name": "Old"}])

    result = station.apply_station(client, desired)

    assert result["action"] == "update"
    assert result["before"] == {"short_name": "main", "name": "Old"}
    assert client.updated == [(3, desired)]


def test_station_absent_deletes_one_station_by_id():
    client = FakeStationClient(live_stations=[{"id": 3, "short_name": "main"}])

    result = station.apply_station(client, {"short_name": "main"}, state="absent")

    assert result["action"] == "delete"
    assert client.deleted == [3]


def test_station_check_mode_reports_without_mutation():
    client = FakeStationClient()

    result = station.apply_station(
        client,
        {"short_name": "main", "name": "Main Radio"},
        check_mode=True,
    )

    assert result["changed"] is True
    assert result["action"] == "create"
    assert client.created == []


def test_build_desired_station_omits_station_scoped_child_arrays():
    desired = station.build_desired_station(
        {
            "short_name": "main",
            "name": "Main Radio",
            "mounts": [{"name": "/radio.mp3"}],
            "playlists": [{"name": "Default"}],
        }
    )

    assert desired == {"short_name": "main", "name": "Main Radio"}


def test_build_desired_station_merges_sensitive_resource():
    desired = station.build_desired_station(
        {"short_name": "main", "name": "Main Radio"},
        {"admin_password": "secret"},
    )

    assert desired == {
        "short_name": "main",
        "name": "Main Radio",
        "admin_password": "secret",
    }


def test_apply_station_resolves_storage_reference_objects_before_mutation():
    client = FakeStationClient(
        live_storage=[{"id": 11, "type": "station_media"}],
    )
    desired = {
        "short_name": "main",
        "name": "Main Radio",
        "media_storage_location": {"type": "station_media"},
    }

    station.apply_station(client, desired)

    assert client.created == [
        {
            "short_name": "main",
            "name": "Main Radio",
            "media_storage_location": 11,
        }
    ]


def test_apply_station_fails_for_unknown_storage_reference_type():
    client = FakeStationClient(live_storage=[])
    desired = {
        "short_name": "main",
        "name": "Main Radio",
        "media_storage_location": {"type": "station_media"},
    }

    with pytest.raises(station.planning.AzuraCastPlanningError) as exc:
        station.apply_station(client, desired)

    assert str(exc.value) == "Unknown AzuraCast storage location type: station_media"


def test_station_openapi_contract_rejects_unsupported_field():
    client = FakeStationClient()
    desired = {"short_name": "main", "name": "Main Radio", "unexpected": True}

    with pytest.raises(station.planning.AzuraCastPlanningError) as exc:
        station.apply_station(
            client,
            desired,
            openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        )

    assert str(exc.value) == (
        "Station payload contains fields not declared by OpenAPI: unexpected"
    )
