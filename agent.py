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

    def call(self, message: str):
        self.current_loop_history.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=openai_model,
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                *self.current_loop_history
            ]
        )
        result = response.choices[0].message.content

        self.current_loop_history.append({"role": "assistant", "content": json.loads(result)})

        return json.loads(result)



