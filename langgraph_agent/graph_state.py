### graph state management, see models.py for specific states ###
from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing import Literal
from langgraph_agent.models import CandidateFilters, CandidateProfile


# New chunk only stores the id of the chunk. Backend will retrieve the chunks when needed
class ChunkMeta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    content_id: int = Field(alias="contentId")
    distance: float
    work_experience_id: int = Field(alias="workExperienceId")
    personal_id: int = Field(alias="personalId")


class ChunkMetaWithKeyword(ChunkMeta):
    keyword: str

class SortCriteria(BaseModel):
    """
    Only three fields for now, fields are related to the candidate profile.
    """
    field: Literal["name", "phone_number", "email"]
    direction: bool
    """
    True for ascending, False for descending
    """

class State(BaseModel):
    # Metadata
    messages: Annotated[
        list[AnyMessage],
        add_messages
    ] = Field(default_factory=list)

    internal_messages: Annotated[
        list[AnyMessage],
        add_messages
    ] = Field(default_factory=list)

    # Final response
    response: str = Field(default="")

    # FILTER
    sql_filters: CandidateFilters = Field(default_factory=CandidateFilters)
    rag_filters: list[str] = Field(default_factory=list)
    resume_bullet_chunks: dict[int, dict[str, list[ChunkMetaWithKeyword]]] = Field(
        default_factory=dict
    )
    candidate_profiles: dict[int, CandidateProfile] = Field(default_factory=dict)

    # SORTING criteria
    order_by: SortCriteria | None = Field(
        default=None,
        description=(
            "Optional explicit SQL sorting criteria. "
            "When provided, takes precedence over candidate scores. "
            "Candidate scores are the secondary sorting criteria."
        )
    )
    keyword_weight: dict[str, float] = Field(default_factory=dict)

    # Results State
    candidate_ids: list[int] = Field(default_factory=list)

    # Display State
    candidate_sorted_ids: list[int] = Field(default_factory=list)
    display_window: tuple[int, int] = (0, 10)
    
