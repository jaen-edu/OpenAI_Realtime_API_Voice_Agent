from pathlib import Path

from voice_agent.domain.conversation import Conversation
from voice_agent.domain.turn import Turn
from voice_agent.usecase.ports import TranscriptStorePort


def _speaker(turn: Turn) -> str:
    return turn.role.value


def _render_turn(turn: Turn) -> str:
    return f"## {_speaker(turn)}\n\n{turn.text}"


def render_markdown(conversation: Conversation) -> str:
    return "\n\n".join(_render_turn(turn) for turn in conversation.turns)


def _normalize_session_id(session_id: str) -> str:
    normalized = "".join(
        char for char in session_id if char.isalnum() or char in "-_"
    )
    return normalized or "session"


class FileTranscriptStore(TranscriptStorePort):
    def __init__(self, directory: str | Path):
        self._directory = Path(directory)

    def save(self, session_id: str, conversation: Conversation) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        safe_id = _normalize_session_id(session_id)
        path = self._directory / f"{safe_id}.md"
        path.write_text(render_markdown(conversation), encoding="utf-8")