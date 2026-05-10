try:
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils import (
        azuracast_planning as planning,
    )
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils.azuracast_resources import (
        ResourceSpec,
        reconcile_resource,
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
    azuracast_resources = _load_module_util("azuracast_resources")
    ResourceSpec = azuracast_resources.ResourceSpec
    reconcile_resource = azuracast_resources.reconcile_resource


def station_resource_spec(family, collection_path, item_path, key):
    return ResourceSpec(
        family=family,
        collection_path=collection_path,
        item_path=item_path,
        key=key,
        scope_fields=("station_id",),
    )


def build_desired_station_resource(key, key_value, resource, sensitive_resource=None, label=None):
    desired = dict(resource or {})
    desired.update(sensitive_resource or {})
    if key in desired and desired[key] != key_value:
        resource_label = label or "Station resource"
        raise planning.AzuraCastPlanningError(
            f"{resource_label} resource {key} must match the module {key} option"
        )
    desired[key] = key_value
    return desired


def resolve_station_id(client, station_short_name=None, station_id=None):
    if station_id is not None:
        return station_id
    if not station_short_name:
        raise planning.AzuraCastPlanningError(
            "station_short_name or station_id is required"
        )

    stations = client.list_resources("/api/admin/stations", {})
    stations_by_short_name = planning.azuracast_index_by(stations, "short_name")
    station = stations_by_short_name.get(station_short_name)
    if station is None:
        raise planning.AzuraCastPlanningError(
            f"Unknown AzuraCast station short_name: {station_short_name}"
        )
    resolved_station_id = station.get("id")
    if resolved_station_id is None:
        raise planning.AzuraCastPlanningError(
            f"AzuraCast station is missing id: {station_short_name}"
        )
    return resolved_station_id


def apply_station_resource(
    client,
    resource,
    desired,
    station_short_name=None,
    station_id=None,
    state="present",
    check_mode=False,
    openapi_contract=None,
):
    scope = {
        "station_id": resolve_station_id(
            client,
            station_short_name=station_short_name,
            station_id=station_id,
        )
    }

    return reconcile_resource(
        client,
        resource,
        desired,
        state=state,
        check_mode=check_mode,
        openapi_contract=openapi_contract,
        scope=scope,
    )
