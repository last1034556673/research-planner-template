import EventKit
import Foundation

struct StatusLog: Decodable {
    let statuses: [StatusEntry]
}

struct StatusEntry: Decodable {
    let date: String
    let title_match: String?
    let title_contains: String?
    let status: String
}

struct Args {
    let calendarTitle: String
    let statusFile: String
    let fromDate: String
    let timeZone: String
}

let isoFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd"
    return formatter
}()

func parseArgs() -> Args {
    var calendarTitle = "Research"
    var statusFile = "./workspace/data/status_log.json"
    var fromDate = ProcessInfo.processInfo.environment["PLANNER_TODAY"]
        ?? ProcessInfo.processInfo.environment["TODAY"]
        ?? isoFormatter.string(from: Date()).prefix(10).description
    var timeZone = "Asia/Shanghai"

    var index = 1
    while index < CommandLine.arguments.count {
        let arg = CommandLine.arguments[index]
        let next = index + 1 < CommandLine.arguments.count ? CommandLine.arguments[index + 1] : nil
        switch arg {
        case "--calendar":
            if let next { calendarTitle = next; index += 1 }
        case "--status-file":
            if let next { statusFile = next; index += 1 }
        case "--from-date":
            if let next { fromDate = next; index += 1 }
        case "--timezone":
            if let next { timeZone = next; index += 1 }
        default:
            break
        }
        index += 1
    }

    return Args(calendarTitle: calendarTitle, statusFile: statusFile, fromDate: fromDate, timeZone: timeZone)
}

func dayBounds(for dateString: String, tz: TimeZone) -> (Date, Date)? {
    isoFormatter.timeZone = tz
    guard let day = isoFormatter.date(from: dateString) else { return nil }
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = tz
    let start = calendar.startOfDay(for: day)
    guard let end = calendar.date(byAdding: DateComponents(day: 1, second: -1), to: start) else {
        return nil
    }
    return (start, end)
}

func matches(_ eventTitle: String, _ entry: StatusEntry) -> Bool {
    if let exact = entry.title_match, !exact.isEmpty {
        return eventTitle == exact || eventTitle.contains(exact)
    }
    if let contains = entry.title_contains, !contains.isEmpty {
        return eventTitle.contains(contains)
    }
    return false
}

let args = parseArgs()
let tz = TimeZone(identifier: args.timeZone) ?? .current

guard let fromDay = isoFormatter.date(from: args.fromDate) else {
    fputs("Invalid --from-date: \(args.fromDate)\n", stderr)
    exit(1)
}

let statusURL = URL(fileURLWithPath: args.statusFile)
let data = try Data(contentsOf: statusURL)
let log = try JSONDecoder().decode(StatusLog.self, from: data)
let movedEntries = log.statuses.filter { entry in
    guard entry.status == "moved", let day = isoFormatter.date(from: entry.date) else {
        return false
    }
    return day >= fromDay
}

if movedEntries.isEmpty {
    print("No moved entries on or after \(args.fromDate).")
    exit(0)
}

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var granted = false
store.requestFullAccessToEvents { ok, _ in
    granted = ok
    semaphore.signal()
}
semaphore.wait()

guard granted else {
    fputs("Calendar access denied.\n", stderr)
    exit(1)
}

guard let calendar = store.calendars(for: .event).first(where: { $0.title == args.calendarTitle }) else {
    fputs("Calendar not found: \(args.calendarTitle)\n", stderr)
    exit(1)
}

var deleted = 0
for entry in movedEntries {
    guard let (start, end) = dayBounds(for: entry.date, tz: tz) else { continue }
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: [calendar])
    let events = store.events(matching: predicate)
    for event in events where matches(event.title ?? "", entry) {
        try store.remove(event, span: .thisEvent)
        deleted += 1
        print("DELETE  \(entry.date)  \(event.title ?? "(untitled)")")
    }
}

print("Removed \(deleted) moved calendar event(s).")
