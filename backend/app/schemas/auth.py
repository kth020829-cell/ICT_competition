from pydantic import BaseModel, Field


class StudentJoinRequest(BaseModel):
    classCode: int = Field(ge=100000, le=999999)
    nickname: str = Field(min_length=1, max_length=20)