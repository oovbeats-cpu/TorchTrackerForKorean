"""Sessions API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from titrack.api.dependencies import get_repository
from titrack.db.repository import Repository

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    name: Optional[str] = None  # None이면 자동 생성 "Session N"


class UpdateSessionNameRequest(BaseModel):
    """Request to update a session name."""

    name: str


class CompareSessionsRequest(BaseModel):
    """Request to compare sessions."""

    session_ids: list[int]  # 2~3개


@router.post("")
def create_session(
    request: Request,
    body: CreateSessionRequest = CreateSessionRequest(),
    repo: Repository = Depends(get_repository),
) -> dict:
    """세션 저장 & 초기화

    1. 현재 session_id=NULL인 런들을 새 세션으로 묶음
    2. TimeTracker 상태를 세션에 스냅샷 저장
    3. TimeTracker 리셋 (새 세션 시작 준비)
    """
    time_tracker = getattr(request.app.state, "time_tracker", None)

    # TimeTracker에서 현재 시간 가져오기
    total_play_seconds = 0.0
    mapping_play_seconds = 0.0
    if time_tracker:
        total_play_seconds = time_tracker.total_play_seconds
        mapping_play_seconds = time_tracker.mapping_play_seconds

    # 세션 이름 결정
    name = body.name
    if not name:
        # 기존 세션 수 기반으로 자동 이름 생성
        existing = repo.get_sessions()
        name = f"Session {len(existing) + 1}"

    # 세션 생성 (런 연결 + 통계 스냅샷)
    session = repo.create_session(name, total_play_seconds, mapping_play_seconds)

    # TimeTracker 리셋
    if time_tracker:
        time_tracker.reset_all()

    return {"success": True, "session": session}


@router.get("")
def list_sessions(
    repo: Repository = Depends(get_repository),
) -> dict:
    """세션 목록 조회"""
    sessions = repo.get_sessions()
    return {"sessions": sessions}


@router.get("/{session_id}/stats")
def get_session_stats(
    session_id: int,
    repo: Repository = Depends(get_repository),
) -> dict:
    """세션 상세 통계"""
    stats = repo.get_session_stats(session_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Session not found")
    return stats


@router.patch("/{session_id}")
def update_session_name(
    session_id: int,
    body: UpdateSessionNameRequest,
    repo: Repository = Depends(get_repository),
) -> dict:
    """세션 이름 변경"""
    success = repo.update_session_name(session_id, body.name)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": success}


@router.delete("/{session_id}")
def delete_session(
    session_id: int,
    repo: Repository = Depends(get_repository),
) -> dict:
    """세션 삭제"""
    success = repo.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": success}


@router.post("/compare")
def compare_sessions(
    body: CompareSessionsRequest,
    repo: Repository = Depends(get_repository),
) -> dict:
    """세션 비교 분석"""
    if len(body.session_ids) < 2 or len(body.session_ids) > 3:
        raise HTTPException(
            status_code=400, detail="2~3개의 세션을 선택해주세요"
        )

    result = repo.compare_sessions(body.session_ids)
    return result
