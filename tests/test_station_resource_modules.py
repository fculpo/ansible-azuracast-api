import importlib.util
from pathlib import Path

import pytest
import yaml


MODULE_DIR = Path(__file__).resolve().parents[1] / "plugins" / "modules"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


RESOURCE_MODULES = (
    {
        "module": "station_playlist",
        "apply": "apply_station_playlist",
        "collection_path": "/api/station/{station_id}/playlists",
        "item_path": "/api/station/{station_id}/playlist/{id}",
        "key": "name",
        "key_value": "Default",
        "changed_field": "source",
        "old_value": "songs",
        "new_value": "playlist",
        "fixture": "station_playlists_openapi.yml",
        "error_prefix": "Station playlist",
    },
    {
        "module": "station_remote",
        "apply": "apply_station_remote",
        "collection_path": "/api/station/{station_id}/remotes",
        "item_path": "/api/station/{station_id}/remote/{id}",
        "key": "display_name",
        "key_value": "Relay",
        "changed_field": "url",
        "old_value": "https://old.example.com/live",
        "new_value": "https://relay.example.com/live",
        "fixture": "station_remotes_openapi.yml",
        "error_prefix": "Station remote",
    },
    {
        "module": "station_webhook",
        "apply": "apply_station_webhook",
        "collection_path": "/api/station/{station_id}/webhooks",
        "item_path": "/api/station/{station_id}/webhook/{id}",
        "key": "name",
        "key_value": "Notify",
        "changed_field": "url",
        "old_value": "https://old.example.com/hook",
        "new_value": "https://hooks.example.com/azuracast",
        "fixture": "station_webhooks_openapi.yml",
        "error_prefix": "Station webhook",
    },
)


def load_module(name):
    path = MODULE_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeStationResourceClient:
    def __init__(self, spec, stations=None, resources=None):
        self.spec = spec
        self.stations = stations or []
        self.resources = resources or []
        self.created = []
        self.updated = []
        self.deleted = []

    def list_resources(self, path, scope=None):
        if path == "/api/admin/stations":
            return self.stations
        assert path == self.spec["collection_path"]
        assert scope == {"station_id": 7}
        return self.resources

    def create_resource(self, path, payload, scope=None):
        self.created.append((path, payload, scope))
        return {"id": 10, **payload}

    def update_resource(self, path, resource_id, payload, scope=None):
        self.updated.append((path, resource_id, payload, scope))
        return {"id": resource_id, **payload}

    def delete_resource(self, path, resource_id, scope=None):
        self.deleted.append((path, resource_id, scope))
        return {"deleted": resource_id}


def desired_for(spec, value=None):
    desired = {spec["key"]: spec["key_value"]}
    desired[spec["changed_field"]] = value or spec["new_value"]
    return desired


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_noops_when_key_matches_live_state(resource_spec):
    module = load_module(resource_spec["module"])
    desired = desired_for(resource_spec)
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
        resources=[{"id": 3, **desired}],
    )

    result = getattr(module, resource_spec["apply"])(
        client,
        desired,
        station_short_name="main",
    )

    assert result["changed"] is False
    assert result["action"] == "noop"
    assert result["before"] == desired


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_creates_missing_resource_under_resolved_station(resource_spec):
    module = load_module(resource_spec["module"])
    desired = desired_for(resource_spec)
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
    )

    result = getattr(module, resource_spec["apply"])(
        client,
        desired,
        station_short_name="main",
    )

    assert result["action"] == "create"
    assert client.created == [
        (resource_spec["collection_path"], desired, {"station_id": 7})
    ]


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_updates_changed_resource_by_station_and_resource_id(resource_spec):
    module = load_module(resource_spec["module"])
    desired = desired_for(resource_spec)
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
        resources=[{"id": 3, **desired_for(resource_spec, resource_spec["old_value"])}],
    )

    result = getattr(module, resource_spec["apply"])(
        client,
        desired,
        station_short_name="main",
    )

    assert result["action"] == "update"
    assert client.updated == [
        (resource_spec["item_path"], 3, desired, {"station_id": 7})
    ]


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_absent_deletes_by_station_and_resource_id(resource_spec):
    module = load_module(resource_spec["module"])
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
        resources=[{"id": 3, resource_spec["key"]: resource_spec["key_value"]}],
    )

    result = getattr(module, resource_spec["apply"])(
        client,
        {resource_spec["key"]: resource_spec["key_value"]},
        station_short_name="main",
        state="absent",
    )

    assert result["action"] == "delete"
    assert client.deleted == [
        (resource_spec["item_path"], 3, {"station_id": 7})
    ]


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_check_mode_reports_without_mutation(resource_spec):
    module = load_module(resource_spec["module"])
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
    )

    result = getattr(module, resource_spec["apply"])(
        client,
        {resource_spec["key"]: resource_spec["key_value"]},
        station_short_name="main",
        check_mode=True,
    )

    assert result["changed"] is True
    assert result["action"] == "create"
    assert client.created == []


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_fails_for_unknown_station_short_name(resource_spec):
    module = load_module(resource_spec["module"])
    client = FakeStationResourceClient(resource_spec, stations=[])

    with pytest.raises(module.planning.AzuraCastPlanningError) as exc:
        getattr(module, resource_spec["apply"])(
            client,
            {resource_spec["key"]: resource_spec["key_value"]},
            station_short_name="main",
        )

    assert str(exc.value) == "Unknown AzuraCast station short_name: main"


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_openapi_validation_uses_scoped_paths(resource_spec):
    module = load_module(resource_spec["module"])
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
    )

    result = getattr(module, resource_spec["apply"])(
        client,
        desired_for(resource_spec),
        station_short_name="main",
        openapi_contract=yaml.safe_load((FIXTURE_DIR / resource_spec["fixture"]).read_text()),
    )

    assert result["action"] == "create"


@pytest.mark.parametrize("resource_spec", RESOURCE_MODULES)
def test_station_resource_openapi_rejects_unsupported_field(resource_spec):
    module = load_module(resource_spec["module"])
    client = FakeStationResourceClient(
        resource_spec,
        stations=[{"id": 7, "short_name": "main"}],
    )
    desired = {
        resource_spec["key"]: resource_spec["key_value"],
        "unexpected": True,
    }

    with pytest.raises(module.planning.AzuraCastPlanningError) as exc:
        getattr(module, resource_spec["apply"])(
            client,
            desired,
            station_short_name="main",
            openapi_contract=yaml.safe_load((FIXTURE_DIR / resource_spec["fixture"]).read_text()),
        )

    assert str(exc.value) == (
        f"{resource_spec['error_prefix']} payload contains fields not declared by OpenAPI: unexpected"
    )
