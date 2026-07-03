from voice_agent.domain.conversation import Conversation
from voice_agent.domain.summary import summarize
from voice_agent.usecase.ports import SummarizerPort, TranscriptStorePort


class SaveConversation:
    def __init__(
        self,
        store: TranscriptStorePort,
        summarizer: SummarizerPort | None = None,
    ):
        self._store = store
        self._summarizer = summarizer

    def execute(self, conversation: Conversation, session_id: str) -> str:
        self._store.save(session_id, conversation)
        if self._summarizer is not None:
            try:
                return self._summarizer.summarize(conversation)
            except Exception:
                pass
        return summarize(conversation)