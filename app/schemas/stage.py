from enum import IntEnum


class StageEnum(IntEnum):
    brainstorm = -1
    outline = 0
    draft_1 = 1
    draft_2 = 2
    draft_3 = 3
    draft_4 = 4
    draft_5 = 5
    draft_6 = 6
    draft_7 = 7
    draft_8 = 8
    draft_9 = 9
    draft_10 = 10
    final = 11


def stage_to_confidence(stage: StageEnum) -> float:
    """
    Convert a stage to a confidence level.
    """
    if stage == StageEnum.brainstorm:
        return 0.1
    elif stage == StageEnum.outline:
        return 0.1
    elif stage == StageEnum.final:
        return 1.0

    return 0.5 + (stage.value / 20.0)
