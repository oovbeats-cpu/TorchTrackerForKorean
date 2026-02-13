"""Log line parser - converts raw lines to typed events."""

from titrack.core.models import (
    ParsedBagEvent,
    ParsedContractSettingEvent,
    ParsedContextMarker,
    ParsedEvent,
    ParsedLevelEvent,
    ParsedLevelIdEvent,
    ParsedPlayerDataEvent,
    ParsedViewEvent,
)
from titrack.parser.patterns import (
    BAG_MODIFY_PATTERN,
    BAG_INIT_PATTERN,
    CONTRACT_SETTING_PATTERN,
    ITEM_CHANGE_PATTERN,
    LEVEL_EVENT_PATTERN,
    LEVEL_ID_PATTERN,
    CUR_RUN_VIEW_PATTERN,
)
from titrack.parser.player_parser import parse_player_line


def parse_line(line: str) -> ParsedEvent:
    """
    단일 로그 라인을 타입별 이벤트로 파싱.

    정규식 패턴 매칭으로 로그 라인 타입 식별 후 적절한 이벤트 객체 생성.
    BagMgr, ItemChange, Level, Player, View, Contract 등 7가지 이벤트 타입 지원.

    Args:
        line: 원본 로그 라인 (개행 문자 포함 가능)

    Returns:
        ParsedEvent 객체 (매칭 실패 시 None)
        - ParsedBagEvent: 인벤토리 변경 (획득/소비/정렬)
        - ParsedContextMarker: 컨텍스트 마커 (PickItems, Spv3Open 등)
        - ParsedLevelEvent: 존 전환 (맵 진입/퇴장)
        - ParsedLevelIdEvent: 레벨 메타데이터 (LevelId, LevelType, LevelUid)
        - ParsedPlayerDataEvent: 플레이어 정보 (캐릭터 변경 감지)
        - ParsedViewEvent: UI 뷰 변경 (자동 일시정지용)
        - ParsedContractSettingEvent: 계약 설정 변경
    """
    line = line.rstrip("\r\n")

    if not line:
        return None

    # Try BagMgr modification
    match = BAG_MODIFY_PATTERN.search(line)
    if match:
        return ParsedBagEvent(
            page_id=int(match.group("page_id")),
            slot_id=int(match.group("slot_id")),
            config_base_id=int(match.group("config_base_id")),
            num=int(match.group("num")),
            raw_line=line,
            is_init=False,
        )

    # Try BagMgr init/snapshot (triggered by sorting inventory)
    match = BAG_INIT_PATTERN.search(line)
    if match:
        return ParsedBagEvent(
            page_id=int(match.group("page_id")),
            slot_id=int(match.group("slot_id")),
            config_base_id=int(match.group("config_base_id")),
            num=int(match.group("num")),
            raw_line=line,
            is_init=True,
        )

    # Try ItemChange context marker
    match = ITEM_CHANGE_PATTERN.search(line)
    if match:
        return ParsedContextMarker(
            proto_name=match.group("proto_name"),
            is_start=match.group("marker") == "start",
            raw_line=line,
        )

    # Try level event
    match = LEVEL_EVENT_PATTERN.search(line)
    if match:
        return ParsedLevelEvent(
            event_type=match.group("event_type"),
            level_info=match.group("level_info").strip(),
            raw_line=line,
        )

    # Try LevelId event (for zone differentiation)
    match = LEVEL_ID_PATTERN.search(line)
    if match:
        return ParsedLevelIdEvent(
            level_uid=int(match.group("level_uid")),
            level_type=int(match.group("level_type")),
            level_id=int(match.group("level_id")),
            raw_line=line,
        )

    # Try player data (for character detection)
    player_data = parse_player_line(line)
    if player_data:
        return ParsedPlayerDataEvent(
            name=player_data.get("name"),
            level=player_data.get("level"),
            season_id=player_data.get("season_id"),
            hero_id=player_data.get("hero_id"),
            player_id=player_data.get("player_id"),
            raw_line=line,
        )

    # Try CurRunView (for UI view-based auto-pause)
    match = CUR_RUN_VIEW_PATTERN.search(line)
    if match:
        return ParsedViewEvent(
            view_id=match.group("view_id"),
            view_name=match.group("view_name"),
            raw_line=line,
        )

    # Try contract setting change
    match = CONTRACT_SETTING_PATTERN.search(line)
    if match:
        return ParsedContractSettingEvent(
            contract_name=match.group("contract_name"),
            raw_line=line,
        )

    return None


def parse_lines(lines: list[str]) -> list[ParsedEvent]:
    """
    여러 로그 라인을 일괄 파싱.

    Args:
        lines: 원본 로그 라인 리스트

    Returns:
        파싱된 이벤트 리스트 (None 값 필터링됨)
    """
    events = [parse_line(line) for line in lines]
    return [e for e in events if e is not None]
