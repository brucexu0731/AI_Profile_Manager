
import requests
from pydantic import BaseModel, ConfigDict, Field
from models import Chunk, ChunkWithKeyword

RAG_API_URL = "http://localhost:8080/agents/rag/work-experiences"

class SearchPayload(BaseModel):
    query: str
    ids: list[int] | None = None

# class Chunk(BaseModel):
#     model_config = ConfigDict(populate_by_name=True)

#     content_id: int = Field(alias="contentId")
#     distance: float
#     content: str
#     work_experience_id: int = Field(alias="workExperienceId")
#     personal_id: int = Field(alias="personalId")


# class ChunkWithKeyword(Chunk):
#     keyword: str

def call_rag_api(payload: SearchPayload) -> list[Chunk]:

    response = requests.post(
        RAG_API_URL,
        json=payload.model_dump()
    )

    if not response.ok:
        print("STATUS:", response.status_code)
        print("BODY:", response.text)

    response.raise_for_status()

    res = [
        Chunk.model_validate(chunk)
        for chunk in response.json()
    ]

    return res

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

def get_rag_results(filtered_ids: list[int], resume_bullets: list[str],
    keyword_weight: dict[str, float]) -> tuple[
    dict[int, dict[str, list[ChunkWithKeyword]]],
    dict[int, float],
    list[int]
]:

    candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]] = {} #id -> {keyword -> list of ChunkWithKeyword}
    candidate_score = {} #id -> score

    final_ids = filtered_ids

    if not resume_bullets:
        return candidate_chunks, candidate_score, final_ids

    #iterate through each keyword, 
    for keyword in resume_bullets:
        rag_result = call_rag_api(SearchPayload(query = keyword, ids = final_ids))

        ids = set()
        keyword_chunks = {}

        #for each chunk, add it to its respective user_id, then add the appeared user ids to a list
        for chunk in rag_result:
            save_chunk = ChunkWithKeyword(
                **chunk.model_dump(),
                keyword = keyword
            )

            if save_chunk.personal_id not in keyword_chunks:
                keyword_chunks[save_chunk.personal_id] = []
            
            ids.add(save_chunk.personal_id)
            keyword_chunks[save_chunk.personal_id].append(save_chunk)
        
        #if the newest keyword gives us no matches, end the filtering.  
        final_ids = list(ids)
        if not final_ids:
            break
        
        #grab top 5 chunks from each keyword for each candidate, and add to candidate_chunks
        for candidate_id, chunks in keyword_chunks.items():
            save_chunks = sorted(chunks, key=lambda x: x.distance)[:5]
            if candidate_id not in candidate_chunks:
                candidate_chunks[candidate_id] = {}
            candidate_chunks[candidate_id][keyword] = save_chunks
        
    
    candidate_chunks = {
        candidate_id: chunks
        for candidate_id, chunks in candidate_chunks.items()
        if candidate_id in final_ids
    }

    candidate_score = calculate_candidate_scores(candidate_chunks, keyword_weight)

    final_ids.sort(key = lambda x : candidate_score[x], reverse = True)

    return candidate_chunks, candidate_score, final_ids
