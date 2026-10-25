import redis
import os
from dotenv import load_dotenv
import json

from python_agent_old.models import SearchState, ResultState, DisplayState

load_dotenv()

### Setting up local redis connection (will use elasticache redis when deployed) ###
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True
)


def update_redis_states(
    new_search_state: SearchState | None, 
    new_result_state: ResultState | None, 
    new_display_state: DisplayState | None,
    agent_message: str,
    latest_search_state_version: int,
    current_version: int,
    session_id: str
    ):

    result_key = f"agent:{session_id}:result"
    display_key = f"agent:{session_id}:display"
    conversation_key = f"agent:{session_id}:conversation"
    latest_version_key = f"agent:{session_id}:latest_version"
    current_version_key = f"agent:{session_id}:current_version"

    # Save latest ResultState
    if new_result_state:
        redis_client.set(
            result_key,
            new_result_state.model_dump_json(),
        )

    # Save latest DisplayState
    if new_display_state:
        redis_client.set(
            display_key,
            new_display_state.model_dump_json(),
        )

    # Update version pointers
    redis_client.set(
        latest_version_key,
        latest_search_state_version,
    )

    redis_client.set(
        current_version_key,
        current_version,
    )

    # Add assistant message to conversation history
    redis_client.rpush(
        conversation_key,
        json.dumps({
            "role": "assistant",
            "message": agent_message,
            "version": current_version
        })
    )

    #if not a rollback:
    if new_search_state and current_version == latest_search_state_version:
        redis_client.set(
            f"agent:{session_id}:search:v{current_version}",
            new_search_state.model_dump_json(),
        )