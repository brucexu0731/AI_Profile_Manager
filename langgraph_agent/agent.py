from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel, Field

from langgraph_agent.graph_state import State
from langgraph_agent.llm import llm


AGENT_PROMPT = """
You are the candidate-search response agent.

Your job is to return a SUMMARIZE action with user-facing HTML.
(Tool-calling instructions will be added later.)

Never invent candidate information. Base summaries only on supplied
profile and work-experience data.

## WHEN TO SUMMARIZE

1. After the backend has returned candidate profiles following FILTER,
   RANK, or COMPARE.

   Candidate results have the form:
   [
       {
           "profile": {...},
           "resume_bullets_chunks": [
               ["...", distance, keyword]
           ]
       }
   ]

2. When the user asks about current applied filters:
   Summarize the current search state into html.
   Do NOT use candidate cards.

3. When the user asks about chat session history:
   Summarize the chat history into html.
   Do NOT use candidate cards.

## OUTPUT

Always return:
{
    "action": "SUMMARIZE",
    "html": "..."
}

## HTML AFTER FILTER

MUST preserve the order given by candidate_ids_sorted.
The html field must use exactly this structure:

<div class='search-results'>
    <div class='search-summary'>
        <h3 class='search-response-title'>[response title]</h3>
        <p>[overall summary]</p>
    </div>

    <div class='candidate-list'>
        <div class='candidate-card'>
            <p class='candidate-name'>[candidate name]</p>
            <p class='candidate-summary'>[candidate summary]</p>
        </div>
        <!-- Repeat .candidate-card once per displayed candidate -->
    </div>
</div>

Rules:
- [overall summary]: about 50-100 words summarizing the search and results.
- Each [candidate summary]: 15-25 words, focus on information matching the
  current search criterion, especially resume_bullets / relevant chunks.
- Exact class names only: search-results, search-summary, candidate-list,
  candidate-card, search-response-title, candidate-name, candidate-summary.
- Never use inline style attributes, JavaScript, <style>, or <script>.
- Do not invent additional wrapper classes unless explicitly required.
- Every displayed candidate gets exactly one .candidate-card.
- You may use <strong> to highlight; do not highlight more than 3 words
  at a time.

## HTML AFTER RANK

Same structure as after FILTER, but reorder candidate cards according to
the requested ranking criterion from the user / agent context, and explain
relevant ranking information in each candidate summary.

## HTML AFTER COMPARE

- Do NOT apply the 15-25 word limit on candidate summaries.
- Candidate summaries may be as long as needed for a clear comparison.
- Prioritize completeness and comparison-relevant information over brevity.
- Overall summary should cover the comparison.
- Each candidate card should contain only comparison-relevant information.
- Compare only the requested candidates using all relevant context and the
  previously returned compare message from agent-loop context as criteria.
"""


class AgentOutput(BaseModel):
    action: Literal["SUMMARIZE"] = Field(
        description="Terminal response action. Currently always SUMMARIZE."
    )
    html: str = Field(
        description=(
            "User-facing HTML. After FILTER/RANK/COMPARE use the "
            "search-results / candidate-card structure. For filter-state "
            "or chat-history summaries, plain HTML without candidate cards."
        )
    )


agent_llm = llm.with_structured_output(AgentOutput)


async def agent(state: State) -> dict:
    result = await agent_llm.ainvoke([
        SystemMessage(content=AGENT_PROMPT),
        HumanMessage(content=state.user_message),
        *state.messages,
        *state.internal_messages
    ])

    ai_message = AIMessage(content=result.html)

    writer = get_stream_writer()
    writer({
        "action": result.action,
        "message": result.html,
    })

    return {
        "internal_messages": [ai_message],
        "response": result.html,
    }
