from voice_agent.domain.conversation import Conversation      # 대화(턴 모음)
from voice_agent.domain.session_config import SessionConfig   # 세션 설정 값객체
from voice_agent.usecase.start_conversation import StartConversation  # 아직 없음 → RED
from usecase.fakes import FakeRealtimeSession

# class FakeRealtimeSession:
#     """이 테스트에 필요한 만큼만 가진 가짜 세션.

#     StartConversation은 open()만 쓰므로, 나머지 메서드는 '모양만' 맞춰 둔다.
#     (포트의 세 메서드를 다 갖춰야 타입상 세션으로 인정된다.)
#     """

#     def __init__(self):
#         # opened_with: open()이 '어떤 설정으로' 호출됐는지 저장(검증용).
#         #   아직 안 열렸으면 None.
#         self.opened_with: SessionConfig | None = None

#     def open(self, config: SessionConfig) -> None:
#         self.opened_with = config   # 넘어온 설정을 그대로 기록해 둔다

#     def send_user_text(self, text: str) -> str:
#         return ""   # 이 테스트에선 안 쓰지만, 포트 모양을 맞추려 빈 문자열 반환

#     def close(self) -> None:
#         pass        # 이 테스트에선 할 일 없음(모양만 충족)


def test_start_opens_session_and_returns_empty_conversation():
    session = FakeRealtimeSession()                 # 준비: 가짜 세션
    usecase = StartConversation(session=session)    # 유즈케이스에 주입(DI)

    convo = usecase.execute(SessionConfig())        # 실행: 기본 설정으로 대화 시작

    # 검증 1: open()이 호출됐다(기록이 None이 아니다).
    assert session.opened_with is not None
    # 검증 2: 그때 넘어간 설정의 모델이 기본값이다.
    assert session.opened_with.model == "gpt-realtime"
    # 검증 3: 돌려받은 것이 Conversation 타입이고,
    assert isinstance(convo, Conversation)
    # 검증 4: 아직 발화가 없어 비어 있다.
    assert convo.turns == []