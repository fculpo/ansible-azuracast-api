class AzuraCastPlanningError(Exception):
    pass


READONLY_KEYS = {
    "id",
    "links",
    "listeners_total",
    "listeners_unique",
    "num_songs",
    "played_at",
    "queue_reset_at",
    "station_id",
    "total_length",
    "created_at",
    "updated_at",
    "createdAt",
    "updatedAt",
    "api_url",
    "public_url",
    "art",
    "art_updated_at",
}

SENSITIVE_FRAGMENTS = (
    "authorization",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "credential",
)

STATION_RESOURCE_KEYS = ("mounts", "playlists", "remotes", "webhooks")


def _is_storage_reference_key(key):
    return str(key).endswith("_storage_location")


def _is_sensitive_key(key):
    lowered = str(key).lower()
    return any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS)


def azuracast_strip_readonly(value):
    if isinstance(value, list):
        return [azuracast_strip_readonly(item) for item in value]

    if isinstance(value, dict):
        stripped = {}
        for key, item in value.items():
            if key in READONLY_KEYS:
                continue
            stripped[key] = azuracast_strip_readonly(item)
        return stripped

    return value


def azuracast_normalize(value):
    value = azuracast_strip_readonly(value)

    if isinstance(value, list):
        return [azuracast_normalize(item) for item in value]

    if isinstance(value, dict):
        return {
            key: azuracast_normalize(value[key])
            for key in sorted(value.keys())
            if value[key] is not None
        }

    return value


def azuracast_compare_shape(value):
    value = azuracast_strip_readonly(value)

    if isinstance(value, list):
        return [azuracast_compare_shape(item) for item in value]

    if isinstance(value, dict):
        return {
            key: azuracast_compare_shape(value[key])
            for key in sorted(value.keys())
            if value[key] is not None and not _is_sensitive_key(key)
        }

    return value


def azuracast_desired_shape(value, desired):
    if isinstance(value, dict) and isinstance(desired, dict):
        return {
            key: azuracast_desired_shape(value[key], desired[key])
            for key in desired.keys()
            if key in value
        }

    return value


def azuracast_index_by(resources, key):
    indexed = {}
    for resource in resources or []:
        resource_key = resource.get(key)
        if resource_key is None:
            raise AzuraCastPlanningError(f"AzuraCast resource is missing key: {key}")
        if resource_key in indexed:
            raise AzuraCastPlanningError(f"Duplicate AzuraCast resource key: {resource_key}")
        indexed[resource_key] = resource
    return indexed


def azuracast_plan_actions(desired, live, key):
    desired_by_key = azuracast_index_by(desired or [], key)
    live_by_key = azuracast_index_by(live or [], key)
    plan = {"create": [], "update": [], "noop": [], "unmanaged": []}

    for resource_key, desired_resource in desired_by_key.items():
        live_resource = live_by_key.get(resource_key)
        if live_resource is None:
            plan["create"].append(desired_resource)
            continue

        desired_normalized = azuracast_compare_shape(desired_resource)
        live_normalized = azuracast_desired_shape(
            azuracast_compare_shape(live_resource),
            desired_normalized,
        )
        if desired_normalized == live_normalized:
            plan["noop"].append({"id": live_resource.get("id"), "key": resource_key})
            continue

        plan["update"].append(
            {
                "id": live_resource.get("id"),
                "key": resource_key,
                "before": live_normalized,
                "after": desired_normalized,
            }
        )

    for resource_key, live_resource in live_by_key.items():
        if resource_key not in desired_by_key:
            plan["unmanaged"].append(live_resource)

    return plan


def _has_sensitive_field(value):
    if isinstance(value, list):
        return any(_has_sensitive_field(item) for item in value)

    if isinstance(value, dict):
        return any(
            _is_sensitive_key(key) or _has_sensitive_field(item)
            for key, item in value.items()
        )

    return False


def azuracast_sensitive_update_plan(desired, live, key):
    live_by_key = azuracast_index_by(live or [], key)
    updates = []

    for desired_resource in desired or []:
        if not _has_sensitive_field(desired_resource):
            continue

        resource_key = desired_resource.get(key)
        live_resource = live_by_key.get(resource_key)
        if live_resource is None:
            continue

        updates.append(
            {
                "id": live_resource.get("id"),
                "key": resource_key,
                "after": desired_resource,
            }
        )

    return updates


def azuracast_destructive_deletes(plan, destructive_sync, destructive_allow, family):
    if not destructive_sync:
        return []
    if family not in (destructive_allow or []):
        return []
    return plan.get("unmanaged", [])


def azuracast_redact(value):
    if isinstance(value, list):
        return [azuracast_redact(item) for item in value]

    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                redacted[key] = "********"
            else:
                redacted[key] = azuracast_redact(item)
        return redacted

    return value


def azuracast_sensitive_shape(value):
    if isinstance(value, list):
        return [
            sensitive_item
            for sensitive_item in (azuracast_sensitive_shape(item) for item in value)
            if sensitive_item not in ({}, [])
        ]

    if isinstance(value, dict):
        shaped = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                shaped[key] = item
                continue

            sensitive_item = azuracast_sensitive_shape(item)
            if sensitive_item not in ({}, []):
                shaped[key] = sensitive_item
        return shaped

    return {}


def azuracast_resolve_storage_references(payload, storage_locations):
    storage_by_type = azuracast_index_by(storage_locations, "type")

    def resolve(value, parent_key=None):
        if isinstance(value, list):
            return [resolve(item, parent_key) for item in value]

        if isinstance(value, dict):
            if _is_storage_reference_key(parent_key) and "type" in value:
                storage_type = value.get("type")
                if storage_type is None:
                    raise AzuraCastPlanningError(
                        f"AzuraCast storage reference is missing type: {parent_key}"
                    )
                storage = storage_by_type.get(storage_type)
                if storage is None:
                    raise AzuraCastPlanningError(
                        f"Unknown AzuraCast storage location type: {storage_type}"
                    )
                storage_id = storage.get("id")
                if storage_id is None:
                    raise AzuraCastPlanningError(
                        f"AzuraCast storage location is missing id: {storage_type}"
                    )
                return storage_id

            return {key: resolve(item, key) for key, item in value.items()}

        return value

    return resolve(payload)


def azuracast_station_api_payloads(stations):
    payloads = []
    for station in stations or []:
        payloads.append(
            {
                key: value
                for key, value in station.items()
                if key not in STATION_RESOURCE_KEYS
            }
        )
    return payloads


def azuracast_station_resource_plans(stations, live_results):
    plans = []
    stations_by_key = azuracast_index_by(stations or [], "short_name")

    for live_result in live_results or []:
        station_key = live_result["station"]
        family = live_result["family"]
        key = live_result["key"]
        desired = stations_by_key.get(station_key, {}).get(family, [])
        live = live_result.get("resources", [])
        plan = azuracast_plan_actions(desired, live, key)
        plan.update({"station": station_key, "family": family, "key": key})
        plans.append(plan)

    return plans
