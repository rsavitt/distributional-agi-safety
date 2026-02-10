"""AgentRxiv integration helpers for SWARM paper runs."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from swarm.research.agents import PeerReview
from swarm.research.platforms import AgentRxivClient, Paper, SubmissionResult
from swarm.research.swarm_papers.memory import (
    MemoryArtifact,
    new_artifact_id,
    relevance_score,
)
from swarm.research.swarm_papers.review_store import ReviewStore

logger = logging.getLogger(__name__)


@dataclass
class AgentRxivHit:
    paper: Paper
    score: float


class AgentRxivBridge:
    """Lightweight bridge for AgentRxiv retrieval + submission."""

    def __init__(
        self,
        base_url: str | None = None,
        review_path: str | Path | None = None,
    ):
        self.client = AgentRxivClient(base_url=base_url)
        self._review_store: ReviewStore | None = None
        if review_path is not None:
            self._review_store = ReviewStore(review_path)

    def available(self) -> bool:
        return self.client.health_check()

    def search(self, query: str, limit: int = 5) -> list[AgentRxivHit]:
        if not self.available():
            return []
        result = self.client.search(query, limit=limit)
        hits: list[AgentRxivHit] = []
        for paper in result.papers:
            text = " ".join([paper.title, paper.abstract])
            score = relevance_score(query, text)
            hits.append(AgentRxivHit(paper=paper, score=score))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits

    def to_artifacts(
        self,
        query: str,
        limit: int = 5,
        *,
        min_score: float = 0.15,
    ) -> list[MemoryArtifact]:
        artifacts: list[MemoryArtifact] = []
        for hit in self.search(query, limit=limit):
            if hit.score < min_score:
                continue
            paper = hit.paper
            artifacts.append(
                MemoryArtifact(
                    artifact_id=new_artifact_id(),
                    title=paper.title or "AgentRxiv Paper",
                    summary=(paper.abstract or "").strip()[:400],
                    use_when="Related SWARM research context",
                    failure_modes=[],
                    metrics={"relevance": round(hit.score, 3)},
                    source="agentrxiv",
                    source_id=paper.paper_id,
                )
            )
        return artifacts

    def submit(self, paper: Paper, pdf_path: str) -> SubmissionResult:
        return self.client.submit(paper, pdf_path=pdf_path)

    def trigger_update(self) -> bool:
        return self.client.trigger_update()

    def set_review_store(self, path: str | Path) -> None:
        """Late-bind a ReviewStore (e.g. when output_dir is determined after construction)."""
        self._review_store = ReviewStore(path)

    def submit_review(self, review: PeerReview) -> bool:
        """Persist a peer review via the ReviewStore."""
        if self._review_store is None:
            logger.warning("submit_review called but no ReviewStore configured")
            return False
        self._review_store.append(review)
        return True

    def get_reviews(self, paper_id: str) -> list[PeerReview]:
        """Retrieve reviews for a paper from the ReviewStore."""
        if self._review_store is None:
            return []
        return self._review_store.get_for_paper(paper_id)

    def review_summary(self, paper_id: str) -> dict:
        """Return count, avg_rating, and recommendation_counts for a paper."""
        reviews = self.get_reviews(paper_id)
        if not reviews:
            return {"count": 0, "avg_rating": None, "recommendation_counts": {}}
        avg_rating = sum(r.rating for r in reviews) / len(reviews)
        rec_counts = dict(Counter(r.recommendation for r in reviews))
        return {
            "count": len(reviews),
            "avg_rating": avg_rating,
            "recommendation_counts": rec_counts,
        }

    def related_work(self, query: str, limit: int = 5) -> list[Paper]:
        return [hit.paper for hit in self.search(query, limit=limit)]


def format_related_work(papers: Iterable[Paper]) -> str:
    lines = []
    for paper in papers:
        title = paper.title or "Untitled"
        paper_id = paper.paper_id or "unknown"
        lines.append(f"- {title} ({paper_id})")
    return "\n".join(lines)
