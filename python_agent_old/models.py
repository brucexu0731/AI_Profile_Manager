### Search state management: Models ###
from pydantic import BaseModel, Field, ConfigDict

class Chunk(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content_id: int = Field(alias="contentId")
    distance: float
    content: str
    work_experience_id: int = Field(alias="workExperienceId")
    personal_id: int = Field(alias="personalId")


class ChunkWithKeyword(Chunk):
    keyword: str

class SearchState(BaseModel):
    session_id: str
    filters: dict[str, str | int | list] = Field(default_factory=dict)
    resume_bullets: list[str] = Field(default_factory=list)
    #feedback: list[str] = Field(default_factory=list)
    keyword_weight: dict[str, float] = Field(default_factory=dict)

class ResultState(BaseModel):
    session_id: str
    candidate_ids: list[int] = Field(default_factory=list)

    resume_bullet_chunks: dict[int, dict[str, list[ChunkWithKeyword]]] = Field(
        default_factory = dict
    )

    # {
    #     id1: {
    #         keyword1: [chunk1, chunk2]
    #         keyword2: [chunk1, chunk2, ....]
    #     }
    #     id2: {
    #         keyword1: [chunk1, chunk2]
    #         keyword2: [chunk1, chunk2, ....]
    #     }

    # }

    #feedback_chunks: dict[int, list[tuple[int, float, str]]] = Field(default_factory=dict)

    candidate_score: dict[int, float] = Field(default_factory=dict)
    keyword_weight: dict[str, float] = Field(default_factory=dict)

class DisplayState(BaseModel):
    session_id: str
    total_match_count: int = 0

    #by default after each search, the bot would display the top 10 candidates
    candidate_ids_sorted: list[int] = Field(default_factory=list)
    display_window: tuple[int, int] = (0, 10) #display window of the candidates list
    