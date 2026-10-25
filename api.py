from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
from pydantic import BaseModel 
from dotenv import load_dotenv
from python_agent_old.models import SearchState, ResultState, DisplayState
from python_agent_old.utils.get_or_create_session import get_or_create_session
from python_agent_old.utils.filter_and_rank import filter_and_rank
from python_agent_old.system_prompts.system_promptV2 import prompt

import json
from python_agent_old.agent import Agent
from python_agent_old.utils.rag_results import get_rag_results
from python_agent_old.utils.get_candidate_info import get_candidate_info
from python_agent_old.utils.generate_display_profiles import generate_display_profiles
from python_agent_old.utils.update_redis_states import update_redis_states

from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from routers import agent_v1, agent_v1_SSE


load_dotenv()

app = FastAPI(
    title="AI Document Inteligence API",
    description="Fast API layer for the PDF-to-ML-Ready data document intelligence project.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

### Setting up local redis connection (will use elasticache redis when deployed) ###
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True
)

app.include_router(agent_v1.router, prefix = "/agentV1/{session_id}/ask", tags = ["Old Agent Endpoint"])
app.include_router(agent_v1_SSE.router, prefix = "/agentV1/{session_id}/ask-stream", tags = ["Old Agent Endpoint SSE"])

@app.get("/test")
def test_server():
    return "Hi"

@app.post("/agent/reset-cache")
def reset_cache():
    redis_client.flushdb()

# Mount static frontend last so API routes take priority
app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)
