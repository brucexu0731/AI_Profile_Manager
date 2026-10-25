def generate_display_profiles(candidate_sorted_ids: list[int], 
candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]],
candidate_profiles: dict[int, CandidateProfile]) -> list[dict]:

    displayed_candidates: list[dict] = get_candidate_info(sorted_display_ids)
    candidate_by_id = {
        candidate["id"]: {
            "basic_info": candidate,
            "relevant_chunks": {
                keyword: [chunk.model_dump() for chunk in chunks]
                for keyword, chunks in candidate_chunks.get(candidate["id"], {}).items()
            }
        }
        for candidate in displayed_candidates
    }

    displayed_candidates_sorted = [
        candidate_by_id[candidate_id]
        for candidate_id in sorted_display_ids
    ]


    return displayed_candidates_sorted