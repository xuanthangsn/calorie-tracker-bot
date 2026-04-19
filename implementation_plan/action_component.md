### This file contains the detail description of how the "Action component" should be implemented


- Base class for Action object abstraction
    - class: `BaseAction` (parent class for all concrete actions)
    - core property:
        - `name`: action name (string)
        - `params`: params of the action (ActionParam)
    - execution lifecycle:
        - `before_execute()`: optional hook before action logic
        - `_execute_impl()`: concrete action logic implemented by subclass
        - `after_execute(result)`: optional hook after successful execution
    - abstract method: each concreate class must implement the following method
        - `validate_param`: validate the param object before object initilization
        - `_execute_impl`: concrete execution of each action
    - error model:
        - `ActionValidationError`: invalid action payload/params
        - `ActionError`: runtime error while executing action
    - observability:
        - `to_dict()`: serialize action state for logging/tracing
    - the initialization process, __init__ method:
        1. params of __init__: name (string), params (ActionParam)
        2. initilization process:
            - set the name
            - call `validate_param` to validate the ActionParam being passed against the concrete Action's param schema
        