import requests
from pydantic import BaseModel, ConfigDict, Field
from python_agent_old.models import Chunk, ChunkWithKeyword

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
        timeout = 20
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


def filter_rag(filtered_ids: list[int], resume_bullets: list[str]) -> tuple[
    dict[int, dict[str, list[ChunkWithKeyword]]],list[int]
]:

    candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]] = {} #id -> {keyword -> list of ChunkWithKeyword}
    final_ids = filtered_ids

    if not resume_bullets:
        return candidate_chunks, final_ids

    #iterate through each keyword, 
    for keyword in resume_bullets:
        rag_result = call_rag_api(SearchPayload(query = keyword, ids = final_ids))

        ids = set()
        keyword_chunks = {} #id -> list of ChunkWithKeyword 

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

    return candidate_chunks, final_ids
