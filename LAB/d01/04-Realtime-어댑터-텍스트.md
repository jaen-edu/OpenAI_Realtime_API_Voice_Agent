# 4교시 — OpenAI Realtime 어댑터 (텍스트 우선, 모킹으로 TDD)

> **이 교시가 끝나면** 3교시에서 정한 `RealtimeSessionPort`의 **첫 진짜 구현**(OpenAI Realtime 어댑터)이 생기고, **텍스트로 한 턴**이 왕복합니다. 통신은 가짜 연결로 모킹해 **인터넷·비용 0**으로 검증합니다. (실제 API 호출은 맨 끝 선택 과제)

---

## 0. 이 교시에 만드는 것 (한눈에)

3교시의 포트(약속)를 **실제 OpenAI Realtime 프로토콜**로 구현합니다. 단, 음성은 6교시에서, 이 교시에는 **텍스트 한 턴**만.

```
SendUserUtterance(유즈케이스)
   → RealtimeSessionPort  ← 이 교시에 만드는 OpenAIRealtimeAdapter
        ├─ open()          : session.update 전송
        ├─ send_user_text(): conversation.item.create → response.create → 응답 누적
        └─ close()         : 연결 종료
             │
             └─ RealtimeConnection (저수준 통신 시드)
                  ├─ FakeConnection           (테스트용, 이 교시)
                  └─ WebSocketConnection       (실제, 선택 과제)
```

**핵심 아이디어**: 어댑터는 "어떤 이벤트를 어떤 순서로 주고받는가"(프로토콜)만 책임집니다. 진짜 WebSocket이냐 가짜냐는 **연결 시드(seam)** 뒤로 숨겨, 테스트는 가짜로 비용 없이 돌립니다.

---

## 🧭 잠깐, 배경지식

이 교시에 처음 나오는 통신 개념을 짚습니다.

**① REST vs 실시간 연결.** 우리가 흔히 아는 웹 통신(REST(Representational State Transfer) API)은 **"요청 한 번 → 응답 한 번"**으로 끝나고 연결이 닫힙니다. 편지를 한 통 보내고 답장 한 통을 받는 것과 같습니다. 반면 음성 대화는 말이 오가는 내내 연결을 **열어둔 채** 계속 주고받아야 합니다. 전화 통화처럼요.

**② WebSocket.** 그 "열어두고 양방향으로 계속 주고받는" 연결을 만드는 기술이 **WebSocket**입니다. 한 번 연결(handshake)하면, 그 통로로 서버와 클라이언트가 **아무 때나 메시지를 밀어 넣을 수 있습니다.** 주소가 `http://`가 아니라 `wss://`로 시작하는 게 특징입니다(ws=WebSocket, s=보안). OpenAI Realtime는 이 WebSocket 위에서 동작합니다.

**③ 이벤트(event) 기반.** WebSocket으로 주고받는 메시지 하나하나를 **이벤트**라 부릅니다. 각 이벤트는 `{"type": "...", ...}` 형태의 **JSON(JavaScript Object Notation)**(키-값으로 데이터를 적는 표준 형식)입니다. 우리가 보내는 것은 클라이언트 이벤트(`session.update` 등), 서버가 보내는 것은 서버 이벤트(`response.done` 등)입니다.

**④ 스트리밍과 델타(delta).** 모델은 응답을 한 번에 완성해 주지 않고, 만들어지는 대로 **조각(delta)**을 흘려보냅니다. "맑고 " → "따뜻해요." 처럼요. 우리는 이 조각들을 순서대로 이어붙여 완성 문장을 만듭니다. (빠르게 보여주기 위한 방식입니다.)

> 💡 이 교시에서는 **진짜 WebSocket 대신 가짜 연결(Fake)**로 이 이벤트 흐름을 테스트합니다. 진짜 접속은 맨 끝 선택 과제에서 다룹니다.

---

---

## 1. 개념 빠르게 잡기

### Realtime는 "이벤트를 주고받는" 방식

> 일반 REST API는 "요청 → 응답" 한 번이지만, Realtime는 **연결을 열어두고 이벤트(JSON 메시지)를 계속 주고받습니다.** 우리가 보내는 건 **클라이언트 이벤트**, 서버가 보내는 건 **서버 이벤트**입니다.

이 교시의 텍스트 한 턴에 쓰는 이벤트는 이렇습니다.

| 방향 | 이벤트 | 의미 |
|---|---|---|
| 보냄 | `session.update` | 세션 설정(모델·출력 형식 등)을 정한다 |
| 보냄 | `conversation.item.create` | 사용자 입력 텍스트를 대화에 넣는다 |
| 보냄 | `response.create` | "이제 응답을 만들어줘"라고 요청한다 |
| 받음 | `response.output_text.delta` | 응답 텍스트가 **조각조각** 도착한다 |
| 받음 | `response.done` | 응답이 **끝났다** (이때 누적을 멈춘다) |
| 받음 | `error` | 뭔가 잘못됐다 |

> 💡 **왜 조각(delta)으로 올까?** 모델이 글자를 생성하는 즉시 흘려보내 **빠르게 보여주기** 위해서입니다. 우리는 조각들을 이어붙여 완성된 문장을 만듭니다.

### 연결 시드(seam)로 모킹

> 진짜 WebSocket을 붙이면 테스트가 느리고 돈이 듭니다. 그래서 어댑터와 실제 소켓 사이에 **얇은 약속(`RealtimeConnection`)**을 둡니다. 테스트에선 "미리 짜둔 서버 이벤트를 차례로 돌려주는" **가짜 연결**을 끼웁니다.

💡 이게 3교시의 Fake와 같은 전략입니다. **"바깥(소켓)을 약속 뒤로 숨기면, 안쪽 로직을 공짜로 테스트할 수 있다."**

---

## STEP 1 — 🔴 저수준 연결 약속 + 어댑터 테스트 쓰기

먼저 "연결"이 가져야 할 모양을 정하고, 어댑터를 어떻게 쓸지 테스트로 그립니다.

```powershell
New-Item -ItemType File -Force -Path tests/adapter/__init__.py | Out-Null
notepad src/voice_agent/adapter/realtime_connection.py
```

```python
from typing import Protocol   # '이런 메서드가 있어야 한다'는 약속(인터페이스)을 만드는 도구


class RealtimeConnection(Protocol):
    """어댑터와 실제 통신 채널 사이의 얇은 약속(저수준 시드).

    어댑터는 이 약속에만 의존한다.
    진짜 구현(WebSocket)은 선택 과제, 가짜(Fake)는 테스트에서 쓴다.
    """

    def send_event(self, event: dict) -> None:
        """클라이언트 이벤트(JSON dict)를 서버로 보낸다."""
        ...   # 실제 전송 방법(소켓 write 등)은 구현이 채운다

    def recv_event(self) -> dict:
        """서버가 보낸 이벤트(JSON dict) 하나를 받는다."""
        ...   # 실제 수신 방법(소켓 read 등)은 구현이 채운다

    def close(self) -> None:
        """연결을 닫는다."""
        ...
```

이제 어댑터 테스트를 씁니다. 가짜 연결도 함께 만듭니다.

```powershell
notepad tests/adapter/test_openai_realtime.py
```

```python
from voice_agent.adapter.openai_realtime import OpenAIRealtimeAdapter  # 아직 없음 → RED의 원인
from voice_agent.domain.session_config import SessionConfig            # 세션 설정 값객체 — 2교시


class FakeConnection:
    """테스트용 가짜 연결. 미리 짜둔 서버 이벤트를 차례로 돌려준다.

    RealtimeConnection(약속)과 같은 메서드 모양(send_event/recv_event/close)을 갖춰,
    어댑터에 진짜 소켓 대신 끼운다. 실제 네트워크 없이 이벤트 흐름만 검증한다.
    """

    def __init__(self, scripted_events: list[dict]):
        # sent: 어댑터가 '보낸' 이벤트들을 순서대로 쌓아 둔다(무엇을 보냈는지 검증용).
        self.sent: list[dict] = []
        # _incoming: 서버가 '보낼' 이벤트 대본. list(...)로 복사해 원본을 건드리지 않는다.
        self._incoming = list(scripted_events)
        # closed: close()가 호출됐는지 표시하는 깃발.
        self.closed = False

    def send_event(self, event: dict) -> None:
        # 진짜라면 소켓으로 보내겠지만, 가짜는 '보냈다'고 기록만 한다.
        self.sent.append(event)

    def recv_event(self) -> dict:
        # 대본의 맨 앞(index 0) 이벤트를 꺼내(pop) 하나씩 돌려준다.
        # → 호출할 때마다 대본이 한 개씩 줄어든다(FIFO, 먼저 넣은 걸 먼저 내보냄).
        return self._incoming.pop(0)

    def close(self) -> None:
        self.closed = True


def test_text_round_trip():
    # 준비: 서버가 '텍스트 조각 두 개 → 완료(done)' 순서로 보낸다고 가정한 대본.
    conn = FakeConnection(scripted_events=[
        {"type": "response.output_text.delta", "delta": "맑고 "},      # 조각 1
        {"type": "response.output_text.delta", "delta": "따뜻해요."},  # 조각 2
        {"type": "response.done", "response": {}},                     # 끝 신호
    ])
    adapter = OpenAIRealtimeAdapter(connection=conn)   # 어댑터에 가짜 연결 주입

    # 실행: 세션을 열고, 사용자 텍스트 한 턴을 보낸다.
    adapter.open(SessionConfig())
    reply = adapter.send_user_text("오늘 날씨 어때?")

    # 검증 1: 흩어진 조각(delta)들이 이어붙어 완성 문장이 된다.
    assert reply == "맑고 따뜻해요."

    # 검증 2: 어댑터가 '맨 처음' 보낸 건 session.update이고, 모델이 올바르다.
    #         (conn.sent[0] = 첫 번째로 보낸 이벤트)
    assert conn.sent[0]["type"] == "session.update"
    assert conn.sent[0]["session"]["model"] == "gpt-realtime"

    # 검증 3: 두 번째로 사용자 입력을 input_text 형태로 전달했다.
    #         중첩 dict를 단계별로 파고들어 실제 텍스트까지 확인한다.
    assert conn.sent[1]["type"] == "conversation.item.create"
    assert conn.sent[1]["item"]["content"][0]["text"] == "오늘 날씨 어때?"

    # 검증 4: 세 번째로 '응답을 만들어달라'(response.create)고 요청했다.
    assert conn.sent[2]["type"] == "response.create"
```

돌려서 **빨강**을 확인합니다.

```powershell
uv run pytest tests/adapter/test_openai_realtime.py
```

**예상 출력** (🔴):

```text
ModuleNotFoundError: No module named 'voice_agent.adapter.openai_realtime'
```

> 💡 **가짜 연결이 "보낸 것"을 기록하는 이유**: 어댑터가 **올바른 이벤트를, 올바른 순서로** 보냈는지까지 검증하려고요. 응답이 맞게 나오는 것뿐 아니라 "프로토콜을 제대로 말하는가"가 중요합니다.

---

## STEP 2 — 🟢 Realtime 어댑터 구현

테스트를 통과시키는 어댑터를 만듭니다. 이벤트 흐름은 1번에서 본 표 그대로입니다.

```powershell
notepad src/voice_agent/adapter/openai_realtime.py
```

```python
from voice_agent.adapter.realtime_connection import RealtimeConnection  # 저수준 연결 '약속'
from voice_agent.domain.session_config import SessionConfig             # 세션 설정 값객체


class OpenAIRealtimeAdapter:
    """RealtimeSessionPort의 실제 구현. OpenAI Realtime 이벤트로 통신한다.

    (4교시는 텍스트 우선. 음성 입출력은 5·6교시에서 확장한다.)
    """

    def __init__(self, connection: RealtimeConnection):
        # 저수준 연결을 주입받는다(진짜 WebSocket이든 가짜든 상관없음).
        # 어댑터는 send_event/recv_event/close 세 가지만 쓰므로,
        # 그 모양만 맞으면 무엇이든 받아들인다.
        self._conn = connection

    def open(self, config: SessionConfig) -> None:
        # 세션을 시작하며 설정을 알려주는 첫 이벤트(session.update)를 보낸다.
        self._conn.send_event({
            "type": "session.update",            # 이벤트 종류: 세션 설정
            "session": {
                "type": "realtime",              # 실시간 세션임을 명시
                "model": config.model,           # 쓸 모델(SessionConfig 기본값 gpt-realtime)
                "output_modalities": ["text"],   # 4교시는 텍스트만 받는다(음성은 6교시)
                "instructions": "You are a helpful voice assistant.",  # 시스템 지시(성격/역할)
            },
        })

    def send_user_text(self, text: str) -> str:
        # 1) 사용자 입력 텍스트를 '대화 아이템'으로 추가한다.
        self._conn.send_event({
            "type": "conversation.item.create",  # 이벤트 종류: 대화에 아이템 추가
            "item": {
                "type": "message",               # 아이템 종류: 메시지
                "role": "user",                  # 이 메시지의 주체: 사용자
                "content": [{"type": "input_text", "text": text}],  # 입력 텍스트 본문
            },
        })

        # 2) "이제 응답을 만들어 달라"고 요청한다(텍스트 형태로).
        self._conn.send_event({
            "type": "response.create",                        # 이벤트 종류: 응답 생성 요청
            "response": {"output_modalities": ["text"]},      # 응답도 텍스트로 받겠다
        })

        # 3) 서버가 보내오는 이벤트들을 '끝날 때까지' 읽으며 텍스트 조각을 모은다.
        chunks: list[str] = []          # 조각(delta)들을 담을 리스트
        while True:                     # 끝(response.done)을 만날 때까지 반복
            event = self._conn.recv_event()      # 서버 이벤트 하나를 받는다
            etype = event.get("type")            # 그 이벤트의 종류를 꺼낸다

            if etype == "response.output_text.delta":
                # 텍스트 조각이면 모은다. 'delta' 키가 없으면 빈 문자열로.
                chunks.append(event.get("delta", ""))
            elif etype == "response.done":
                break                            # 끝 신호 → 반복 종료
            elif etype == "error":
                # 실제 error 이벤트는 message가 error 객체 '안에' 중첩돼 있다:
                #   {"type": "error", "error": {"message": "...", ...}}
                # event.get("error", event): error 객체가 있으면 그걸, 없으면 event 자체를 쓴다.
                err = event.get("error", event)
                # 실제 메시지를 담아 예외를 던진다(메시지가 없으면 이벤트 전체를 문자열로).
                raise RuntimeError(err.get("message") or str(event))
            # 그 밖의 이벤트(session.created 등)는 어느 분기에도 안 걸리므로 그냥 무시하고 계속 읽는다.

        # 모은 조각들을 순서대로 이어붙여 완성된 한 문장으로 만든다.
        return "".join(chunks)

    def close(self) -> None:
        # 연결을 닫는다(정리).
        self._conn.close()
```

테스트를 다시 돌립니다.

```powershell
uv run pytest tests/adapter/test_openai_realtime.py
```

**예상 출력** (🟢):

```text
tests/adapter/test_openai_realtime.py .   [100%]
1 passed in 0.02s
```

✅ Realtime 어댑터(텍스트)가 프로토콜을 올바르게 말합니다.

> 💡 **`while True` + `recv_event()`가 무섭나요?** 서버가 이벤트를 여러 개(조각들 + 완료) 보내므로, "끝(`response.done`)을 만날 때까지 계속 읽는" 구조입니다. `session.created` 같은 다른 이벤트는 그냥 흘려보냅니다(어떤 분기에도 안 걸리면 다음 줄로).
>
> 💡 **이 어댑터가 곧 `RealtimeSessionPort`입니다.** `open / send_user_text / close` 세 메서드 모양이 3교시 포트와 똑같으므로, 유즈케이스에 그대로 끼울 수 있습니다(다음 STEP에서 확인).

---

## STEP 3 — 🟢 유즈케이스 + 진짜 어댑터 결선 테스트

3교시 유즈케이스(`SendUserUtterance`)에 **이 교시에 만든 어댑터**를 끼워, 계층이 실제로 맞물리는지 확인합니다. (연결만 가짜)

```powershell
notepad tests/adapter/test_usecase_with_adapter.py
```

```python
from voice_agent.adapter.openai_realtime import OpenAIRealtimeAdapter  # 진짜 어댑터
from voice_agent.domain.conversation import Conversation              # 대화(턴 모음)
from voice_agent.domain.turn import Role                              # 발화 주체
from voice_agent.usecase.send_user_utterance import SendUserUtterance  # 3교시 유즈케이스


class FakeConnection:
    """STEP 1과 동일한 가짜 연결 (간단히 재사용).

    여기선 타입 힌트를 생략해 더 짧게 썼다. 동작은 STEP 1과 같다.
    (중복이 거슬리면 아래 필수 미션에서 fakes.py로 모은다.)
    """

    def __init__(self, scripted_events):
        self.sent = []                          # 어댑터가 보낸 이벤트 기록
        self._incoming = list(scripted_events)  # 서버가 보낼 이벤트 대본(복사본)

    def send_event(self, event):
        self.sent.append(event)                 # 보낸 것을 기록만

    def recv_event(self):
        return self._incoming.pop(0)            # 대본 맨 앞부터 하나씩 꺼내 줌

    def close(self):
        pass                                    # 이 테스트에선 할 일 없음


def test_usecase_uses_real_adapter():
    # 준비: 서버가 '인사말 한 조각 → 완료' 순으로 보낸다는 대본.
    conn = FakeConnection([
        {"type": "response.output_text.delta", "delta": "안녕하세요!"},
        {"type": "response.done", "response": {}},
    ])
    # 유즈케이스에 '진짜 어댑터'를 주입한다(단, 그 안의 연결만 가짜).
    # → 3교시에선 세션 자체가 가짜였지만, 여기선 진짜 어댑터 + 가짜 연결이다.
    adapter = OpenAIRealtimeAdapter(connection=conn)
    convo = Conversation()
    usecase = SendUserUtterance(session=adapter, conversation=convo)

    # 실행: 유즈케이스를 통해 한마디 보낸다.
    reply = usecase.execute("안녕")

    # 검증 1: 응답이 어댑터를 거쳐 그대로 흘러나온다.
    assert reply == "안녕하세요!"
    # 검증 2: 대화에 사용자 → 어시스턴트 턴이 순서대로 쌓였다.
    assert convo.turns[0].role == Role.USER
    assert convo.turns[1].role == Role.ASSISTANT
    assert convo.turns[1].text == "안녕하세요!"
```

확인:

```powershell
uv run pytest tests/adapter/test_usecase_with_adapter.py
```

**예상 출력** (🟢):

```text
1 passed
```

✅ **도메인 → 유즈케이스 → 포트 → 어댑터**가 한 줄로 맞물렸습니다. 유즈케이스 코드는 한 글자도 안 바꿨는데 진짜 어댑터가 들어갔습니다 — Clean Architecture 적용에 대한 보상의 순간입니다.

> 💡 `open()`을 호출하지 않았는데 동작하나요? 이 테스트는 `send_user_text`만 검증합니다. 실제 앱에선 `StartConversation`이 먼저 `open()`을 부릅니다(5교시에서 한 흐름으로 묶습니다).

---

## STEP 4 — 전체 테스트 한 번에 돌리기

```powershell
uv run pytest
```

**예상 출력** (3교시까지 + 이 교시 어댑터 2):

```text
... 21 passed in 0.07s
```

🔵 **REFACTOR 점검**: `FakeConnection`이 또 두 파일에 중복됩니다. 3교시처럼 `tests/adapter/fakes.py`로 모으면 깔끔합니다(아래 필수 미션).

---

## 🧪 이 교시 TDD 테스트 목록 (체크리스트)

- [x] `test_text_round_trip`
- [x] `test_usecase_uses_real_adapter`

**🎯 필수 미션 테스트 (다음 교시 진행 전 반드시 완성)**
- [ ] `error` 이벤트가 오면 `RuntimeError`가 나는지 테스트 (1개) — *4교시 이후 모든 통신 안정성*
- [ ] `FakeConnection` 공유 리팩터링: `tests/adapter/fakes.py`로 중복 제거 후에도 전체 그린

**🟦 선택 (여유 있으면)**
- [ ] 실제 OpenAI Realtime에 접속해 텍스트 한 턴 왕복 (과금 발생 · 아래 풀이 참고)

> 💡 막히면 맨 아래 **🧩 필수 미션 — 풀이** 를 펼쳐 보세요.

---

## ✅ 완성 체크포인트 (= 어댑터 계층 완성 게이트)

아래가 **모두 충족되어야 다음 교시로 진행**합니다.

- [ ] `src/voice_agent/adapter/` 에 `realtime_connection.py`, `openai_realtime.py` 존재
- [ ] `OpenAIRealtimeAdapter`가 3교시 `RealtimeSessionPort`와 같은 메서드(`open`/`send_user_text`/`close`)를 가짐
- [ ] `uv run pytest` → **최소 22 passed** (3교시 19 + 어댑터 2 + error 미션 1)
- [ ] `uv run ruff check src/voice_agent` → **All checks passed!**

> **계층 규칙 자가 점검**: 통신(이벤트 JSON)을 아는 코드는 **어댑터에만** 있어야 합니다. 유즈케이스·도메인에는 `session.update` 같은 문자열이 한 번도 등장하면 안 됩니다.

---

## ⚠️ 자주 나는 오류 & 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `IndexError: pop from empty list` | 대본(scripted_events)에 `response.done`이 없음 | 테스트 대본 마지막에 `{"type": "response.done", ...}`를 넣을 것 |
| `reply`가 빈 문자열 | delta 이벤트의 키가 `delta`가 아님 | 서버 이벤트 키 이름(`delta`) 확인 |
| 무한 루프(멈추지 않음) | 종료 이벤트(`response.done`)를 못 만남 | 대본에 종료 이벤트 포함 여부 확인 |
| `ModuleNotFoundError: ...adapter...` | `tests/adapter/__init__.py` 누락 | STEP 1에서 만든 `__init__.py` 확인 |
| `AttributeError: 'SessionConfig'...` | 2교시 `SessionConfig` 미완성 | 2교시 게이트부터 통과시킬 것 |
| (실제 API) `RuntimeError: realtime error` | error 메시지가 중첩(`error.message`)인데 최상위만 읽음 | 어댑터 error 분기를 `event.get("error", event).get("message")`로 수정 |
| (실제 API) `RuntimeError: model ... does not exist / access` | 상위 모델 접근 권한 없음 **또는** URL(`?model=`)과 `session.update`의 모델 불일치 | 기본 `gpt-realtime` 사용. `WebSocketConnection(model=config.model)`로 **두 곳을 같은 값**으로 맞출 것 |

---

## 📖 용어 사전 (이 교시 신규)

- **REST API(Representational State Transfer)**: "요청 한 번 → 응답 한 번"으로 끝나는 일반적인 웹 통신 방식.
- **WebSocket**: 연결을 열어두고 서버·클라이언트가 **양방향으로 계속** 메시지를 주고받는 기술. 주소가 `wss://`로 시작.
- **이벤트(event) 기반**: 통신을 "요청/응답"이 아니라 **메시지(이벤트)의 흐름**으로 다루는 방식.
- **JSON(JavaScript Object Notation)**: `{"key": "value"}` 형태로 데이터를 적는 표준 형식. 이벤트의 본문이 JSON이다.
- **클라이언트/서버 이벤트**: Realtime에서 우리가 보내는/서버가 보내는 JSON 메시지.
- **`session.update`**: 세션 설정(모델·출력 형식)을 정하는 클라이언트 이벤트.
- **`conversation.item.create`**: 대화에 입력 아이템(사용자 텍스트 등)을 추가하는 이벤트.
- **`response.create`**: 모델에게 응답 생성을 요청하는 이벤트.
- **스트리밍 / delta(델타)**: 응답을 한 번에 주지 않고 조각조각 흘려보내는 방식과 그 조각. 이어붙여 완성한다.
- **`response.done`**: 응답이 끝났음을 알리는 서버 이벤트.
- **프로토콜(protocol)**: "어떤 이벤트를 어떤 순서로 주고받는가"에 대한 약속·규칙.
- **모킹(mocking)**: 테스트에서 진짜 대신 **가짜(Fake)**를 끼워 동작을 흉내 내는 것.
- **연결 시드(seam)**: 어댑터와 실제 소켓 사이의 얇은 약속. 테스트에서 가짜로 대체한다.
- **`wss://`**: 보안(TLS)이 적용된 WebSocket 주소 체계(`https`의 WebSocket 판).

---

## 🎯 필수 미션 — 다음 교시로 가기 전 반드시 완성

직접 🔴RED → 🟢GREEN 으로 만들고, **막히면 아래 접이식 풀이를 펼쳐** 끝까지 완성하세요.

### 1) `error` 이벤트 처리 테스트

어댑터는 이미 `error` 이벤트에서 `RuntimeError`를 냅니다. 이를 **테스트로 고정**하세요. (서버가 에러를 보내는 상황을 시나리오로 만들어 검증)

### 2) `FakeConnection` 공유 리팩터링

두 테스트 파일의 `FakeConnection`을 `tests/adapter/fakes.py` 하나로 모으고, 두 테스트가 import하게 바꾸세요. 리팩터링 후에도 **전체 그린** 유지.

> 풀이는 모두 아래 **🧩 필수 미션 — 풀이** 에 접이식으로 있습니다.

### 🟦 선택 (여유 있으면) — 실제 API 한 턴 (과금 주의)

가짜 연결 대신 **진짜 WebSocket**으로 한 턴을 왕복해 봅니다. 약간의 비용이 발생하며, 1교시에서 만든 `.env`의 키가 필요합니다.

---

## 🧩 필수 미션 — 풀이 (막히면 펼치기)

> 위 **필수 미션**의 풀이입니다. **먼저 스스로 시도한 뒤** 각 제목을 클릭해 펼쳐 보세요. (기본은 접혀 있습니다.)

<details>
<summary><strong>📂 풀이 1 — <code>error</code> 이벤트 처리 테스트</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**🔴 테스트** — `tests/adapter/test_openai_realtime.py` 에 추가

```python
import pytest


def test_error_event_raises():
    # 실제 서버 error 이벤트의 모양: message가 error 객체 안에 중첩된다
    conn = FakeConnection(scripted_events=[
        {"type": "error", "error": {"message": "rate limit"}},
    ])
    adapter = OpenAIRealtimeAdapter(connection=conn)
    adapter.open(SessionConfig())

    # send_user_text 도중 error 를 만나면 RuntimeError 가 나야 한다.
    # match= 로 '실제 메시지'가 예외에 실려 오는지까지 확인한다.
    with pytest.raises(RuntimeError, match="rate limit"):
        adapter.send_user_text("안녕")
```

> ⚠️ **모킹은 실제 모양을 따라야 합니다.** 실제 Realtime의 `error` 이벤트는 `{"type": "error", "error": {"message": "..."}}`처럼 **중첩**되어 있습니다. 가짜 이벤트를 실제보다 단순한 평평한 모양(`{"type": "error", "message": ...}`)으로 만들면, 테스트는 통과해도 **실제 API에서 진짜 에러 메시지를 못 읽는** 함정(예: "model does not exist" 대신 밋밋한 문구)에 빠집니다.

**🟢 구현**: STEP 2 어댑터에 이미 `error` 분기가 있으므로 **추가 코드 없이 통과**합니다. (테스트가 기존 동작을 고정해 주는 역할)

```powershell
uv run pytest tests/adapter/test_openai_realtime.py
```

**예상 출력**: `2 passed`

> 💡 이미 구현된 동작을 "테스트로 못 박는" 것도 TDD의 일부입니다. 다음에 누군가 error 처리를 실수로 지우면 이 테스트가 빨갛게 알려 줍니다.

</details>

---

<details>
<summary><strong>📂 풀이 2 — <code>FakeConnection</code> 공유 리팩터링</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**🟢 공유 Fake** — `tests/adapter/fakes.py`

```python
class FakeConnection:
    """어댑터 테스트들이 공유하는 가짜 연결."""

    def __init__(self, scripted_events: list[dict]):
        self.sent: list[dict] = []
        self._incoming = list(scripted_events)
        self.closed = False

    def send_event(self, event: dict) -> None:
        self.sent.append(event)

    def recv_event(self) -> dict:
        return self._incoming.pop(0)

    def close(self) -> None:
        self.closed = True
```

두 테스트 파일에서 클래스 정의를 지우고, 맨 위에서 import 합니다.

```python
from tests.adapter.fakes import FakeConnection
```

리팩터링 후 **전체 그린** 확인:

```powershell
uv run pytest
```

> 💡 동작은 그대로고 개수도 그대로입니다. 코드만 깔끔해집니다(🔵 REFACTOR).

</details>

---

<details>
<summary><strong>📂 풀이 3 (선택) — 실제 OpenAI Realtime 한 턴 (과금)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**무엇 / 왜**: 가짜 연결을 **진짜 WebSocket**으로 바꿔 한 턴을 실제로 왕복합니다. 같은 어댑터 코드가 진짜 연결로도 동작함을 확인하는 게 목적입니다.

> ⚠️ **과금**: 실제 모델을 호출하므로 소액 비용이 발생합니다. 1교시 비용 한도를 걸어 두었는지 확인하세요.

**준비**: 동기식 WebSocket 클라이언트를 추가합니다.

```powershell
uv add websocket-client
```

**진짜 연결 구현** — `src/voice_agent/adapter/websocket_connection.py`

```python
import json
import os

from websocket import create_connection  # websocket-client 라이브러리


class WebSocketConnection:
    """실제 OpenAI Realtime WebSocket 연결. RealtimeConnection 약속을 만족한다."""

    def __init__(self, model: str = "gpt-realtime"):
        api_key = os.environ["OPENAI_API_KEY"]   # .env에서 load_dotenv로 올라온 키
        # GA 인터페이스: 베타 헤더 없이 Authorization 헤더로 연결
        self._ws = create_connection(
            f"wss://api.openai.com/v1/realtime?model={model}",
            header=[f"Authorization: Bearer {api_key}"],
        )

    def send_event(self, event: dict) -> None:
        self._ws.send(json.dumps(event))

    def recv_event(self) -> dict:
        return json.loads(self._ws.recv())

    def close(self) -> None:
        self._ws.close()
```

> ⚠️ **정확한 접속 URL·헤더는 버전에 따라 바뀔 수 있습니다.** 동작이 이상하면 OpenAI의 **Realtime WebSocket 연결 가이드**(`/api/docs/guides/realtime-websocket`)에서 현재 형식을 확인하세요.

**실제 한 턴 스크립트** — 프로젝트 루트 `realtime_smoke.py`

```python
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
```

> ⚠️ **모델은 두 곳에서 쓰입니다** — 접속 URL의 `?model=`(WebSocketConnection)과 `session.update`의 `model`(SessionConfig). 이 둘이 **어긋나면** "model ... does not exist or you do not have access"가 납니다. 위처럼 `config.model`을 **단일 출처**로 넘겨 항상 일치시키세요. (한쪽만 `gpt-realtime`으로 바꾸고 다른 쪽을 `gpt-realtime-2`로 두면 실패합니다.)

```powershell
uv run python realtime_smoke.py
```

**예상 출력** (예시):

```text
어시스턴트: 안녕하세요! 반갑습니다.
```

> 💡 **같은 `OpenAIRealtimeAdapter`인데** 연결만 가짜→진짜로 바꿨습니다. 연결 시드 덕분에 어댑터 로직은 그대로입니다. (단, 실제 스트림에는 `session.created` 등 다른 이벤트가 섞여 오는데, 어댑터가 모르는 이벤트는 무시하므로 문제없습니다.)
>
> ⚠️ **`RuntimeError`가 뜨면** 서버가 `error` 이벤트를 보낸 것입니다. 위 어댑터는 `error` 객체 안의 실제 메시지를 그대로 올려 줍니다. 가장 흔한 원인은 **모델 접근/이름**입니다 — 예: "model `gpt-realtime-2` does not exist or you do not have access" 라면, 그 모델은 접근 권한이 필요한 상위 모델입니다. 기본값 **`gpt-realtime`**(첫 GA 실시간 모델)은 대부분의 계정에서 바로 되므로, `SessionConfig()` 기본값 그대로 두거나 `SessionConfig(model="gpt-realtime")`로 지정하세요. 현재 사용 가능한 이름은 [모델 목록](https://developers.openai.com/api/docs/models)에서 확인할 수 있습니다.

</details>

---

### ✅ 미션 완료 확인 (= 진행 게이트)

```powershell
uv run pytest
```

**예상 출력** (대략):

```text
... 22 passed in 0.07s
```

- **필수**: 3교시 19 + `test_text_round_trip` 1 + `test_usecase_uses_real_adapter` 1 + `error` 미션 1 = **22 passed** (Fake 리팩터링은 개수 변화 없음)

여기에 더해 `uv run ruff check src/voice_agent` 이 **All checks passed!** 면 게이트 통과입니다. 선택 과제(실제 API)는 개수에 포함하지 않습니다.

---

**다음 교시 예고 — 5교시**: FastRTC를 결합합니다. 브라우저 마이크 음성을 받아 Realtime로 흘려보내고, **전사·응답 텍스트가 화면에 뜨는** 단계까지 갑니다. 여기서 2교시 `AudioFrame`이 쓰입니다. (음성 재생·바지인 완성은 6교시)
> **선행**: 위 어댑터 계층 완성 게이트(최소 22 passed + ruff clean) 통과 상태.
