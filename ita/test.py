from database.approvals import escalate_expired_approvals

task_ids = escalate_expired_approvals(timeout_minutes=2)

print("Escalated task IDs:")
for task_id in task_ids:
    print(task_id)
