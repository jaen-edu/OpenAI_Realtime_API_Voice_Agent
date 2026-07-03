from dotenv import load_dotenv

from voice_agent.adapter.openai_realtime import OpenAIRealtimeAdapter
from voice_agent.adapter.websocket_connection import WebSocketConnection
from voice_agent.domain.session_config import SessionConfig

load_dotenv()  # .env의 OPENAI_API_KEY 로딩

# 모델은 한 곳(SessionConfig)에서만 정하고, 접속 URL과 session.update가 같은 값을 쓰게 한다.
config = SessionConfig()
adapter = OpenAIRealtimeAdapter(
    connection=WebSocketConnection(model=config.model),  # URL의 ?model= 도 같은 모델로
)
adapter.open(config)                                     # session.update의 model 도 같은 값
print("어시스턴트:", adapter.send_user_text("한국어로 짧게 인사해줘."))
adapter.close()