import requests

from langgraph_agent.models import CandidateProfile

PROFILE_API_URL = "http://localhost:8080/agents/candidate-basic-info"


def get_candidate_info(ids: list[int]) -> dict[int, CandidateProfile]:
    response = requests.post(
        PROFILE_API_URL,
        json={"ids": ids},
    )
    response.raise_for_status()

    profiles = [
        CandidateProfile.model_validate(item) for item in response.json()
    ]
    return {profile.id: profile for profile in profiles}