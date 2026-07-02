# 5교시 — FastRTC 오디오 입력 결합 (async 스트리밍 + 전사)

> **이 교시가 끝나면** 브라우저 마이크 음성이 **실시간으로 Realtime에 흘러 들어가고**, 어시스턴트의 응답 **전사(자막)가 터미널에 뜹니다.** 여기서 처음으로 **비동기(async)** 와 오디오 스트리밍이 등장합니다. (음성 재생·바지인은 6교시)

---

## 0. 이 교시에 만드는 것 (한눈에)

4교시는 "텍스트 한 턴"이었죠. 이 교시에는 **음성이 끊김 없이 흐르는** 구조로 바꿉니다.

```
[내 목소리] → 브라우저 마이크
   → FastRTC (AsyncStreamHandler.receive)        ← 오디오 프레임 도착
      → AsyncRealtimeSession.send_audio           ← PCM을 base64로 Realtime에 append
         → OpenAI Realtime (서버 VAD가 말끝 감지 → 응답 생성)
      ← 이벤트 스트림 (response.output_audio_transcript.delta)
   → 전사 텍스트를 터미널에 출력   ← 이 교시의 결과물
```

> ⚠️ **이 교시에는 소리를 재생하지 않습니다.** 말하면 **응답 자막이 터미널에 흐르는 것**이 5교시의 완성 신호입니다. 실제 음성 재생과 끼어들기(바지인)는 6교시에서 `emit`으로 얹습니다.

---

## 🧭 잠깐, 배경지식

이 교시의 열쇠인 **비동기(async)**를 짚습니다. 지금까지(1~4교시)의 코드는 모두 **동기(synchronous)**였습니다.

**① 동기 vs 비동기.** 동기는 **한 줄이 끝나야 다음 줄로** 갑니다. 식당에서 종업원이 한 손님의 주문·조리·서빙을 끝낼 때까지 다음 손님을 아예 못 받는 것과 같습니다. 비동기는 **기다리는 동안 다른 일을 처리**합니다. 종업원이 주방에 주문을 넣어두고(기다리는 사이) 다른 손님을 받는 식입니다. 음성 대화는 "내가 말하는 중에도 서버가 자막을 보내는" 등 여러 일이 겹치므로 비동기가 맞습니다.

**② `async def` / `await`.** 비동기 함수는 `async def`로 정의합니다. 그 안에서 오래 걸리는 작업 앞에 **`await`**를 붙이면 "이 작업이 끝날 때까지 **잠깐 자리를 양보**하고, 끝나면 이어서 진행"이라는 뜻이 됩니다. 양보한 그 틈에 다른 작업이 돌아갑니다.

**③ 이벤트 루프(event loop).** 이 "양보와 재개(yield, resume)"를 지휘하는 관제탑이 이벤트 루프입니다. 여러 async 작업을 번갈아 조금씩 돌립니다. 그래서 한 작업이 `await`로 양보하지 않고 자리를 독차지하면, 다른 작업(예: 연결)이 **굶어서** 멈춥니다 — 이게 STEP 5에서 만날 `emit` 함정의 정체입니다.

**④ async 제너레이터 / `async for`.** 서버 이벤트처럼 **끝을 모르고 계속 흘러오는** 데이터는 `async for`로 하나씩 받아 처리합니다. 이런 흐름을 내보내는 함수를 async 제너레이터(`yield`를 쓰는 async 함수)라고 합니다.

> 💡 아래 "1. 개념 빠르게 잡기"에서 FastRTC 핸들러가 이 비동기를 어떻게 쓰는지 이어서 봅니다.

---

## 1. 개념 빠르게 잡기

### 왜 갑자기 async(비동기)인가?

> 4교시의 텍스트 어댑터는 "보내고 → 응답 다 올 때까지 기다림"이었습니다(동기). 하지만 음성은 **내가 말하는 중에도 서버가 무언가를 보내고**, 여러 일이 **동시에** 벌어집니다. 이걸 "기다렸다 처리"로 짜면 멈춰버립니다.
>
> **async**는 "한 가지를 기다리는 동안 다른 일도 할 수 있게" 해주는 방식입니다. 마이크 입력 보내기 / 서버 이벤트 받기 / 자막 출력이 서로를 막지 않고 흐릅니다.

💡 **핵심 규칙**: async 함수는 `async def`로 정의하고, 기다릴 때 `await`를 씁니다. "이 줄에서 잠깐 양보하고, 끝나면 이어서" 라는 뜻입니다.

### FastRTC의 `AsyncStreamHandler` — 4개의 약속

speech-to-speech는 FastRTC의 **`AsyncStreamHandler`**로 만듭니다. 우리가 채워야 할 메서드는 네 개입니다.

| 메서드 | 언제 불리나 | 우리가 할 일 |
|---|---|---|
| `start_up()` | 스트림 시작 시 1번 | Realtime에 **연결**하고, 서버 이벤트 **읽기 루프** 시작 |
| `receive(frame)` | 마이크 프레임이 올 때마다 | 오디오를 Realtime에 **append** |
| `emit()` | 재생할 프레임이 필요할 때 | (5교시엔 재생 없음 → `await asyncio.sleep(...)` 후 `None`. **반드시 await로 양보**) |
| `copy()` | 접속자마다 | 핸들러 **새 인스턴스** 반환 |

- emit : 재생하기 위해 evnet loop에서 꺼내기 
> 💡 FastRTC가 마이크·스피커·WebRTC·VAD를 다 처리해 줍니다. **우리는 "받은 오디오로 무엇을 할지"만** 채우면 됩니다.

### Realtime에 오디오 보내기 — `input_audio_buffer.append`

> 음성은 텍스트처럼 한 번에 안 보냅니다. **조각(프레임)마다** `input_audio_buffer.append` 이벤트로 흘려보냅니다. 오디오는 **PCM16 → base64 문자열**로 인코딩합니다. 서버 **VAD(Voice Activity Detection)**가 "말이 끝났다"를 자동 감지해 응답을 만듭니다(우리가 commit/response.create를 안 해도 됨).
>
> PCM16(음성 아날로그정보를 디지털로 변환)

받는 쪽에서 이 교시에 쓰는 이벤트는 하나입니다.

| 서버 이벤트 | 의미 |
|---|---|
| `response.output_audio_transcript.delta` | 어시스턴트 음성의 **자막**이 조각조각 도착 (이 교시에 화면에 출력) |
| `response.output_audio.delta` | 실제 **음성 바이트** (6교시에서 재생) |

---

## STEP 1 — async 테스트 도구 설치

async 코드를 테스트하려면 `pytest-asyncio`가 필요합니다.

```powershell
uv add --dev pytest-asyncio
```

`pyproject.toml`의 `[tool.pytest.ini_options]`에 한 줄을 추가합니다. (async 테스트를 자동 인식하게)

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
asyncio_mode = "auto"
```

> 💡 `asyncio_mode = "auto"`는 "`async def test_...` 함수를 알아서 실행해줘"라는 설정입니다. 이게 없으면 async 테스트가 그냥 건너뛰어집니다.

---

## STEP 2 — 🔴🟢 async Realtime 세션 (오디오용)

4교시의 동기 어댑터는 그대로 두고, **오디오를 스트리밍하는 async 세션**을 새로 만듭니다. 먼저 저수준 async 연결 약속부터.

```powershell
New-Item -ItemType Directory -Force -Path tests/adapter | Out-Null
notepad src/voice_agent/adapter/async_connection.py
```

```python
from typing import Protocol


class AsyncRealtimeConnection(Protocol):
    """async 통신 채널의 약속. 진짜 WebSocket도, 테스트용 가짜도 이 모양."""

    async def send_event(self, event: dict) -> None: ...
    async def recv_event(self) -> dict: ...
    async def close(self) -> None: ...
```

이제 세션 테스트를 **먼저** 씁니다. (2교시 `AudioFrame`을 오디오 경계 타입으로 씁니다.)

```powershell
notepad tests/adapter/test_async_realtime.py
```

```python
import base64   # 테스트에서 base64를 되돌려(디코드) 원본 PCM과 비교하려고

from voice_agent.adapter.async_realtime import AsyncRealtimeSession  # 아직 없음 → RED
from voice_agent.domain.audio_frame import AudioFrame               # 오디오 한 조각
from voice_agent.domain.session_config import SessionConfig         # 세션 설정


class FakeAsyncConnection:
    """테스트용 가짜 async 연결. 보낸 이벤트를 기록한다.

    실제 소켓 없이, 메서드 모양(async send/recv/close)만 맞춰 세션에 끼운다.
    """

    def __init__(self):
        self.sent: list[dict] = []   # 세션이 보낸 이벤트를 순서대로 기록
        self.closed = False          # close() 호출 여부

    async def send_event(self, event: dict) -> None:
        self.sent.append(event)      # 보낸 것을 기록만(실제 전송 없음)

    async def recv_event(self) -> dict:
        return {}                    # 이 두 테스트에선 수신을 안 쓰므로 빈 dict

    async def close(self) -> None:
        self.closed = True


async def test_open_sends_audio_session_update():
    conn = FakeAsyncConnection()                       # 가짜 연결
    session = AsyncRealtimeSession(connection=conn)     # 세션에 주입

    await session.open(SessionConfig())                # 세션 열기(= session.update 전송)

    # 검증: 첫 전송이 session.update이고, 오디오 출력·올바른 모델로 열렸다.
    assert conn.sent[0]["type"] == "session.update"
    assert conn.sent[0]["session"]["output_modalities"] == ["audio"]
    assert conn.sent[0]["session"]["model"] == "gpt-realtime"


async def test_send_audio_appends_base64_pcm():
    conn = FakeAsyncConnection()
    session = AsyncRealtimeSession(connection=conn)

    # 4바이트짜리 가짜 PCM (int16 두 샘플). \x01\x00 = 1, \x02\x00 = 2 (리틀엔디언).
    frame = AudioFrame(sample_rate=24000, data=b"\x01\x00\x02\x00")
    await session.send_audio(frame)

    ev = conn.sent[0]                                        # 보낸 이벤트 하나를 꺼내
    assert ev["type"] == "input_audio_buffer.append"        # 오디오 추가 이벤트인지
    # base64를 '되돌리면(decode)' 원래 PCM 바이트가 그대로 나와야 한다 → 인코딩이 올바름.
    assert base64.b64decode(ev["audio"]) == b"\x01\x00\x02\x00"
```

돌려서 **빨강** 확인:

```powershell
uv run pytest tests/adapter/test_async_realtime.py
```

**예상 출력** (🔴): `ModuleNotFoundError: ...async_realtime`

이제 구현합니다.

```powershell
notepad src/voice_agent/adapter/async_realtime.py
```

```python
import base64                          # PCM 바이트 ↔ base64 문자열 변환용 표준 라이브러리
from typing import AsyncIterator       # async 제너레이터의 반환 타입 표기

from voice_agent.adapter.async_connection import AsyncRealtimeConnection  # 저수준 연결 '약속'
from voice_agent.domain.audio_frame import AudioFrame                     # 오디오 한 조각(2교시 값객체)
from voice_agent.domain.session_config import SessionConfig              # 세션 설정 값객체


class AsyncRealtimeSession:
    """오디오를 스트리밍하는 async Realtime 세션."""

    def __init__(self, connection: AsyncRealtimeConnection):
        # 저수준 연결(진짜 WebSocket이든 가짜든)을 주입받아 보관한다.
        self._conn = connection

    async def open(self, config: SessionConfig) -> None:
        # 오디오 입출력 세션으로 설정한다(첫 이벤트 session.update).
        # - output_modalities=["audio"]: 음성으로 응답 (자막 delta도 함께 옴)
        # - turn_detection: 서버가 말끝을 자동 감지(VAD)
        await self._conn.send_event({          # await: 전송이 끝날 때까지 양보
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": config.model,               # 설정에서 온 모델(기본 gpt-realtime)
                "output_modalities": ["audio"],      # 음성으로 응답받기
                "audio": {
                    "input": {                       # 입력(마이크) 오디오 설정
                        "format": {"type": "audio/pcm", "rate": 24000},   # 24kHz PCM
                        "turn_detection": {"type": "semantic_vad"},       # 말끝 자동 감지
                    },
                    "output": {                      # 출력(응답) 오디오 설정
                        "format": {"type": "audio/pcm", "rate": 24000},   # rate 필수!(누락 시 오류)
                        "voice": config.voice,       # 합성 음성 종류
                    },
                },
                "instructions": "You are a helpful voice assistant. 한국어로 짧고 자연스럽게 답하세요.",
            },
        })

    async def send_audio(self, frame: AudioFrame) -> None:
        # 오디오 한 조각을 Realtime에 흘려보낸다.
        # PCM 원본 바이트 → base64 문자열로 인코딩(JSON에 담아 보내려면 문자열이어야 함).
        b64 = base64.b64encode(frame.data).decode("ascii")
        await self._conn.send_event({
            "type": "input_audio_buffer.append",   # '입력 버퍼에 오디오 조각 추가' 이벤트
            "audio": b64,                          # base64로 인코딩한 오디오
        })
        # ※ commit/response.create를 우리가 안 보내도, 서버 VAD가 말끝을 감지해 알아서 응답한다.

    async def events(self) -> AsyncIterator[dict]:
        # 서버 이벤트를 '끝없이' 하나씩 내보내는 async 제너레이터.
        # 호출한 쪽은 `async for event in session.events():` 로 받아 쓴다.
        while True:
            yield await self._conn.recv_event()   # 이벤트 하나를 받아(await) 내보낸다(yield)

    async def close(self) -> None:
        # 내부 연결을 닫는다.
        await self._conn.close()
```

테스트 다시:

```powershell
uv run pytest tests/adapter/test_async_realtime.py
```

**예상 출력** (🟢): `2 passed`

> 💡 **`AudioFrame`이 여기서 쓰입니다.** 2교시에서 만든 도메인 값객체가 "오디오 한 조각"의 표준 모양이 되어, 인프라(FastRTC)와 어댑터 사이의 깨끗한 경계가 됩니다.

---

## STEP 3 — 🔴🟢 전사·오류 추출 헬퍼

서버 이벤트에서 "자막 조각"과 "오류 메시지"를 골라내는 작은 순수 함수 **두 개**를 만듭니다. (순수 함수라 테스트가 쉽고, 핸들러는 "출력"만 맡게 됩니다.)

**🔴 테스트** — `tests/adapter/test_transcript.py`

```python
from voice_agent.adapter.transcript import extract_transcript_delta, extract_error_message


def test_returns_delta_for_transcript_event():
    event = {"type": "response.output_audio_transcript.delta", "delta": "안녕"}
    assert extract_transcript_delta(event) == "안녕"


def test_returns_none_for_other_events():
    assert extract_transcript_delta({"type": "response.output_audio.delta"}) is None
    assert extract_transcript_delta({"type": "session.updated"}) is None


def test_extracts_nested_error_message():
    # 실제 error 이벤트는 message가 error 객체 안에 중첩된다
    event = {"type": "error", "error": {"message": "rate limit"}}
    assert extract_error_message(event) == "rate limit"


def test_returns_none_when_no_error():
    assert extract_error_message({"type": "response.done"}) is None
```

**🟢 구현** — `src/voice_agent/adapter/transcript.py`

```python
def extract_transcript_delta(event: dict) -> str | None:
    """자막(transcript) 조각 이벤트면 그 텍스트를, 아니면 None을 돌려준다."""
    if event.get("type") == "response.output_audio_transcript.delta":
        return event.get("delta", "")
    return None


def extract_error_message(event: dict) -> str | None:
    """error 이벤트면 (중첩된) 메시지를, 아니면 None을 돌려준다."""
    if event.get("type") == "error":
        err = event.get("error", event)   # 실제 message는 error 객체 안에 중첩
        return err.get("message") or "unknown error"
    return None
```

```powershell
uv run pytest tests/adapter/test_transcript.py
```

**예상 출력**: `4 passed`

> 💡 **왜 오류도 헬퍼로?** 자막·오류를 모두 "어댑터가 판정 → 핸들러는 출력만"으로 맞추면 계층이 일관됩니다. 특히 4교시에서 배운 "중첩 `error.message`" 교훈을 여기서 재사용합니다. (8교시부터 도구 이벤트가 늘어날 때도 이 패턴이 이어집니다.)

---

## STEP 4 — 실제 async WebSocket 연결

`websockets`(1교시에서 설치, async 라이브러리)로 진짜 연결을 만듭니다.

```powershell
notepad src/voice_agent/adapter/async_websocket.py
```

```python
import json
import os

import websockets


class AsyncWebSocketConnection:
    """실제 OpenAI Realtime async WebSocket 연결. AsyncRealtimeConnection 약속을 만족한다."""

    def __init__(self, ws):
        self._ws = ws

    @classmethod
    async def connect(cls, model: str) -> "AsyncWebSocketConnection":
        api_key = os.environ["OPENAI_API_KEY"]   # .env에서 load_dotenv로 올라온 키
        ws = await websockets.connect(
            f"wss://api.openai.com/v1/realtime?model={model}",
            additional_headers={"Authorization": f"Bearer {api_key}"},
        )
        return cls(ws)

    async def send_event(self, event: dict) -> None:
        await self._ws.send(json.dumps(event))

    async def recv_event(self) -> dict:
        return json.loads(await self._ws.recv())

    async def close(self) -> None:
        await self._ws.close()
```

> ⚠️ **버전 주의**: `websockets` 최신 버전은 `additional_headers`를 쓰지만, 구버전은 `extra_headers`입니다. 연결 시 `TypeError`가 나면 둘을 바꿔 시도하세요.

---

## STEP 5 — FastRTC 핸들러 (오디오 입력 + 자막 출력)

이제 FastRTC `AsyncStreamHandler`에 위 조각들을 결선합니다. **여기에 실시간 오디오의 함정 두 개가 숨어 있어, 그대로 따라 하는 게 안전합니다.**

```powershell
notepad src/voice_agent/infra/voice_handler.py
```

```python
import asyncio

from fastrtc import AsyncStreamHandler
from websockets.exceptions import ConnectionClosed

from voice_agent.adapter.async_realtime import AsyncRealtimeSession
from voice_agent.adapter.async_websocket import AsyncWebSocketConnection
from voice_agent.adapter.transcript import extract_transcript_delta, extract_error_message
from voice_agent.domain.audio_frame import AudioFrame
from voice_agent.domain.session_config import SessionConfig


class RealtimeVoiceHandler(AsyncStreamHandler):
    """마이크 오디오를 Realtime으로 흘려보내고, 응답 자막을 터미널에 출력한다."""

    def __init__(self):
        # 입력 오디오를 24kHz로 받아 Realtime의 24kHz PCM에 맞춘다.
        super().__init__(input_sample_rate=24000)
        self._session: AsyncRealtimeSession | None = None

    def copy(self) -> "RealtimeVoiceHandler":
        # 접속자마다 새 핸들러 인스턴스
        return RealtimeVoiceHandler()

    async def start_up(self) -> None:
        # Realtime에 연결하고 오디오 세션을 연 뒤, 이벤트 읽기 루프를 돈다.
        # (start_up은 스트림당 한 번 호출되며, 여기서 계속 이벤트를 읽어도 된다.)
        config = SessionConfig()
        conn = await AsyncWebSocketConnection.connect(model=config.model)
        self._session = AsyncRealtimeSession(connection=conn)
        await self._session.open(config)
        print("[연결됨] Realtime 세션 시작", flush=True)
        await self._read_events()

    async def _read_events(self) -> None:
        # 자막·오류를 헬퍼로 판정하고, 핸들러는 출력만 맡는다.
        try:
            async for event in self._session.events():
                text = extract_transcript_delta(event)
                if text:
                    print(text, end="", flush=True)
                    continue
                error = extract_error_message(event)
                if error:
                    print(f"\n[오류] {error}", flush=True)
                elif event.get("type") == "response.done":
                    print(flush=True)   # 한 응답이 끝나면 줄바꿈
        except ConnectionClosed:
            # 중지/새로고침 등으로 세션이 닫히면 조용히 종료 (정상 상황)
            print("[종료] 세션이 닫혔습니다", flush=True)

    async def receive(self, frame) -> None:
        # FastRTC가 마이크 프레임이 올 때마다 호출한다.
        # frame = (sample_rate, numpy 배열) 튜플.
        if self._session is None:
            return   # 아직 연결 준비 전이면 조용히 건너뜀
        sample_rate, array = frame
        # numpy 오디오 배열을 Realtime이 원하는 'PCM16 바이트'로 변환한다:
        #   .squeeze()        : (1, N) 같은 불필요한 차원을 없애 1차원으로
        #   .astype("<i2")    : 리틀엔디언 16비트 정수(int16)로 형변환 ("<"=리틀엔디언, "i2"=2바이트 정수)
        #   .tobytes()        : 숫자 배열을 실제 바이트열로
        pcm = array.squeeze().astype("<i2").tobytes()
        # AudioFrame(도메인 값객체)에 담아 세션으로 보낸다.
        await self._session.send_audio(AudioFrame(sample_rate=sample_rate, data=pcm))

    async def emit(self):
        # ⚠️ 중요: emit은 반드시 await로 이벤트 루프에 '양보'해야 한다.
        # 그냥 return None 하면 루프가 굶어 start_up의 연결까지 멈춘다(FastRTC 함정).
        # 5교시엔 재생하지 않으므로 잠깐 sleep 후 None을 반환한다. (재생은 6교시)
        await asyncio.sleep(0.02)
        return None

    async def shutdown(self) -> None:
        if self._session is not None:
            await self._session.close()
```

> ⚠️ **함정 1 — `emit`은 반드시 `await` 한다.** `async def emit`이 `await` 없이 `return None`만 하면, FastRTC가 `emit`을 반복 호출할 때 이벤트 루프가 **양보를 못 받아 굶습니다.** 그러면 같은 루프의 `start_up`이 연결(`await ...connect`)을 진행하지 못해 **접속이 "Connecting…"에서 멈춥니다.** `await asyncio.sleep(0.02)` 한 줄이 이걸 막습니다.
>
> 💡 **함정 2 — `start_up`이 오래 걸려도 됨.** 위처럼 `start_up`이 `await self._read_events()`로 계속 이벤트를 읽어도, FastRTC는 `receive`·`emit`을 **동시에** 호출합니다. 그래서 한 곳에서 이벤트를 읽는 동안에도 마이크 입력이 정상 전송됩니다.
>
> 💡 **함정 3 — 중지 시 종료는 정상이다.** 사용자가 "중지"를 누르면 세션이 닫히고, 이벤트 읽기 루프는 `ConnectionClosed`(코드 `1000 OK`)를 만납니다. 이건 오류가 아니라 **정상 종료**이므로, 위처럼 `try/except ConnectionClosed`로 감싸 빨간 스택트레이스 대신 `[종료]` 한 줄만 남깁니다.

---

## STEP 6 — 실행하고 자막 확인 (관찰형 완성)

> ⚠️ **실행 방식이 중요합니다.** async 핸들러는 Gradio의 `stream.ui.launch()`와 **이벤트 루프가 꼬여** 연결이 안 되는 경우가 있습니다. 그래서 **FastAPI에 마운트하고 uvicorn으로 실행**합니다. (이 방식은 7교시 커스텀 UI로도 이어집니다.)

먼저 Gradio UI 마운트에 필요한 패키지를 확인합니다.

```powershell
uv add gradio
```

`voice_app.py`를 이렇게 만듭니다.

```powershell
notepad voice_app.py
```

```python
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
```

uvicorn으로 실행합니다.

```powershell
uv run uvicorn voice_app:app --host 127.0.0.1 --port 7860
```

브라우저로 **`http://127.0.0.1:7860/ui`** 를 열고 → 마이크 허용 → **"안녕하세요, 오늘 날씨 어때요?"** 라고 말한 뒤 잠깐 멈춥니다. 그러면 **터미널에 어시스턴트 응답 자막이 흐릅니다.**

**예상 출력** (터미널, 예시):

```text
[연결됨] Realtime 세션 시작
안녕하세요! 오늘 날씨 궁금하신가 보네요. 지금 보니까 하늘이 맑고 햇빛이 쨍쨍한 편이에요...
```

> ⚠️ **이 부분은 순수 단위테스트가 아니라 "실행·관찰"로 확인합니다.** 실시간 오디오·async·브라우저·서버 VAD가 얽혀 있어, 여기서의 완성 신호는 **"말하면 터미널에 자막이 뜬다"**입니다. (도메인·어댑터 로직은 STEP 2·3에서 이미 TDD로 검증했습니다.)

---

## 🧪 이 교시 TDD 테스트 목록 (체크리스트)

- [x] `test_open_sends_audio_session_update`
- [x] `test_send_audio_appends_base64_pcm`
- [x] `test_returns_delta_for_transcript_event`
- [x] `test_returns_none_for_other_events`
- [x] `test_extracts_nested_error_message`
- [x] `test_returns_none_when_no_error`

**🎯 필수 미션 테스트 (다음 교시 진행 전 반드시 완성)**
- [ ] 미션 1 — `AsyncRealtimeSession.close()`가 연결을 닫는지 테스트 (1개) — *자원 정리*
- [ ] 미션 2 — 세션이 닫히면(`ConnectionClosed`) `_read_events`가 조용히 끝나는지 테스트 (1개) — *중지·새로고침 정상 처리 회귀 방지*

**🟦 선택 (여유 있으면)**
- [ ] 사용자 발화 전사도 보기: 세션에 입력 전사(`input_audio_transcription`)를 켜고, 그 delta도 출력

> 💡 막히면 맨 아래 **🧩 필수 미션 — 풀이** 를 펼쳐 보세요.

---

## ✅ 완성 체크포인트 (= 오디오 입력 계층 게이트)

- [ ] `src/voice_agent/adapter/`에 `async_connection.py`, `async_realtime.py`, `async_websocket.py`, `transcript.py` 존재
- [ ] `src/voice_agent/infra/voice_handler.py` 존재
- [ ] `uv run pytest` → **최소 30 passed** (4교시 22 + async 6 + 미션 1·2 각 1 — 오차 가능)
- [ ] `uv run ruff check src/voice_agent` → **All checks passed!**
- [ ] **실행 관찰**: `uv run uvicorn voice_app:app --port 7860` → `/ui`에서 말하면 **터미널에 응답 자막**이 뜬다

> **계층 규칙 자가 점검**: 오디오 바이트 변환(numpy↔bytes)은 **인프라(handler)에만**, base64·이벤트 JSON은 **어댑터에만** 있어야 합니다. 도메인 `AudioFrame`은 여전히 표준 라이브러리만 씁니다.

---

## ⚠️ 자주 나는 오류 & 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| **접속이 "Connecting…"에서 멈춤 / `connect`가 반환 안 함** | `emit`이 `await` 없이 `return None` → 이벤트 루프 기아 | `emit`에 `await asyncio.sleep(0.02)` 추가(STEP 5) |
| `[오류] Missing required parameter: 'session.audio.output.format.rate'` | 출력 포맷에 `rate` 누락 | `audio.output.format`에 `"rate": 24000` 추가(STEP 2) |
| `ui.launch()`로 띄우면 연결이 꼬임 | Gradio 런처와 async 핸들러의 이벤트 루프 충돌 | **uvicorn + `stream.mount(app)` + `/ui`** 방식(STEP 6) |
| `connect`에서 멈춤(터미널 단독은 됨) | 앱의 이벤트 루프 안에서 연결 지연 | 먼저 `conn_test.py`로 네트워크/코드 분리 → uvicorn 방식으로 실행 |
| **중지 버튼 누르면 `ConnectionClosedOK: ... 1000 (OK)`** | 세션 정상 종료를 루프가 예외로 만남 | `_read_events`를 `try/except ConnectionClosed`로 감쌈(정상 상황) |
| async 테스트가 전부 skip | `asyncio_mode` 미설정 | STEP 1의 `asyncio_mode = "auto"` 확인 |
| `TypeError: ... additional_headers` | `websockets` 버전 차이 | `additional_headers` ↔ `extra_headers` 바꿔 시도 |
| 말해도 자막이 안 뜸 | 마이크 권한 / 모델 접근 / 세션 설정 오류 | 브라우저 마이크 허용, `gpt-realtime` 사용, 터미널의 `[오류]` 로그 확인 |
| 자막이 깨져 나옴 | 터미널 인코딩 | 1교시 UTF-8 프로파일 확인 |
| `AttributeError: 'AudioFrame'` | 2교시 `AudioFrame` 미완성 | 2교시 게이트부터 통과 |

---

<details>
<summary><strong>🔧 부록 — 연결이 안 될 때 진단 순서</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

실시간 오디오는 "코드·네트워크·이벤트 루프" 중 어디가 문제인지 **분리**하는 게 먼저입니다. 순서대로 확인하세요.

**1) 네트워크·코드 분리 — 터미널 단독 연결 테스트**

FastRTC를 빼고, OpenAI Realtime에 붙기만 시도합니다. 루트에 `conn_test.py`:

```python
import asyncio
import os

import websockets
from dotenv import load_dotenv

load_dotenv()


async def main():
    k = os.environ["OPENAI_API_KEY"]
    print("연결 시도...", flush=True)
    try:
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?model=gpt-realtime",
            additional_headers={"Authorization": f"Bearer {k}"},
        ) as ws:
            print("연결 성공! 첫 이벤트 대기...", flush=True)
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            print("받음:", msg[:200], flush=True)
    except Exception as e:
        print(f"실패: {type(e).__name__}: {e}", flush=True)


asyncio.run(main())
```

```powershell
uv run python conn_test.py
```

- **"연결 성공! … 받음: {…session.created…}"** → 네트워크·인증·async 연결은 정상. 문제는 **앱 안의 이벤트 루프**(→ 2, 3번).
- **"실패: …"** → 그 메시지가 원인(인증/차단/핸드셰이크).
- **아무것도 안 뜨고 멈춤** → `wss://api.openai.com` 아웃바운드가 방화벽/프록시에 막힘.

**2) 실행 방식 — uvicorn 마운트**

`ui.launch()` 대신 STEP 6의 uvicorn + `stream.mount(app)` + `/ui`로 실행합니다. Gradio 런처와 async 핸들러의 루프 충돌을 피합니다.

**3) 이벤트 루프 기아 — `emit`의 `await`**

"Connecting…"에서 안 넘어가고 `[연결됨]`도 안 뜨면, `emit`에 `await asyncio.sleep(0.02)`가 있는지 확인합니다. 이게 없으면 루프가 굶어 연결이 진행되지 않습니다.

**4) 흐름이 보이게 — 이벤트 로그**

원인을 못 잡겠으면 `_read_events`에 한 줄을 임시로 넣어 **오는 이벤트를 전부** 찍습니다.

```python
        async for event in self._session.events():
            print(f"[event] {event.get('type')}", flush=True)   # 임시 진단
            ...
```

`session.created` 직후 `error`가 뜨면 그 메시지가 세션 설정 문제를 정확히 알려줍니다(예: `output.format.rate` 누락).

</details>

---

## 📖 용어 사전 (이 교시 신규)

- **동기(synchronous)**: 한 줄이 끝나야 다음 줄로 가는 방식. 4교시까지의 코드.
- **비동기(asynchronous) / async**: 기다리는 동안 다른 일을 처리하는 방식.
- **`async def` / `await`**: 비동기 함수 정의와, "이 작업을 기다리며 잠깐 양보"하는 표시.
- **이벤트 루프(event loop)**: 여러 async 작업을 번갈아 돌리는 관제탑. 양보 안 하면 다른 작업이 굶는다.
- **코루틴(coroutine)**: `async def`로 만든, 중간에 양보·재개가 가능한 함수(객체).
- **async 제너레이터 / `async for`**: 끝없이 흘러오는 값을 하나씩 내보내고(`yield`) 받는(`async for`) 구조.
- **`AsyncStreamHandler`**: FastRTC의 async 오디오 핸들러. `start_up/receive/emit/copy/shutdown`을 채운다.
- **`input_audio_buffer.append`**: 오디오 조각을 base64로 Realtime에 흘려보내는 클라이언트 이벤트.
- **서버 VAD(Voice Activity Detection)**: 서버가 "말이 끝났다"를 감지해 자동으로 응답을 만드는 기능.
- **PCM16(Pulse-Code Modulation, 16비트)**: 16비트 정수로 표현한 오디오 원본 포맷.
- **base64**: 바이너리(바이트) 데이터를 문자열로 바꿔 JSON 등에 실어 보내는 인코딩.
- **리틀엔디언(`<i2`)**: 16비트 정수를 낮은 바이트부터 저장하는 방식. Realtime PCM이 요구하는 배치.
- **numpy 배열**: 오디오 같은 숫자 묶음을 빠르게 다루는 파이썬 자료구조.
- **이벤트 루프 양보(기아)**: `await`로 제어를 넘기지 않으면 루프가 굶어 다른 작업(연결 등)이 멈추는 현상.
- **`response.output_audio_transcript.delta`**: 어시스턴트 음성의 자막이 조각으로 오는 서버 이벤트.

---

## 🎯 필수 미션 — 다음 교시로 가기 전 반드시 완성

> **참고**: `error` 처리와 종료 처리(`ConnectionClosed`)는 STEP 5에서 이미 코드에 넣었습니다. 아래 미션은 그 동작을 **테스트로 못 박아(회귀 방지)** 계층을 마무리하는 것입니다. 직접 🔴RED → 🟢GREEN 으로 해보고, **막히면 접이식 풀이**를 펼치세요.

### 미션 1 (필수) — `close()` 자원 정리 테스트

`AsyncRealtimeSession.close()`가 연결의 `close()`를 부르는지 async 테스트로 고정합니다.
- **어디에**: `tests/adapter/test_async_realtime.py` 에 테스트 1개 추가
- **왜**: 세션이 닫힐 때 소켓이 확실히 닫혀야 다음 세션이 깨끗이 열림 (6교시 재생 루프에서 특히 중요)

### 미션 2 (필수) — 종료 처리 테스트

세션이 닫히면(`ConnectionClosed`) `_read_events`가 예외를 밖으로 흘리지 않고 **조용히 끝나는지** 검증합니다.
- **어디에**: `tests/infra/test_voice_handler.py` (새 파일)에 테스트 1개 추가
- **왜**: 중지·새로고침은 매번 일어나는 정상 경로. 누가 나중에 `try/except`를 지우면 이 테스트가 빨갛게 잡아줌

> 풀이는 모두 아래 **🧩 필수 미션 — 풀이** 에 접이식으로 있습니다. (`error` 처리는 STEP 3에서 이미 헬퍼로 만들었으므로 미션에서 뺐습니다.)

### 🟦 선택 (여유 있으면)

- 세션 설정에 `input_audio_transcription`을 켜서 **내가 한 말의 전사**도 받아 출력해 보세요. (내 발화 전사 이벤트는 어시스턴트 자막과 다른 타입입니다 — 이벤트 타입을 로그로 찍어 확인.)

---

## 🧩 필수 미션 (테스트 안된것 추가)— 풀이 (막히면 펼치기)

> 위 **필수 미션**의 풀이입니다. **먼저 스스로 시도한 뒤** 각 제목을 클릭해 펼쳐 보세요. (기본은 접혀 있습니다.)

<details>
<summary><strong>📂 풀이 1 — <code>close()</code> 자원 정리 테스트</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**무엇 / 왜**: 세션을 닫으면 내부 연결도 닫혀야 합니다. STEP 2의 `AsyncRealtimeSession.close()`는 이미 `await self._conn.close()`를 부르므로, 이 동작을 **테스트로 고정**합니다.

**준비 확인**: STEP 2에서 만든 `FakeAsyncConnection`에 아래가 이미 있습니다(그대로 재사용).

```python
    def __init__(self):
        self.sent: list[dict] = []
        self.closed = False        # ← close()가 호출되면 True로 바뀐다

    async def close(self) -> None:
        self.closed = True
```

**🔴 테스트** — `tests/adapter/test_async_realtime.py` 맨 아래에 **추가**

```python
async def test_close_closes_connection():
    conn = FakeAsyncConnection()
    session = AsyncRealtimeSession(connection=conn)

    await session.close()          # 세션을 닫으면

    assert conn.closed is True      # 내부 연결도 닫혀야 한다
```

**🟢 구현**: 추가 코드 없이 통과합니다. STEP 2의 `close()`가 이미 이렇게 되어 있기 때문입니다.

```python
    async def close(self) -> None:
        await self._conn.close()
```

```powershell
uv run pytest tests/adapter/test_async_realtime.py
```

**예상 출력**: `3 passed` (기존 `open`/`send_audio` 2 + 새 `close` 1)

> 💡 "이미 동작하는 코드를 테스트로 못 박는" 것도 TDD의 일부입니다. 다음에 누가 `close()`에서 `await self._conn.close()`를 실수로 지우면, 이 테스트가 빨갛게 알려 줍니다.

</details>

---

<details>
<summary><strong>📂 풀이 2 — 종료 처리 테스트(<code>ConnectionClosed</code>)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**무엇 / 왜**: 중지를 누르면 세션이 닫히고, `_read_events`의 `async for ... recv_event()`가 `ConnectionClosed`를 만납니다. STEP 5에서 이미 `try/except ConnectionClosed`로 감쌌으니, 그게 **밖으로 예외를 흘리지 않고 조용히 끝나는지** 테스트로 고정합니다.

**대상 코드 확인** — `_read_events`가 이렇게 감싸져 있어야 합니다(STEP 5).

```python
    async def _read_events(self) -> None:
        try:
            async for event in self._session.events():
                ...
        except ConnectionClosed:
            print("[종료] 세션이 닫혔습니다", flush=True)
```

**준비**: infra 테스트 폴더를 패키지로 만듭니다.

```powershell
New-Item -ItemType File -Force -Path tests/infra/__init__.py | Out-Null
```

**🔴 테스트** — `tests/infra/test_voice_handler.py` (새 파일)

```python
from websockets.exceptions import ConnectionClosed

from voice_agent.adapter.async_realtime import AsyncRealtimeSession
from voice_agent.infra.voice_handler import RealtimeVoiceHandler


class ClosingFakeConnection:
    """자막 한 개를 준 뒤 ConnectionClosed를 던지는 가짜 연결 (= 중지 상황 재현)."""

    def __init__(self):
        self._events = [
            {"type": "response.output_audio_transcript.delta", "delta": "안녕"},
        ]

    async def send_event(self, event: dict) -> None:
        pass

    async def recv_event(self) -> dict:
        if self._events:
            return self._events.pop(0)   # 먼저 자막 한 개를 돌려주고
        raise ConnectionClosed(None, None)   # 그다음 정상 종료(1000 OK) 신호

    async def close(self) -> None:
        pass


async def test_read_events_stops_quietly_on_close():
    # 핸들러를 만들고, 내부 세션에 '닫히는 가짜 연결'을 꽂는다.
    handler = RealtimeVoiceHandler()
    handler._session = AsyncRealtimeSession(connection=ClosingFakeConnection())

    # 핵심: ConnectionClosed가 밖으로 새지 않고 '예외 없이' 끝나야 한다.
    # (try/except가 없으면 이 줄에서 예외가 터져 테스트가 실패한다.)
    await handler._read_events()
```

**🟢 구현**: STEP 5의 `_read_events`가 이미 `try/except ConnectionClosed`를 가지므로 **추가 코드 없이 통과**합니다.

```powershell
uv run pytest tests/infra/test_voice_handler.py
```

**예상 출력**: `1 passed`

> 💡 **이 테스트가 하는 일**: "예외가 안 나면 통과"입니다. 별도 `assert`가 없어도, `_read_events`가 예외를 던지면 pytest가 실패로 잡습니다. 그래서 나중에 누가 `try/except`를 지우면 이 테스트가 즉시 빨개집니다.
>
> ⚠️ `ConnectionClosed(None, None)`는 `websockets` 15.x 기준입니다. 버전에 따라 생성자 인자가 다르면, 테스트에서 `ConnectionClosedOK(None, None)`로 바꾸거나 `pytest.raises` 없이 그대로 두세요.

</details>

---

### ✅ 미션 완료 확인 (= 진행 게이트)

```powershell
uv run pytest
```

**예상 출력** (대략):

```text
... 30 passed
```

- **필수**: 4교시 22 + `open`/`send_audio` 2 + `transcript` 2 + `error 헬퍼` 2 + 미션 1(`close`) 1 + 미션 2(종료 처리) 1 = **30 passed**

여기에 더해 `uv run ruff check src/voice_agent`가 **All checks passed!**, 그리고 **`/ui`에서 말하면 자막이 뜨면** 게이트 통과입니다.

---

**다음 교시 예고 — 6교시**: `emit()`을 채워 **어시스턴트 음성을 실제로 재생**하고, 내가 말을 걸면 응답이 멈추는 **바지인(barge-in)**까지 넣어 **기본 보이스 에이전트(MVP)**를 완성합니다. 여기서 `response.output_audio.delta`(음성 바이트)를 재생 큐로 흘려보냅니다.
> **선행**: 위 오디오 입력 계층 게이트(최소 30 passed + ruff clean + 자막 관찰) 통과 상태.
