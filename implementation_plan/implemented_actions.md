# Plan: implemented actions

Concrete actions under `BaseAction`; `params` is the object inside `ActionParam` (LLM JSON). Each subclass implements `validate_param` against the schema below; invalid payloads → `ActionValidationError`.

---

## `read`

**Behavior:** Read file contents at `path` (text).

**Param schema (validation):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["path"],
  "properties": {
    "path": { "type": "string", "minLength": 1 }
  }
}
```

- `path`: filesystem path to read.
- Runtime defaults (encoding, read limits) are internal and not exposed in LLM `params`.

---

## `write`

**Behavior:** Write `content` to `path` (overwrite semantics for simplicity).

**Param schema (validation):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["path", "content"],
  "properties": {
    "path": { "type": "string", "minLength": 1 },
    "content": { "type": "string" }
  }
}
```

- `path`: target file path.
- `content`: full text to write.
- Runtime defaults (encoding, parent dir policy) are internal and not exposed in LLM `params`.

---

## `final_answer`

**Behavior:**
- Return the final user-facing message and can be seen as the signal that the Task is complete.
- When executed, this action will log the LLM final message to terminal

**Param schema (validation):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["message"],
  "properties": {
    "message": { "type": "string", "minLength": 1 }
  }
}
```

- `message`: final response text to send to the user.

---

## Permission architecture for `read` / `write`

Strict filesystem permission must be enforced by a dedicated guard layer (not by LLM prompt behavior).

1. **Single policy source** — Define one `PathPermissionPolicy` config loaded at app startup:
   - `memory_root = <cwd>/memory` (resolved absolute path).
   - `read_allow_roots = [memory_root]`.
   - `write_allow_roots = [memory_root]`.
   - no other filesystem roots are allowed.

2. **Canonical path check** — Before any I/O:
   - normalize and resolve (`realpath`) the requested `path`,
   - reject path traversal and symlink-escape attempts,
   - allow only when resolved path is inside `memory_root`.

3. **Action guard flow** — In `_execute_impl` for `ReadAction` and `WriteAction`:
   - call a shared permission service (e.g. `PermissionGuard.authorize(operation, path)`),
   - on denial, raise `ActionError` with a safe message (`permission denied for read/write path`),
   - never bypass this guard from action code.

4. **Write/create behavior in `memory` only** — `write` may create a new file if it does not exist, but only under `memory_root`; parent directories may be created only inside `memory_root`.

5. **Default-deny + minimal surface** — If requested path is outside `memory_root`, deny by default. Keep `params` minimal (`path`, `content`) and keep permission rules outside LLM-controlled fields.

6. **Auditability** — Log allow/deny decisions with action name, normalized path, decision reason, and task id (no sensitive file content in logs).

---

## Implementation notes

- Class names: e.g. `ReadAction`, `WriteAction`, `FinalAnswerAction`; `name`: `"read"`, `"write"`, `"final_answer"`.
- Keep params minimal to reduce LLM construction errors.
- Validate in `validate_param` using the same rules as the schemas (library or hand checks).
- `_execute_impl`: perform I/O for `read`/`write`; map OS errors to `ActionError` as appropriate.
- Enforce permission guard checks before any filesystem access in `read` / `write`.
- Task integration contract: when action name is `"final_answer"` and validation passes, set `Task.final_response = params.message`, set `Task.status = "completed"`, and stop the ReAct loop (no next LLM cycle).

---

## Param Validation strategy (clean schema via Pydantic)

Use **Pydantic models as the canonical param schema** for each action instead of hand-written dict checks.

### Target model shape

- `ReadParamsModel`: `path: str` with non-empty constraint.
- `WriteParamsModel`: `path: str` (non-empty), `content: str`.
- `FinalAnswerParamsModel`: `message: str` (non-empty).
- Set model config to forbid unknown fields (equivalent to `additionalProperties: false`).

### How action validation should work

1. In each concrete action file, define a local `ParamsModel` class.
2. In `_validate_param`, call model validation from `self.params.to_dict()`.
3. On validation failure, map Pydantic error(s) to `ActionValidationError` with concise, user-safe messages.
4. Store validated model instance on the action (optional) to avoid re-parsing in `_execute_impl`.


### Rollout plan

1. Add Pydantic dependency (single validation stack for all actions).
2. Introduce param models for `read`, `write`, `final_answer`.
3. Migrate action `_validate_param` implementations to model-based validation.
4. Keep behavior and permission checks unchanged (`PathPermissionPolicy` still gates filesystem access).
5. Add focused tests for: valid payload, missing required fields, wrong types, unknown extra keys, empty string constraints.
