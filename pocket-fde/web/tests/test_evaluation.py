from web.evaluate_variants import incident_payload


def test_variant_payload_cannot_send_answers_or_scenarios_to_live_model():
    case = {"id": "VAR-TEST", "title": "Widget fails", "description": "Error during upgrade", "version": "v3",
            "provided_evidence": ["u.request status=error"], "ground_truth": {"owning_team": "B"},
            "scenario": {"secret_cause": "override"}, "resolution_notes": "Restore default"}
    payload = incident_payload(case)
    assert payload == {key: case[key] for key in ("id", "title", "description", "version", "provided_evidence")}
