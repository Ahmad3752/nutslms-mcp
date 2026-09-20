"""Command-line interface — the same operations without an agent attached."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from .client import Moodle, MoodleError
from . import lms


def _print(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        return
    if isinstance(data, dict) and "items" in data:
        print(f"as of {data['as_of']}  ·  next {data['window_days']} days  ·  "
              f"{data['documents_scanned']} documents read\n")
        if not data["items"]:
            print("  nothing found")
        for i in data["items"]:
            flag = "  OVERDUE" if i.get("overdue") else ""
            print(f"  {i['date'][:16]:<18}{i['course'][:16]:<18}{i['title'][:40]}{flag}")
            detail = []
            if i.get("status"):
                detail.append(f"{i['status']}/{i.get('grading')}")
            if i["kind"] == "in document":
                detail.append(f"found in {i['source']} ({i['confidence']} confidence)")
            if detail:
                print(f"     {' · '.join(detail)}")
        print(f"\n{data['note']}")
        return
    if isinstance(data, list) and data and isinstance(data[0], dict):
        cols = list(data[0].keys())[:5]
        for row in data:
            print("  " + "  ".join(f"{str(row.get(c, ''))[:34]:<34}" for c in cols))
        return
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="moodle-mcp",
        description="Talk to a Moodle LMS from the terminal, or serve it over MCP.")
    ap.add_argument("--url", help="Moodle base URL (or set MOODLE_URL)")
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="run the MCP server on stdio")
    sub.add_parser("login", help="authenticate and cache a token")
    sub.add_parser("whoami", help="show the logged-in account")
    sub.add_parser("courses", help="list enrolled courses")

    p = sub.add_parser("agenda", help="everything due, including dates hidden in documents")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--shallow", action="store_true", help="skip reading documents")

    p = sub.add_parser("contents", help="outline one course")
    p.add_argument("courseid", type=int)

    sub.add_parser("assignments", help="list Moodle assignments")
    sub.add_parser("grades", help="show grades")
    p = sub.add_parser("news", help="what changed recently")
    p.add_argument("--days", type=int, default=7)

    p = sub.add_parser("read", help="read a course document as text")
    p.add_argument("name", help="partial file or activity name")

    p = sub.add_parser("search", help="search course material")
    p.add_argument("query")
    p.add_argument("--deep", action="store_true", help="search inside documents")

    args = ap.parse_args(argv)

    if args.cmd == "serve":
        from .server import main as serve
        serve()
        return 0

    m = Moodle(url=args.url)

    try:
        if args.cmd == "login":
            user = os.environ.get("MOODLE_USER") or input("username: ")
            pw = os.environ.get("MOODLE_PASS") or getpass.getpass("password: ")
            m.login(user, pw)
            print(f"Logged in as {m.siteinfo['fullname']}. Token cached.")
            return 0

        m.ensure_auth()
        if args.cmd == "whoami":
            _print(lms.whoami(m), args.json)
        elif args.cmd == "courses":
            _print(lms.courses(m), args.json)
        elif args.cmd == "agenda":
            _print(lms.agenda(m, days=args.days, deep=not args.shallow), args.json)
        elif args.cmd == "contents":
            _print(lms.contents(m, args.courseid), args.json)
        elif args.cmd == "assignments":
            _print(lms.assignments(m), args.json)
        elif args.cmd == "grades":
            _print(lms.grades(m), args.json)
        elif args.cmd == "news":
            _print(lms.whats_new(m, days=args.days), args.json)
        elif args.cmd == "search":
            _print(lms.search(m, args.query, deep=args.deep), args.json)
        elif args.cmd == "read":
            hits = lms.find_file(m, name=args.name)
            if not hits:
                print(f"No file matching {args.name!r}")
                return 1
            h = hits[0]
            print(f"--- {h['activity']} :: {h['filename']} ---\n")
            print(lms.read_file(m, h["fileurl"], h["filename"])["text"])
    except MoodleError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
