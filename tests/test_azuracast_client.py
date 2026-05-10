import importlib.util
from pathlib import Path
from urllib.error import HTTPError, URLError


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "module_utils"
    / "azuracast_client.py"
)
spec = importlib.util.spec_from_file_location("azuracast_client", MODULE_PATH)
azuracast_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(azuracast_client)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def close(self):
        pass


def test_client_sends_json_request_with_api_headers():
    calls = []

    def open_url(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(b'{"ok": true}')

    client = azuracast_client.AzuraCastClient(
        "https://radio.example.test/",
        "api-token",
        validate_certs=False,
        timeout=7,
        opener=open_url,
    )

    result = client.request("POST", "/api/admin/storage_locations", {"type": "backup"})

    assert result == {"ok": True}
    assert calls == [
        (
            "https://radio.example.test/api/admin/storage_locations",
            {
                "data": b'{"type": "backup"}',
                "method": "POST",
                "headers": {
                    "X-API-Key": "api-token",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                "timeout": 7,
                "validate_certs": False,
            },
        )
    ]


def test_client_returns_empty_dict_for_empty_response_body():
    client = azuracast_client.AzuraCastClient(
        "https://radio.example.test",
        "api-token",
        opener=lambda *args, **kwargs: FakeResponse(b""),
    )

    assert client.request("DELETE", "/api/admin/storage_location/8") == {}


def test_client_raises_api_error_with_http_status_and_body():
    def open_url(*args, **kwargs):
        raise HTTPError(
            "https://radio.example.test/api/admin/storage_locations",
            422,
            "Unprocessable Content",
            {},
            FakeResponse(b'{"message": "invalid"}'),
        )

    client = azuracast_client.AzuraCastClient(
        "https://radio.example.test",
        "api-token",
        opener=open_url,
    )

    try:
        client.request("POST", "/api/admin/storage_locations", {"type": "backup"})
    except azuracast_client.AzuraCastApiError as exc:
        assert str(exc) == (
            'AzuraCast API request failed with status 422: {"message": "invalid"}'
        )
    else:
        raise AssertionError("expected AzuraCastApiError")


def test_client_wraps_url_errors():
    def open_url(*args, **kwargs):
        raise URLError("offline")

    client = azuracast_client.AzuraCastClient(
        "https://radio.example.test",
        "api-token",
        opener=open_url,
    )

    try:
        client.request("GET", "/api/admin/storage_locations")
    except azuracast_client.AzuraCastApiError as exc:
        assert "AzuraCast API request failed:" in str(exc)
        assert "offline" in str(exc)
    else:
        raise AssertionError("expected AzuraCastApiError")


def test_client_generic_helpers_render_resource_paths_and_payloads():
    calls = []

    def open_url(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(b'{"id": 3}')

    client = azuracast_client.AzuraCastClient(
        "https://radio.example.test",
        "api-token",
        opener=open_url,
    )

    assert client.list_resources("/api/station/{station_id}/mounts", {"station_id": 7}) == {"id": 3}
    assert client.create_resource(
        "/api/station/{station_id}/mounts",
        {"name": "/radio.mp3"},
        {"station_id": 7},
    ) == {"id": 3}
    assert client.update_resource(
        "/api/station/{station_id}/mount/{id}",
        3,
        {"name": "/radio.mp3"},
        {"station_id": 7},
    ) == {"id": 3}
    assert client.delete_resource(
        "/api/station/{station_id}/mount/{id}",
        3,
        {"station_id": 7},
    ) == {"id": 3}

    assert [call[0] for call in calls] == [
        "https://radio.example.test/api/station/7/mounts",
        "https://radio.example.test/api/station/7/mounts",
        "https://radio.example.test/api/station/7/mount/3",
        "https://radio.example.test/api/station/7/mount/3",
    ]
    assert [call[1]["method"] for call in calls] == ["GET", "POST", "PUT", "DELETE"]
