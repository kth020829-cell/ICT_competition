"""백엔드 → AI 추론 서버 요청 스키마 (지시서 §5.4).

`multipart/form-data` 로 이미지 + 아래 필드가 들어온다.
프론트엔드는 AI 서버를 직접 호출하지 않는다. (지시서 §5.1)
"""

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import Phase, YoloClass


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    scan_session_id: str = Field(alias="scanSessionId")
    phase: Phase = Phase.BEFORE
    #: 지자체 배출 기준 라우팅 키. 기본값은 충북 청주.
    region_code: str = Field(default="KR-43-CHEONGJU", alias="regionCode")
    #: 백엔드가 품목을 이미 아는 경우의 힌트. 강제가 아니라 힌트다.
    expected_class: YoloClass | None = Field(default=None, alias="expectedClass")
    #: AFTER 단계에서 비교 대상이 되는 Before 분석 id.
    before_analysis_id: str | None = Field(default=None, alias="beforeAnalysisId")
    #: 아이스팩처럼 사진으로 판정 불가해 사용자 선택으로 분기하는 값. (지시서 §4.4)
    user_choice: str | None = Field(default=None, alias="userChoice")


def analyze_form(
    scanSessionId: str = Form(...),
    phase: Phase = Form(Phase.BEFORE),
    regionCode: str = Form("KR-43-CHEONGJU"),
    expectedClass: YoloClass | None = Form(None),
    beforeAnalysisId: str | None = Form(None),
    userChoice: str | None = Form(None),
) -> AnalyzeRequest:
    """multipart 폼 필드를 AnalyzeRequest로 모으는 FastAPI 의존성."""
    return AnalyzeRequest(
        scanSessionId=scanSessionId,
        phase=phase,
        regionCode=regionCode,
        expectedClass=expectedClass,
        beforeAnalysisId=beforeAnalysisId,
        userChoice=userChoice,
    )


class CompareRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    before_analysis_id: str = Field(alias="beforeAnalysisId")
    after_analysis_id: str = Field(alias="afterAnalysisId")
