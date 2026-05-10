import re

from ansible.module_utils.common.yaml import yaml_load


class AzuraCastOpenApiError(Exception):
    pass


class OpenApiCapabilities:
    def __init__(self, document):
        self.document = document or {}

    @classmethod
    def from_document(cls, document):
        if isinstance(document, str):
            document = yaml_load(document)
        return cls(document)

    def endpoint_exists(self, path):
        return self._path_key(path) is not None

    def method_exists(self, path, method):
        operation = self._operation(path, method)
        return operation is not None

    def request_schema_fields(self, path, method):
        schema = self._request_schema(path, method)
        return set(schema.get("properties", {}).keys())

    def read_only_fields(self, path, method):
        schema = self._request_schema(path, method)
        return self._fields_with_flag(schema, "readOnly")

    def write_only_fields(self, path, method):
        schema = self._request_schema(path, method)
        return self._fields_with_flag(schema, "writeOnly")

    def required_fields(self, path, method):
        schema = self._request_schema(path, method)
        return set(schema.get("required", []))

    def enum_values(self, path, method):
        schema = self._request_schema(path, method)
        enums = {}
        for field, field_schema in schema.get("properties", {}).items():
            values = field_schema.get("enum")
            if values is not None:
                enums[field] = set(values)
        return enums

    def _operation(self, path, method):
        path_key = self._path_key(path)
        if path_key is None:
            return None

        return self.document.get("paths", {}).get(path_key, {}).get(method.lower())

    def _path_key(self, path):
        paths = self.document.get("paths", {})
        if path in paths:
            return path

        for candidate in paths.keys():
            pattern = re.sub(r"\{[^/]+\}", "[^/]+", candidate)
            if re.match(f"^{pattern}$", path):
                return candidate

        return None

    def _request_schema(self, path, method):
        operation = self._operation(path, method)
        if not operation:
            return {}

        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        return self._resolve_schema(json_content.get("schema", {}))

    def _resolve_schema(self, schema):
        ref = schema.get("$ref")
        if not ref:
            return self._compose_schema(schema)

        if not ref.startswith("#/"):
            raise AzuraCastOpenApiError(f"Unsupported external OpenAPI ref: {ref}")

        node = self.document
        for segment in ref[2:].split("/"):
            node = node.get(segment)
            if node is None:
                raise AzuraCastOpenApiError(f"Unknown OpenAPI ref: {ref}")
        return self._resolve_schema(node)

    def _compose_schema(self, schema):
        all_of = schema.get("allOf")
        if not all_of:
            return schema

        composed = {
            key: value
            for key, value in schema.items()
            if key not in ("allOf", "properties", "required")
        }
        properties = dict(schema.get("properties", {}))
        required = list(schema.get("required", []))

        for child_schema in all_of:
            resolved_child = self._resolve_schema(child_schema)
            properties.update(resolved_child.get("properties", {}))
            for field in resolved_child.get("required", []):
                if field not in required:
                    required.append(field)

        if properties:
            composed["properties"] = properties
        if required:
            composed["required"] = required

        return composed

    def _fields_with_flag(self, schema, flag):
        return {
            field
            for field, field_schema in schema.get("properties", {}).items()
            if field_schema.get(flag) is True
        }
