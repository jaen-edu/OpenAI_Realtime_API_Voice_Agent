from voice_agent.adapter.transcript_store import FileTranscriptStore, render_markdown
from voice_agent.domain.conversation import Conversation
from voice_agent.domain.turn import Role, Turn


def test_render_markdown_includes_speaker_and_text():
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="안녕"))
    convo.add_turn(Turn(role=Role.ASSISTANT, text="반가워요"))

    out = render_markdown(convo)

    assert "user" in out
    assert "assistant" in out
    assert "안녕" in out
    assert "반가워요" in out


def test_file_transcript_store_saves_inside_directory(tmp_path):
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="회의록 저장"))
    store = FileTranscriptStore(tmp_path / "transcripts")

    store.save("../room:42?", convo)

    saved = tmp_path / "transcripts" / "room42.md"
    assert saved.exists()
    assert "회의록 저장" in saved.read_text(encoding="utf-8")


def test_file_transcript_store_falls_back_to_session_name(tmp_path):
    convo = Conversation()
    store = FileTranscriptStore(tmp_path)

    store.save("../??", convo)

    assert (tmp_path / "session.md").exists()