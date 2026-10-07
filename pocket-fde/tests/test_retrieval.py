from pocketfd.knowledge import Item
from pocketfd.retrieval import Index


def _items():
    return [
        Item("CARD-A", "card", "symptom one-way widget empty answer rewrite mode history_aware session", versions=["v2"]),
        Item("CARD-B", "card", "symptom one-way widget empty answer rewrite mode history_aware session", versions=["v3"]),
        Item("CARD-C", "card", "rate limit per tenant rpm 429", versions=["v2", "v3"]),
        Item("DRAFT-D", "card", "one-way widget empty answer rewrite session", versions=["v2"], status="unreviewed"),
    ]


def test_version_match_ranks_first_and_mismatch_is_caveated():
    hits = Index(_items()).search("one-way widget empty answer rewrite session", "v2", k=4)
    ids = [h.item.id for h in hits]
    assert ids.index("CARD-A") < ids.index("CARD-B")
    b = next(h for h in hits if h.item.id == "CARD-B")
    assert not b.version_match and "NOT v2" in b.caveat


def test_unreviewed_flagged_and_excludable():
    ix = Index(_items())
    d = next(h for h in ix.search("one-way widget empty answer", "v2", k=4) if h.item.id == "DRAFT-D")
    assert "UNREVIEWED" in d.caveat
    assert all(h.item.id != "DRAFT-D" for h in ix.search("one-way widget empty answer", "v2", k=4, include_pending=False))


def test_dotted_flag_names_match_keyword():
    ix = Index([Item("F1", "flag", "flag tune.rewrite.mode owner B"), Item("F2", "flag", "flag llm.timeout_ms owner Q")])
    assert ix.search("tune.rewrite.mode", "v2", k=1)[0].item.id == "F1"


def test_upgrade_keeps_relevant_past_card_but_cannot_establish_applicability():
    items = [Item("PAST", "card", "widget empty query session rewrite", versions=["v2"])]
    items += [Item(f"CURRENT-{n}", "card", "widget query", versions=["v3"]) for n in range(8)]
    ix = Index(items)
    ordinary = ix.search("widget empty query session rewrite", "v3", k=3)
    assert "PAST" not in {h.item.id for h in ordinary}
    upgraded = ix.search("widget empty query session rewrite after upgrade", "v3", k=3)
    past = next(h for h in upgraded if h.item.id == "PAST")
    assert len(upgraded) == 3 and not past.version_match
    assert "historical upgrade context" in past.caveat and "old fix" in past.caveat


def test_upgrade_does_not_promote_future_irrelevant_or_unreviewed_cards():
    items = [Item("CURRENT", "card", "widget empty query session rewrite", versions=["v2"]),
             Item("FUTURE", "card", "widget empty query session rewrite", versions=["v3"]),
             Item("PAST-DRAFT", "card", "widget empty query session rewrite", versions=["v1"], status="unreviewed"),
             Item("UNRELATED", "card", "adapter weights tuning", versions=["v1"])]
    hits = Index(items).search("widget empty query session rewrite after upgrade", "v2", k=2, include_pending=False)
    assert hits[0].item.id == "CURRENT"
    future = next(h for h in hits if h.item.id == "FUTURE")
    assert "historical upgrade context" not in future.caveat
    assert "PAST-DRAFT" not in {h.item.id for h in hits}
    assert "UNRELATED" not in {h.item.id for h in hits}


def test_negated_transition_does_not_expand_version_scope():
    from pocketfd.retrieval import mentions_transition
    assert not mentions_transition("No upgrade was performed; widget empty")
    assert not mentions_transition("Without a migration, widget failed")
    assert mentions_transition("No upgrade was performed last week; migrated yesterday")


def test_upgrade_context_policy_also_applies_to_embedding_rankings():
    ix = Index([Item("PAST", "card", "old mechanism", versions=["v2"]),
                Item("CURRENT", "card", "new mechanism", versions=["v3"])])
    class DenseArm:
        def scores(self, query):
            assert isinstance(query, str)
            return [.9, .4]
    ix.sem, ix.sem_name = DenseArm(), "minilm"
    hits = ix.search("failures after migration", "v3", k=2)
    assert hits[0].item.id == "PAST" and not hits[0].version_match
    assert "historical upgrade context" in hits[0].caveat


def test_upgrade_retains_competing_history_and_current_flag_definitions_within_budget():
    items = [Item("PAST-A", "card", "widget empty query", versions=["v2"], meta={"config_involved": ["tune.rewrite.mode"]}),
             Item("PAST-B", "card", "widget empty query", versions=["v2"]),
             Item("FLAG:tune.rewrite.mode", "flag", "configuration default history_aware single_shot", versions=["v2", "v3"])]
    items += [Item(f"CURRENT-{n}", "card", "widget query", versions=["v3"]) for n in range(8)]
    hits = Index(items).search("widget empty query after upgrade", "v3", k=8)
    assert len(hits) == 8
    assert {"PAST-A", "PAST-B", "FLAG:tune.rewrite.mode"} <= {h.item.id for h in hits}
    assert all(not h.version_match and "historical" in h.caveat for h in hits if h.item.id.startswith("PAST"))


def test_strong_keyword_history_survives_broad_dense_similarity():
    ix = Index([Item("PAST", "card", "migration mechanism", versions=["v2"])] +
               [Item(f"CURRENT-{n}", "card", "broad current issue", versions=["v3"]) for n in range(4)])
    class KeywordArm:
        def scores(self, query):
            return [1, .9, .8, .7, .6]
    class DenseArm:
        def scores(self, query):
            return [.001, 1, .9, .8, .7]
    ix.bm25, ix.sem, ix.sem_name = KeywordArm(), DenseArm(), "minilm"
    assert "PAST" not in {h.item.id for h in ix.search("ordinary symptom", "v3", k=2)}
    upgraded = ix.search("symptom after migration", "v3", k=2)
    assert len(upgraded) == 2 and "PAST" in {h.item.id for h in upgraded}
