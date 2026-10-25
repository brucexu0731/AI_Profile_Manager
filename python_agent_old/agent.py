import os
from dotenv import load_dotenv

from openai import OpenAI
from langchain_openai import ChatOpenAI
from typing import TypedDict
from pydantic import BaseModel
import redis 
import json

#Load environment variables 
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
openai_model = os.getenv("OPENAI_API_MODEL")

client = OpenAI(api_key=openai_key) #open ai's api client 
model = ChatOpenAI(api_key=openai_key, model=openai_model) #langchain's openai wrapper


### Setting up the Agent ###
def sse(data):
    return f"data: {json.dumps(data)}\n\n"

class Agent():

    def __init__(self, 
        system_prompt, current_version, session_id):

        self.session_id = session_id
        self.system_prompt = system_prompt
        self.current_version = current_version
        self.result_key = f"agent:{session_id}:result"
        self.display_key = f"agent:{session_id}:display"
        self.conversation_key = f"agent:{session_id}:conversation"

        self.current_version_key = f"agent:{session_id}:current_version"
        self.latest_version_key = f"agent:{session_id}:latest_version"

        self.current_loop_history = []
    
    def _get_search_state_key(self, version: int) -> str:
        return f"agent:{self.session_id}:search:v{version}"

    def call(self, message: str | dict):
        if not isinstance(message, str):
            message = json.dumps(message)
            
        self.current_loop_history.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=openai_model,
            #temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                *self.current_loop_history
            ]
        )
        result = response.choices[0].message.content
        parsed_result = json.loads(result)
        clean_result = json.dumps(parsed_result)

        self.current_loop_history.append({"role": "assistant", "content": clean_result})

        return parsed_result



    def call_stream(self, message: str | dict):
        if not isinstance(message, str):
            message = json.dumps(message)

        self.current_loop_history.append({
            "role": "user",
            "content": message
        })

        stream = client.chat.completions.create(
            model=openai_model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                *self.current_loop_history
            ],
            stream=True
        )

        prefix = '{"action":"SUMMARIZE","html":"'
        suffix = '"}'
        full_result = ""
        prefix_buffer = ""
        html_buffer = ""
        started = False

        for chunk in stream:
            content = chunk.choices[0].delta.content

            if not content:
                continue

            full_result += content

            # Still waiting until we've received the entire fixed prefix
            if not started:
                prefix_buffer += content

                if len(prefix_buffer) < len(prefix):
                    continue

                if not prefix_buffer.startswith(prefix):
                    raise ValueError(
                        f"Unexpected SUMMARIZE response prefix: {prefix_buffer}"
                    )

                # Anything after the prefix is HTML
                html_buffer += prefix_buffer[len(prefix):]
                prefix_buffer = ""
                started = True

            else:
                html_buffer += content

            # Always keep the final len(suffix) characters buffered.
            # This prevents `"}` from being streamed to the frontend.
            if len(html_buffer) > len(suffix):
                send = html_buffer[:-len(suffix)]
                html_buffer = html_buffer[-len(suffix):]

                if send:
                    yield sse({
                        "type": "summarizing",
                        "output": {
                            "html": send
                        }
                    })


        # stream is now finished
        parsed_result = json.loads(full_result)
        clean_result = json.dumps(parsed_result)

        self.current_loop_history.append({
            "role": "assistant",
            "content": clean_result
        })

        return parsed_result