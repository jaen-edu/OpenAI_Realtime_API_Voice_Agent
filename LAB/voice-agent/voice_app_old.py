import gradio as gr
from dotenv import load_dotenv
from fastapi import FastAPI
from fastrtc import Stream

from voice_agent.infra.voice_handler import RealtimeVoiceHandler

load_dotenv()  # .env의 OPENAI_API_KEY 로딩

stream = Stream(
    handler=RealtimeVoiceHandler(),
    modality="audio",
    mode="send-receive",
)

app = FastAPI()
stream.mount(app)                                   # WebRTC 시그널링 엔드포인트
app = gr.mount_gradio_app(app, stream.ui, path="/ui")   # 마이크 UI를 /ui 에 붙인다


@app.get("/")
def index():
    return {"status": "voice agent up", "ui": "/ui"}