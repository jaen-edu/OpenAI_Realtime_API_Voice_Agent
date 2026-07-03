from voice_agent.domain.conversation import Conversation
from voice_agent.domain.summary import summarize
from voice_agent.domain.turn import Role, Turn
from voice_agent.usecase.save_conversation import SaveConversation


class FakeStore:
    def __init__(self):
        self.saved_session_id: str | None = None
        self.saved_conversation: Conversation | None = None

    def save(self, session_id: str, conversation: Conversation) -> None:
        self.saved_session_id = session_id
        self.saved_conversation = conversation


class FakeSummarizer:
    def __init__(self, summary: str):
        self.summary = summary
        self.called_with: Conversation | None = None

    def summarize(self, conversation: Conversation) -> str:
        self.called_with = conversation
        return self.summary


class BrokenSummarizer:
    def summarize(self, conversation: Conversation) -> str:
        raise RuntimeError("model down")


def test_save_conversation_saves_and_returns_summary():
    store = FakeStore()
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="회의 내용 저장해줘"))
    convo.add_turn(Turn(role=Role.ASSISTANT, text="저장할게요"))
    usecase = SaveConversation(store=store)

    summary = usecase.execute(conversation=convo, session_id="sess-9")

    assert store.saved_session_id == "sess-9"
    assert store.saved_conversation is convo
    assert summary == summarize(convo)


def test_save_conversation_returns_model_summary_when_available():
    store = FakeStore()
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="오늘 대화 요약해줘"))
    summarizer = FakeSummarizer("사용자가 오늘 대화 요약을 요청했다.")
    usecase = SaveConversation(store=store, summarizer=summarizer)

    summary = usecase.execute(conversation=convo, session_id="sess-9")

    assert store.saved_session_id == "sess-9"
    assert summarizer.called_with is convo
    assert summary == "사용자가 오늘 대화 요약을 요청했다."


def test_save_conversation_falls_back_when_model_summary_fails():
    store = FakeStore()
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="요약 실패 시 폴백 확인"))
    usecase = SaveConversation(store=store, summarizer=BrokenSummarizer())

    summary = usecase.execute(conversation=convo, session_id="sess-9")

    assert store.saved_session_id == "sess-9"
    assert summary == summarize(convo)