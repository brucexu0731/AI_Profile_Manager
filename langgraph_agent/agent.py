from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel

from langgraph_agent.graph_state import State
from langgraph_agent.llm import llm

AGENT_PROMPT = "Always output 'Testing agent node'"


class AgentOutput(BaseModel):
    action: str
    message: str


agent_llm = llm.with_structured_output(AgentOutput)


async def agent(state: State) -> Command[Literal["__end__"]]:
    result = await agent_llm.ainvoke([
        SystemMessage(content=AGENT_PROMPT)
    ])

    writer = get_stream_writer()
    writer({
        "action": result.action,
        "message": result.message,
    })

    return {
            "messages": [AIMessage(content=result.message)],
            "response": result.message,
            "action": result.action,
        }
