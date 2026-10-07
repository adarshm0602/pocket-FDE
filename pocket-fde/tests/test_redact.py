from pocketfd.redact import Redactor, leaks, log_outbound


def test_masks_all_identifier_kinds():
    t = ("Acme Logistics, contact priya.n@acmelogistics.example, 203.0.113.0/24, +1 415 555 0132, WL-8841, "
         "sk-abc123def456ghi789, tenant t-wayne (Wayne Foods)")
    r = Redactor()
    out = r.redact(t)
    assert leaks(out) == []
    for placeholder in ("[EMAIL_1]", "[IP_1]", "[CUSTOMER_ID_1]", "[API_KEY_1]", "[CUSTOMER_1]", "[CUSTOMER_2]"):
        assert placeholder in out


def test_keeps_technical_ids_and_is_consistent():
    r = Redactor()
    out = r.redact("Acme Logistics trace tr-7f3a91 code VAL_REJECT_042 CASE-101; again acme logistics")
    assert "tr-7f3a91" in out and "VAL_REJECT_042" in out and "CASE-101" in out
    assert out.count("[CUSTOMER_1]") == 2


def test_restore_roundtrips_customer_names():
    r = Redactor()
    assert "Wayne Foods" in r.restore(r.redact("Wayne Foods is affected"))


def test_outbound_log_records_only_redacted(tmp_path):
    r = Redactor()
    p = r.redact("Globex Bank ops@globexbank.example")
    log_outbound("t", p, ["CARD-1"], r.counts, path=tmp_path / "o.jsonl")
    body = (tmp_path / "o.jsonl").read_text()
    assert "globexbank" not in body.lower() and "Globex" not in body
