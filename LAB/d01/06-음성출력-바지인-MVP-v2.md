# 6교시 — 음성 출력 + 바지인 = 보이스 에이전트 MVP

> **이 교시가 끝나면** 어시스턴트의 **음성이 실제로 재생**되고, 내가 말을 걸면 응답이 **즉시 멈추는 끼어들기(바지인)**까지 되는 **기본 보이스 에이전트(MVP, Minimum Viable Product)**가 완성됩니다.

---

## 0. 이번 시간에 만드는 것 (한눈에)

5교시는 "자막만" 봤습니다. 이번 시간은 **소리가 나고, 끼어들 수 있게** 만듭니다.

```
서버 → response.output_audio.delta (음성 조각, base64 PCM)
   → 디코드해서 재생 큐(output_queue)에 넣기
       → FastRTC의 emit()이 큐에서 꺼내 브라우저 스피커로 재생   ← 소리가 남!

내가 말을 걸면 → input_audio_buffer.speech_started
   → 재생 큐를 비우고 clear_queue() → 즉시 조용해짐   ← 바지인!
```

5교시에서 이미 `response.output_audio.delta`가 잔뜩 도착하고 있었죠(로그에서 확인). **데이터는 이미 오고 있고, 이 교시에는 그걸 재생 큐로 흘려보내고 끼어들기를 얹기만** 하면 됩니다.

---

## 🧭 잠깐, 배경지식

이 교시의 핵심 장치인 **큐(queue)**와 **바지인**을 짚습니다.

**① 큐(queue) = 줄서기.** 큐는 먼저 들어온 것이 먼저 나가는(FIFO) 대기 줄입니다. 은행 번호표나 컨베이어 벨트를 떠올리면 됩니다. 여기서는 서버가 보낸 음성 조각을 **잠시 담아두는 대기 줄**로 씁니다.

**② 왜 큐가 필요한가(생산자–소비자).** 음성 조각이 **도착하는 쪽**(이벤트 읽기 루프)과, 그걸 **스피커로 꺼내 쓰는 쪽**(FastRTC의 `emit`)은 서로 다른 타이밍에 움직입니다. 둘을 직접 연결하면 한쪽이 다른 쪽을 기다리다 엉킵니다. 그래서 가운데에 큐를 두고, 한쪽은 **넣기만**(생산자) 다른 쪽은 **꺼내기만**(소비자) 하게 분리합니다. 컨베이어 벨트 양 끝에서 각자 자기 일만 하는 셈입니다.

**③ `asyncio.Queue`.** 우리가 쓰는 큐는 비동기용입니다. `put_nowait(x)`로 즉시 넣고, 꺼낼 땐 항목이 생길 때까지 `await`로 기다릴 수 있습니다(FastRTC의 `wait_for_item`이 이 역할을 대신해 줍니다).

**④ 바지인(barge-in) = 끼어들기.** 어시스턴트가 말하는 도중 사용자가 말을 시작하면, **재생 대기 중인 소리를 즉시 비워** 말을 뚝 끊는 동작입니다. 사람 대화에서 상대가 끼어들면 말을 멈추는 것과 같습니다.

> 💡 아래 "1. 개념 빠르게 잡기"에서 `emit`·재생 큐·바지인을 코드 흐름으로 이어서 봅니다.

---

## 1. 개념 빠르게 잡기

### `emit()`은 "재생할 오디오 한 조각"을 돌려준다

> FastRTC는 스피커에 보낼 오디오가 필요할 때 `emit()`을 반복 호출합니다. `emit()`은 **`(sample_rate, numpy 배열)`** 튜플을 돌려주면 그게 재생됩니다. 5교시엔 `None`(재생 없음)을 줬지만, 이번 시간엔 **재생 큐에서 꺼내** 돌려줍니다.

### 재생 큐 + `wait_for_item`

> 서버 오디오는 이벤트 루프(백그라운드)에서 도착하고, `emit()`은 FastRTC가 부릅니다. 이 둘을 잇는 게 **`asyncio.Queue`**(재생 큐)입니다. 이벤트 루프가 큐에 **넣고**, `emit()`이 큐에서 **꺼냅니다.**
>
> 큐가 비었을 때 `emit()`이 멈추면 안 되므로, FastRTC의 **`wait_for_item(queue)`**를 씁니다. 있으면 꺼내 주고, 없으면 잠깐 기다렸다 `None`을 돌려줍니다. (5교시의 `await asyncio.sleep(...)` 양보를 이게 대신합니다 — `wait_for_item`이 알아서 `await` 합니다.)

💡 즉 5교시의 "emit은 반드시 await" 규칙은 그대로입니다. 다만 `sleep` 대신 **`await wait_for_item(self.output_queue)`**로 바뀝니다.

### 바지인(barge-in) = 끼어들기

> 어시스턴트가 말하는 중에 내가 말을 시작하면, 서버는 `input_audio_buffer.speech_started`를 보냅니다. 이때 **재생 큐를 비우고**, FastRTC의 **`clear_queue()`**로 이미 전송 대기 중인 오디오까지 지우면 **즉시 조용해집니다.** 서버(VAD)는 알아서 이전 응답 생성을 멈추고 새 발화를 처리합니다.

```my
WebRTC : UDP 기반, WebSocket : TCP 기반 
```
---

## STEP 1 — 🔴🟢 오디오 델타 디코드 헬퍼 (TDD)

서버가 보낸 base64 음성 조각을 numpy 배열(int16)로 바꾸는 **순수 함수**를 만듭니다. 순수 함수라 테스트가 쉽습니다.

**🔴 테스트** — `tests/adapter/test_audio_output.py`

```python
import base64          # PCM ↔ base64 변환
import numpy as np      # 오디오 숫자 배열을 다루는 라이브러리

from voice_agent.adapter.audio_output import decode_audio_delta   # 아직 없음 → RED


def test_decodes_pcm16_audio_delta():
    # 준비: int16 샘플 3개[1, -2, 3]를 리틀엔디언 PCM 바이트로 만들고, base64로 감싸 이벤트에 싣는다.
    pcm = np.array([1, -2, 3], dtype="<i2").tobytes()
    event = {"type": "response.output_audio.delta",
             "delta": base64.b64encode(pcm).decode("ascii")}

    out = decode_audio_delta(event)   # 실행: 디코드

    assert out is not None            # 음성 이벤트이므로 None이 아니어야
    assert out.dtype == np.int16      # int16으로 해석됐는지
    assert out.tolist() == [1, -2, 3]  # 원래 샘플이 그대로 복원됐는지


def test_returns_none_for_non_audio_event():
    # 음성이 아닌 이벤트(자막/완료)에는 None을 돌려줘야 한다.
    assert decode_audio_delta({"type": "response.output_audio_transcript.delta"}) is None
    # 종료할 때
    assert decode_audio_delta({"type": "response.done"}) is None
```

```powershell
uv run pytest tests/adapter/test_audio_output.py
```

**예상 출력** (🔴): `ModuleNotFoundError: ...audio_output`

**🟢 구현** — `src/voice_agent/adapter/audio_output.py`

```python
import base64          # base64 문자열 → 바이트 디코드
import numpy as np      # 바이트 → 숫자 배열 해석


def decode_audio_delta(event: dict) -> np.ndarray | None:
    """음성 델타 이벤트면 base64 PCM16을 int16 배열로 디코드해 돌려준다.
    음성 이벤트가 아니면 None.
    """
    # 1) 음성 델타 이벤트가 아니면 즉시 None(관심 밖).
    if event.get("type") != "response.output_audio.delta":
        return None
    # 2) 서버 버전에 따라 base64가 'delta' 또는 'audio' 필드에 올 수 있어 둘 다 대응.
    #    ('delta'가 있으면 그걸, 없으면 'audio'를 쓴다.) 최근-delta, 구형-audio
    b64 = event.get("delta") or event.get("audio")
    # 3) 알맹이가 비어 있으면(빈 문자열/None) 안전하게 None.
    if not b64:
        return None
    # 4) base64 문자열을 원본 PCM 바이트로 되돌린다.
    pcm = base64.b64decode(b64)
    # 5) 그 바이트를 리틀엔디언 int16 배열로 '해석'한다.
    #    frombuffer는 원본을 가리키는 읽기전용 '뷰'라, .copy()로 쓰기 가능한 복사본을 만든다.
    return np.frombuffer(pcm, dtype="<i2").copy()
```

```powershell
uv run pytest tests/adapter/test_audio_output.py
```

**예상 출력** (🟢): `2 passed`

> 💡 **왜 `.copy()`?** `np.frombuffer`는 원본 바이트를 가리키는 **읽기 전용 뷰**를 줍니다. FastRTC가 이 배열을 손대다 오류가 날 수 있어, 안전하게 복사본을 만들어 넘깁니다.

---

## STEP 2 — 핸들러에 재생 큐 얹기 (실행·관찰)

5교시 핸들러를 확장합니다. **바뀌는 곳만** 표시했습니다.

먼저 import를 정리합니다. `voice_handler.py` 상단:

```python
import asyncio

import numpy as np
from fastrtc import AsyncStreamHandler, wait_for_item
from websockets.exceptions import ConnectionClosed

from voice_agent.adapter.async_realtime import AsyncRealtimeSession
from voice_agent.adapter.async_websocket import AsyncWebSocketConnection
from voice_agent.adapter.audio_output import decode_audio_delta
from voice_agent.adapter.transcript import extract_transcript_delta, extract_error_message
from voice_agent.domain.audio_frame import AudioFrame
from voice_agent.domain.session_config import SessionConfig
```

`__init__`에 **재생 큐**를 추가합니다.

```python
    def __init__(self):
        # 입출력 모두 24kHz로 Realtime PCM에 맞춘다.
        super().__init__(input_sample_rate=24000, output_sample_rate=24000)
        self._session: AsyncRealtimeSession | None = None
        self.output_queue: asyncio.Queue = asyncio.Queue()   # ← 재생 큐 추가
```

`_read_events`에 **음성 분기**를 추가합니다(자막·오류·종료는 5교시 그대로).

```python
    async def _read_events(self) -> None:
        try:
            async for event in self._session.events():
                # 1) 자막: 텍스트 조각이면 화면에 출력하고 다음 이벤트로.
                text = extract_transcript_delta(event)
                if text:
                    print(text, end="", flush=True)
                    continue
                # 2) 음성: base64 PCM을 디코드해 재생 큐에 넣는다.  ← 이 교시에 추가
                #    put_nowait: 기다리지 않고 즉시 큐에 넣기(생산자 역할).
                #    reshape(1, -1): (N,) 1차원을 (1, N) 2차원(모노 한 채널)으로.
                audio = decode_audio_delta(event)
                if audio is not None:
                    self.output_queue.put_nowait((24000, audio.reshape(1, -1)))
                    continue
                # 3) 오류 / 응답 끝 (오류는 5교시 헬퍼로 판정)
                error = extract_error_message(event)
                if error:
                    print(f"\n[오류] {error}", flush=True)
                elif event.get("type") == "response.done":
                    print(flush=True)
        except ConnectionClosed:
            print("[종료] 세션이 닫혔습니다", flush=True)
```

`emit()`을 **재생 큐에서 꺼내도록** 바꿉니다(5교시의 `sleep` 대신).

```python
    async def emit(self):
        # FastRTC가 '스피커로 보낼 오디오'가 필요할 때 반복 호출한다(소비자 역할).
        # wait_for_item: 큐에 항목이 있으면 꺼내 주고, 없으면 잠깐 기다렸다 None을 준다.
        #   → 내부적으로 await(양보)하므로, 5교시의 sleep 없이도 루프가 굶지 않는다.
        return await wait_for_item(self.output_queue)
```

> 💡 **`(24000, audio.reshape(1, -1))`**: FastRTC는 오디오를 `(sample_rate, 2차원 배열)`로 다룹니다. 디코드한 1차원 배열을 `reshape(1, -1)`로 `(1, N)` 모양(모노 한 채널)으로 바꿔 넣습니다.

여기까지 하고 실행하면 **소리가 납니다.** (바지인은 다음 STEP)

```powershell
uv run uvicorn voice_app:app --host 127.0.0.1 --port 7860
```

`/ui`에서 말하면, 이번엔 자막과 **함께 음성이 스피커로 재생**됩니다.

> ⚠️ **관찰형 확인**: 이 부분은 오디오 타이밍·브라우저가 얽혀 순수 단위테스트가 아니라 **"실행해서 소리가 들리는지"**로 확인합니다. (디코드 로직은 STEP 1에서 이미 TDD로 검증했습니다.)

---

## STEP 3 — 바지인(끼어들기) 얹기 (실행·관찰)

어시스턴트가 말하는 중에 내가 말을 시작하면 즉시 멈추게 합니다. `_read_events`의 이벤트 분기에 **`speech_started` 처리**를 추가합니다.

```python
                # 2.5) 바지인: 사용자가 말을 시작하면 재생 중인 오디오를 즉시 버린다
                if event.get("type") == "input_audio_buffer.speech_started":
                    self._barge_in()
                    continue
```

(위 `_read_events`에서 음성 분기 다음, 오류 분기 앞에 넣으면 됩니다.)

그리고 큐를 비우는 메서드를 추가합니다.

```python
    def _barge_in(self) -> None:
        # 사용자가 끼어들면, 아직 재생 안 한 오디오를 전부 버린다.
        # 1) 우리 재생 큐를 완전히 비운다(get_nowait로 하나씩 꺼내 버림).
        while not self.output_queue.empty():
            self.output_queue.get_nowait()
        # 2) FastRTC가 이미 전송하려고 쥐고 있는 내부 출력 버퍼도 비운다.
        self.clear_queue()   # 둘 다 비워야 소리가 '뚝' 끊긴다
```

다시 실행해서, 어시스턴트가 길게 말하는 도중에 **끼어들어 말해** 보세요. 재생이 **즉시 멈추고** 새 응답으로 넘어가면 성공입니다.

```powershell
uv run uvicorn voice_app:app --host 127.0.0.1 --port 7860
```

> 💡 **왜 두 가지를 다 비우나?** `output_queue`는 우리가 채운 "아직 안 보낸" 오디오이고, `clear_queue()`는 FastRTC가 이미 전송하려고 쥐고 있는 오디오입니다. 둘 다 비워야 **말이 뚝 끊깁니다.** 서버(VAD)는 알아서 이전 응답을 멈추고 새 발화를 처리합니다.
>
> ⚠️ `self.clear_queue()`에서 오류가 나면(버전 차이), 그 줄만 빼도 됩니다 — `output_queue`만 비워도 대부분 끊깁니다. 다만 이미 전송된 짧은 꼬리가 남을 수 있습니다.

---

## STEP 4 — MVP 완성 확인

이제 **말 → 음성 응답 → 끼어들기**가 한 흐름으로 됩니다. 아래를 모두 확인하세요.

- 말하면 어시스턴트 **목소리가 스피커로 재생**된다.
- 말하는 도중 **끼어들면 즉시 멈추고** 내 새 말에 반응한다.
- 중지 버튼을 누르면 `[종료] 세션이 닫혔습니다` 한 줄로 깔끔히 끝난다.

여기까지면 **speech-to-speech 보이스 에이전트 MVP**가 완성된 것입니다. 이후 교시는 이 위에 커스텀 UI(7교시)와 도구(8교시~)를 얹습니다.

---

## 🧪 이 교시 TDD 테스트 목록 (체크리스트)

- [x] `test_decodes_pcm16_audio_delta`
- [x] `test_returns_none_for_non_audio_event`

**🎯 필수 미션 테스트 (다음 교시 진행 전 반드시 완성)**
- [ ] 미션 1 — 바지인 판정 헬퍼 `is_speech_started(event)` + 테스트, 핸들러가 이를 사용 (1개)
- [ ] 미션 2 — `decode_audio_delta`가 빈/누락 오디오에 안전한지 테스트 (1개)

**🟦 선택 (여유 있으면)**
- [ ] 미션 3 — 바지인 시 서버에 `response.cancel`도 보내 생성 자체를 중단

> 💡 막히면 맨 아래 **🧩 필수 미션 — 풀이** 를 펼쳐 보세요.

```my
차세대 인터페이스로 음성 각광 - 보안이 이슈 예) 음성코딩 생산성 10배  
다자간 회의 등 : 음성지문 기술 이용 화자의 identity 구분
```
---

## ✅ 완성 체크포인트 (= MVP 게이트)

- [ ] `src/voice_agent/adapter/audio_output.py` 존재
- [ ] `voice_handler.py`에 `output_queue`, `emit`의 `wait_for_item`, `_barge_in` 존재
- [ ] `uv run pytest` → **최소 34 passed** (5교시 30 + audio 2 + 미션 2 — 오차 가능)
- [ ] `uv run ruff check src/voice_agent` → **All checks passed!**
- [ ] **실행 관찰**: `/ui`에서 말하면 **음성이 재생**되고, **끼어들면 멈춘다**

> **계층 규칙 자가 점검**: base64→numpy 디코드는 **어댑터(`audio_output.py`)**, 큐·재생·`clear_queue`는 **인프라(handler)**, 도메인은 그대로입니다.

---

## ⚠️ 자주 나는 오류 & 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 자막은 나오는데 **소리가 안 남** | 음성 델타 필드명 불일치 | `decode_audio_delta`가 `delta`·`audio` 둘 다 보는지 확인. 안 되면 이벤트를 로그로 찍어 실제 키 확인 |
| 소리가 **깨지거나 느림/빠름** | 샘플레이트 불일치 | `output_sample_rate=24000`과 emit의 `(24000, ...)`이 세션 `output.format.rate`(24000)와 같은지 확인 |
| `ValueError: cannot reshape` | 디코드 배열 길이 문제 | `reshape(1, -1)` 사용(자동 계산). 빈 배열이면 STEP 1의 `if not b64` 가드 확인 |
| 끼어들어도 **안 멈춤** | 큐를 한쪽만 비움 | `output_queue` 비우기 **+** `clear_queue()` 둘 다 호출 확인 |
| `AttributeError: clear_queue` | FastRTC 버전 차이 | 그 줄을 빼고 `output_queue`만 비움(꼬리 오디오는 감수) |
| `emit`이 멈춤/`None`만 | `wait_for_item` 미사용 | `return await wait_for_item(self.output_queue)` 확인 |

---

## 📖 용어 사전 (이 교시 신규)

- **큐(queue) / FIFO(First In, First Out)**: 먼저 들어온 것이 먼저 나가는 대기 줄(번호표·컨베이어 벨트).
- **`asyncio.Queue`**: 비동기용 큐. 넣기(`put_nowait`)와 꺼내기(기다릴 수 있음)를 분리해 쓴다.
- **생산자–소비자(producer–consumer)**: 데이터를 넣는 쪽과 꺼내 쓰는 쪽을 큐로 분리하는 패턴.
- **`put_nowait` / `get_nowait`**: 기다리지 않고 즉시 큐에 넣기 / 꺼내기.
- **재생 큐(output queue)**: 서버 음성 조각을 담아 `emit`이 꺼내가는 `asyncio.Queue`.
- **`wait_for_item`**: 큐에 항목이 있으면 꺼내 주고, 없으면 잠깐 기다렸다 `None`을 주는 FastRTC 유틸(비차단).
- **`emit`**: FastRTC가 스피커로 보낼 오디오 `(sample_rate, 배열)`를 요청하는 메서드(소비자).
- **`reshape(1, -1)`**: 1차원 배열을 `(1, N)` 2차원(모노 한 채널)으로 바꾸기. `-1`은 길이 자동 계산.
- **`np.frombuffer`**: 바이트열을 숫자 배열로 '해석'하는 함수(복사 없이 뷰를 만듦 → `.copy()` 필요).
- **뷰(view) vs 복사(copy)**: 뷰는 원본을 가리키기만 하는 것, 복사는 별도 데이터를 만드는 것.
- **바지인(barge-in)**: 어시스턴트가 말하는 중 사용자가 끼어들어 응답을 중단시키는 것.
- **`clear_queue()`**: FastRTC 내부 출력 버퍼를 비우는 핸들러 메서드(바지인에 사용).
- **`response.output_audio.delta`**: 어시스턴트 음성 바이트(base64 PCM)가 조각으로 오는 서버 이벤트.

---

## 🎯 필수 미션 — 다음 교시로 가기 전 반드시 완성

직접 🔴RED → 🟢GREEN 으로 하고, **막히면 접이식 풀이**를 펼치세요.

### 미션 1 (필수) — 바지인 판정 헬퍼

지금 핸들러는 `event.get("type") == "input_audio_buffer.speech_started"`를 **인라인**으로 봅니다. 이걸 순수 함수 `is_speech_started(event)`로 빼고 테스트한 뒤, 핸들러가 그 헬퍼를 쓰게 바꾸세요.
- **어디에**: `src/voice_agent/adapter/audio_output.py` + `tests/adapter/test_audio_output.py`
- **왜**: 판정 로직을 순수 함수로 두면 테스트가 쉽고, 핸들러(인프라)는 "무엇을 할지"만 남음

### 미션 2 (필수) — 디코드 안전성 테스트

`decode_audio_delta`가 **음성 이벤트지만 오디오가 비었거나 없는** 경우 `None`을 돌려주는지 테스트로 고정하세요. (실시간 스트림엔 별별 이벤트가 다 옵니다.)
- **어디에**: `tests/adapter/test_audio_output.py`

> 풀이는 아래 **🧩 필수 미션 — 풀이** 에 접이식으로 있습니다.

### 🟦 선택 (여유 있으면)

- **미션 3** — 바지인 시 서버에 `{"type": "response.cancel"}`도 보내 생성 자체를 멈춰 보세요. (큐 비우기는 "재생 중단", `response.cancel`은 "생성 중단" — 둘을 합치면 더 확실합니다. 단, **진행 중인 응답이 있을 때만** 보내야 `no active response` 오류가 안 납니다 → 풀이의 조건부 취소 참고.)

---

## 🧩 필수 미션 — 풀이 (막히면 펼치기)

<details>
<summary><strong>📂 풀이 1 — 바지인 판정 헬퍼 <code>is_speech_started</code></strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**🔴 테스트** — `tests/adapter/test_audio_output.py` 에 추가

```python
from voice_agent.adapter.audio_output import is_speech_started


def test_true_on_speech_started():
    assert is_speech_started({"type": "input_audio_buffer.speech_started"}) is True


def test_false_on_other_events():
    assert is_speech_started({"type": "response.output_audio.delta"}) is False
    assert is_speech_started({"type": "response.done"}) is False
```

**🟢 구현** — `src/voice_agent/adapter/audio_output.py` 에 함수 추가

```python
def is_speech_started(event: dict) -> bool:
    """사용자가 말을 시작했다는 신호면 True (바지인 트리거)."""
    return event.get("type") == "input_audio_buffer.speech_started"
```

**핸들러 반영** — `voice_handler.py` import에 추가하고,

```python
from voice_agent.adapter.audio_output import decode_audio_delta, is_speech_started
```

`_read_events`의 인라인 판정을 헬퍼로 바꿉니다.

```python
                if is_speech_started(event):     # ← 인라인 대신 헬퍼
                    await self._barge_in()
                    continue
```

```powershell
uv run pytest tests/adapter/test_audio_output.py
```

**예상 출력**: `4 passed` (기존 2 + 새 2)

</details>

---

<details>
<summary><strong>📂 풀이 2 — 디코드 안전성 테스트</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**🔴 테스트** — `tests/adapter/test_audio_output.py` 에 추가

```python
def test_returns_none_when_audio_missing():
    # 음성 이벤트지만 base64가 비었거나 없음
    assert decode_audio_delta({"type": "response.output_audio.delta", "delta": ""}) is None
    assert decode_audio_delta({"type": "response.output_audio.delta"}) is None
```

**🟢 구현**: STEP 1의 `decode_audio_delta`에 이미 `if not b64: return None` 가드가 있어 **추가 코드 없이 통과**합니다.

```powershell
uv run pytest tests/adapter/test_audio_output.py
```

**예상 출력**: 위 미션 1까지 하면 `6 passed`

> 💡 실시간 스트림은 "형식은 맞지만 알맹이가 빈" 이벤트가 흔합니다. 이런 방어 코드를 테스트로 고정하면 재생 루프가 갑자기 죽는 걸 막습니다.

</details>

---

<details>
<summary><strong>📂 풀이 3 (선택) — <code>response.cancel</code>로 생성 중단</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**무엇 / 왜**: 큐 비우기는 "이미 만들어진 오디오의 재생"을 멈춥니다. `response.cancel`은 서버가 **아직 만들고 있는 응답 생성 자체**를 멈춥니다. 둘을 합치면 바지인이 더 확실해집니다. 단, **진행 중인 응답이 없을 때** 취소를 보내면 서버가 `Cancellation failed: no active response found` 오류를 돌려줍니다. 그래서 **"진행 중일 때만" 취소**하는 조건부 방식으로 만듭니다.

**① 취소 메서드** — `src/voice_agent/adapter/async_realtime.py`

```python
    async def cancel_response(self) -> None:
        """진행 중인 응답 생성을 중단하도록 서버에 요청한다."""
        await self._conn.send_event({"type": "response.cancel"})
```

**② 진행 상태 플래그** — `voice_handler.py`의 `__init__`에 추가

```python
        self._response_active = False   # 응답 생성 진행 중 여부
```

**③ 플래그 켜고 끄기** — `_read_events`에서 `response.created`/`response.done`으로 추적

```python
    async def _read_events(self) -> None:
        try:
            async for event in self._session.events():
                etype = event.get("type")
                # 응답 생성 진행 상태 추적
                if etype == "response.created":
                    self._response_active = True
                elif etype == "response.done":
                    self._response_active = False
                    print(flush=True)

                text = extract_transcript_delta(event)
                if text:
                    print(text, end="", flush=True)
                    continue
                audio = decode_audio_delta(event)
                if audio is not None:
                    self.output_queue.put_nowait((24000, audio.reshape(1, -1)))
                    continue
                if is_speech_started(event):
                    await self._barge_in()
                    continue
                error = extract_error_message(event)
                if error:
                    print(f"\n[오류] {error}", flush=True)
        except ConnectionClosed:
            print("[종료] 세션이 닫혔습니다", flush=True)
```

**④ 조건부 취소** — `_barge_in`을 async로, 진행 중일 때만 취소

```python
    async def _barge_in(self) -> None:
        # 재생 대기 오디오 버리기 + FastRTC 출력 비우기
        while not self.output_queue.empty():
            self.output_queue.get_nowait()
        self.clear_queue()
        # 실제로 응답이 진행 중일 때만 취소 (헛된 취소 → no active response 방지)
        if self._response_active and self._session is not None:
            await self._session.cancel_response()
            self._response_active = False
```

**테스트**(선택) — 취소 이벤트가 나가는지 `tests/adapter/test_async_realtime.py`

```python
async def test_cancel_sends_response_cancel():
    conn = FakeAsyncConnection()
    session = AsyncRealtimeSession(connection=conn)

    await session.cancel_response()

    assert conn.sent[-1]["type"] == "response.cancel"
```

> 💡 **왜 조건부인가?** 서버 VAD가 말끝을 감지해 응답을 만들다가, 사용자가 다시 말하면 바지인이 발동합니다. 그런데 응답이 이미 끝났거나 아직 시작 전이면 취소할 대상이 없어 `no active response` 오류가 납니다. `response.created`~`response.done` 사이에만 취소를 보내면 이 오류가 원천적으로 사라집니다. (무해한 오류지만, 로그가 깔끔해집니다.)

</details>

---

### ✅ 미션 완료 확인 (= 진행 게이트)

```powershell
uv run pytest -v
```

**예상 출력** (대략):

```text
... 34 passed
```

- **필수**: 5교시 30 + audio 디코드 2 + 미션 1(speech 2) + 미션 2(안전성 1) ≈ **34 passed** (선택 포함 시 그 이상)

여기에 더해 `uv run ruff check src/voice_agent`가 **All checks passed!**, 그리고 **`/ui`에서 음성 재생 + 바지인**이 되면 게이트 통과입니다.

---

**다음 교시 예고 — 7교시**: FastRTC 기본 UI 대신 **커스텀 웹 UI**를 붙입니다. `stream.mount(app)` 위에 우리만의 화면(대화 자막 표시, 연결 상태등)을 올려, 데모에서 제품 느낌으로 한 걸음 나아갑니다.
> **선행**: 위 MVP 게이트(최소 34 passed + ruff clean + 음성·바지인 관찰) 통과 상태.
