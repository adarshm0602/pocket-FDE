"""Capture learning into the shared second brain, pending human review."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

import yaml

from .knowledge import KB


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def categorize_learning(text):
    lower = text.lower()
    if any(word in lower for word in ["issue", "bug", "fix", "root cause", "problem"]):
        return "feedback"
    if any(word in lower for word in ["team", "owner", "deadline", "initiative", "project"]):
        return "project"
    return "reference"


def index_memory(path, description, state, kb=KB):
    """Update the shared index without presenting a draft as reviewed knowledge."""
    kb = Path(kb)
    index = kb.parent / "MEMORY.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    lines = index.read_text().splitlines() if index.exists() else []
    lines = [line for line in lines if f"/{Path(path).name})" not in line]
    if state != "rejected":
        relative = Path(path).relative_to(kb.parent).as_posix()
        label = description.replace("\n", " ").replace("[", "(").replace("]", ")")
        lines.append(f"- [{label}]({relative}) — {state}")
    index.write_text("\n".join(lines).rstrip() + "\n")


def capture_learning(name, description, memory_type, content, kb=KB):
    slug = slugify(name)
    if not slug or not content.strip():
        raise ValueError("A learning needs a name and non-empty content.")
    if memory_type not in {"reference", "feedback", "project", "user"}:
        raise ValueError("Unknown learning category.")
    directory = Path(kb) / "pending"
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{slug}-{uuid.uuid4().hex[:12]}"
    path = directory / f"{stem}.md"
    meta = {"id": f"NOTE:{stem}", "name": name, "description": description,
            "review_status": "unreviewed", "captured_at": datetime.now(timezone.utc).isoformat(),
            "affected_versions": [], "metadata": {"type": memory_type}}
    with path.open("x") as handle:
        handle.write("---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n" + content.strip() + "\n")
    index_memory(path, description, "pending review", kb)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", metavar="DRAFT_NAME", help="Review a Markdown draft from second-brain/pending")
    parser.add_argument("--by", help="Human reviewer name")
    parser.add_argument("--reject", action="store_true", help="Reject the selected draft")
    parser.add_argument("--list", action="store_true", help="List pending learning drafts")
    args = parser.parse_args()
    if args.list:
        for path in sorted((KB / "pending").glob("*.md")):
            print(path.name)
        return
    if args.review:
        from .curator import approve, reject
        from .knowledge import read_markdown
        name = Path(args.review).name
        if name != args.review or not name.endswith(".md"):
            parser.error("Choose a Markdown filename from --list.")
        path = KB / "pending" / name
        if not path.is_file():
            parser.error("Pending draft not found.")
        meta, body = read_markdown(path)
        print(f"\n{meta.get('description', name)}\n\n{body}\n")
        if args.reject:
            reject(path)
            print("Rejected; excluded from search.")
            return
        by = args.by or input("Your reviewer name: ").strip()
        if not by:
            parser.error("A human reviewer name is required.")
        if input("Approve this learning for shared search? Type APPROVE: ").strip() != "APPROVE":
            print("Kept pending; excluded from search.")
            return
        dest = approve(path, by)
        print(f"Approved: {dest}. Both search modes refresh on the next request.")
        return
    learning = input("What did you learn? ").strip()
    if not learning:
        parser.error("No learning provided.")
    description = input("One-line description: ").strip() or learning[:120]
    print("Detailed content (END on a new line to finish):")
    lines = []
    while (line := input()).strip() != "END":
        lines.append(line)
    path = capture_learning(learning, description, categorize_learning(learning), "\n".join(lines).strip() or learning)
    print(f"Saved pending review: {path.name}. It is excluded from live search.")
    print(f"Review with: python -m pocketfd.learning --review {path.name} --by YOUR_NAME")


if __name__ == "__main__":
    main()
