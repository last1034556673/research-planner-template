import EventKit
import Foundation

struct EventRecord: Codable {
    let calendar: String
    let title: String
    let start: String
    let end: String
    let isAllDay: Bool
}

let tzName = ProcessInfo.processInfo.environment["TZ_NAME"] ?? "Asia/Shanghai"
let startText = ProcessInfo.processInfo.environment["START_ISO"] ?? ""
let endText = ProcessInfo.processInfo.environment["END_ISO"] ?? ""

let formatter = ISO8601DateFormatter()
formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
formatter.timeZone = TimeZone(identifier: tzName)

func parseDate(_ text: String) -> Date {
    if let date = formatter.date(from: text) {
        return date
    }
    let fallback = ISO8601DateFormatter()
    fallback.timeZone = TimeZone(identifier: tzName)
    guard let date = fallback.date(from: text) else {
        fatalError("Could not parse date: \(text)")
    }
    return date
}

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var granted = false
store.requestFullAccessToEvents { ok, _ in
    granted = ok
    semaphore.signal()
}
_ = semaphore.wait(timeout: .now() + 15)

guard granted else {
    fputs("Calendar access not granted.\n", stderr)
    exit(1)
}

let startDate = parseDate(startText)
let endDate = parseDate(endText)
let calendars = store.calendars(for: .event)
let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: calendars)
let events = store.events(matching: predicate).sorted { $0.startDate < $1.startDate }

let outputFormatter = ISO8601DateFormatter()
outputFormatter.formatOptions = [.withInternetDateTime]
outputFormatter.timeZone = TimeZone(identifier: tzName)

let payload = events.map { event in
    EventRecord(
        calendar: event.calendar.title,
        title: event.title ?? "",
        start: outputFormatter.string(from: event.startDate),
        end: outputFormatter.string(from: event.endDate),
        isAllDay: event.isAllDay
    )
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .withoutEscapingSlashes]
let data = try encoder.encode(payload)
FileHandle.standardOutput.write(data)
