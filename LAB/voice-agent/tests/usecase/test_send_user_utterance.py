import pytest
# 이 테스트가 쓰는 것들을 가져온다(import).
from voice_agent.domain.conversation import Conversation      # 대화(턴 모음) — 2교시
from voice_agent.domain.session_config import SessionConfig   # 세션 설정 값객체 — 2교시
from voice_agent.domain.turn import Role                      # 발화 주체(USER/ASSISTANT) — 2교시
from voice_agent.usecase.send_user_utterance import SendUserUtterance  # 아직 없음 → RED의 원인
from usecase.fakes import FakeRealtimeSession
# class FakeRealtimeSession:
#     """테스트용 가짜 세션. 진짜 통신 대신, 미리 정한 답을 돌려준다.

#     포트(RealtimeSessionPort)와 '같은 메서드 모양'만 갖추면 되므로,
#     Protocol을 상속하지 않아도 유즈케이스에 그대로 끼울 수 있다(덕 타이핑).
#     """

#     def __init__(self, reply: str):
#         # reply: 이 가짜 세션이 '항상' 돌려줄 어시스턴트 답변(테스트가 미리 정함)
#         self.reply = reply
#         # opened: open()이 호출됐는지 기록하는 깃발(나중에 검증에 쓸 수 있음)
#         self.opened = False
#         # sent_texts: 어떤 사용자 텍스트가 전달됐는지 순서대로 쌓는 기록장
#         self.sent_texts: list[str] = []

#     def open(self, config: SessionConfig) -> None:
#         # 진짜라면 세션을 열겠지만, 가짜는 '열렸다'는 깃발만 세운다
#         self.opened = True

#     def send_user_text(self, text: str) -> str:
#         # 전달받은 텍스트를 기록장에 남기고
#         self.sent_texts.append(text)
#         # 미리 정한 고정 답변을 돌려준다(진짜 통신 없음 → 즉시·무료)
#         return self.reply

#     def close(self) -> None:
#         # 가짜는 '닫혔다' 상태로만 되돌린다
#         self.opened = False


def test_utterance_is_recorded_and_reply_returned():
    # 준비(Arrange): 가짜 세션 + 빈 대화 + 유즈케이스를 조립한다.
    session = FakeRealtimeSession(reply="맑고 따뜻해요.")   # 항상 이 답을 주는 가짜
    convo = Conversation()                                 # 처음엔 턴이 하나도 없는 대화
    # 유즈케이스에 '가짜 세션'과 '대화'를 주입(DI). 진짜 대신 가짜가 들어간다.
    usecase = SendUserUtterance(session=session, conversation=convo)

    # 실행(Act): 사용자가 한마디 한다.
    reply = usecase.execute("오늘 날씨 어때?")

    # 검증(Assert) 1: 어시스턴트 응답이 그대로 반환된다.
    assert reply == "맑고 따뜻해요."

    # 검증 2: 대화에 '사용자 → 어시스턴트' 두 턴이 '순서대로' 쌓였다.
    assert len(convo.turns) == 2                    # 턴이 정확히 2개
    assert convo.turns[0].role == Role.USER         # 첫 턴은 사용자
    assert convo.turns[0].text == "오늘 날씨 어때?"
    assert convo.turns[1].role == Role.ASSISTANT    # 둘째 턴은 어시스턴트
    assert convo.turns[1].text == "맑고 따뜻해요."

    # 검증 3: 가짜 세션에 사용자 텍스트가 '실제로' 전달됐다(유즈케이스가 포트를 올바르게 호출).
    assert session.sent_texts == ["오늘 날씨 어때?"]

def test_empty_utterance_is_rejected():
    usecase = SendUserUtterance(
        session=FakeRealtimeSession(reply="응답"),
        conversation=Conversation(),
    )
    # 빈 문자열/공백만 있는 발화는 ValueError
    with pytest.raises(ValueError):
        usecase.execute("   ")