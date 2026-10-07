"""Verify restored editor entry points without paid calls or review writes."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def module(path):
    spec = importlib.util.spec_from_file_location("restored_" + str(abs(hash(str(path)))), path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_case_helpers_work_from_an_unrelated_directory_without_ground_truth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for directory in (ROOT / ".claude/skills", ROOT / "pocket-fde/.claude/skills"):
        helper = module(directory / "analyze-case/analyze.py")
        case, error = helper.load_case("CASE-101")
        assert error is None and case["id"] == "CASE-101"
        assert "ground_truth" not in case
        assert helper.load_case("../../private-file")[0] is None


def test_case_demo_identifies_its_heuristics_and_reports_no_model_tokens():
    helper = module(ROOT / ".claude/skills/analyze-case/analyze.py")
    case, error = helper.load_case("CASE-001")
    assert error is None
    out = helper.analyze_case(case)
    assert out["prototype"] is True and out["cost"]["tokens_used"] == 0
    assert "not measured accuracy" in out["measurement_note"]


def test_distributed_sources_resolve_locally_and_exclude_pending_and_hidden_answers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for directory in (ROOT / ".claude/skills", ROOT / "pocket-fde/.claude/skills"):
        helper = module(directory / "analyze-case-distributed/orchestrator.py")
        orch = helper.Orchestrator(directory / "analyze-case-distributed")
        out = orch.orchestrate("CASE-101")
        case = out["sources"]["cases"]
        assert case["status"] == "success" and "ground_truth" not in case["data"]
        brain = out["sources"]["second_brain"]
        assert brain["status"] == "success" and brain["count"] >= 14
        assert all(i["status"] == "approved" for i in brain["data"])
        assert out["sources"]["documentation"]["count"] > 0
        assert out["sources"]["code"]["file_count"] > 0


def test_generic_analyzer_cannot_present_templates_as_verified_analysis():
    helper = module(ROOT / ".claude/skills/analyze/analyzer.py")
    answer = helper.Analyzer().analyze("Who owns retrieval?")
    assert answer["prototype"] is True
    assert "not verified diagnoses" in answer["measurement_note"]
