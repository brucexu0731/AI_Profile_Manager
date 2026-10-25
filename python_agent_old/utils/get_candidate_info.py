import requests 

PROFILE_API_URL = "http://localhost:8080/agents/candidate-basic-info"

def get_candidate_info(ids: list[int]) -> list[dict]:

    response = requests.post(
        PROFILE_API_URL,
        json = {"ids": ids}
    )

    response.raise_for_status()

    return response.json()