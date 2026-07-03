from voice_agent.domain.conversation import Conversation
from voice_agent.domain.summary import summarize
from voice_agent.domain.turn import Role, Turn


def test_summarize_includes_turn_count_and_first_user_preview():
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="안녕하세요, 오늘 일정 정리해줘"))
    convo.add_turn(Turn(role=Role.ASSISTANT, text="오늘 일정은 오전 회의와 오후 리뷰입니다."))

    summary = summarize(convo)

    assert "2" in summary
    assert "안녕하세요, 오늘 일정 정리해줘" in summary


def test_summarize_empty_conversation_returns_empty_label():
    convo = Conversation()

    assert summarize(convo) == "빈 대화"