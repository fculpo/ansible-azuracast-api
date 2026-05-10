import importlib.util
from pathlib import Path

import pytest
import yaml


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "modules"
    / "storage_location.py"
)
spec = importlib.util.spec_from_file_location("storage_location", MODULE_PATH)
storage_location = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage_location)


OPENAPI_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "storage_locations_openapi.yml"
)


class FakeStorageClient:
    def __init__(self, live):
        self.live = live
        self.created = []
        self.updated = []
        self.deleted = []

    def list_storage_locations(self):
        return self.live

    def create_storage_location(self, payload):
        self.created.append(payload)
        return {"id": 10, **payload}

    def update_storage_location(self, storage_id, payload):
        self.updated.append((storage_id, payload))
        return {"id": storage_id, **payload}

    def delete_storage_location(self, storage_id):
        self.deleted.append(storage_id)
        return {"deleted": storage_id}


def test_present_noops_when_storage_location_matches_live_state():
    desired = {"type": "backup", "adapter": "local", "path": "/var/azuracast/backups"}
    client = FakeStorageClient([{"id": 8, **desired, "links": {"self": "/api/storage/8"}}])

    result = storage_location.apply_storage_location(client, desired)

    assert result == {
        "changed": False,
        "action": "noop",
        "before": desired,
        "after": desired,
        "resource": {"id": 8, **desired, "links": {"self": "/api/storage/8"}},
    }
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_present_creates_missing_storage_location():
    desired = {"type": "backup", "adapter": "local", "path": "/var/azuracast/backups"}
    client = FakeStorageClient([])

    result = storage_location.apply_storage_location(client, desired)

    assert result["changed"] is True
    assert result["action"] == "create"
    assert result["before"] is None
    assert result["after"] == desired
    assert result["diff"] == {"before": None, "after": desired}
    assert result["resource"] == {"id": 10, **desired}
    assert client.created == [desired]
    assert client.updated == []
    assert client.deleted == []


def test_build_desired_storage_location_merges_sensitive_resource():
    desired = storage_location.build_desired_storage_location(
        "backup",
        {"adapter": "s3", "s3Bucket": "backups"},
        {"s3CredentialKey": "key", "s3CredentialSecret": "secret"},
    )

    assert desired == {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "backups",
        "s3CredentialKey": "key",
        "s3CredentialSecret": "secret",
    }


def test_present_updates_changed_storage_location():
    desired = {"type": "backup", "adapter": "local", "path": "/srv/backups"}
    live = {"id": 8, "type": "backup", "adapter": "local", "path": "/var/azuracast/backups"}
    client = FakeStorageClient([live])

    result = storage_location.apply_storage_location(client, desired)

    assert result["changed"] is True
    assert result["action"] == "update"
    assert result["before"] == {
        "type": "backup",
        "adapter": "local",
        "path": "/var/azuracast/backups",
    }
    assert result["after"] == desired
    assert result["diff"] == {
        "before": {
            "type": "backup",
            "adapter": "local",
            "path": "/var/azuracast/backups",
        },
        "after": desired,
    }
    assert result["resource"] == {"id": 8, **desired}
    assert client.created == []
    assert client.updated == [(8, desired)]
    assert client.deleted == []


def test_present_update_omits_sensitive_fields_from_normal_payload():
    desired = {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "new-backups",
        "s3CredentialKey": "desired-key",
        "s3CredentialSecret": "desired-secret",
    }
    live = {
        "id": 8,
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "old-backups",
        "s3CredentialKey": "masked-key",
        "s3CredentialSecret": "masked-secret",
    }
    client = FakeStorageClient([live])

    result = storage_location.apply_storage_location(client, desired)

    assert result["changed"] is True
    assert result["action"] == "update"
    assert result["after"] == {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "new-backups",
    }
    assert result["diff"] == {
        "before": {
            "type": "backup",
            "adapter": "s3",
            "s3Bucket": "old-backups",
        },
        "after": {
            "type": "backup",
            "adapter": "s3",
            "s3Bucket": "new-backups",
        },
    }
    assert client.updated == [
        (
            8,
            {
                "type": "backup",
                "adapter": "s3",
                "s3Bucket": "new-backups",
            },
        )
    ]


def test_absent_noops_when_storage_location_is_missing():
    client = FakeStorageClient([])

    result = storage_location.apply_storage_location(client, {"type": "backup"}, state="absent")

    assert result == {
        "changed": False,
        "action": "noop",
        "before": None,
        "after": None,
        "resource": None,
    }
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_absent_deletes_existing_storage_location():
    live = {"id": 8, "type": "backup", "adapter": "local", "path": "/var/azuracast/backups"}
    client = FakeStorageClient([live])

    result = storage_location.apply_storage_location(client, {"type": "backup"}, state="absent")

    assert result == {
        "changed": True,
        "action": "delete",
        "before": {"type": "backup"},
        "after": None,
        "diff": {"before": {"type": "backup"}, "after": None},
        "resource": {"deleted": 8},
    }
    assert client.created == []
    assert client.updated == []
    assert client.deleted == [8]


def test_check_mode_reports_create_without_mutating():
    desired = {"type": "backup", "adapter": "local", "path": "/var/azuracast/backups"}
    client = FakeStorageClient([])

    result = storage_location.apply_storage_location(client, desired, check_mode=True)

    assert result == {
        "changed": True,
        "action": "create",
        "before": None,
        "after": desired,
        "diff": {"before": None, "after": desired},
        "resource": None,
    }
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_openapi_contract_rejects_unknown_storage_payload_field():
    desired = {
        "type": "backup",
        "adapter": "local",
        "path": "/var/azuracast/backups",
        "unexpected": True,
    }
    client = FakeStorageClient([])

    with pytest.raises(storage_location.planning.AzuraCastPlanningError) as exc:
        storage_location.apply_storage_location(
            client,
            desired,
            openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        )

    assert str(exc.value) == (
        "Storage location payload contains fields not declared by OpenAPI: unexpected"
    )
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_openapi_contract_rejects_missing_required_storage_payload_field():
    desired = {
        "type": "backup",
        "path": "/var/azuracast/backups",
    }
    client = FakeStorageClient([])

    with pytest.raises(storage_location.planning.AzuraCastPlanningError) as exc:
        storage_location.apply_storage_location(
            client,
            desired,
            openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        )

    assert str(exc.value) == (
        "Storage location payload is missing required OpenAPI fields: adapter"
    )
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_openapi_contract_rejects_read_only_storage_payload_field():
    desired = {
        "id": 8,
        "type": "backup",
        "adapter": "local",
        "path": "/var/azuracast/backups",
    }
    client = FakeStorageClient([])

    with pytest.raises(storage_location.planning.AzuraCastPlanningError) as exc:
        storage_location.apply_storage_location(
            client,
            desired,
            openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        )

    assert str(exc.value) == (
        "Storage location payload contains read-only OpenAPI fields: id"
    )
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_openapi_contract_rejects_invalid_storage_payload_enum_value():
    desired = {
        "type": "backup",
        "adapter": "unsupported",
        "path": "/var/azuracast/backups",
    }
    client = FakeStorageClient([])

    with pytest.raises(storage_location.planning.AzuraCastPlanningError) as exc:
        storage_location.apply_storage_location(
            client,
            desired,
            openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
        )

    assert str(exc.value) == "Storage location field adapter must be one of: local, s3"
    assert client.created == []
    assert client.updated == []
    assert client.deleted == []


def test_openapi_contract_allows_declared_storage_payload_fields():
    desired = {
        "type": "backup",
        "adapter": "s3",
        "s3Bucket": "backups",
        "s3CredentialKey": "key",
        "s3CredentialSecret": "secret",
    }
    client = FakeStorageClient([])

    result = storage_location.apply_storage_location(
        client,
        desired,
        openapi_contract=yaml.safe_load(OPENAPI_FIXTURE.read_text()),
    )

    assert result["changed"] is True
    assert result["action"] == "create"
    assert client.created == [desired]
