# moodle-mcp

Run your university's Moodle LMS from an agent. Exposes deadlines, course
documents, grades and submissions over **MCP**, plus a standalone **CLI**.

Built and tested against NUST's LMS (`lms.nust.edu.pk`, Moodle 5.1.1), but
nothing is NUST-specific — point `MOODLE_URL` at any Moodle install.

```
$ moodle-mcp agenda
as of 2026-09-20  ·  next 30 days  ·  16 documents read

  2026-09-18 18:59  CS-101   Lab 01 Manual + Submission
     submitted/notgraded
  2026-09-22        HU-200   First Graded Activity
     found in First Graded Activity.docx (high confidence)
  2026-10-20        HU-200   Group Assignment 1
     found in Group Assignment 1.docx (high confidence)
```

## Why this exists

Moodle's calendar and assignment APIs only know about work that was entered as
a Moodle *activity*. In practice, instructors constantly just upload a Word or
PowerPoint handout instead — so the deadline exists only as a sentence inside a
file, invisible to every API and to the student's dashboard.

On the account this was built against, the official surfaces reported **zero**
calendar events and **zero** announcements. Reading the documents surfaced
three real graded deliverables the LMS itself never showed.

So `agenda` merges three sources: the assignment API, the calendar, and the
**text inside course documents**. Mined dates are labelled `in document` with a
confidence rating and the surrounding sentence as evidence — leads to confirm,
not gospel.

## Install

```bash
uv tool install moodle-mcp          # or: pipx install moodle-mcp
uvx moodle-mcp agenda               # or run without installing
```

From a checkout: `uv pip install -e ".[pdf]"`.
The `pdf` extra pulls in `pypdf`; without it, PDFs are skipped and everything
else still works.

## Authenticate

```bash
export MOODLE_URL=https://lms.your-university.edu
moodle-mcp login          # prompts, caches a token in ~/.cache/moodle-mcp
```

Or set `MOODLE_USER` / `MOODLE_PASS`, or supply `MOODLE_TOKEN` directly if you
already have one. Moodle mobile tokens are long-lived; only a password change
or admin revocation ends them.

This uses Moodle's standard `moodle_mobile_app` web service — the same API the
official Moodle phone app uses. If your site has web services disabled, the
login call will say so and nothing here will work.

## Use it from an agent

Claude Code:

```bash
claude mcp add moodle -e MOODLE_URL=https://lms.your-university.edu -- moodle-mcp serve
```

Claude Desktop / Cursor / any MCP client — add to the config file:

```json
{
  "mcpServers": {
    "moodle": {
      "command": "moodle-mcp",
      "args": ["serve"],
      "env": { "MOODLE_URL": "https://lms.your-university.edu" }
    }
  }
}
```

Authenticate once with `moodle-mcp login` first; the server picks up the cached
token, so no credentials need to live in the config file.

## Tools

| Tool | What it does |
|---|---|
| `whoami` | Confirm the connection and account |
| `list_courses` | Enrolled courses with ids |
| **`agenda`** | **Everything due, including dates mined from documents** |
| `course_contents` | Sections, activities and files for one course |
| `find_files` | Locate files by partial name |
| `read_document` | Any course file as plain text |
| `download_file` | Save a file to disk |
| `search_lms` | Search material; `deep=True` searches inside documents |
| `list_assignments` | Moodle assignments with due dates |
| `assignment_status` | Submitted? graded? which files? |
| `get_grades` | Grades so far |
| `announcements` | Recent forum announcements |
| `whats_new` | Material changed in the last N days — the polling hook |
| `call_api` | Escape hatch to any of Moodle's ~450 functions |
| `submit_assignment` | Upload files and submit for grading |

CLI equivalents: `whoami`, `courses`, `agenda`, `contents`, `assignments`,
`grades`, `news`, `read`, `search`, plus `serve` and `login`.

Text extraction covers `.docx`, `.pptx`, `.xlsx`, `.pdf`, legacy `.doc`/`.ppt`
and plain text.

## Writing is off by default

`submit_assignment` and any mutating `call_api` function are refused unless the
server runs with `MOODLE_ALLOW_WRITE=1`. Submitting additionally requires an
explicit `confirm=True`. Read-only is the default because an agent that can
silently overwrite your graded submission of record is not a good trade.

## Two things this handles that break other clients

Both were found against a real university deployment and are common in the wild.

**Incomplete TLS chains.** Many campus servers send only their leaf certificate
and omit the intermediate, so stock clients fail to verify. Rather than turning
verification off, this reads the leaf's AIA `CA Issuers` URL, downloads the
missing intermediate, caches it, and retries against a repaired trust store.
Verification stays on the whole time; if repair fails it errors out rather than
connecting insecurely. Old TLS 1.2-only servers without secure renegotiation
are also accommodated.

**Responses that aren't quite JSON.** Local plugins sometimes print HTML before
the JSON body — NUST's emits an HTML comment on *every* web-service response,
which is enough to break a standard Moodle client. Parsing starts at the first
structural character.

## Caveats

- Mined dates are a best-effort read of prose. `high` confidence means the date
  sat next to words like *due*, *submission* or *graded*; it is still worth
  opening the document. `agenda` returns the evidence so you can check.
- Ambiguous numeric dates are read day-first (`22-09-2026` → 22 September),
  which is right for most of the world and wrong for US-format courses.
- The first `agenda` run downloads and parses every course document, so it is
  slow. Files are cached in `~/.cache/moodle-mcp` afterwards.

## Licence

MIT.
