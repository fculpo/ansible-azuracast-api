import json
import urllib.error

from ansible.module_utils.urls import open_url as ansible_open_url


class AzuraCastApiError(Exception):
    pass


class AzuraCastClient:
    def __init__(
        self,
        base_url,
        api_key,
        validate_certs=True,
        timeout=30,
        opener=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.validate_certs = validate_certs
        self.timeout = timeout
        self.opener = opener or ansible_open_url

    def request(self, method, path, payload=None):
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        try:
            response = self.opener(
                f"{self.base_url}{path}",
                data=data,
                method=method,
                headers={
                    "X-API-Key": self.api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
                validate_certs=self.validate_certs,
            )
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AzuraCastApiError(
                f"AzuraCast API request failed with status {exc.code}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AzuraCastApiError(f"AzuraCast API request failed: {exc}") from exc

    def render_path(self, path, scope=None, resource_id=None):
        values = dict(scope or {})
        if resource_id is not None:
            values["id"] = resource_id

        rendered = path
        for key, value in values.items():
            rendered = rendered.replace("{" + str(key) + "}", str(value))
        return rendered

    def list_resources(self, collection_path, scope=None):
        return self.request("GET", self.render_path(collection_path, scope))

    def create_resource(self, collection_path, payload, scope=None):
        return self.request("POST", self.render_path(collection_path, scope), payload)

    def update_resource(self, item_path, resource_id, payload, scope=None):
        return self.request(
            "PUT",
            self.render_path(item_path, scope, resource_id),
            payload,
        )

    def delete_resource(self, item_path, resource_id, scope=None):
        return self.request(
            "DELETE",
            self.render_path(item_path, scope, resource_id),
        )

    def list_storage_locations(self):
        return self.list_resources("/api/admin/storage_locations")

    def create_storage_location(self, payload):
        return self.create_resource("/api/admin/storage_locations", payload)

    def update_storage_location(self, storage_id, payload):
        return self.update_resource(
            "/api/admin/storage_location/{id}",
            storage_id,
            payload,
        )

    def delete_storage_location(self, storage_id):
        return self.delete_resource("/api/admin/storage_location/{id}", storage_id)
