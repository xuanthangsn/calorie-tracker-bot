# Task component — abstract implementation plan

- A **Task** is one user-originated run of the agent: from the initial user request through a **bounded** ReAct loop until a final reply to the user or terminal failure.
- A **Task** will encapsulate all the state, the interaction so far with LLM to perform the current task, and perform the ReAct loop (parsing LLM response, initializing corresponding **Action**, execute it, sending the result back to LLM, and repeat)


## Class: `Task`

**Core properties (conceptual)**

- `id` Stable identifier (trace/logging).
- `user_request`: Initial user message. 
- `final_response`: User-facing answer when the task is finished. 
- `status`: e.g. `pending` → `running` → `completed` \ `failed` \ `cancelled`. 
- `cycle_index`: Current ReAct cycle count (0 before first LLM step). 
- `max_cycle`: Hard cap aligned with design: finite loops. 
- `task_context`: 
    - Ordered exchanged message history with LLM so that LLM understand the context of current task.
    - keep the history as an array of exchaged message like this, so that this can be easily feed into `contents` param of client.models.generate_content api of google-genai
    ```code
    chat_history = [
    {"role": "user", "parts": [{"text": "Read the user.md file."}]},
    {"role": "model", "parts": [{"text": '{"action": "read", ...}'}]},
    {"role": "user", "parts": [{"text": "OBSERVATION: ..."}]}
    ]
    ```
- `actions`: list of **Action** taken so far.
- `error`: Terminal error info when `failed` (optional). 

**Behaviors (conceptual)**

| Method | Purpose |
|--------|--------|
| `execute` | executing the task, implement the ReAct loop |
| `to_dict` | snapshot for logging/tracing (id, status, cycle counts, timestamps, no huge payloads unless configured). |
| `force_stop` | forcefully stop the task |
| `basic getter` | basic getter for current task state |

**Edge case**

- force the Task to be cancelled when the cycle_index exceed the max_cycle, in such case, the status of the task will be 'failed'

**Task life cycle**

- caller initialize an instance of **Task**, with an user's initial request task = Task(user_request="What is my favourite football player?"), then the caller call task.execute() to start the task
- caller can call task.force_stop() to forcefully stop the task from executing




**Error model**

- **`TaskError`** (or reuse a small hierarchy): invalid task setup, illegal state transition, max cycles exceeded without completion — distinct from `ActionValidationError` / `ActionError` on the action side.
