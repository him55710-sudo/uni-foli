# 11 Notifications And Workflow

The mascot concept only works if the backend supports a real task loop.

## Notification goals

- remind without spamming
- turn diagnosis gaps into concrete tasks
- keep long-running projects moving

## Backend objects

- `notification_tasks`
- `scheduled_jobs`
- `delivery_logs`
- `nudge_preferences`

## Suggested triggers

- upload parsed successfully
- diagnosis completed
- export ready
- draft inactive for too long
- deadline approaching

## Rules

- notifications must be tied to a real user task
- do not send generic motivational spam
- rate-limit aggressively for minors
- every notification should link to a recommended next step

## MVP channels

- in-app first
- email second
- push later
