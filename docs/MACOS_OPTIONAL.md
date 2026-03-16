# Optional macOS Integration

The core planner works without any calendar integration. If you want to read or clean Apple Calendar events on macOS, use the files under [`integrations/macos/`](../integrations/macos/).

## What is optional

- Event export via EventKit
- cleanup of moved calendar events
- AppleScript launchers

## Enable macOS event export

Edit your workspace config:

```yaml
# workspace/config/integrations.yaml
calendar_provider: "macos"
primary_calendar_name: "Research"
auto_open_outputs: false
event_source_file: "data/calendar_events.json"
```

The CLI will then use:

- [`export_events.swift`](../integrations/macos/export_events.swift)

## Permissions

Grant Calendar access to the terminal app or host app you use to run the CLI.

Without permissions, the planner still works in file-only mode. It should degrade gracefully rather than fail hard.

## Cleanup helper

The optional cleanup script removes future calendar events that are already marked as `moved` in the status log:

- [`cleanup_future_moved_calendar.swift`](../integrations/macos/cleanup_future_moved_calendar.swift)

## Launchers

- [`dashboard_launcher.applescript`](../integrations/macos/dashboard_launcher.applescript)
- [`issue_logger.applescript`](../integrations/macos/issue_logger.applescript)

These are optional examples, not required for normal usage.
