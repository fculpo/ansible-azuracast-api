from ansible.errors import AnsibleFilterError

try:
    from ansible_collections.fculpo.azuracast_api.plugins.module_utils import (
        azuracast_planning as planning,
    )
except ImportError:
    import importlib.util
    from pathlib import Path

    PLANNING_PATH = (
        Path(__file__).resolve().parents[1]
        / "module_utils"
        / "azuracast_planning.py"
    )
    spec = importlib.util.spec_from_file_location("azuracast_planning", PLANNING_PATH)
    planning = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planning)


def _filter_error(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except planning.AzuraCastPlanningError as exc:
        raise AnsibleFilterError(str(exc)) from exc


azuracast_strip_readonly = planning.azuracast_strip_readonly
azuracast_normalize = planning.azuracast_normalize
azuracast_compare_shape = planning.azuracast_compare_shape
azuracast_desired_shape = planning.azuracast_desired_shape
azuracast_destructive_deletes = planning.azuracast_destructive_deletes
azuracast_redact = planning.azuracast_redact
azuracast_sensitive_shape = planning.azuracast_sensitive_shape


def azuracast_index_by(resources, key):
    return _filter_error(planning.azuracast_index_by, resources, key)


def azuracast_plan_actions(desired, live, key):
    return _filter_error(planning.azuracast_plan_actions, desired, live, key)


def azuracast_sensitive_update_plan(desired, live, key):
    return _filter_error(planning.azuracast_sensitive_update_plan, desired, live, key)


def azuracast_resolve_storage_references(value, storage_locations):
    return _filter_error(
        planning.azuracast_resolve_storage_references,
        value,
        storage_locations,
    )


def azuracast_station_api_payloads(stations):
    return planning.azuracast_station_api_payloads(stations)


def azuracast_station_resource_plans(stations, live_results):
    return _filter_error(
        planning.azuracast_station_resource_plans,
        stations,
        live_results,
    )


class FilterModule:
    def filters(self):
        return {
            "azuracast_strip_readonly": azuracast_strip_readonly,
            "azuracast_normalize": azuracast_normalize,
            "azuracast_compare_shape": azuracast_compare_shape,
            "azuracast_desired_shape": azuracast_desired_shape,
            "azuracast_index_by": azuracast_index_by,
            "azuracast_plan_actions": azuracast_plan_actions,
            "azuracast_sensitive_update_plan": azuracast_sensitive_update_plan,
            "azuracast_destructive_deletes": azuracast_destructive_deletes,
            "azuracast_redact": azuracast_redact,
            "azuracast_sensitive_shape": azuracast_sensitive_shape,
            "azuracast_resolve_storage_references": azuracast_resolve_storage_references,
            "azuracast_station_api_payloads": azuracast_station_api_payloads,
            "azuracast_station_resource_plans": azuracast_station_resource_plans,
        }
