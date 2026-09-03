import redis
import os
from dotenv import load_dotenv
import json

from models import SearchState, ResultState, DisplayState

load_dotenv()

### Setting up local redis connection (will use elasticache redis when deployed) ###
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True
)

SESSION_TTL = 60 * 60 * 24  # 1 day

def refresh_session_ttl(
    session_id: str,
    latest_version_key: str,
    current_version_key: str,
    result_key: str,
    display_key: str,
    conversation_key: str
):
    # Refresh main session keys
    redis_client.expire(latest_version_key, SESSION_TTL)
    redis_client.expire(current_version_key, SESSION_TTL)
    redis_client.expire(result_key, SESSION_TTL)
    redis_client.expire(display_key, SESSION_TTL)
    redis_client.expire(conversation_key, SESSION_TTL)

    # Refresh every historical SearchState
    latest_version_raw = redis_client.get(latest_version_key)

    if latest_version_raw is not None:
        latest_version = int(latest_version_raw)

        for version in range(latest_version + 1):
            search_state_key = f"agent:{session_id}:search:v{version}"
            redis_client.expire(search_state_key, SESSION_TTL)

"""
REDIS KEY GUIDE:

VERSION CONTROL:
1. agent:{session_id}:current_version --> int (stores the value of the current verion)
2. agent:{session_id}:latest_version --> int (stores the latest version, by extension all the versions since it's 
monotonically increasing) 
3. agent:{session_id}:search:v{version} --> SearchState (stores each version of search state)

NON VERSIONED KEYS
result_key = f"agent:{session_id}:result"
display_key = f"agent:{session_id}:display"
conversation_key = f"agent:{session_id}:conversation"
"""

def get_or_create_session(session_id: str, user_message: str):

    result_key = f"agent:{session_id}:result"
    display_key = f"agent:{session_id}:display"
    conversation_key = f"agent:{session_id}:conversation"

    latest_version_key = f"agent:{session_id}:latest_version"
    current_version_key = f"agent:{session_id}:current_version"

    current_version_raw = redis_client.get(current_version_key)

    # -------------------------
    # Existing session
    # -------------------------
    if current_version_raw is not None:

        current_version = int(current_version_raw)

        current_search_state_key = f"agent:{session_id}:search:v{current_version}"

        current_search_state = SearchState.model_validate_json(
            redis_client.get(current_search_state_key)
        )

        result_state = ResultState.model_validate_json(
            redis_client.get(result_key)
        )

        display_state = DisplayState.model_validate_json(
            redis_client.get(display_key)
        )

        #add latest user message
        redis_client.rpush(
            conversation_key,
            json.dumps({"role": "user", "message": user_message, "version": current_version})
        )
        #reads last 100 conversations from the redis list 
        messages = redis_client.lrange(conversation_key, -100, -1)
        conversation = [
            json.loads(message)
            for message in messages
        ]

        #extend TTL 
        refresh_session_ttl(
            session_id,
            latest_version_key,
            current_version_key,
            result_key,
            display_key,
            conversation_key
        )

        return (current_search_state, result_state, display_state, conversation, 
        current_version)

    # -------------------------
    # New session
    # -------------------------

    current_version = 0

    current_search_state = SearchState(
        session_id=session_id
    )

    result_state = ResultState(
        session_id=session_id
    )

    display_state = DisplayState(
        session_id=session_id
    )

    current_search_state_key = (
        f"agent:{session_id}:search:v{current_version}"
    )

    # Initialize latest version counter
    redis_client.set(
        latest_version_key,
        current_version,
        ex=SESSION_TTL
    )

    # Initialize current SearchState pointer
    redis_client.set(
        current_version_key,
        current_version,
        ex=SESSION_TTL
    )


    # Save SearchState v0
    redis_client.set(
        current_search_state_key,
        current_search_state.model_dump_json(),
        ex=SESSION_TTL
    )

    # Save ResultState
    redis_client.set(
        result_key,
        result_state.model_dump_json(),
        ex=SESSION_TTL
    )

    # Save DisplayState
    redis_client.set(
        display_key,
        display_state.model_dump_json(),
        ex=SESSION_TTL
    )

    # Initialize conversation with first user message
    first_message = {"role": "user", "message": user_message, "version": current_version}

    redis_client.rpush(
        conversation_key,
        json.dumps(first_message)
    )
    redis_client.expire(
        conversation_key,
        SESSION_TTL
    )

    conversation = [first_message]

    return (current_search_state, result_state, display_state, conversation, 
        current_version)