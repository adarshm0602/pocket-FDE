import io
from pathlib import Path
import subprocess
import sys

import pytest

from pocketfd.curator import approve, reject, review
from pocketfd.knowledge import load_all, read_markdown, write_markdown
from pocketfd.learning import capture_learning
from pocketfd.retrieval import Index


def test_capture_is_shared_pending_and_does_not_overwrite(tmp_path):
    kb = tmp_path / "second-brain"
    first = capture_learning("File mismatch", "A colon: and quotes 'remain valid'", "feedback", "Compare deployed files.", kb=kb)
    second = capture_learning("File mismatch", "Second observation", "feedback", "Verify the skipped file.", kb=kb)
    assert first != second and first.exists() and second.exists()
    assert first.parent == kb / "pending"
    assert read_markdown(first)[0]["description"] == "A colon: and quotes 'remain valid'"
    assert len([i for i in load_all(include_pending=False, kb=kb) if i.kind == "note"]) == 0
    assert len([i for i in load_all(include_pending=True, kb=kb) if i.kind == "note"]) == 2
    assert "pending review" in (tmp_path / "MEMORY.md").read_text()


def test_human_approval_preserves_identity_and_enables_search(tmp_path):
    kb = tmp_path / "second-brain"
    draft = capture_learning("Deployment parity", "Compare instance files", "feedback", "A missing upgrade file causes deployment divergence.", kb=kb)
    source_id = read_markdown(draft)[0]["id"]
    with pytest.raises(ValueError):
        approve(draft, "", kb=kb)
    approved = approve(draft, "human-reviewer", kb=kb)
    assert not draft.exists() and approved.parent == kb / "notes"
    meta, _ = read_markdown(approved)
    assert meta["approved_by"] == "human-reviewer" and meta["review_status"] == "approved"
    assert meta["id"] == source_id
    items = load_all(include_pending=False, kb=kb)
    hit = Index(items).search("missing upgrade file deployment divergence", "v2", k=1)[0]
    assert hit.item.id == source_id and "unconfirmed" in hit.caveat
    assert "pending/" not in (tmp_path / "MEMORY.md").read_text()
    assert "notes/" in (tmp_path / "MEMORY.md").read_text()


def test_rejection_and_auto_approval_cannot_publish_learning(tmp_path):
    kb = tmp_path / "second-brain"
    draft = capture_learning("Unverified hypothesis", "Needs proof", "feedback", "An unconfirmed cause.", kb=kb)
    output = io.StringIO()
    assert review("automation", kb=kb, auto=True, stream=output) == 0
    assert draft.exists() and "requires interactive review" in output.getvalue()
    reject(draft, kb=kb)
    assert not draft.exists()
    assert not any(i.kind == "note" for i in load_all(include_pending=True, kb=kb))
    assert draft.name not in (tmp_path / "MEMORY.md").read_text()


def test_unreviewed_metadata_is_respected_even_outside_pending(tmp_path):
    kb = tmp_path / "second-brain"
    notes = kb / "notes"
    notes.mkdir(parents=True)
    write_markdown(notes / "draft.md", {"review_status": "unreviewed", "description": "Not approved"}, "Unverified claim")
    assert not any(i.kind == "note" for i in load_all(include_pending=False, kb=kb))


def test_capture_entry_point_is_portable_from_other_directory(tmp_path):
    script = Path(__file__).resolve().parents[2] / ".claude/skills/capture-learning/capture.py"
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and "--review" in result.stdout
