### graph state management, see models.py for specific states ###
from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


# New chunk only stores the id of the chunk. Backend will retrieve the chunks when needed
class ChunkMeta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    content_id: int = Field(alias="contentId")
    distance: float
    work_experience_id: int = Field(alias="workExperienceId")
    personal_id: int = Field(alias="personalId")


class ChunkMetaWithKeyword(ChunkMeta):
    keyword: str


class State(BaseModel):
    # Metadata
    user_message: str = Field(default="")
    messages: Annotated[
        list[AnyMessage],
        add_messages
    ] = Field(default_factory=list)
    # Final response
    response: str = Field(default="")

    # For agent
    action: str = Field(default="")

    # FILTER
    sql_filters: dict[str, str | int | list] = Field(default_factory=dict)
    resume_rag: list[str] = Field(default_factory=list)

    # RANKING criteria
    order_by: str = Field(default="")
    keyword_weight: dict[str, float] = Field(default_factory=dict)

    # Results State
    resume_bullet_chunks: dict[int, dict[str, list[ChunkMetaWithKeyword]]] = Field(
        default_factory=dict
    )
    candidate_score: dict[int, float] = Field(default_factory=dict)
    candidate_ids_ordered: list[int] = Field(default_factory=list)

    # Display State
    display_window: tuple[int, int] = (0, 10)
    display_profiles: list[dict] = Field(default_factory=list)
