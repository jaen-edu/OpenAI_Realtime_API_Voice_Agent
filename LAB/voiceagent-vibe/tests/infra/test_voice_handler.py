from websockets.exceptions import ConnectionClosed

from voice_agent.adapter.async_realtime import AsyncRealtimeSession
from voice_agent.domain.turn import Role
from voice_agent.infra.voice_handler import RealtimeVoiceHandler


class ClosingFakeConnection:
    """자막 한 개를 준 뒤 ConnectionClosed를 던지는 가짜 연결 (= 중지 상황 재현)."""

    def __init__(self):
        self._events = [
            {"type": "response.output_audio_transcript.delta", "delta": "안녕"},
        ]

    async def send_event(self, event: dict) -> None:
        pass

    async def recv_event(self) -> dict:
        if self._events:
            return self._events.pop(0)   # 먼저 자막 한 개를 돌려주고
        raise ConnectionClosed(None, None)   # 그다음 정상 종료(1000 OK) 신호

    async def close(self) -> None:
        pass


class DoneFakeConnection:
    def __init__(self):
        self._events = [
            {"type": "response.created"},
            {"type": "response.output_audio_transcript.delta", "delta": "안녕"},
            {"type": "response.done"},
        ]

    async def send_event(self, event: dict) -> None:
        pass

    async def recv_event(self) -> dict:
        if self._events:
            return self._events.pop(0)
        raise ConnectionClosed(None, None)

    async def close(self) -> None:
        pass


class UserTranscriptFakeConnection:
    def __init__(self):
        self._events = [
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "사용자 질문",
            },
        ]

    async def send_event(self, event: dict) -> None:
        pass

    async def recv_event(self) -> dict:
        if self._events:
            return self._events.pop(0)
        raise ConnectionClosed(None, None)

    async def close(self) -> None:
        pass


class FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeSaveConversation:
    def __init__(self, summary: str = "2개 턴 · 시작: 안녕"):
        self.summary = summary
        self.calls: list[tuple[object, str]] = []

    def execute(self, conversation, session_id: str) -> str:
        self.calls.append((conversation, session_id))
        return self.summary


async def test_read_events_stops_quietly_on_close():
    # 핸들러를 만들고, 내부 세션에 '닫히는 가짜 연결'을 꽂는다.
    handler = RealtimeVoiceHandler()
    handler._session = AsyncRealtimeSession(connection=ClosingFakeConnection())

    # 핵심: ConnectionClosed가 밖으로 새지 않고 '예외 없이' 끝나야 한다.
    # (try/except가 없으면 이 줄에서 예외가 터져 테스트가 실패한다.)
    await handler._read_events()


async def test_read_events_flushes_assistant_buffer_on_response_done():
    handler = RealtimeVoiceHandler()
    handler._session = AsyncRealtimeSession(connection=DoneFakeConnection())

    await handler._read_events()

    assert len(handler._conversation.turns) == 1
    assert handler._conversation.turns[0].role == Role.ASSISTANT
    assert handler._conversation.turns[0].text == "안녕"
    assert handler._assistant_buffer == ""


async def test_shutdown_saves_conversation_summary():
    handler = RealtimeVoiceHandler()
    handler._session = FakeSession()
    fake_save = FakeSaveConversation()
    handler._save = fake_save

    await handler.shutdown()

    assert handler._session.closed is True
    assert fake_save.calls == [(handler._conversation, handler._session_id)]


async def test_read_events_records_user_transcript_completion():
    handler = RealtimeVoiceHandler()
    handler._session = AsyncRealtimeSession(connection=UserTranscriptFakeConnection())

    await handler._read_events()

    assert len(handler._conversation.turns) == 1
    assert handler._conversation.turns[0].role == Role.USER
    assert handler._conversation.turns[0].text == "사용자 질문"