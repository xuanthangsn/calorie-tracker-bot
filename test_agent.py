from agent.task import Task


# task = Task("for lunch today, I have ate 200gr of grilled chicken breast, 100gr of rice, and 100gr of cabbage")
task = Task("it would be great if I can buy a new phone this year")
result = task.execute()
print(result)