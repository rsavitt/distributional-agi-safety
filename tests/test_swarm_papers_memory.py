"""Tests for swarm.research.swarm_papers.memory module."""

import json
from pathlib import Path

from swarm.research.swarm_papers.memory import (
    BasicAudit,
    MemoryArtifact,
    MemoryStore,
    RetrievalPolicy,
    WritePolicy,
    new_artifact_id,
    relevance_score,
    summarize_artifacts,
)

# ── relevance_score ────────────────────────────────────────────────


def test_relevance_score_exact_match():
    assert relevance_score("hello world", "hello world") == 1.0


def test_relevance_score_partial_overlap():
    score = relevance_score("hello world", "hello there friend")
    assert 0 < score < 1


def test_relevance_score_no_overlap():
    assert relevance_score("hello world", "foo bar baz") == 0.0


def test_relevance_score_empty_query():
    assert relevance_score("", "hello world") == 0.0


def test_relevance_score_empty_text():
    assert relevance_score("hello", "") == 0.0


# ── MemoryArtifact ─────────────────────────────────────────────────


def test_artifact_to_dict():
    art = MemoryArtifact(
        artifact_id="a1",
        title="Test",
        summary="A test artifact",
        use_when="testing",
        failure_modes=["fail1"],
        metrics={"acc": 0.9},
    )
    d = art.to_dict()
    assert d["artifact_id"] == "a1"
    assert d["title"] == "Test"
    assert d["failure_modes"] == ["fail1"]
    assert d["metrics"] == {"acc": 0.9}


def test_artifact_from_dict():
    d = {
        "artifact_id": "b2",
        "title": "From Dict",
        "summary": "reconstructed",
        "use_when": "always",
        "failure_modes": ["x"],
        "metrics": {"f1": 0.8},
        "source": "agentrxiv",
        "source_id": "paper-123",
    }
    art = MemoryArtifact.from_dict(d)
    assert art.artifact_id == "b2"
    assert art.source == "agentrxiv"
    assert art.source_id == "paper-123"


def test_artifact_from_dict_defaults():
    art = MemoryArtifact.from_dict({})
    assert art.artifact_id == ""
    assert art.title == ""
    assert art.source == "local"
    assert art.failure_modes == []


def test_artifact_roundtrip():
    art = MemoryArtifact(
        artifact_id="c3",
        title="Round",
        summary="trip",
        use_when="now",
    )
    reconstructed = MemoryArtifact.from_dict(art.to_dict())
    assert reconstructed.artifact_id == art.artifact_id
    assert reconstructed.title == art.title
    assert reconstructed.summary == art.summary


# ── MemoryStore ────────────────────────────────────────────────────


def test_memory_store_load_empty(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    assert store.load() == []


def test_memory_store_append_and_load(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    art = MemoryArtifact(
        artifact_id="s1",
        title="Stored",
        summary="in file",
        use_when="test",
    )
    store.append(art)
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].artifact_id == "s1"


def test_memory_store_append_multiple(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    for i in range(3):
        store.append(MemoryArtifact(
            artifact_id=f"m{i}",
            title=f"Art {i}",
            summary=f"summary {i}",
            use_when="always",
        ))
    assert len(store.load()) == 3


def test_memory_store_ignores_bad_json(tmp_path: Path):
    path = tmp_path / "mem.jsonl"
    path.write_text('{"artifact_id":"ok","title":"t","summary":"s","use_when":"u"}\nnot json\n')
    store = MemoryStore(path)
    loaded = store.load()
    assert len(loaded) == 1


def test_memory_store_ignores_blank_lines(tmp_path: Path):
    path = tmp_path / "mem.jsonl"
    art = MemoryArtifact(artifact_id="x", title="t", summary="s", use_when="u")
    path.write_text(json.dumps(art.to_dict()) + "\n\n\n")
    store = MemoryStore(path)
    assert len(store.load()) == 1


def test_memory_store_search(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.append(MemoryArtifact(
        artifact_id="r1",
        title="sigmoid calibration",
        summary="calibrate sigmoid parameters",
        use_when="proxy tuning",
    ))
    store.append(MemoryArtifact(
        artifact_id="r2",
        title="payoff formula",
        summary="soft payoff computation",
        use_when="payoff engine",
    ))
    results = store.search("sigmoid calibration")
    assert len(results) >= 1
    assert results[0].artifact_id == "r1"


def test_memory_store_search_respects_max_items(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    for i in range(10):
        store.append(MemoryArtifact(
            artifact_id=f"a{i}",
            title=f"topic alpha beta {i}",
            summary="alpha beta gamma",
            use_when="alpha beta",
        ))
    policy = RetrievalPolicy(max_items=2, min_score=0.0)
    results = store.search("alpha beta", policy=policy)
    assert len(results) <= 2


def test_memory_store_search_respects_min_score(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.append(MemoryArtifact(
        artifact_id="lo",
        title="xyz",
        summary="abc",
        use_when="def",
    ))
    policy = RetrievalPolicy(min_score=0.99)
    results = store.search("completely different query", policy=policy)
    assert len(results) == 0


def test_memory_store_search_respects_source_filter(tmp_path: Path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.append(MemoryArtifact(
        artifact_id="ext",
        title="external topic search",
        summary="from external source",
        use_when="always",
        source="external",
    ))
    policy = RetrievalPolicy(allow_sources={"local"}, min_score=0.0)
    results = store.search("external topic search", policy=policy)
    assert len(results) == 0


# ── BasicAudit ─────────────────────────────────────────────────────


def test_audit_passes():
    audit = BasicAudit()
    art = MemoryArtifact(
        artifact_id="a1", title="Good", summary="Valid", use_when="always"
    )
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=0.05,
        n_tasks=100,
        critic_flag_rate=0.1,
        adversary_rate=0.01,
        policy=WritePolicy(),
    )
    assert report.passed
    assert report.reasons == []


def test_audit_fails_missing_title():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="", summary="s", use_when="u")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=0.05,
        n_tasks=100,
        critic_flag_rate=0.1,
        adversary_rate=0.01,
        policy=WritePolicy(),
    )
    assert not report.passed
    assert any("title or summary" in r for r in report.reasons)


def test_audit_fails_low_accuracy():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="T", summary="S", use_when="U")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.3,
        delta_vs_baseline=0.05,
        n_tasks=100,
        critic_flag_rate=0.1,
        adversary_rate=0.01,
        policy=WritePolicy(),
    )
    assert not report.passed
    assert any("accuracy" in r for r in report.reasons)


def test_audit_fails_insufficient_tasks():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="T", summary="S", use_when="U")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=0.05,
        n_tasks=10,
        critic_flag_rate=0.1,
        adversary_rate=0.01,
        policy=WritePolicy(),
    )
    assert not report.passed
    assert any("insufficient" in r for r in report.reasons)


def test_audit_fails_low_delta():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="T", summary="S", use_when="U")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=-0.1,
        n_tasks=100,
        critic_flag_rate=0.1,
        adversary_rate=0.01,
        policy=WritePolicy(),
    )
    assert not report.passed
    assert any("delta" in r for r in report.reasons)


def test_audit_fails_no_critic():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="T", summary="S", use_when="U")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=0.05,
        n_tasks=100,
        critic_flag_rate=None,
        adversary_rate=0.01,
        policy=WritePolicy(require_critic=True),
    )
    assert not report.passed
    assert any("critic gating" in r for r in report.reasons)


def test_audit_fails_high_critic_flag_rate():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="T", summary="S", use_when="U")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=0.05,
        n_tasks=100,
        critic_flag_rate=0.9,
        adversary_rate=0.01,
        policy=WritePolicy(),
    )
    assert not report.passed
    assert any("critic flag rate" in r for r in report.reasons)


def test_audit_fails_high_adversary_rate():
    audit = BasicAudit()
    art = MemoryArtifact(artifact_id="a1", title="T", summary="S", use_when="U")
    report = audit.evaluate(
        artifact=art,
        accuracy=0.8,
        delta_vs_baseline=0.05,
        n_tasks=100,
        critic_flag_rate=0.1,
        adversary_rate=0.5,
        policy=WritePolicy(),
    )
    assert not report.passed
    assert any("adversary" in r for r in report.reasons)


# ── Helpers ────────────────────────────────────────────────────────


def test_new_artifact_id():
    aid = new_artifact_id()
    assert len(aid) == 12
    assert aid != new_artifact_id()


def test_summarize_artifacts():
    arts = [
        MemoryArtifact(artifact_id="1", title="A", summary="B", use_when="C"),
        MemoryArtifact(artifact_id="2", title="X", summary="Y", use_when="Z"),
    ]
    result = summarize_artifacts(arts)
    assert "A: B" in result
    assert "X: Y" in result
    assert result.count("\n") == 1


def test_summarize_artifacts_empty():
    assert summarize_artifacts([]) == ""
