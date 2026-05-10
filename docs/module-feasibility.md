# Custom Module Feasibility

This note assesses whether the collection should move from generic
`ansible.builtin.uri` tasks plus planning filters toward custom Ansible modules
for AzuraCast resources.

## Summary

Custom modules are feasible, but a full switch is not a quick or low-risk
change. A narrow proof of concept is quick enough to validate the direction.
The most practical path is hybrid: keep the roles as the high-level convergence
interface, introduce one resource module first, and move role internals to
modules only after the module shape proves clearer than the current task/filter
shape.

## Current Shape

The collection currently exposes roles for API preflight, settings, storage
locations, stations, and station-scoped resources. Those roles use
`ansible.builtin.uri` for network calls and `plugins/filter/azuracast_api.py`
for deterministic local planning.

The important existing behavior is not just HTTP transport. The collection also
handles:

- Normalizing live AzuraCast API responses before comparison.
- Removing read-only and operational fields from drift checks.
- Ignoring sensitive write-only fields during normal comparison.
- Producing explicit `create`, `update`, `noop`, and `unmanaged` plans.
- Redacting sensitive values before display.
- Resolving storage references before API writes.
- Gating destructive deletes behind explicit configuration.
- Planning station-scoped resources by station and resource family.

Any module direction should preserve those behaviors. Replacing `uri` tasks
alone would not be enough.

## Feasibility

Adding modules is technically straightforward for this collection. Ansible
collections support modules under `plugins/modules/`, shared Python helpers
under `plugins/module_utils/`, and module documentation that is visible through
`ansible-doc`.

The work becomes larger because modules need a stable public interface. Each
module should have:

- A clear argument spec.
- `DOCUMENTATION`, `EXAMPLES`, and `RETURN` blocks.
- Check-mode behavior.
- Idempotent change detection.
- Structured return values.
- Shared API authentication and request handling.
- Unit tests for planning behavior and module outcomes.
- Sanity/doc validation through Ansible tooling.

The current filters already contain much of the idempotency logic, but they are
shaped for roles and plan output. A module implementation would need to move or
wrap that logic so modules and roles share one source of truth.

## Why Switch

Modules become attractive when users need resource-level tasks rather than
whole-role convergence. A module can expose one AzuraCast concept as a direct
Ansible task with native changed status, structured return values, and
`ansible-doc` documentation.

This is useful when:

- Users want to manage one resource in a playbook without adopting the full role
  variable model.
- A resource needs richer return values than the current debug plan provides.
- Troubleshooting is easier when a resource operation is a named module instead
  of a role task loop.
- The collection wants first-class generated documentation per resource.
- The current role variables become too broad or awkward for common workflows.

## Why Not Switch Yet

A full module-first rewrite would add carrying cost before the public interface
has been proven. Every resource module would need to maintain arguments,
documentation, return contracts, tests, and API behavior. AzuraCast's API shape
also includes noisy read-only data, sensitive write-only fields, and station
resource nesting, so the modules cannot be thin wrappers around HTTP calls.

The current role/filter model is still a good fit when the user wants to
describe a complete AzuraCast configuration and reconcile it against a live
instance. Roles can coordinate multiple resources, fetch shared state once, and
present a whole-instance plan in check mode.

## Recommended Direction

Do not switch everything at once. Build one module as a proof of concept and
keep the roles as the supported high-level interface.

The first module should be a simple but representative resource. Storage
locations are a strong candidate because they already exercise create, update,
delete safety, sensitive-field handling, and stable matching by type. A station
resource such as a mount is also useful, but it introduces station scoping and
should probably come after the first module pattern is stable.

The proof of concept should answer these questions:

- Is the module task interface clearer than the equivalent role variables?
- Can check mode report useful `changed`, `before`, `after`, and plan data?
- Can sensitive-field behavior remain safe and understandable?
- Can roles call the module without losing whole-instance planning ergonomics?
- Can shared code avoid duplicating planning logic between filters and modules?

If the answer is yes, the collection can expand modules resource by resource.
If the answer is no, the current role/filter interface should remain primary
and the module idea should be deferred.

## Migration Shape

A safe migration would look like this:

1. Extract shared API and planning behavior into module utilities while keeping
   existing filters stable.
2. Add one resource module that reuses the shared planning rules.
3. Add module-specific tests and `ansible-doc` validation.
4. Keep the existing role behavior unchanged for users.
5. Optionally update one role internally to call the module after the module API
   has proven stable.
6. Repeat only for resources where modules make the user interface better.

This keeps compatibility while testing whether modules are actually an
improvement.

## Effort Assessment

A proof of concept is moderate effort. It should be feasible without redesigning
the whole collection, especially if it starts with one resource and reuses the
existing planning code.

A complete switch is high effort. It would touch every resource family, public
documentation, tests, role internals, and possibly how users structure desired
state. It should be treated as a multi-step product decision, not a cleanup
task.

## Decision Criteria

Introduce more modules when at least one of these is true:

- Users ask for direct resource-level tasks.
- A role variable shape becomes hard to document or hard to use.
- A resource needs structured return values that debug plan output cannot
  provide well.
- The same operation is repeatedly needed outside the high-level roles.
- The module proof of concept reduces complexity instead of moving complexity
  from YAML into Python.

Avoid expanding modules when:

- The module is only a thin wrapper over `uri`.
- It duplicates existing filter planning logic.
- It makes whole-instance convergence harder to understand.
- The AzuraCast API behavior for the resource is still too unstable to expose
  as a durable module contract.

## References

- Ansible module overview:
  https://docs.ansible.com/ansible/latest/module_plugin_guide/modules_intro.html
- Ansible module documentation format:
  https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_documenting.html
- Ansible collection structure:
  https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_structure.html
