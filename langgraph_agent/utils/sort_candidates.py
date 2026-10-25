from langgraph_agent.graph_state import SortCriteria
from langgraph_agent.models import CandidateProfile
from langgraph_agent.utils.filter_rag import ChunkWithKeyword

def chunk_score(distance: float) -> float:
    anchors = [
        (0.35, 1.00),
        (0.40, 0.75),
        (0.50, 0.50),
        (0.60, 1 / 3),
        (0.65, 0.25),
    ]

    if distance <= anchors[0][0]:
        return anchors[0][1]

    if distance >= anchors[-1][0]:
        return 0.0

    for i in range(len(anchors) - 1):
        d1, s1 = anchors[i]
        d2, s2 = anchors[i + 1]

        if d1 <= distance <= d2:
            ratio = (distance - d1) / (d2 - d1)
            return s1 + ratio * (s2 - s1)

    return 0.0

def calculate_candidate_scores(
    candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]],
    keyword_weight: dict[str, float]
) -> dict[int, float]:

    candidate_scores: dict[int, float] = {}

    for candidate_id, keyword_chunks in candidate_chunks.items():
        total_score = 0.0

        for keyword, chunks in keyword_chunks.items():
            weight = keyword_weight.get(keyword, 1.0)

            keyword_score = sum(
                chunk_score(chunk.distance)
                for chunk in chunks
            )

            total_score += keyword_score * weight

        candidate_scores[candidate_id] = total_score

    return candidate_scores

def sort_candidates(
    candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]],
    keyword_weight: dict[str, float],
    sort_criteria: SortCriteria | None = None,
    candidate_ids: list[int],
    candidate_profiles: dict[int, CandidateProfile],
) -> list[int]:

    candidate_scores = calculate_candidate_scores(candidate_chunks, keyword_weight)

    def profile_field(candidate_id: int):
        return getattr(candidate_profiles[candidate_id], sort_criteria.field) or ""

    if not sort_criteria and not candidate_scores:
        return candidate_ids
    elif not sort_criteria:
        return sorted(candidate_ids, key=lambda x: candidate_scores[x], reverse=True)
    elif not candidate_scores:
        return sorted(
            candidate_ids,
            key=profile_field,
            reverse=sort_criteria.direction,
        )
    else:
        return sorted(
            candidate_ids,
            key=lambda x: [candidate_scores[x], profile_field(x)],
            reverse=True,
        )
