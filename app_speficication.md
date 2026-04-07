## TODO:

- refine LLM output, for now, force LLM to output params for function call
- design the context injecting mechanism
- design more tools, extending agent ability
- refine project structure

## App specification:

- user-LLM-agent SESSION: when user send a message in telegram, this trigger the agent to send a API request to LLM asking what to do, after getting the response from LLM, agent perform the associated function call parsed from LLM response, then it reply to user. All of that set of operation is called a SESSION.
- Action: * action is an action that the agent need to do triggered by user's message
    this app has a set of predefined section including:
    - refuse to answer (not related to calorie tracking)
    - log meal
    - modify meal
    - set goal
    - modify goal
    - get report
    ....
    * an action may involves in only 1 session, or multiple sessions. Multiple sessions will be involved if the user's intention is unclear (the action is determined but the params for the action is unclear), in that case, multiple follow-up session is instantiated to clarify user's intention.
    + an action can be cancelled

## The tech stack:

- aiogran for communication with telegram
- Instructor -> force LLM to output structured json
- database: json
- scheduling: APScheduler

## Calory tracking bot:

### what it is: 

- CALORIES TRACKING AI AGENT
- no personality, no memory about user, just focused on its GOAL of TRACKING CALORY, hard-coded to do what it's supposed to do.
- no generate too long answer, just pure TOKEN-OPTIMIZED
- refuse to answer questions that are not related to its goal
- not stateless, can still relate to the chat history, make modification to assumption in the past. For example, if user want to correct the calories intake in the morning, which has already been logged to database, user can told the bot to modify it like this "wait, I make a mistake, actually this morning I ate 2 bananas, not 1"
or if user's provided information is too ambiguous, agent can ask follow up question to make things clear before taking any action

### what it can do:

- it know user's daily, weekly, monthly calories intake goal
- it know to log user's calories intake for each meal
- it know the calories of each food
- it can report user's calories intake in the specified time
- it can produce automatic report like weekly report, monthly report,...

