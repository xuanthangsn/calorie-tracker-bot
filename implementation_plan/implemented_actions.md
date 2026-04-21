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

## Workspace path resolution utility for `read` / `write` action

- follow the "agent workspace" or LLM sandbox envinronment proposed in `agent_system_design.md`, create a utility function that resolve the requested read/write file path from LLM to the real system file path
- treat the requested read/write file path from LLM as always relative the the `$memory_root` (a env variable defined by user) folder, therefore resolve it under `$memory_root`

- enforce the following rules:
   - normalized/canonical path resolution (`realpath` semantics),
   - no traversal/symlink escape outside `$memory_root`,
   - fail fast with `ActionError` if resolved path is outside `$memory_root`.

- Error model: create InvalidLLMRequestedPath error model, throw if the requested path violate these above rules

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
