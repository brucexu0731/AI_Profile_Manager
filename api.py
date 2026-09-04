from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
from pydantic import BaseModel 
from dotenv import load_dotenv
from models import SearchState, ResultState, DisplayState
from utils.get_or_create_session import get_or_create_session
from utils.filter_and_rank import filter_and_rank
from system_prompts.system_promptV2 import prompt

import json
from agent import Agent
from utils.rag_results import get_rag_results


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


class UserQuery(BaseModel):
    query: str

@app.get("/test")
def test_server():
    return "Hi"

TERMINAL_ACTIONS = {
    "SUMMARIZE",
    "CLARIFY",
    "REJECT",
    "ROLLBACK_OUT_OF_SCOPE",
    "RANK_COMPARE_DENIED",
}

@app.post("/agent/{session_id}/ask")
def ask_agent(session_id: str, body: UserQuery):
    # Retreive from redis if existing session / initialize if new session:
    # 1. current search state
    # 2. current display state
    # 3. Conversation log with versions
    #     [
    #     {"role":"user","message":"Find backend engineers","searchState":null},
    #     {"role":"assistant","message":[18,25,31],"searchState":"v1"},

    #     {"role":"user","message":"Only in Singapore","searchState":"v1"},
    #     {"role":"assistant","message":[18,25],"searchState":"v2"},

    #     {"role":"user","message":"Tell me about candidate 18","searchState":"v2"},
    #     {"role":"assistant","message":"Candidate 18 has 6 years of backend experience...","searchState":"v2"},

    #     {"role":"user","message":"Make experience stricter","searchState":"v2"},
    #     {"role":"assistant","message":"Do you mean require more years of experience?","searchState":"v2"},
    #     {"role":"user","message":"Yes, at least 5 years","searchState":"v2"},
    #     {"role":"assistant","message":[18],"searchState":"v3"},

    #     {"role":"user","message":"Go back to before the 5-year requirement","searchState":"v3"},
    #     {"role":"assistant","message":[18,25],"searchState":"v2"},

    #     {"role":"user","message":"Add fintech experience","searchState":"v2"},
    #     {"role":"assistant","message":[25],"searchState":"v4"},

    #     {"role":"user","message":"Go back to right after the first search","searchState":"v4"},
    #     {"role":"assistant","message":[18,25,31],"searchState":"v1"}
    #     ]
    #  
    #     ---> THOSE THREE GETS APPENDED TO SYSTEM PROMPT

    # 4. ResultsState --> should be in sync with display state(display state is just a summary of results state)
    # 

    user_message = body.query
    (
        search_state, 
        result_state, 
        display_state, 
        conversation,
        current_version
    ) = get_or_create_session(session_id, user_message)


    system_prompt = f"""
        {prompt}

        ## CURRENT SESSION STATE

        ### SearchState
        {search_state.model_dump_json(indent=2)}

        ### ResultState
        {result_state.model_dump_json(indent=2)}

        ### DisplayState
        {display_state.model_dump_json(indent=2)}

        ## CONVERSATION HISTORY

        {json.dumps(conversation, indent=2)}
    """

    agent = Agent(
        system_prompt=system_prompt,
        current_version=current_version,
        session_id=session_id
    )


    #out of loop variables
    action = ""
    new_search_state = {}
    new_result_state = {}
    new_display_state = {}
    message = user_message
    res = {}

    #agent loop
    #while action not in TERMINAL_ACTIONS:

    res = agent.call("Begin processing user request: " + message)
    action = res["action"]

    if action == "FILTER":
        #FILTER candidates -> get list of ids & chunks -> update result state/display_state/search_state -> SUMMARIZE
        filter_results = filter_and_rank(res.get("filters"))
        candidate_chunks, candidate_score, final_ids = get_rag_results(filter_results, res.get("resume_bullets"), res.get("keyword_weight"))
    
    # if action == "ROLLBACK":
    #     #ROLLBACK -> filter_and_rank -> update result state/display_state/search_state -> SUMMARIZE
    #     version = res.get("version")

    if action == "RANK":
        pass

    if action == "COMPARE":
        pass
    
    if action == "SUMMARIZE":
        pass
    
    if action == "RESIZE":
        pass
    



    redis_client.flushdb()

    return {
        "result": res,
        "agent_loop_history": agent.current_loop_history,
        "action": action,
        "filter_results": filter_results,
        "candidate_chunks": candidate_chunks,
        "candidate_score": candidate_score,
        "final_ids": final_ids
    }