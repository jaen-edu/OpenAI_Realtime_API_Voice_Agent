from voice_agent.domain.conversation import Conversation
from voice_agent.domain.turn import Role


def _first_user_preview(conversation: Conversation) -> str:
    for turn in conversation.turns:
        if turn.role == Role.USER:
            return turn.text
    return ""


def summarize(conversation: Conversation) -> str:
    if not conversation.turns:
        return "빈 대화"
    preview = _first_user_preview(conversation)
    return f"{len(conversation.turns)}개 턴 · 시작: {preview}"