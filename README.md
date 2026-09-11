# pdf2ics

Turn Kita/school newsletters, closure schedules, and event flyers into a calendar file you can actually import.

Point it at a PDF, image, or text file — Claude reads it, pulls out every dated event (closures, excursions, parent evenings, deadlines, holidays...), and lets you review and tweak the list before writing a standard `.ics` file you can import into Google Calendar, Apple Calendar, Outlook, etc.

## Features

- Reads **PDF**, **images** (`.jpg`, `.png`, `.gif`, `.webp`), and **plain text** files
- Understands dates given without a year by inferring the school year from context
- Distinguishes all-day events (closures, holidays) from timed events (parent evenings)
- Handles multi-day ranges (e.g. school holidays)
- Interactive review step — accept, edit, or drop any event before anything is saved
- Outputs a clean, standard `.ics` file

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/Kaufmanntra/pdf2ics.git
cd pdf2ics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Add your Anthropic API key**

Get a key from [console.anthropic.com](https://console.anthropic.com) (Settings → API Keys), then:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your real key:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

The key is loaded automatically from `.env` — no need to `export` it manually.

## Usage

> Make sure your virtual environment is active first (`source .venv/bin/activate`), otherwise you'll get `ModuleNotFoundError: No module named 'anthropic'`. If a path contains spaces, wrap it in quotes.

```bash
python3 kita2ics.py "path/to/schedule.pdf"
```

This extracts events and walks you through reviewing them, then writes the result to `output/events.ics` by default.

**Multiple files at once:**

```bash
python3 kita2ics.py flyer1.pdf flyer2.jpg notes.txt
```

**Custom output path:**

```bash
python3 kita2ics.py schedule.pdf -o calendars/2027.ics
```

**Different model:**

```bash
python3 kita2ics.py schedule.pdf --model claude-sonnet-5
```

### Reviewing extracted events

After extraction, you'll see a numbered list of events and a prompt:

```
Commands: [Enter]/a = accept & save, d <n> = drop event n, e <n> = edit event n, q = quit without saving
```

- **Enter** or `a` — accept everything and save the `.ics` file
- `d 3` — drop event #3
- `e 3` — edit event #3 field by field (leave a field blank to keep it unchanged)
- `q` — quit without saving anything

## Importing the result

Most calendar apps accept `.ics` files directly:

- **Google Calendar**: Settings → Import & export → Import
- **Apple Calendar**: File → Import
- **Outlook**: File → Open & Export → Import/Export

## Notes

- Requires an [Anthropic API key](https://console.anthropic.com) with available credits.
- `.env` is git-ignored — never commit your API key.
