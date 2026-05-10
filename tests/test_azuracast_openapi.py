import importlib.util
from pathlib import Path

import yaml


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "module_utils"
    / "azuracast_openapi.py"
)
spec = importlib.util.spec_from_file_location("azuracast_openapi", MODULE_PATH)
azuracast_openapi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(azuracast_openapi)


def load_storage_openapi():
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "storage_locations_openapi.yml"
    )
    return yaml.safe_load(fixture_path.read_text())


def test_openapi_capabilities_normalize_endpoint_methods_and_request_schema():
    capabilities = azuracast_openapi.OpenApiCapabilities.from_document(
        load_storage_openapi()
    )

    assert capabilities.endpoint_exists("/api/admin/storage_locations") is True
    assert capabilities.endpoint_exists("/api/admin/storage_location/8") is True
    assert capabilities.method_exists("/api/admin/storage_locations", "GET") is True
    assert capabilities.method_exists("/api/admin/storage_locations", "POST") is True
    assert capabilities.method_exists("/api/admin/storage_location/8", "PUT") is True
    assert capabilities.method_exists("/api/admin/storage_location/8", "DELETE") is True
    assert capabilities.method_exists("/api/admin/storage_locations", "PATCH") is False
    assert capabilities.request_schema_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {
        "adapter",
        "id",
        "links",
        "path",
        "s3Bucket",
        "s3CredentialKey",
        "s3CredentialSecret",
        "type",
    }


def test_openapi_capabilities_expose_field_contract_metadata():
    capabilities = azuracast_openapi.OpenApiCapabilities.from_document(
        load_storage_openapi()
    )

    assert capabilities.read_only_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {"id", "links"}
    assert capabilities.write_only_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {"s3CredentialKey", "s3CredentialSecret"}
    assert capabilities.required_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {"type", "adapter"}
    assert capabilities.enum_values(
        "/api/admin/storage_locations",
        "POST",
    ) == {
        "adapter": {"local", "s3"},
        "type": {"backup", "station_media"},
    }


def test_openapi_capabilities_compose_allof_request_schema_metadata():
    document = {
        "openapi": "3.0.0",
        "paths": {
            "/api/admin/storage_locations": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {
                                            "$ref": (
                                                "#/components/schemas/"
                                                "BaseStorageLocationRequest"
                                            )
                                        },
                                        {
                                            "type": "object",
                                            "required": ["path"],
                                            "properties": {
                                                "path": {"type": "string"},
                                                "s3CredentialKey": {
                                                    "type": "string",
                                                    "writeOnly": True,
                                                },
                                                "s3CredentialSecret": {
                                                    "type": "string",
                                                    "writeOnly": True,
                                                },
                                            },
                                        },
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "BaseStorageLocationRequest": {
                    "type": "object",
                    "required": ["type", "adapter"],
                    "properties": {
                        "id": {"type": "integer", "readOnly": True},
                        "type": {
                            "type": "string",
                            "enum": ["backup", "station_media"],
                        },
                        "adapter": {"type": "string", "enum": ["local", "s3"]},
                    },
                }
            }
        },
    }
    capabilities = azuracast_openapi.OpenApiCapabilities.from_document(document)

    assert capabilities.request_schema_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {
        "adapter",
        "id",
        "path",
        "s3CredentialKey",
        "s3CredentialSecret",
        "type",
    }
    assert capabilities.required_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {"adapter", "path", "type"}
    assert capabilities.read_only_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {"id"}
    assert capabilities.write_only_fields(
        "/api/admin/storage_locations",
        "POST",
    ) == {"s3CredentialKey", "s3CredentialSecret"}
    assert capabilities.enum_values(
        "/api/admin/storage_locations",
        "POST",
    ) == {
        "adapter": {"local", "s3"},
        "type": {"backup", "station_media"},
    }
