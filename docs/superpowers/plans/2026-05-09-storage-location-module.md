# Storage Location Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proof-of-concept custom Ansible module for managing one AzuraCast storage location.

**Architecture:** Keep roles as the supported high-level interface. Add shared planning helpers under `plugins/module_utils/` and use them from a new `plugins/modules/storage_location.py` module without changing existing role behavior.

**Tech Stack:** Ansible collection, Python module utilities, pytest unit tests, `ansible-test sanity`.

---

## Current Status

The proof of concept is implemented and verified from the collection worktree.
The current module shape includes:

- Shared planning helpers in `plugins/module_utils/azuracast_planning.py`.
- Shared HTTP behavior in `plugins/module_utils/azuracast_client.py`.
- OpenAPI capability normalization in `plugins/module_utils/azuracast_openapi.py`.
- A `plugins/modules/storage_location.py` module with present/absent, check mode,
  sanitized diff output, sensitive payload splitting, and optional
  `openapi_contract` validation.
- Fixture-backed tests under `tests/`, including saved OpenAPI data in
  `tests/fixtures/storage_locations_openapi.yml`.

Collection-local verification currently covers unit tests, `ansible-doc`,
`ansible-test sanity`, and collection build. Consumer-repo playbook integration
should remain a final smoke test, not the routine development loop.

### Task 1: Shared Planning Utilities

**Files:**
- Create: `plugins/module_utils/azuracast_planning.py`
- Modify: `plugins/filter/azuracast_api.py`
- Test: `tests/test_azuracast_api_filters.py`

- [x] Move the existing pure planning functions into `plugins/module_utils/azuracast_planning.py`.
- [x] Keep filter names and behavior stable by importing the shared helpers from `plugins/filter/azuracast_api.py`.
- [x] Preserve existing filter exceptions as `AnsibleFilterError`.
- [x] Run: `pytest -q tests/test_azuracast_api_filters.py`
- [x] Expected: all existing filter tests pass.

### Task 2: Storage Location Module Behavior

**Files:**
- Create: `plugins/modules/storage_location.py`
- Create: `tests/test_storage_location_module.py`

- [x] Write tests for present/noop, present/create, present/update, absent/noop, absent/delete, and check-mode behavior using a fake client.
- [x] Implement module planning and execution around a single storage location matched by `type`.
- [x] Return structured `before`, `after`, `diff`, `action`, and `resource` data.
- [x] Mark sensitive values as `no_log` in the module argument spec.
- [x] Run: `pytest -q tests/test_storage_location_module.py`
- [x] Expected: storage module tests pass.

### Task 3: Documentation and Sanity

**Files:**
- Modify: `plugins/modules/storage_location.py`

- [x] Add `DOCUMENTATION`, `EXAMPLES`, and `RETURN` blocks for `ansible-doc`.
- [x] Run: `ansible-test sanity --python 3.14` from a temporary `ansible_collections/fculpo/azuracast_api` layout.
- [x] Expected: sanity tests pass when Ansible tooling is installed.

### Task 4: Shared HTTP Client

**Files:**
- Create: `plugins/module_utils/azuracast_client.py`
- Modify: `plugins/modules/storage_location.py`
- Test: `tests/test_azuracast_client.py`

- [x] Move JSON request construction, authentication headers, TLS validation,
  timeout handling, empty-response handling, and HTTP/URL error wrapping out of
  `storage_location.py`.
- [x] Keep storage-location endpoint methods on the shared client for now, so
  the module has no direct HTTP transport code.
- [x] Run: `pytest -q tests/test_azuracast_client.py tests/test_storage_location_module.py`
- [x] Expected: client tests and storage module tests pass.

### Task 5: OpenAPI Capability Validation

**Files:**
- Create: `plugins/module_utils/azuracast_openapi.py`
- Create: `tests/fixtures/storage_locations_openapi.yml`
- Test: `tests/test_azuracast_openapi.py`
- Test: `tests/test_storage_location_module.py`
- Modify: `plugins/modules/storage_location.py`

- [x] Normalize a saved OpenAPI document into endpoint/method capability checks.
- [x] Expose request schema fields, read-only fields, write-only fields,
  required fields, and enum values.
- [x] Add optional `openapi_contract` validation to `storage_location.py`.
- [x] Reject undeclared payload fields, read-only fields, missing required
  fields, and invalid enum values before mutating.
- [x] Keep OpenAPI as capability discovery, not code generation.
- [x] Run: `pytest -q tests/test_azuracast_openapi.py tests/test_storage_location_module.py`
- [x] Expected: OpenAPI utility tests and storage module validation tests pass.

### Task 6: Collection-Local Smoke Playbook

**Files:**
- Create: `examples/storage_location.yml`

- [ ] Add a minimal example playbook that exercises the
  `fculpo.azuracast_api.storage_location` module by FQCN.
- [ ] Verify the playbook with a locally built and installed collection using
  `ANSIBLE_COLLECTIONS_PATH`, so routine module testing does not require edits
  in the consumer repo.
- [ ] Expected: `ansible-playbook --syntax-check examples/storage_location.yml`
  passes against the temporary collection install.

## Remaining Architecture Work

- Add realistic OpenAPI schema support as needed by real AzuraCast contracts,
  especially `allOf` composition if the production schema uses it.
- Consider whether `AzuraCastClient` should grow generic resource helpers or
  stay explicit per endpoint as additional modules are added.
- Decide the second module only after the storage-location architecture remains
  stable through collection-local smoke testing. Prefer another admin-level
  resource before station-scoped resources, unless consumer needs dictate
  otherwise.
