import asyncio
from functools import partial

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from langgraph_agent.graph_state import State
from langgraph_agent.scrutiny import scrutiny
from langgraph_agent.agent import agent
from langgraph_agent.tools import tools


# Build graph
g = StateGraph(State)

# Add nodes
g.add_node("scrutiny", scrutiny)
g.add_node("agent", agent)
g.add_node(
    "tools",
    ToolNode(tools, messages_key="internal_messages"),
)

# Define edges
g.add_edge(START, "scrutiny")
# tools_condition:
#   - tool calls on the last AI message  -> "tools"
#   - otherwise                          -> END
# so you do NOT also need add_edge("agent", END)
g.add_conditional_edges(
    "agent",
    partial(tools_condition, messages_key="internal_messages"),
)
g.add_edge("tools", "agent")

# Compile graph
graph = g.compile()


async def main():
    async for chunk in graph.astream(
        {
            "user_message": "I want software engineers",
            "internal_messages": []
        },
        stream_mode=["custom", "updates"],
        version="v2",
    ):
        print(chunk)


if __name__ == "__main__":
    asyncio.run(main())
