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
from utils.get_candidate_info import get_candidate_info
from utils.generate_display_profiles import generate_display_profiles
from utils.update_redis_states import update_redis_states

from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse


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
    "GENERAL-KNOWLEDGE"
}

@app.post("/agent/{session_id}/ask")
def ask_agent(session_id: str, body: UserQuery):

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
    new_search_state: SearchState | None = None
    new_result_state: ResultState | None = None
    new_display_state: DisplayState | None = None

    latest_search_state_version = int(redis_client.get(f"agent:{session_id}:latest_version"))

    rollback = False 
    message = user_message
    res = {}
    output = {}

    agent_message = ""

    #agent loop
    
    i = 0

    # the maximum agent loop takes 3 iterations, rollback -> filter -> summarize,
    # if the LLM call fails for some reason, the loop would preserve the states and
    # the next iteration is essentially a re-try, so the room for retries is about 3
    # since we are running the loop 6 times
    while action not in TERMINAL_ACTIONS and i < 6:
        i += 1

        res = agent.call(message)
        action = res["action"]

        if action == "FILTER":
            filter_results = filter_and_rank(res.get("filters"))
            candidate_chunks, candidate_score, final_ids = get_rag_results(filter_results, res.get("resume_bullets"), res.get("keyword_weight", {}))

            new_search_state = SearchState(
                session_id=session_id,
                filters=res["filters"],
                resume_bullets=res["resume_bullets"],
                keyword_weight=res["keyword_weight"]
            )

            new_result_state = ResultState(
                session_id = session_id,
                candidate_ids = final_ids,
                resume_bullet_chunks = candidate_chunks,
                candidate_score = candidate_score,
                keyword_weight = new_search_state.keyword_weight
            )

            new_display_state = DisplayState(
                session_id = session_id,
                total_match_count = len(final_ids),
                candidate_ids_sorted = final_ids,  
            )

            if not rollback:
                latest_search_state_version += 1
                current_version = latest_search_state_version

            displayed_candidates_sorted = []

            if not final_ids:
                message = {
                "new_display_state": new_display_state.model_dump(),
                "candidate_profiles": []
                } 
            else:
                displayed_candidate_ids = final_ids[:10]

                displayed_candidates_sorted = generate_display_profiles(
                    displayed_candidate_ids,
                    candidate_chunks
                )

                message = {
                    "new_display_state": new_display_state.model_dump(),
                    "candidate_profiles": displayed_candidates_sorted
                }
            
            agent_message += (
                f"\n FILTER {current_version}, found {len(final_ids)} candidates. "
                f"Displaying {[(c['basic_info']['id'], c['basic_info']['name']) for c in displayed_candidates_sorted]}"
            )
        
        elif action == "ROLLBACK":
            #ROLLBACK -> filter_and_rank -> update result state/display_state/search_state -> SUMMARIZE
            rollback = True
            current_version = res.get("version")

            rollback_search_state_json = redis_client.get(f"agent:{session_id}:search:v{current_version}")
            if rollback_search_state_json is None:
                raise ValueError(f"Search state version {current_version} not found")

            rollback_search_state = SearchState.model_validate_json(rollback_search_state_json)

            message = {
                "rollback_search_state": rollback_search_state.model_dump()
            }

        elif action == "RANK":
            displayed_candidate_ids = res.get("profiles")
            rank_field = res.get("field")
            displayed_candidates_sorted = generate_display_profiles(
                displayed_candidate_ids,
                result_state.resume_bullet_chunks
            )

            message = {
                "candidate_profiles": displayed_candidates_sorted
            }
            agent_message += f"\n RANK {displayed_candidate_ids} by {rank_field}"

        elif action == "COMPARE":
            displayed_candidate_ids = res.get("profiles")
            compare_message = res.get("message")
            displayed_candidates_sorted = generate_display_profiles(
                displayed_candidate_ids,
                result_state.resume_bullet_chunks
            )

            message = {
                "candidate_profiles": displayed_candidates_sorted
            }

            agent_message += f"\n COMPARE {displayed_candidate_ids} by {compare_message}"
        
        elif action == "SUMMARIZE":
            output = {
                "action": "SUMMARIZE",
                "overall_summary": res.get("overall_summary"),
                "results": res.get("results"),
                "html": res.get("html")
                # "chat_history": conversation
            }

        elif action == "RESIZE":
            #LLM will only output resize if the request is valid
            new_window = res.get("new_window")
            new_display_state = display_state.model_copy(
                update={"display_window": new_window}
            )
            l, r = new_window

            displayed_candidate_ids = new_display_state.candidate_ids_sorted[l : r]

            displayed_candidates_sorted = generate_display_profiles(
                displayed_candidate_ids,
                result_state.resume_bullet_chunks
            )

            message = {
                "new_display_state": new_display_state.model_dump(),
                "candidate_profiles": displayed_candidates_sorted
            }
            agent_message += (
                f"\n RESIZE display window to {new_window}"
                f"Displaying {[(c['basic_info']['id'], c['basic_info']['name']) for c in displayed_candidates_sorted]}"
            )

        else:
            output = res
            agent_message += f"\n {action}, {res.get('message')}"

    # If something went wrong with the agent loop, preserve the previous state, and tell the user to 
    # retry, throwing error for now
    if action not in TERMINAL_ACTIONS:
        raise Exception("Agent did not reach a terminal action after 6 iterations. Please check the agent logic.")

    update_redis_states(
        new_search_state, 
        new_result_state, 
        new_display_state,
        agent_message,
        latest_search_state_version,
        current_version,
        session_id
    )

    return {
        #"session_id": session_id,
        #"result": res,
        #"agent_loop_history": agent.current_loop_history,
        "output": output,
        # "chat_history": conversation


        # "action": action,
        # "filter_results": filter_results,
        # "candidate_score": candidate_score,
        # "message": message,
        #"result2": res2
        # "candidate_chunks": candidate_chunks,
        # "candidate_score": candidate_score,
        # "final_ids": final_ids
    }



@app.post("/agent/reset-cache")
def reset_cache():
    redis_client.flushdb()

def sse(data):
    return f"data: {json.dumps(data)}\n\n"

@app.post("/agent/{session_id}/ask-stream")
def ask_agent_stream(session_id: str, body: UserQuery):

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

    def events():
        nonlocal current_version

        #out of loop variables
        action = ""
        new_search_state: SearchState | None = None
        new_result_state: ResultState | None = None
        new_display_state: DisplayState | None = None

        latest_search_state_version = int(redis_client.get(f"agent:{session_id}:latest_version"))

        rollback = False 
        message = user_message
        res = {}
        output = {}

        agent_message = ""

        #agent loop
        i = 0
        # the maximum agent loop takes 3 iterations, rollback -> filter -> summarize,
        # if the LLM call fails for some reason, the loop would preserve the states and
        # the next iteration is essentially a re-try, so the room for retries is about 3
        # since we are running the loop 6 times
        while action not in TERMINAL_ACTIONS and i < 6:
            i += 1

            if action == "FILTER":
                yield sse({
                    "type": "progress",
                    "output": {
                        "html": " Filtering candidates..."
                    }
                })
            elif action == "ROLLBACK":
                yield sse({
                    "type": "progress",
                    "output": {
                        "html": " Rolling back to previous filter..."
                    }
                })
            elif action == "RANK":
                yield sse({
                    "type": "progress",
                    "output": {
                        "html": " Gathering candidate information..."
                    }
                })
            elif action == "COMPARE":
                yield sse({
                    "type": "progress",
                    "output": {
                        "html": " Gathering candidate information..."
                    }
                })
            elif action == "RESIZE":
                yield sse({
                    "type": "progress",
                    "output": {
                        "html": " Gathering candidate information... "
                    }
                })
            
            res = agent.call(message)
            action = res["action"]

            if action == "FILTER":
                filter_results = filter_and_rank(res.get("filters"))
                candidate_chunks, candidate_score, final_ids = get_rag_results(filter_results, res.get("resume_bullets"), res.get("keyword_weight", {}))

                new_search_state = SearchState(
                    session_id=session_id,
                    filters=res["filters"],
                    resume_bullets=res["resume_bullets"],
                    keyword_weight=res["keyword_weight"]
                )

                new_result_state = ResultState(
                    session_id = session_id,
                    candidate_ids = final_ids,
                    resume_bullet_chunks = candidate_chunks,
                    candidate_score = candidate_score,
                    keyword_weight = new_search_state.keyword_weight
                )

                new_display_state = DisplayState(
                    session_id = session_id,
                    total_match_count = len(final_ids),
                    candidate_ids_sorted = final_ids,  
                )

                if not rollback:
                    latest_search_state_version += 1
                    current_version = latest_search_state_version

                displayed_candidates_sorted = []

                if not final_ids:
                    message = {
                    "new_display_state": new_display_state.model_dump(),
                    "candidate_profiles": []
                    } 
                else:
                    displayed_candidate_ids = final_ids[:10]

                    displayed_candidates_sorted = generate_display_profiles(
                        displayed_candidate_ids,
                        candidate_chunks
                    )

                    message = {
                        "new_display_state": new_display_state.model_dump(),
                        "candidate_profiles": displayed_candidates_sorted
                    }
                
                agent_message += (
                    f"\n FILTER {current_version}, found {len(final_ids)} candidates. "
                    f"Displaying {[(c['basic_info']['id'], c['basic_info']['name']) for c in displayed_candidates_sorted]}"
                )
            
            elif action == "ROLLBACK":
                rollback = True
                current_version = res.get("version")

                rollback_search_state_json = redis_client.get(f"agent:{session_id}:search:v{current_version}")
                if rollback_search_state_json is None:
                    raise ValueError(f"Search state version {current_version} not found")

                rollback_search_state = SearchState.model_validate_json(rollback_search_state_json)

                message = {
                    "rollback_search_state": rollback_search_state.model_dump()
                }

            elif action == "RANK":
                displayed_candidate_ids = res.get("profiles")
                rank_field = res.get("field")
                displayed_candidates_sorted = generate_display_profiles(
                    displayed_candidate_ids,
                    result_state.resume_bullet_chunks
                )

                message = {
                    "candidate_profiles": displayed_candidates_sorted
                }
                agent_message += f"\n RANK {displayed_candidate_ids} by {rank_field}"

            elif action == "COMPARE":
                displayed_candidate_ids = res.get("profiles")
                compare_message = res.get("message")
                displayed_candidates_sorted = generate_display_profiles(
                    displayed_candidate_ids,
                    result_state.resume_bullet_chunks
                )

                message = {
                    "candidate_profiles": displayed_candidates_sorted
                }

                agent_message += f"\n COMPARE {displayed_candidate_ids} by {compare_message}"
            
            elif action == "SUMMARIZE":
                output = {
                    "action": "SUMMARIZE",
                    "overall_summary": res.get("overall_summary"),
                    "results": res.get("results"),
                    "html": res.get("html")
                    # "chat_history": conversation
                }

            elif action == "RESIZE":
                new_window = res.get("new_window")
                new_display_state = display_state.model_copy(
                    update={"display_window": new_window}
                )
                l, r = new_window

                displayed_candidate_ids = new_display_state.candidate_ids_sorted[l : r]

                displayed_candidates_sorted = generate_display_profiles(
                    displayed_candidate_ids,
                    result_state.resume_bullet_chunks
                )

                message = {
                    "new_display_state": new_display_state.model_dump(),
                    "candidate_profiles": displayed_candidates_sorted
                }
                agent_message += (
                    f"\n RESIZE display window to {new_window}"
                    f"Displaying {[(c['basic_info']['id'], c['basic_info']['name']) for c in displayed_candidates_sorted]}"
                )

            else:
                output = res
                agent_message += f"\n {action}, {res.get('message')}"

        # If something went wrong with the agent loop, preserve the previous state, and tell the user to 
        # retry, throwing error for now
        if action not in TERMINAL_ACTIONS:
            raise Exception("Agent did not reach a terminal action after 6 iterations. Please check the agent logic.")

        update_redis_states(
            new_search_state, 
            new_result_state, 
            new_display_state,
            agent_message,
            latest_search_state_version,
            current_version,
            session_id
        )

        yield sse({
            "type": "final",
            #"session_id": session_id,
            #"result": res,
            #"agent_loop_history": agent.current_loop_history,
            "output": output,
            # "chat_history": conversation


            # "action": action,
            # "filter_results": filter_results,
            # "candidate_score": candidate_score,
            # "message": message,
            #"result2": res2
            # "candidate_chunks": candidate_chunks,
            # "candidate_score": candidate_score,
            # "final_ids": final_ids
        })
    
    return StreamingResponse(
        events(),
        media_type="text/event-stream"
    )

# Mount static frontend last so API routes take priority
app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)
