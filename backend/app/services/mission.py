def check_mission(
    mission_type: str | None,
    session_data: dict,
    collection_result: dict | None = None
):

    if not mission_type:
        return False

    result = session_data.get(
        "result",
        {}
    )

    detected_class = result.get(
        "detectedClass"
    )

    # 길에서 쓰레기 줍기
    if mission_type == "STREET_TRASH":
        return True

    # 집에서 쓰레기 버리기
    if mission_type == "HOME_TRASH":
        return True

    # Level 3 이상
    if mission_type == "LEVEL3":

        level = result.get(
            "level",
            0
        )

        return level >= 3

    # 플라스틱 페트병
    if mission_type == "PLASTIC_BOTTLE":

        return (
            detected_class
            == "transparency_plastic_bottle"
        )

    # 새로운 쓰레기

    if mission_type == "NEW_TRASH":

        if not collection_result:
            return False

        return collection_result.get(
            "isNew",
            False
        )

    return False