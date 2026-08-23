from typing import Any


def check_mission(
    mission_type: str | None,
    session_data: dict[str, Any],
    student_data: dict[str, Any]
) -> bool:

    if not mission_type:
        return False

    result = session_data.get("result", {})

    detected_class = result.get("detectedClass")
    disposal_category = result.get("disposalCategory")

    # ------------------------------------------
    # 1. 길에서 쓰레기 주워서 버리기
    # ------------------------------------------

    if mission_type == "STREET_TRASH":
        return True

    # ------------------------------------------
    # 2. 집에서도 쓰레기 하나 버려보기
    # ------------------------------------------

    if mission_type == "HOME_TRASH":
        return True

    # ------------------------------------------
    # 3. Level 3 이상 쓰레기 버리기
    # ------------------------------------------

    if mission_type == "LEVEL3":

        # AI가 반환한 level을 사용
        detected_level = result.get("level")

        if detected_level is not None:
            return int(detected_level) >= 3

        # level이 result에 없다면 일단 실패
        return False

    # ------------------------------------------
    # 4. 플라스틱 페트병 버려보기
    # ------------------------------------------

    if mission_type == "PLASTIC_BOTTLE":

        if detected_class is None:
            return False

        return detected_class == "plastic_bottle"

    # ------------------------------------------
    # 5. 새로운 쓰레기 버려보기
    # ------------------------------------------

    if mission_type == "NEW_TRASH":

        # Reward에서 도감 수집 결과를 확인할 수 있도록
        # session_data에 collection 정보를 넣어서 사용
        collection = session_data.get(
            "collection",
            {}
        )

        return collection.get("isNew", False)

    return False