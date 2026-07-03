from voice_agent.adapter.openai_realtime import OpenAIRealtimeAdapter  # 아직 없음 → RED의 원인
from voice_agent.domain.session_config import SessionConfig            # 세션 설정 값객체 — 2교시
import pytest
from adapter.fakes import FakeConnection 


# class FakeConnection:
#     """테스트용 가짜 연결. 미리 짜둔 서버 이벤트를 차례로 돌려준다.

#     RealtimeConnection(약속)과 같은 메서드 모양(send_event/recv_event/close)을 갖춰,
#     어댑터에 진짜 소켓 대신 끼운다. 실제 네트워크 없이 이벤트 흐름만 검증한다.
#     """

#     def __init__(self, scripted_events: list[dict]):
#         # sent: 어댑터가 '보낸' 이벤트들을 순서대로 쌓아 둔다(무엇을 보냈는지 검증용).
#         self.sent: list[dict] = []
#         # _incoming: 서버가 '보낼' 이벤트 대본. list(...)로 복사해 원본을 건드리지 않는다.
#         self._incoming = list(scripted_events)
#         # closed: close()가 호출됐는지 표시하는 깃발.
#         self.closed = False

#     def send_event(self, event: dict) -> None:
#         # 진짜라면 소켓으로 보내겠지만, 가짜는 '보냈다'고 기록만 한다.
#         self.sent.append(event)

#     def recv_event(self) -> dict:
#         # 대본의 맨 앞(index 0) 이벤트를 꺼내(pop) 하나씩 돌려준다.
#         # → 호출할 때마다 대본이 한 개씩 줄어든다(FIFO, 먼저 넣은 걸 먼저 내보냄).
#         return self._incoming.pop(0)

#     def close(self) -> None:
#         self.closed = True


def test_text_round_trip():
    # 준비: 서버가 '텍스트 조각 두 개 → 완료(done)' 순서로 보낸다고 가정한 대본.
    conn = FakeConnection(scripted_events=[
        {"type": "response.output_text.delta", "delta": "맑고 "},      # 조각 1
        {"type": "response.output_text.delta", "delta": "따뜻해요."},  # 조각 2
        {"type": "response.done", "response": {}},                     # 끝 신호
    ])
    adapter = OpenAIRealtimeAdapter(connection=conn)   # 어댑터에 가짜 연결 주입

    # 실행: 세션을 열고, 사용자 텍스트 한 턴을 보낸다.
    adapter.open(SessionConfig())
    reply = adapter.send_user_text("오늘 날씨 어때?")

    # 검증 1: 흩어진 조각(delta)들이 이어붙어 완성 문장이 된다.
    assert reply == "맑고 따뜻해요."

    # 검증 2: 어댑터가 '맨 처음' 보낸 건 session.update이고, 모델이 올바르다.
    #         (conn.sent[0] = 첫 번째로 보낸 이벤트)
    assert conn.sent[0]["type"] == "session.update"
    assert conn.sent[0]["session"]["model"] == "gpt-realtime"

    # 검증 3: 두 번째로 사용자 입력을 input_text 형태로 전달했다.
    #         중첩 dict를 단계별로 파고들어 실제 텍스트까지 확인한다.
    assert conn.sent[1]["type"] == "conversation.item.create"
    assert conn.sent[1]["item"]["content"][0]["text"] == "오늘 날씨 어때?"

    # 검증 4: 세 번째로 '응답을 만들어달라'(response.create)고 요청했다.
    assert conn.sent[2]["type"] == "response.create"

def test_error_event_raises():
    # 실제 서버 error 이벤트의 모양: message가 error 객체 안에 중첩된다
    conn = FakeConnection(scripted_events=[
        {"type": "error", "error": {"message": "rate limit"}},
    ])
    adapter = OpenAIRealtimeAdapter(connection=conn)
    adapter.open(SessionConfig())

    # send_user_text 도중 error 를 만나면 RuntimeError 가 나야 한다.
    # match= 로 '실제 메시지'가 예외에 실려 오는지까지 확인한다.
    with pytest.raises(RuntimeError, match="rate limit"):
        adapter.send_user_text("안녕")