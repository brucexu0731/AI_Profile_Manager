import requests

from langgraph_agent.models import CandidateFilters

FILTER_API_URL = "http://localhost:8080/agents/filter"


def call_filter_api(payload: dict) -> set[int]:
    response = requests.post(
        FILTER_API_URL,
        json=payload,
        timeout=20
    )

    if not response.ok:
        print("STATUS:", response.status_code)
        print("BODY:", response.text)

    response.raise_for_status()

    # Assuming backend returns candidate IDs
    return set(response.json())


def intersect_results(
    current_ids: set[int] | None,
    new_ids: set[int]
) -> set[int]:
    if current_ids is None:
        return new_ids

    return current_ids & new_ids


def process_nested_filter(
    field: str,
    groups: list[list[str]],
    status_field: str | None = None,
    status_value: str | None = None
) -> set[int] | None:

    result_ids = None

    for group in groups:
        if not group:
            continue

        payload = {
            field: group
        }

        if status_field is not None:
            payload[status_field] = status_value

        ids = call_filter_api(payload)

        result_ids = intersect_results(
            result_ids,
            ids
        )

    return result_ids


def filter_sql(filters: CandidateFilters) -> list[int]:

    final_ids: set[int] | None = None

    # ---------------------------------
    # 1. Simple filters
    # ---------------------------------

    simple_payload = {}

    field_mapping = {
        "ids": "ids",
        "name": "name",
        "phone_number": "phoneNumber",
        "email": "email",
        "highest_degree": "highestDegree",
        "add_by": "addBy",
    }

    filters_dict = filters.model_dump(exclude_none=True)

    for python_field, api_field in field_mapping.items():
        if filters_dict.get(python_field):
            simple_payload[api_field] = filters_dict[python_field]

    if simple_payload:
        ids = call_filter_api(simple_payload)

        final_ids = intersect_results(
            final_ids,
            ids
        )

    # ---------------------------------
    # 2. Industry
    # ---------------------------------

    industry_ids = process_nested_filter(
        field="industry",
        groups=filters.industry or []
    )

    if industry_ids is not None:
        final_ids = intersect_results(
            final_ids,
            industry_ids
        )

    # ---------------------------------
    # 3. Current company
    # ---------------------------------

    if filters.current_company:

        ids = call_filter_api({
            "company": filters.current_company,
            "companyStatus": "current"
        })

        final_ids = intersect_results(
            final_ids,
            ids
        )

    # ---------------------------------
    # 4. All companies
    # ---------------------------------

    company_ids = process_nested_filter(
        field="company",
        groups=filters.all_companies or [],
        status_field="companyStatus",
        status_value="all"
    )

    if company_ids is not None:
        final_ids = intersect_results(
            final_ids,
            company_ids
        )

    # ---------------------------------
    # 5. Current title
    # ---------------------------------

    if filters.current_title:

        ids = call_filter_api({
            "title": filters.current_title,
            "titleStatus": "current"
        })

        final_ids = intersect_results(
            final_ids,
            ids
        )

    # ---------------------------------
    # 6. All titles
    # ---------------------------------

    title_ids = process_nested_filter(
        field="title",
        groups=filters.all_titles or [],
        status_field="titleStatus",
        status_value="all"
    )

    if title_ids is not None:
        final_ids = intersect_results(
            final_ids,
            title_ids
        )

    return list(final_ids or [])