- **Task:**
    - a task requested by user
    - a finite number of react cycles until the agent completes the task and responds to the user

- **ReAct loop:**
    1. *Task trigger*: user requests a task, the request is sent to LLM
    2. *LLM reasoning*: LLM receives the request, produces THOUGHT + ACTION TO TAKE
    3. *Execute action*: agent motor receives THOUGHT + ACTION TO TAKE from LLM, executing the action, get the output from action executing
    4. *Send action executing result + context to LLM*: agent motor sends output from previous action executing + context about current reAct loop to LLM
    5. *Repeat cycle*: go back to 2, until LLM decides it has completed the task
    6. *Task accomplished*: agent motor receives LLM response that indicates it has completed the task, response to user
    
- **ReAct cycle:** step 2 + 3 + 4 + 5 inside reAct loop

- **Tool call/action call**
    1. write to file
    2. ask user for further clarification
    ...

- **Abstraction of tool/action object**
    - class: `BaseAction` (parent class for all concrete actions)
    - core property:
        - `name`: action name (string)
        - `params`: params of the action (object/json map)
    - execution lifecycle:
        - `validate()`: validate params and preconditions before execution
        - `before_execute()`: optional hook before action logic
        - `_execute_impl()`: concrete action logic implemented by subclass
        - `after_execute(result)`: optional hook after successful execution
    - abstract method:
        - `validate`
        - `_execute_impl`
    - error model:
        - `ActionValidationError`: invalid action payload/params
        - `ActionError`: runtime error while executing action
    - observability:
        - `to_dict()`: serialize action state for logging/tracing
        - keep last result and last error for debugging/retries
    - helper:
        - `from_llm_action_json(payload)`: parse LLM `action` json into action object (fallback when concrete mapping is not available yet)

- **LLM response in step 2**:
    - LLM response is a strictly structured json includes 2 main fields:
        - thought: the thought it produce in reponse to previous client message
        - action: a json object represent the action to take
    
    - 




