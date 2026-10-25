from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Self


class WorkExperience(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company: str | None = None
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")


class Education(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    school_name: str | None = Field(default=None, alias="schoolName")
    degree: str | None = Field(
        default=None,
        description="May contain a dual degree as a single string.",
    )
    major: str | None = Field(
        default=None,
        description="May contain multiple majors as a single string.",
    )
    graduation_date: str | None = Field(default=None, alias="graduationDate")


class CandidateProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    email: str | None = None

    skills: list[str] = Field(default_factory=list)
    industry: str | None = Field(default=None, alias="Industry")
    need_visa: bool | None = Field(default=None, alias="needVisa")
    add_date: str | None = Field(default=None, alias="addDate")
    add_by: str | None = Field(default=None, alias="addBy")
    update_date: str | None = Field(default=None, alias="updateDate")
    update_by: str | None = Field(default=None, alias="updateBy")
    candidate_source: str | None = Field(default=None, alias="candidateSource")
    preferred_location: str | None = Field(default=None, alias="preferredLocation")
    preferred_industry: str | None = Field(default=None, alias="preferredIndustry")
    preferred_base_salary: str | None = Field(default=None, alias="preferredBaseSalary")
    preferred_annual_package: str | None = Field(
        default=None, alias="preferredAnnualPackage"
    )
    notice_period: str | None = Field(default=None, alias="noticePeriod")
    additional_info: str | None = Field(default=None, alias="additionalInfo")
    motivation: str | None = None

    work_experience: list[WorkExperience] = Field(
        default_factory=list, alias="workExperience"
    )
    educations: list[Education] = Field(default_factory=list)



class CandidateFilters(BaseModel):
    """Allowed SQL/search filters. Only these fields may appear in filters."""

    model_config = ConfigDict(extra="forbid")

    ids: list[int] | None = Field(
        default=None,
        description="Restrict to a known candidate subset (e.g. currently displayed).",
    )
    name: list[str] | None = None
    phone_number: list[str] | None = Field(
        default=None,
        description="Digits only.",
    )
    email: list[str] | None = None
    highest_degree: list[str] | None = None
    industry: list[list[str]] | None = Field(
        default=None,
        description="Nested: same inner list = OR; separate inner lists = AND.",
    )
    add_by: list[str] | None = None
    current_company: list[str] | None = Field(
        default=None,
        description="Do not set together with all_companies.",
    )
    all_companies: list[list[str]] | None = Field(
        default=None,
        description=(
            "Nested: same inner list = OR; separate inner lists = AND. "
            "Do not set together with current_company."
        ),
    )
    current_title: list[str] | None = Field(
        default=None,
        description="Do not set together with all_titles.",
    )
    all_titles: list[list[str]] | None = Field(
        default=None,
        description=(
            "Nested: same inner list = OR; separate inner lists = AND. "
            "Do not set together with current_title."
        ),
    )

    @model_validator(mode="after")
    def mutually_exclusive_company_and_title(self) -> Self:
        if self.current_company and self.all_companies:
            raise ValueError(
                "Cannot set both current_company and all_companies"
            )
        if self.current_title and self.all_titles:
            raise ValueError(
                "Cannot set both current_title and all_titles"
            )
        return self