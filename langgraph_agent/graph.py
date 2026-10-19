import asyncio

from langgraph.graph import StateGraph, START, END

from langgraph_agent.graph_state import State
from langgraph_agent.scrutiny import scrutiny
from langgraph_agent.agent import agent


# Build graph
g = StateGraph(State)

# Add nodes
g.add_node("scrutiny", scrutiny)
g.add_node("agent", agent)

# Define edges
g.add_edge(START, "scrutiny")
g.add_edge("agent", END)

# Compile graph
graph = g.compile()


async def main():
    async for chunk in graph.astream(
        {"user_message": "I want software engineers"},
        stream_mode=["custom", "updates"],
        version="v2",
    ):
        print(chunk)


if __name__ == "__main__":
    asyncio.run(main())
