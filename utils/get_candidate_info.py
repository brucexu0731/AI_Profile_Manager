import requests 

PROFILE_API_URL = "http://localhost:8080/agents/candidate-basic-info"

def get_candidate_info(ids: list[int]) -> dict:

    response = requests.post(
        PROFILE_API_URL,
        json = ids
    )

    return json.loads(response)