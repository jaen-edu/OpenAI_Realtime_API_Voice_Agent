from voice_agent.adapter.openai_realtime import OpenAIRealtimeAdapter
from voice_agent.adapter.websocket_connection import WebSocketConnection
from voice_agent.domain.conversation import Conversation
from voice_agent.domain.session_config import SessionConfig


def _conversation_lines(conversation: Conversation) -> str:
    return "\n".join(
        f"{turn.role.value}: {turn.text}" for turn in conversation.turns
    )


def _summary_prompt(conversation: Conversation) -> str:
    transcript = _conversation_lines(conversation)
    return (
        "다음 대화를 사람이 읽기 좋은 한 문장으로 요약해줘.\n"
        "대화가 비어 있으면 '빈 대화'라고만 답해줘.\n\n"
        f"{transcript}"
    )


class ModelSummarizer:
    def __init__(self, model: str = "gpt-realtime"):
        self._model = model

    def summarize(self, conversation: Conversation) -> str:
        adapter = OpenAIRealtimeAdapter(WebSocketConnection(model=self._model))
        try:
            adapter.open(SessionConfig(model=self._model))
            return adapter.send_user_text(_summary_prompt(conversation))
        finally:
            adapter.close()