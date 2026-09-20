#!/usr/bin/env python3
"""Extract Kita/school event dates from PDFs, images, or text files into an .ics calendar."""

import argparse
import base64
import mimetypes
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from icalendar import Calendar, Event

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-5"

SUPPORTED_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

EXTRACT_TOOL = {
    "name": "extract_events",
    "description": "Record every distinct calendar-worthy event found in the provided document(s).",
    "input_schema": {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short event name."},
                        "date": {"type": "string", "description": "Start date, ISO format YYYY-MM-DD."},
                        "end_date": {
                            "type": "string",
                            "description": "End date, ISO format YYYY-MM-DD, only if the event spans multiple days.",
                        },
                        "all_day": {"type": "boolean", "description": "True if no specific time is given."},
                        "start_time": {"type": "string", "description": "24h HH:MM, only if all_day is false."},
                        "end_time": {"type": "string", "description": "24h HH:MM, optional."},
                        "location": {"type": "string"},
                        "description": {"type": "string", "description": "Any extra relevant detail."},
                    },
                    "required": ["title", "date", "all_day"],
                },
            }
        },
        "required": ["events"],
    },
}

EXTRACT_INSTRUCTIONS = (
    "The attached document(s) are from a Kita/school and list dates parents should remember "
    "(closures, excursions, parent evenings, holidays, deadlines, etc). Extract every distinct "
    "event using the extract_events tool. Use the current/stated school year to resolve dates "
    "that are given without a year. Skip generic text that is not a specific dated event."
)


def build_content_block(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext == ".pdf":
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
    if ext in SUPPORTED_IMAGE_TYPES:
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": SUPPORTED_IMAGE_TYPES[ext], "data": data},
        }
    if ext == ".txt":
        return {"type": "text", "text": path.read_text(encoding="utf-8", errors="replace")}
    raise ValueError(
        f"Unsupported file type '{ext}' for {path}. Supported: .pdf, .txt, "
        + ", ".join(SUPPORTED_IMAGE_TYPES)
    )


def extract_events(paths: list[Path], model: str) -> list[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set. Run: export ANTHROPIC_API_KEY=sk-ant-...")

    content = [build_content_block(p) for p in paths]
    content.append({"type": "text", "text": EXTRACT_INSTRUCTIONS})

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_events"},
        messages=[{"role": "user", "content": content}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_events":
            return block.input.get("events", [])
    return []


def format_event_line(index: int, e: dict) -> str:
    date_part = e["date"]
    if e.get("end_date"):
        date_part += f" – {e['end_date']}"
    time_part = ""
    if not e.get("all_day", True):
        time_part = f" {e.get('start_time', '?')}"
        if e.get("end_time"):
            time_part += f"-{e['end_time']}"
    loc = f"  @ {e['location']}" if e.get("location") else ""
    return f"[{index}] {date_part}{time_part}  {e['title']}{loc}"


def print_events(events: list[dict]) -> None:
    if not events:
        print("(no events remaining)")
        return
    for i, e in enumerate(events, 1):
        print(format_event_line(i, e))
        if e.get("description"):
            print(f"      {e['description']}")


def edit_event(e: dict) -> None:
    fields = ["title", "date", "end_date", "all_day", "start_time", "end_time", "location", "description"]
    print("Leave blank to keep current value.")
    for field in fields:
        current = e.get(field, "")
        raw = input(f"  {field} [{current}]: ").strip()
        if raw == "":
            continue
        if field == "all_day":
            e[field] = raw.lower() in ("y", "yes", "true", "1")
        else:
            e[field] = raw


def review_events(events: list[dict]) -> list[dict]:
    events = list(events)
    while True:
        print()
        print_events(events)
        print("\nCommands: [Enter]/a = accept & save, d <n> = drop event n, e <n> = edit event n, q = quit without saving")
        cmd = input("> ").strip()
        if cmd in ("", "a"):
            return events
        if cmd == "q":
            sys.exit("Aborted, nothing saved.")
        parts = cmd.split(maxsplit=1)
        if len(parts) == 2 and parts[0] in ("d", "e") and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if not (0 <= idx < len(events)):
                print("No such event number.")
                continue
            if parts[0] == "d":
                removed = events.pop(idx)
                print(f"Dropped: {removed['title']}")
            else:
                edit_event(events[idx])
        else:
            print("Unrecognized command.")


def parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def build_calendar(events: list[dict]) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//kita2ics//")
    cal.add("version", "2.0")

    for e in events:
        ev = Event()
        ev.add("uid", str(uuid.uuid4()))
        ev.add("summary", e["title"])
        ev.add("dtstamp", datetime.now())
        if e.get("description"):
            ev.add("description", e["description"])
        if e.get("location"):
            ev.add("location", e["location"])

        start_date = date.fromisoformat(e["date"])
        if e.get("all_day", True):
            end_date = date.fromisoformat(e["end_date"]) if e.get("end_date") else start_date
            ev.add("dtstart", start_date)
            ev.add("dtend", end_date + timedelta(days=1))
        else:
            start_dt = datetime.combine(start_date, parse_hhmm(e["start_time"]))
            if e.get("end_time"):
                end_date = date.fromisoformat(e["end_date"]) if e.get("end_date") else start_date
                end_dt = datetime.combine(end_date, parse_hhmm(e["end_time"]))
            else:
                end_dt = start_dt + timedelta(hours=1)
            ev.add("dtstart", start_dt)
            ev.add("dtend", end_dt)

        cal.add_component(ev)

    return cal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="PDF, image, or .txt file(s) to extract events from")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .ics path (default: output/<input filename>.ics)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model id to use for extraction")
    args = parser.parse_args()

    for f in args.files:
        if not f.exists():
            sys.exit(f"File not found: {f}")

    if args.output is None:
        args.output = Path("output") / (args.files[0].stem + ".ics")

    print(f"Extracting events from {len(args.files)} file(s) using {args.model}...")
    events = extract_events(args.files, args.model)

    if not events:
        sys.exit("No events were extracted. Nothing written.")

    print(f"Found {len(events)} event(s).")
    confirmed = review_events(events)

    if not confirmed:
        sys.exit("No events left after review. Nothing written.")

    cal = build_calendar(confirmed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(cal.to_ical())
    print(f"Wrote {len(confirmed)} event(s) to {args.output}")


if __name__ == "__main__":
    main()
