from typing import Annotated, Any, Self

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)
from langgraph_agent.graph_state import SortCriteria
from langgraph_agent.models import CandidateFilters, CandidateProfile
from langgraph_agent.utils.filter_rag import ChunkWithKeyword, filter_rag
from langgraph_agent.utils.filter_sql import filter_sql
from langgraph_agent.utils.get_candidates_info import get_candidate_info

# Filter, Sort modifies the state of the graph, and sends back
# a summary:
# filter success
# OK: 47 candidates. display_window=[0,10], top_ids=[12,45,...], filters={...}
# filter empty / fail
# EMPTY: 0 candidates for filters={...}. Suggest broadening.

# generate_display_profiles uses the state and gathers relevant information
# of candidates to send back to the llm for final output





@tool
def filter(
    sql_filters: CandidateFilters,
    rag_filters: list[str],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Apply candidate search filters."""
    #1. Filter SQL --> set of ids
    #2. Filter RAG --> set of ids, dictionary ofcandidate_chunks

    filtered_ids = filter_sql(sql_filters)
    candidate_chunks, candidate_ids = filter_rag(filtered_ids, rag_filters)
    candidate_profiles = get_candidate_info(candidate_ids)

    return Command(
        update={
            "sql_filters": sql_filters,
            "rag_filters": rag_filters,
            "resume_bullet_chunks": candidate_chunks,
            "candidate_ids": filtered_ids,
            "candidate_profiles": candidate_profiles,
            "internal_messages": [
                ToolMessage(
                    content=f"Found {len(filtered_ids)} candidates, sql_filters={sql_filters}, rag_filters={rag_filters}",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )


@tool
def sort(
    candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]], 
    keyword_weight: dict[str, float], 
    order_by: SortCriteria | None = None,
    candidate_ids: list[int],
    candidate_profiles: dict[int, CandidateProfile],
    tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """ Sort candidates by rag keyword weight and order by criteria"""

    candidate_sorted_ids = sort_candidates(candidate_chunks, keyword_weight, order_by, candidate_ids, candidate_profiles)
    return Command(
        update={
            "order_by": order_by,
            "keyword_weight": keyword_weight,
            "candidate_sorted_ids": candidate_sorted_ids,
            "internal_messages": [
                ToolMessage(
                    content=f"Filtered {len(candidate_sorted_ids)} candidates, order_by={order_by}, keyword_weight={keyword_weight}",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )

@tool
def generate_display_profiles(
    candidate_sorted_ids: list[int],
    candidate_chunks: dict[int, dict[str, list[ChunkWithKeyword]]],
    candidate_profiles: dict[int, CandidateProfile],
    display_window: tuple[int, int],
    tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """ Generate display profiles for candidates"""

    display_profiles = generate_display_profiles(candidate_sorted_ids, candidate_chunks, candidate_profiles)
    return Command(
        update={
            "display_window": display_window,
            "internal_messages": [
                ToolMessage(
                    content=f"displaying {display_window[0]} to {display_window[1]} candidates",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )
        
tools = [filter, sort]
