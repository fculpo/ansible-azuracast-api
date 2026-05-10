import importlib.util
from pathlib import Path

import pytest
import yaml


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "module_utils"
    / "azuracast_resources.py"
)
spec = importlib.util.spec_from_file_location("azuracast_resources", MODULE_PATH)
azuracast_resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(azuracast_resources)


OPENAPI_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "storage_locations_openapi.yml"
)


class FakeResourceClient:
    def __init__(self, live):
        self.live = live
        self.created = []
        self.updated = []
        self.deleted = []

    def list_resources(self, path, scope=None):
        self.list_path = path
        self.list_scope = scope
        return self.live

    def create_resource(self, path, payload, scope=None):
        self.created.append((path, payload, scope))
        return {"id": 10, **payload}

    def update_resource(self, path, resource_id, payload, scope=None):
        self.updated.append((path, resource_id, payload, scope))
        return {"id": resource_id, **payload}

    def delete_resource(self, path, resource_id, scope=None):
        self.deleted.append((path, resource_id, scope))
        return {"deleted": resource_id}


def storage_spec():
    return azuracast_resources.ResourceSpec(
        family="storage location",
        collection_path="/api/admin/storage_locations",
        item_path="/api/admin/storage_location/{id}",
        key="type",
    )


def test_resource_contract_describes_storage_without_ansible_runtime():
    resource = storage_spec()

    assert resource.family == "storage location"
    assert resource.collection_path == "/api/admin/storage_locations"
    assert resource.item_path == "/api/admin/storage_location/{id}"
    assert resource.key == "type"
    assert resource.result_keys == ("changed", "action", "before", "after", "resource")


def test_resource_contract_rejects_missing_required_metadata():
    with pytest.raises(azuracast_resources.planning.AzuraCastPlanningError) as exc:
        azuracast_resources.ResourceSpec(
            family="",
            collection_path="/api/admin/storage_locations",
            item_path="/api/admin/storage_location/{id}",
            key="type",
        )

    assert str(exc.value) == "Resource metadata is missing required field: family"


def test_resource_contract_supports_scoped_resources():
    resource = azuracast_resources.ResourceSpec(
        family="station mount",
        collection_path="/api/station/{station_id}/mounts",
        item_path="/api/station/{station_id}/mount/{id}",
        key="name",
        scope_fields=("station_id",),
    )

    assert resource.scoped is True
    assert resource.render_collection_path({"station_id": 7}) == "/api/station/7/mounts"
    assert resource.render_item_path(3, {"station_id": 7}) == "/api/station/7/mount/3"


def test_reconcile_creates_missing_resource_with_safe_result():
    desired = {"type": "backup", "adapter": "local", "path": "/var/backups"}
    client = FakeResourceClient([])

    result = azuracast_resources.reconcile_resource(client, storage_spec(), desired)

    assert result == {
        "changed": True,
        "action": "create",
        "before": None,
        "after": desired,
        "diff": {"before": None, "after": desired},
        "resource": {"id": 10, **desired},
    }
    assert client.created == [
        ("/api/admin/storage_locations", desired, {})
    ]
    assert client.updated == []
    assert client.deleted == []


def test_reconcile_updates_changed_resource_with_safe_payload_only():
    desired = {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "new",
        "s3CredentialSecret": "secret",
    }
    live = {
        "id": 8,
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "old",
        "s3CredentialSecret": "masked",
    }
    client = FakeResourceClient([live])

    result = azuracast_resources.reconcile_resource(client, storage_spec(), desired)

    safe_desired = {"type": "backup", "adapter": "s3", "s3Bucket": "new"}
    assert result["action"] == "update"
    assert result["after"] == safe_desired
    assert result["diff"] == {
        "before": {"type": "backup", "adapter": "s3", "s3Bucket": "old"},
        "after": safe_desired,
    }
    assert client.updated == [
        ("/api/admin/storage_location/{id}", 8, safe_desired, {})
    ]


def test_reconcile_noops_when_live_matches_desired_shape():
    desired = {"type": "backup", "adapter": "local", "path": "/var/backups"}
    live = {"id": 8, **desired, "links": {"self": "/api/storage/8"}}
    client = FakeResourceClient([live])

    result = azuracast_resources.reconcile_resource(client, storage_spec(), desired)

    assert result == {
        "changed": False,
        "action": "noop",
        "before": desired,
        "after": desired,
        "resource": live,
    }
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_reconcile_absent_missing_resource_noops():
    client = FakeResourceClient([])

    result = azuracast_resources.reconcile_resource(
        client,
        storage_spec(),
        {"type": "backup"},
        state="absent",
    )

    assert result == {
        "changed": False,
        "action": "noop",
        "before": None,
        "after": None,
        "resource": None,
    }


def test_reconcile_absent_existing_resource_deletes_one_resource():
    client = FakeResourceClient([{"id": 8, "type": "backup", "adapter": "local"}])

    result = azuracast_resources.reconcile_resource(
        client,
        storage_spec(),
        {"type": "backup"},
        state="absent",
    )

    assert result["action"] == "delete"
    assert result["before"] == {"type": "backup"}
    assert client.deleted == [("/api/admin/storage_location/{id}", 8, {})]


def test_reconcile_check_mode_reports_without_mutating():
    client = FakeResourceClient([{"id": 8, "type": "backup", "adapter": "local"}])

    result = azuracast_resources.reconcile_resource(
        client,
        storage_spec(),
        {"type": "backup"},
        state="absent",
        check_mode=True,
    )

    assert result["changed"] is True
    assert result["action"] == "delete"
    assert result["resource"] is None
    assert client.deleted == []


def test_reconcile_duplicate_live_keys_fail_before_mutation():
    client = FakeResourceClient([
        {"id": 8, "type": "backup"},
        {"id": 9, "type": "backup"},
    ])

    with pytest.raises(azuracast_resources.planning.AzuraCastPlanningError):
        azuracast_resources.reconcile_resource(client, storage_spec(), {"type": "backup"})

    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_reconcile_sensitive_fields_never_appear_in_diff():
    desired = {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "new",
        "s3CredentialSecret": "secret",
    }
    client = FakeResourceClient([
        {
            "id": 8,
            "type": "backup",
            "adapter": "s3",
            "s3Bucket": "old",
            "s3CredentialSecret": "masked",
        }
    ])

    result = azuracast_resources.reconcile_resource(client, storage_spec(), desired)

    assert "s3CredentialSecret" not in result["diff"]["before"]
    assert "s3CredentialSecret" not in result["diff"]["after"]


def test_openapi_contract_validation_accepts_storage_payload_fields():
    desired = {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "backups",
        "s3CredentialKey": "key",
        "s3CredentialSecret": "secret",
    }

    azuracast_resources.validate_resource_openapi(
        storage_spec(),
        yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        desired,
        "present",
    )


def test_openapi_contract_validation_rejects_undeclared_payload_field():
    desired = {
        "type": "backup",
        "adapter": "local",
        "path": "/var/backups",
        "unexpected": True,
    }

    with pytest.raises(azuracast_resources.planning.AzuraCastPlanningError) as exc:
        azuracast_resources.validate_resource_openapi(
            storage_spec(),
            yaml.safe_load(OPENAPI_FIXTURE.read_text()),
            desired,
            "present",
        )

    assert str(exc.value) == (
        "Storage location payload contains fields not declared by OpenAPI: unexpected"
    )


def test_openapi_contract_validation_rejects_invalid_enum_value():
    desired = {"type": "backup", "adapter": "unsupported", "path": "/var/backups"}

    with pytest.raises(azuracast_resources.planning.AzuraCastPlanningError) as exc:
        azuracast_resources.validate_resource_openapi(
            storage_spec(),
            yaml.safe_load(OPENAPI_FIXTURE.read_text()),
            desired,
            "present",
        )

    assert str(exc.value) == "Storage location field adapter must be one of: local, s3"
