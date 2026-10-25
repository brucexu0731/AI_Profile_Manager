
    # "filters": {
    #                 "current_company": [],
    #                 "current_title": [],
    #                 "all_companies": [],
    #                 "all_titles": [],
    #                 "highest_degree": [],
    #                 "industry": [],
    #                 "add_by": [],
    #                 "name": [],
    #                 "phone_number": [],
    #                 "email": [],
    #                 "ids": []
    #             },
    
    # Allowed filters:
    # - ids: list[int]
    # - name: list[str]
    # - phone_number: list[str]
    # - email: list[str]
    # - highest_degree: list[str]
    # - industry: list[list[str]]
    # - add_by: list[str]
    # - current_company: list[str]
    # - all_companies: list[list[str]]
    # - current_title: list[str]
    # - all_titles: list[list[str]]

    #the api takes a body like this:
    # public record AgentCandidateFiltersDTO(
    #     List<Long> ids,

    #     List<String> name,
    #     List<String> phoneNumber,
    #     List<String> email,
    #     List<String> highestDegree, //list of options
    #     List<String> industry,
    #     List<String> addBy,

    #     List<String> company,
    #     String companyStatus, //all or current
    #     List<String> title,
    #     String titleStatus //all or current
    # ) {
    # }

    #1. takes in a search state
    #2. Grab all the list filters first:
    # ids, name, phone_number, email, highest_degree, add_by --> send those over, get result 1
    #3. for nested lists, the backend can only handle 1 list at a time, so unpack them into 
    # single lists and send them over one by one --> get results for each and combine using AND 
    # for example, if i have "industry": ["software engineer", "consulting"], ["fintech"],
    # i would make two requests sending over {"industry": ["software engineer", "consulting"]}, 
    # "industry": ["fintech"]}, and then join those results together using inner join 
    # 4. if current company, send over the company list with company status as current, same for title
    # 5. if all companies or all titles, do the same with nested lists but every time send over 
    # company status or title status as all
    # might be easier to write a separate function to handle each of industry, all companies and all titles

import requests


FILTER_API_URL = "http://localhost:8080/agents/filter"


def call_filter_api(payload: dict) -> set[int]:
    response = requests.post(
        FILTER_API_URL,
        json=payload
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


def filter_and_rank(filters: dict):

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

    for python_field, api_field in field_mapping.items():
        if filters.get(python_field):
            simple_payload[api_field] = filters[python_field]

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
        groups=filters.get("industry", [])
    )

    if industry_ids is not None:
        final_ids = intersect_results(
            final_ids,
            industry_ids
        )

    # ---------------------------------
    # 3. Current company
    # ---------------------------------

    if filters.get("current_company"):

        ids = call_filter_api({
            "company": filters["current_company"],
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
        groups=filters.get("all_companies", []),
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

    if filters.get("current_title"):

        ids = call_filter_api({
            "title": filters["current_title"],
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
        groups=filters.get("all_titles", []),
        status_field="titleStatus",
        status_value="all"
    )

    if title_ids is not None:
        final_ids = intersect_results(
            final_ids,
            title_ids
        )

    return list(final_ids or [])