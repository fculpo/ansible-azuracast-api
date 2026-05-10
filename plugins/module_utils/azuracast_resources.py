try:
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils import (
        azuracast_planning as planning,
    )
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils.azuracast_openapi import (
        OpenApiCapabilities,
    )
except ImportError:
    import importlib.util
    import sys
    from pathlib import Path

    def _load_module_util(name):
        if name in sys.modules:
            return sys.modules[name]
        module_path = Path(__file__).resolve().parent / f"{name}.py"
        spec = importlib.util.spec_from_file_location(name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    planning = _load_module_util("azuracast_planning")
    azuracast_openapi = _load_module_util("azuracast_openapi")
    OpenApiCapabilities = azuracast_openapi.OpenApiCapabilities


class ResourceSpec:
    result_keys = ("changed", "action", "before", "after", "resource")

    def __init__(
        self,
        family,
        collection_path,
        item_path,
        key,
        scope_fields=None,
        create=True,
        update=True,
        delete=True,
    ):
        self.family = family
        self.collection_path = collection_path
        self.item_path = item_path
        self.key = key
        self.scope_fields = tuple(scope_fields or ())
        self.create = create
        self.update = update
        self.delete = delete
        self._validate()

    @property
    def scoped(self):
        return bool(self.scope_fields)

    @property
    def display_name(self):
        return str(self.family).capitalize()

    def render_collection_path(self, scope=None):
        return self._render_path(self.collection_path, scope or {})

    def render_item_path(self, resource_id, scope=None):
        values = dict(scope or {})
        values["id"] = resource_id
        return self._render_path(self.item_path, values)

    def sample_collection_path(self):
        return self.render_collection_path(self._sample_scope())

    def sample_item_path(self):
        return self.render_item_path(1, self._sample_scope())

    def _validate(self):
        for field in ("family", "collection_path", "item_path", "key"):
            if not getattr(self, field):
                raise planning.AzuraCastPlanningError(
                    f"Resource metadata is missing required field: {field}"
                )

    def _sample_scope(self):
        return {field: 1 for field in self.scope_fields}

    def _render_path(self, path, values):
        rendered = path
        for key, value in values.items():
            rendered = rendered.replace("{" + str(key) + "}", str(value))
        return rendered


def changed_result(action, before, after, resource):
    return {
        "changed": True,
        "action": action,
        "before": before,
        "after": after,
        "diff": {"before": before, "after": after},
        "resource": planning.azuracast_redact(resource),
    }


def noop_result(before, after, resource):
    return {
        "changed": False,
        "action": "noop",
        "before": before,
        "after": after,
        "resource": resource,
    }


def validate_resource_openapi(resource, openapi_contract, desired, state):
    if not openapi_contract:
        return

    capabilities = OpenApiCapabilities.from_document(openapi_contract)
    collection_path = resource.sample_collection_path()
    item_path = resource.sample_item_path()
    required_methods = [(collection_path, "GET")]

    if state == "present":
        if resource.create:
            required_methods.append((collection_path, "POST"))
        if resource.update:
            required_methods.append((item_path, "PUT"))
    elif resource.delete:
        required_methods.append((item_path, "DELETE"))

    for path, method in required_methods:
        if not capabilities.method_exists(path, method):
            raise planning.AzuraCastPlanningError(
                f"OpenAPI contract does not declare {method} {path}"
            )

    if state == "absent":
        return

    schema_methods = []
    if resource.create:
        schema_methods.append((collection_path, "POST"))
    if resource.update:
        schema_methods.append((item_path, "PUT"))

    fields = set()
    read_only_fields = set()
    required_fields = set()
    enum_values = {}
    for path, method in schema_methods:
        fields.update(capabilities.request_schema_fields(path, method))
        read_only_fields.update(capabilities.read_only_fields(path, method))
        required_fields.update(capabilities.required_fields(path, method))
        enum_values.update(capabilities.enum_values(path, method))

    payload_fields = set((desired or {}).keys())
    unknown_fields = sorted(payload_fields - fields)
    if unknown_fields:
        raise planning.AzuraCastPlanningError(
            f"{resource.display_name} payload contains fields not declared by OpenAPI: "
            + ", ".join(unknown_fields)
        )

    missing_required_fields = sorted(required_fields - payload_fields)
    if missing_required_fields:
        raise planning.AzuraCastPlanningError(
            f"{resource.display_name} payload is missing required OpenAPI fields: "
            + ", ".join(missing_required_fields)
        )

    read_only_payload_fields = sorted(payload_fields & read_only_fields)
    if read_only_payload_fields:
        raise planning.AzuraCastPlanningError(
            f"{resource.display_name} payload contains read-only OpenAPI fields: "
            + ", ".join(read_only_payload_fields)
        )

    for field, values in enum_values.items():
        if field in desired and desired[field] not in values:
            raise planning.AzuraCastPlanningError(
                f"{resource.display_name} field {field} must be one of: "
                + ", ".join(sorted(values))
            )


def reconcile_resource(
    client,
    resource,
    desired,
    state="present",
    check_mode=False,
    openapi_contract=None,
    scope=None,
):
    scope = dict(scope or {})
    validate_resource_openapi(resource, openapi_contract, desired, state)

    live_resources = client.list_resources(resource.collection_path, scope)
    live_by_key = planning.azuracast_index_by(live_resources, resource.key)
    live = live_by_key.get(desired[resource.key])
    desired_compare = planning.azuracast_compare_shape(desired)

    if state == "absent":
        if live is None:
            return noop_result(None, None, None)

        before = planning.azuracast_desired_shape(
            planning.azuracast_compare_shape(live),
            desired_compare,
        )
        mutation_resource = None
        if not check_mode:
            mutation_resource = client.delete_resource(
                resource.item_path,
                live["id"],
                scope,
            )
        return changed_result("delete", before, None, mutation_resource)

    if live is None:
        mutation_resource = None
        if not check_mode:
            mutation_resource = client.create_resource(
                resource.collection_path,
                desired,
                scope,
            )
        return changed_result("create", None, desired_compare, mutation_resource)

    before = planning.azuracast_desired_shape(
        planning.azuracast_compare_shape(live),
        desired_compare,
    )
    if before == desired_compare:
        return noop_result(before, desired_compare, live)

    mutation_resource = None
    if not check_mode:
        mutation_resource = client.update_resource(
            resource.item_path,
            live["id"],
            desired_compare,
            scope,
        )
    return changed_result("update", before, desired_compare, mutation_resource)
