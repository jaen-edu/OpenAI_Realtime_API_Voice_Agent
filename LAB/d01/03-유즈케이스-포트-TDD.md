# 3교시 — 유즈케이스 · 포트(인터페이스) 만들기 (Fake로 TDD)

> **이 교시가 끝나면** 도메인을 사용하는 **유즈케이스**와, 외부 세계로 통하는 문인 **포트**가 생깁니다. 아직 OpenAI는 붙이지 않고, **가짜(Fake) 구현**으로 "대화 한 턴" 시나리오를 통과시킵니다.

---

## 0. 이 교시에 만드는 것 (한눈에)

2교시에서 만든 도메인(데이터)을 **실제로 움직이는 흐름**으로 엮습니다.

```
[사용자 발화] 
   → SendUserUtterance(유즈케이스)
       → RealtimeSessionPort 로 "보내고 받기"  ← 진짜 OpenAI는 4교시, 지금은 Fake
   → Conversation 에 사용자 턴 + 어시스턴트 턴 기록
   → 어시스턴트 응답 텍스트 반환
```

**핵심 아이디어**: 유즈케이스는 "무엇을 할지"만 알고, "어떻게 통신할지"는 **포트(인터페이스)**에 맡깁니다. 그래서 이 교시에는 OpenAI 없이도 Fake 포트로 전체 흐름을 테스트할 수 있습니다. (장점: 여러번 테스트해도 토큰사용x)

---

## 🧭 잠깐, 배경지식

이 교시의 열쇠가 되는 개념 네 가지를 먼저 짚습니다.

**① 인터페이스(약속).** "이런 기능이 있어야 한다"는 **모양(약속)**만 정해두고, 실제 동작은 나중에 채우는 것입니다. 콘센트 규격을 떠올리면 쉽습니다 — 규격(약속)만 맞으면 어떤 기기를 꽂아도 됩니다. 여기서는 "세션을 열고, 텍스트를 보내고, 닫는다"는 약속을 정합니다.

**② 의존성(dependency).** 어떤 코드가 동작하려고 **다른 코드에 기대는 것**을 의존이라 합니다. A가 B를 직접 불러 쓰면 "A는 B에 의존한다"고 말합니다. 의존이 많고 딱딱할수록, 한쪽이 바뀔 때 다른 쪽이 잘 깨집니다.

**③ 의존성 주입(DI, Dependency Injection).** 필요한 부품을 코드 **안에서 직접 만들지 않고, 밖에서 받아쓰는** 방식입니다. 유즈케이스가 세션을 직접 생성하지 않고 생성자로 건네받으면, 테스트에선 가짜(Fake)를, 실제에선 OpenAI를 끼워줄 수 있습니다.

**④ 테스트 대역(Fake).** 영화의 대역 배우처럼, 진짜 대신 세워두는 가벼운 구현입니다. 진짜 OpenAI는 느리고·돈이 들고·인터넷이 필요하지만, Fake는 **즉시·무료·항상 같은 결과**라 테스트에 적합합니다.

> 💡 아래 "1. 개념 빠르게 잡기"에서 포트·어댑터·의존성 역전을 그림으로 이어서 설명합니다. 지금은 이 네 단어의 감만 잡으면 됩니다.

---

---

## 1. 개념 빠르게 잡기

### 포트(Port)와 어댑터(Adapter)

> **포트**는 "이런 기능이 필요하다"는 **약속(인터페이스)**입니다. 실제 코드는 없고, "이런 함수가 있어야 한다"는 모양만 정합니다.
> **어댑터**는 그 약속을 실제로 구현한 것입니다. (OpenAI 어댑터, Fake 어댑터 등)
>
> ```
> usecase  →  RealtimeSessionPort (약속)
>                 ├─ OpenAIRealtimeAdapter   (진짜, 4교시)
>                 └─ FakeRealtimeSession     (가짜, 이 교시)
> ```

💡 **왜 이렇게 나눌까?** 유즈케이스가 포트(약속)에만 의존하면, 진짜 OpenAI를 Fake로 갈아 끼워도 유즈케이스 코드는 한 줄도 안 바뀝니다. **테스트는 빠르고(인터넷·키 불필요), 비용은 0**입니다. 이게 Clean Architecture의 원칙을 적용할 때 얻게 되는 보상입니다.

### 의존성 역전 (Dependency Inversion)

> 보통은 "유즈케이스 → OpenAI" 와 같은 의존성을 갖습니다. 하지만 이럴 경우 OpenAI가 바뀌면 유즈케이스도 흔들립니다.
> 대신 **유즈케이스 → 포트 ← 어댑터** 로, 양쪽 모두 가운데 **약속(포트)**에 의존하게 뒤집습니다(역전). 그래서 바깥(어댑터)이 바뀌어도 안쪽(유즈케이스)은 안전합니다.

### 이 교시의 TDD 전략: Fake로 먼저

> 진짜 OpenAI 어댑터(4교시) 없이도, **Fake 포트**를 만들어 유즈케이스를 완성합니다. "사용자가 '안녕'이라고 하면, 어시스턴트가 미리 정한 답을 돌려준다"는 가짜 세션으로 흐름만 검증합니다.

---

## STEP 1 — 🔴 포트(약속) 정의: `RealtimeSessionPort`

유즈케이스가 기대하는 "약속"을 먼저 적습니다. 파이썬에서는 `Protocol`로 인터페이스(약속)를 표현합니다.

먼저 테스트 폴더를 패키지로 만들고, 포트의 사용처를 상상하며 테스트를 씁니다. (포트 자체는 "모양"이라 직접 테스트하기보다, 다음 STEP의 유즈케이스 테스트가 포트를 검증합니다.) 그래서 STEP 1에서는 **포트를 먼저 정의**합니다.

```powershell
New-Item -ItemType File -Force -Path tests/usecase/__init__.py | Out-Null
notepad src/voice_agent/usecase/ports.py
```

```python
from typing import Protocol   # '이런 메서드를 가진 무언가'라는 약속(인터페이스)을 만드는 도구

from voice_agent.domain.session_config import SessionConfig  # 2교시에서 만든 세션 설정 값객체


class RealtimeSessionPort(Protocol):
    """음성/텍스트 세션과 통신하기 위한 '약속(인터페이스)'.

    유즈케이스는 이 약속에만 의존한다.
    진짜 구현(OpenAI)은 4교시, 가짜 구현(Fake)은 이번 교시에서 만든다.
    """

    def open(self, config: SessionConfig) -> None:
        """주어진 설정으로 세션을 연다."""
        ...   # 본문 없음 — '이런 메서드가 있어야 한다'는 모양만 선언한다

    def send_user_text(self, text: str) -> str:
        """사용자 텍스트를 보내고, 어시스턴트 응답 텍스트를 받는다."""
        ...   # 실제 통신 코드는 어댑터(진짜/가짜)가 채운다

    def close(self) -> None:
        """세션을 닫는다."""
        ...
```

> 💡 **`Protocol`이 뭐죠?** "이런 메서드들을 가진 무언가"라는 **모양만 정하는** 약속입니다. 상속하지 않아도, 같은 모양의 메서드를 가진 클래스면 이 약속을 만족한 것으로 칩니다(덕 타이핑). 그래서 진짜/가짜 구현을 자유롭게 갈아 끼울 수 있습니다.
>
> 💡 **`...`(Ellipsis)**: "본문은 비어 있음(여기선 약속만)"을 뜻합니다. 실제 동작은 어댑터가 채웁니다.

---

## STEP 2 — 🔴 Fake 세션 + 유즈케이스 테스트 쓰기

이제 유즈케이스를 어떻게 쓸지 **테스트로 먼저** 그립니다. 테스트 안에서 쓸 **Fake 세션**도 같이 만듭니다.

```powershell
notepad tests/usecase/test_send_user_utterance.py
```

```python
# 이 테스트가 쓰는 것들을 가져온다(import).
from voice_agent.domain.conversation import Conversation      # 대화(턴 모음) — 2교시
from voice_agent.domain.session_config import SessionConfig   # 세션 설정 값객체 — 2교시
from voice_agent.domain.turn import Role                      # 발화 주체(USER/ASSISTANT) — 2교시
from voice_agent.usecase.send_user_utterance import SendUserUtterance  # 아직 없음 → RED의 원인


class FakeRealtimeSession:
    """테스트용 가짜 세션. 진짜 통신 대신, 미리 정한 답을 돌려준다.

    포트(RealtimeSessionPort)와 '같은 메서드 모양'만 갖추면 되므로,
    Protocol을 상속하지 않아도 유즈케이스에 그대로 끼울 수 있다(덕 타이핑).
    """

    def __init__(self, reply: str):
        # reply: 이 가짜 세션이 '항상' 돌려줄 어시스턴트 답변(테스트가 미리 정함)
        self.reply = reply
        # opened: open()이 호출됐는지 기록하는 깃발(나중에 검증에 쓸 수 있음)
        self.opened = False
        # sent_texts: 어떤 사용자 텍스트가 전달됐는지 순서대로 쌓는 기록장
        self.sent_texts: list[str] = []

    def open(self, config: SessionConfig) -> None:
        # 진짜라면 세션을 열겠지만, 가짜는 '열렸다'는 깃발만 세운다
        self.opened = True

    def send_user_text(self, text: str) -> str:
        # 전달받은 텍스트를 기록장에 남기고
        self.sent_texts.append(text)
        # 미리 정한 고정 답변을 돌려준다(진짜 통신 없음 → 즉시·무료)
        return self.reply

    def close(self) -> None:
        # 가짜는 '닫혔다' 상태로만 되돌린다
        self.opened = False


def test_utterance_is_recorded_and_reply_returned():
    # 준비(Arrange): 가짜 세션 + 빈 대화 + 유즈케이스를 조립한다.
    session = FakeRealtimeSession(reply="맑고 따뜻해요.")   # 항상 이 답을 주는 가짜
    convo = Conversation()                                 # 처음엔 턴이 하나도 없는 대화
    # 유즈케이스에 '가짜 세션'과 '대화'를 주입(DI). 진짜 대신 가짜가 들어간다.
    usecase = SendUserUtterance(session=session, conversation=convo)

    # 실행(Act): 사용자가 한마디 한다.
    reply = usecase.execute("오늘 날씨 어때?")

    # 검증(Assert) 1: 어시스턴트 응답이 그대로 반환된다.
    assert reply == "맑고 따뜻해요."

    # 검증 2: 대화에 '사용자 → 어시스턴트' 두 턴이 '순서대로' 쌓였다.
    assert len(convo.turns) == 2                    # 턴이 정확히 2개
    assert convo.turns[0].role == Role.USER         # 첫 턴은 사용자
    assert convo.turns[0].text == "오늘 날씨 어때?"
    assert convo.turns[1].role == Role.ASSISTANT    # 둘째 턴은 어시스턴트
    assert convo.turns[1].text == "맑고 따뜻해요."

    # 검증 3: 가짜 세션에 사용자 텍스트가 '실제로' 전달됐다(유즈케이스가 포트를 올바르게 호출).
    assert session.sent_texts == ["오늘 날씨 어때?"]
```

돌려서 **빨강**을 확인합니다.

```powershell
uv run pytest tests/usecase/test_send_user_utterance.py
```

**예상 출력** (🔴):

```text
ModuleNotFoundError: No module named 'voice_agent.usecase.send_user_utterance'
```

> 💡 **Fake를 왜 직접 만드나요?** 진짜 OpenAI는 느리고, 돈이 들고, 인터넷이 필요합니다. Fake는 **즉시·무료·항상 같은 결과**라 테스트에 완벽합니다. 게다가 "무엇을 보냈는지"를 기록해 두면, 유즈케이스가 올바르게 호출했는지까지 확인할 수 있습니다.

---

## STEP 3 — 🟢 유즈케이스 구현: `SendUserUtterance`

테스트를 통과시키는 유즈케이스를 만듭니다.

```powershell
notepad src/voice_agent/usecase/send_user_utterance.py
```

```python
from voice_agent.domain.conversation import Conversation      # 대화(턴 모음)
from voice_agent.domain.turn import Turn, Role                 # 턴 한 개 + 발화 주체
from voice_agent.usecase.ports import RealtimeSessionPort      # 세션 '약속'(포트) — 진짜가 아니라 약속에만 의존


class SendUserUtterance:
    """사용자 한마디를 받아: 세션에 보내고, 응답을 대화에 기록하고, 돌려준다."""

    def __init__(self, session: RealtimeSessionPort, conversation: Conversation):
        # 생성자에서 '약속(포트)'과 '대화'를 주입받는다(의존성 주입, DI).
        # 타입 힌트가 RealtimeSessionPort라, 그 모양을 만족하면 진짜든 가짜든 받는다.
        self._session = session              # 통신을 맡길 세션(포트 구현체)
        self._conversation = conversation    # 오간 발화를 쌓아둘 대화
        # ↑ 앞의 밑줄(_)은 '이건 내부용'이라는 관례적 표시(파이썬에 강제성은 없음).

    def execute(self, user_text: str) -> str:
        """사용자 발화 한 번을 처리하고 어시스턴트 응답 텍스트를 반환한다."""
        # 1) 사용자 턴을 대화에 기록한다(방금 사용자가 한 말을 남긴다).
        self._conversation.add_turn(Turn(role=Role.USER, text=user_text))

        # 2) 세션(포트)에 보내고 응답을 받는다.
        #    이 한 줄이 진짜 OpenAI인지 가짜인지 유즈케이스는 '전혀 모른다' — 포트 뒤에 숨겨져 있다.
        reply_text = self._session.send_user_text(user_text)

        # 3) 어시스턴트 턴을 대화에 기록한다(받은 응답도 대화에 남긴다).
        self._conversation.add_turn(Turn(role=Role.ASSISTANT, text=reply_text))

        # 4) 응답 텍스트를 호출한 쪽에 돌려준다.
        return reply_text
```

테스트를 다시 돌립니다.

```powershell
uv run pytest tests/usecase/test_send_user_utterance.py
```

**예상 출력** (🟢):

```text
tests/usecase/test_send_user_utterance.py .   [100%]
1 passed in 0.02s
```

✅ 유즈케이스 한 바퀴 완료.

> 💡 **의존성 주입(DI)이란?** 유즈케이스가 세션을 **직접 만들지 않고**, 생성자에서 **받아쓰는** 방식입니다. 덕분에 테스트에선 Fake를, 실제론 OpenAI를 넣어주면 됩니다. 유즈케이스 코드는 그대로입니다.
>
> 💡 **타입 힌트 `session: RealtimeSessionPort`**: "이 자리에는 포트 약속을 만족하는 무엇이든 온다"는 표시입니다. `FakeRealtimeSession`은 같은 메서드 모양을 가지므로 자연스럽게 들어맞습니다.

---

## STEP 4 — 🔴🟢 세션 시작 유즈케이스: `StartConversation`

세션을 열고 빈 대화를 준비하는 유즈케이스도 만듭니다. 빠르게 한 바퀴 돕니다.

**🔴 먼저 테스트:**

```powershell
notepad tests/usecase/test_start_conversation.py
```

```python
from voice_agent.domain.conversation import Conversation      # 대화(턴 모음)
from voice_agent.domain.session_config import SessionConfig   # 세션 설정 값객체
from voice_agent.usecase.start_conversation import StartConversation  # 아직 없음 → RED


class FakeRealtimeSession:
    """이 테스트에 필요한 만큼만 가진 가짜 세션.

    StartConversation은 open()만 쓰므로, 나머지 메서드는 '모양만' 맞춰 둔다.
    (포트의 세 메서드를 다 갖춰야 타입상 세션으로 인정된다.)
    """

    def __init__(self):
        # opened_with: open()이 '어떤 설정으로' 호출됐는지 저장(검증용).
        #   아직 안 열렸으면 None.
        self.opened_with: SessionConfig | None = None

    def open(self, config: SessionConfig) -> None:
        self.opened_with = config   # 넘어온 설정을 그대로 기록해 둔다

    def send_user_text(self, text: str) -> str:
        return ""   # 이 테스트에선 안 쓰지만, 포트 모양을 맞추려 빈 문자열 반환

    def close(self) -> None:
        pass        # 이 테스트에선 할 일 없음(모양만 충족)


def test_start_opens_session_and_returns_empty_conversation():
    session = FakeRealtimeSession()                 # 준비: 가짜 세션
    usecase = StartConversation(session=session)    # 유즈케이스에 주입(DI)

    convo = usecase.execute(SessionConfig())        # 실행: 기본 설정으로 대화 시작

    # 검증 1: open()이 호출됐다(기록이 None이 아니다).
    assert session.opened_with is not None
    # 검증 2: 그때 넘어간 설정의 모델이 기본값이다.
    assert session.opened_with.model == "gpt-realtime"
    # 검증 3: 돌려받은 것이 Conversation 타입이고,
    assert isinstance(convo, Conversation)
    # 검증 4: 아직 발화가 없어 비어 있다.
    assert convo.turns == []
```

**🟢 그다음 구현:**

```powershell
notepad src/voice_agent/usecase/start_conversation.py
```

```python
from voice_agent.domain.conversation import Conversation      # 돌려줄 빈 대화
from voice_agent.domain.session_config import SessionConfig   # 세션을 열 때 쓰는 설정
from voice_agent.usecase.ports import RealtimeSessionPort     # 세션 '약속'(포트)


class StartConversation:
    """세션을 열고, 비어 있는 새 대화를 만들어 돌려준다."""

    def __init__(self, session: RealtimeSessionPort):
        # 세션(포트 구현체)을 주입받아 보관한다(DI).
        self._session = session

    def execute(self, config: SessionConfig) -> Conversation:
        # 1) 주어진 설정으로 세션을 연다(내부적으로 session.update가 나간다 — 4교시 어댑터).
        self._session.open(config)
        # 2) 아직 발화가 없는 '빈 대화'를 만들어 돌려준다.
        #    이후 실제 발화는 SendUserUtterance가 이 대화에 채워 넣는다.
        return Conversation()
```

확인:

```powershell
uv run pytest tests/usecase/test_start_conversation.py
```

**예상 출력**: `1 passed`

---

## STEP 5 — 전체 테스트 한 번에 돌리기

지금까지(2교시 도메인 + 이 교시 유즈케이스)를 모두 검사합니다.

```powershell
uv run pytest -v
```

**예상 출력** (도메인 16 + 유즈케이스 2):

```text
... 18 passed in 0.05s
```

🔵 **REFACTOR 점검**: 두 테스트 파일에 `FakeRealtimeSession`이 중복됩니다. 지금은 각자 필요한 모양이 달라 둬도 되지만, 더 늘어나면 `tests/usecase/fakes.py`로 모아 공유하는 게 좋습니다. (아래 필수 미션에서 다룹니다.)

---

## 🧪 이 교시 TDD 테스트 목록 (체크리스트)

- [x] `test_utterance_is_recorded_and_reply_returned`
- [x] `test_start_opens_session_and_returns_empty_conversation`

**🎯 필수 미션 테스트 (다음 교시 진행 전 반드시 완성)**
- [ ] `ToolRegistryPort` 정의 + `ToolToggleState` 기반 "활성 도구 목록" 유즈케이스 (1개) — *8교시 도구 토글에서 사용*
- [ ] Fake 공유 리팩터링: `tests/usecase/fakes.py`로 중복 제거 후에도 전체 그린 — *3교시 이후 모든 유즈케이스 테스트에서 사용*

**🟦 선택 (여유 있으면)**
- [ ] `SendUserUtterance`가 빈 문자열을 받으면 `ValueError`를 내도록 가드 추가 (1개)

> 💡 막히면 맨 아래 **🧩 필수 미션 — 풀이** 를 펼쳐 보세요.

---

## ✅ 완성 체크포인트 (= 유즈케이스 계층 완성 게이트)

아래가 **모두 충족되어야 다음 교시로 진행**합니다.

- [ ] `src/voice_agent/usecase/` 에 `ports.py`, `send_user_utterance.py`, `start_conversation.py` 존재
- [ ] 유즈케이스 파일들이 **`openai`·`fastrtc`·`fastapi`를 import 하지 않음** (포트와 도메인에만 의존)
- [ ] `uv run pytest` → **최소 19 passed** (도메인 16 + 유즈케이스 2 + 필수 미션 1)
- [ ] `uv run ruff check src/voice_agent` → **All checks passed!**

> **계층 규칙 자가 점검**: 유즈케이스는 "무엇을 할지"만 압니다. `import openai` 같은 게 보이면, 그 통신 코드는 4교시 **어댑터**로 가야 합니다.

---

## ⚠️ 자주 나는 오류 & 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: voice_agent.usecase...` | 파일 경로/이름 오타 또는 `__init__.py` 누락 | 1교시에서 만든 `src/voice_agent/usecase/__init__.py` 확인 |
| `ImportError: cannot import name 'SessionConfig'` | 2교시 필수 미션(`session_config.py`) 미완성 | 2교시 게이트(16 passed)부터 통과시킬 것 |
| 유즈케이스 테스트가 `AttributeError: ... send_user_text` | Fake에 필요한 메서드가 빠짐 | Fake도 포트와 같은 메서드 모양을 갖춰야 함 |
| `TypeError: __init__() missing ... 'session'` | 유즈케이스 생성 시 의존성 미주입 | `SendUserUtterance(session=..., conversation=...)`처럼 넣어줄 것 |
| 테스트가 0개 수집됨 | 함수 이름이 `test_`로 시작 안 함 | pytest는 `test_`로 시작하는 함수만 인식 |

---

## 📖 용어 사전 (이 교시 신규)

- **유즈케이스(use case)**: "사용자 발화 한 번 처리하기"처럼, 앱이 수행하는 하나의 작업 흐름.
- **인터페이스(약속)**: "이런 기능이 있어야 한다"는 모양만 정한 것. 실제 동작은 구현이 채운다.
- **포트(port)**: 바깥과 통신하기 위한 인터페이스(약속). 실제 코드는 없고 모양만 정함.
- **어댑터(adapter)**: 포트를 실제로 구현한 것 (OpenAI 어댑터, Fake 등).
- **`Protocol`**: 파이썬에서 "이런 메서드를 가진 무언가"라는 약속을 표현하는 타입.
- **덕 타이핑(duck typing)**: 상속하지 않아도, **같은 모양의 메서드**만 있으면 그 약속을 만족한 것으로 보는 방식. ("오리처럼 걷고 울면 오리")
- **`...`(Ellipsis)**: Protocol에서 "본문 없음(모양만 선언)"을 나타내는 표기.
- **의존성(dependency)**: 어떤 코드가 동작하려고 기대는 다른 코드.
- **의존성 주입(DI, Dependency Injection)**: 필요한 객체를 직접 만들지 않고 **밖에서 받아쓰는** 방식(주로 생성자로).
- **의존성 역전(DIP, Dependency Inversion Principle)**: 위·아래가 직접 의존하지 않고, 가운데 **약속(포트)**에 의존하도록 뒤집는 원칙.
- **생성자(`__init__`)**: 객체가 만들어질 때 처음 실행되어, 필요한 값을 받아 보관하는 메서드.
- **Fake / 테스트 대역(test double)**: 테스트용으로 진짜 대신 끼우는, 미리 정한 대로 동작하는 객체.
- **리팩터링(refactoring)**: 동작(테스트 결과)은 그대로 두고 코드 구조만 깔끔히 정리하는 작업.

---

## 🎯 필수 미션 — 다음 교시로 가기 전 반드시 완성

직접 🔴RED → 🟢GREEN 으로 만들고, **막히면 아래 접이식 풀이를 펼쳐** 끝까지 완성하세요.

### 1) `ToolRegistryPort` + "활성 도구 목록" 유즈케이스

토글로 켠 도구만 추려 주는 흐름을 만듭니다. (2교시 `ToolToggleState`·`ToolSpec` 사용)

| 미션 | 무엇 | 이게 없으면 막히는 교시 |
|---|---|---|
| `ToolRegistryPort` | 등록된 도구 명세를 돌려주는 약속 | **8교시** — 토글이 어떤 도구가 있는지 알 수 없음 |
| `ListActiveTools` 유즈케이스 | 토글 상태로 활성 도구만 필터 | **8교시** — `session.update`에 넘길 활성 목록을 못 만듦 |

### 2) Fake 공유 리팩터링

두 테스트 파일에 흩어진 `FakeRealtimeSession`을 `tests/usecase/fakes.py` 하나로 모으고, 두 테스트가 그걸 import하도록 바꿉니다. 리팩터링 후에도 **전체 그린**을 유지하세요.

> 풀이는 모두 아래 **🧩 필수 미션 — 풀이** 에 접이식으로 있습니다.

### 🟦 선택 (여유 있으면)

- `SendUserUtterance.execute("")`처럼 빈 발화가 오면 `ValueError`를 내도록 가드를 추가하세요. (테스트부터!)

---

## 🧩 필수 미션 — 풀이 (막히면 펼치기)

> 위 **필수 미션**의 풀이입니다. **먼저 스스로 🔴RED → 🟢GREEN 으로 시도한 뒤** 각 제목을 클릭해 펼쳐 보세요. (기본은 접혀 있습니다.) 모든 코드에 줄별 주석을 달았습니다.

<details>
<summary><strong>📂 풀이 1 — <code>ToolRegistryPort</code> + <code>ListActiveTools</code></strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**무엇 / 왜**: 토글로 켠 도구만 골라, 모델에 넘길 "활성 도구 목록"을 만듭니다. 8교시에서 `session.update`로 보낼 바로 그 목록입니다.

**🟢 포트 추가** — `src/voice_agent/usecase/ports.py` 에 아래를 추가

```python
# 파일 위쪽 import에 ToolSpec 추가
from voice_agent.domain.tool_spec import ToolSpec


class ToolRegistryPort(Protocol):
    """등록된 도구 명세 전체를 돌려주는 약속."""

    def all_specs(self) -> list[ToolSpec]:
        """등록된 모든 도구의 명세를 돌려준다."""
        ...
```

**🔴 테스트** — `tests/usecase/test_list_active_tools.py`

```python
from voice_agent.domain.tool_spec import ToolSpec
from voice_agent.domain.tool_toggle import ToolToggleState
from voice_agent.usecase.list_active_tools import ListActiveTools


class FakeToolRegistry:
    """테스트용 가짜 레지스트리. 고정된 도구 목록을 돌려준다."""

    def __init__(self, specs):
        self._specs = specs

    def all_specs(self):
        return self._specs


def test_only_enabled_tools_are_returned():
    # 두 개의 도구가 등록돼 있고
    registry = FakeToolRegistry([
        ToolSpec(name="weather", description="날씨"),
        ToolSpec(name="search", description="검색"),
    ])
    # 토글로 'weather'만 켠 상태
    toggles = ToolToggleState()
    toggles.toggle("weather")

    usecase = ListActiveTools(registry=registry)
    active = usecase.execute(toggles)

    # 켜진 'weather'만 나와야 한다
    assert [spec.name for spec in active] == ["weather"]
```

**🟢 유즈케이스** — `src/voice_agent/usecase/list_active_tools.py`

```python
from voice_agent.domain.tool_spec import ToolSpec
from voice_agent.domain.tool_toggle import ToolToggleState
from voice_agent.usecase.ports import ToolRegistryPort


class ListActiveTools:
    """토글 상태를 받아, 켜진 도구의 명세만 추려 돌려준다."""

    def __init__(self, registry: ToolRegistryPort):
        # 도구 명세들을 제공하는 레지스트리(포트)를 주입받는다(DI).
        self._registry = registry

    def execute(self, toggles: ToolToggleState) -> list[ToolSpec]:
        # 아래는 '리스트 컴프리헨션'. 세 줄을 위→아래로 이렇게 읽는다:
        #   1) self._registry.all_specs() 로 등록된 전체 도구를 꺼내
        #   2) 하나씩 spec 이라는 이름으로 돌면서
        #   3) toggles.is_enabled(spec.name) 이 참인(켜진) 것만 남겨
        #   → 남은 spec 들을 모아 새 리스트로 돌려준다.
        return [
            spec                                      # 남길 값: 도구 명세 그 자체
            for spec in self._registry.all_specs()    # 전체 도구를 하나씩
            if toggles.is_enabled(spec.name)          # 켜진 것만 통과
        ]
```

```powershell
uv run pytest tests/usecase/test_list_active_tools.py
```

**예상 출력**: `1 passed`

> 💡 유즈케이스는 "켜진 것만 거른다"는 **규칙**만 압니다. 도구가 어디서 등록됐는지(코드/DB/설정)는 `ToolRegistryPort` 뒤의 어댑터 몫입니다.

</details>

---

<details>
<summary><strong>📂 풀이 2 — Fake 공유 리팩터링(<code>tests/usecase/fakes.py</code>)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**무엇 / 왜**: 같은 `FakeRealtimeSession`이 두 파일에 중복됩니다. 한 곳에 모아 import하면 유지보수가 쉬워집니다. (🔵 REFACTOR: 초록을 유지한 채 정리)

**🟢 공유 Fake** — `tests/usecase/fakes.py`

```python
from voice_agent.domain.session_config import SessionConfig


class FakeRealtimeSession:
    """유즈케이스 테스트들이 공유하는 가짜 세션."""

    def __init__(self, reply: str = ""):
        self.reply = reply
        self.opened_with: SessionConfig | None = None
        self.sent_texts: list[str] = []

    def open(self, config: SessionConfig) -> None:
        self.opened_with = config

    def send_user_text(self, text: str) -> str:
        self.sent_texts.append(text)
        return self.reply

    def close(self) -> None:
        self.opened_with = None
```

**두 테스트에서 중복 클래스를 지우고**, 맨 위에서 공유 Fake를 import합니다.

```python
# tests/usecase/test_send_user_utterance.py 맨 위
from tests.usecase.fakes import FakeRealtimeSession
# (파일 안에 있던 class FakeRealtimeSession 정의는 삭제)
```

```python
# tests/usecase/test_start_conversation.py 맨 위
from tests.usecase.fakes import FakeRealtimeSession
# (파일 안에 있던 class FakeRealtimeSession 정의는 삭제)
```

> ⚠️ `from tests.usecase.fakes import ...`가 동작하려면 `tests/__init__.py`와 `tests/usecase/__init__.py`가 있어야 합니다(1·3교시에서 생성). 없으면 만들어 주세요.

리팩터링 후 **전체가 여전히 그린**인지 확인합니다.

```powershell
uv run pytest
```

**예상 출력**: 이전과 같은 개수가 그대로 `passed` (동작은 그대로, 코드만 깔끔)

> 💡 **리팩터링의 철칙**: 테스트가 초록인 상태에서만 정리하고, 정리 직후 다시 돌려 **여전히 초록**인지 확인합니다. 그래야 "정리하다 망가뜨리는" 사고를 막습니다.

</details>

---

<details>
<summary><strong>📂 풀이 3 (선택) — 빈 발화 가드</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**🔴 테스트** — `tests/usecase/test_send_user_utterance.py` 에 추가

```python
import pytest

from voice_agent.domain.conversation import Conversation
from voice_agent.usecase.send_user_utterance import SendUserUtterance
from tests.usecase.fakes import FakeRealtimeSession


def test_empty_utterance_is_rejected():
    usecase = SendUserUtterance(
        session=FakeRealtimeSession(reply="응답"),
        conversation=Conversation(),
    )
    # 빈 문자열/공백만 있는 발화는 ValueError
    with pytest.raises(ValueError):
        usecase.execute("   ")
```

**🟢 구현** — `SendUserUtterance.execute` 맨 앞에 가드 추가

```python
    def execute(self, user_text: str) -> str:
        # 공백을 제거했을 때 비어 있으면 처리하지 않는다
        if not user_text.strip():
            raise ValueError("빈 발화는 보낼 수 없습니다")
        # ... 이하 기존 로직 동일
```

```powershell
uv run pytest tests/usecase/test_send_user_utterance.py
```

**예상 출력**: 기존 + 새 테스트 모두 `passed`

</details>

---

### ✅ 미션 완료 확인 (= 진행 게이트)

필수 미션까지 끝내고 전체 테스트를 돌립니다.

```powershell
uv run pytest
```

**예상 출력** (대략):

```text
... 19 passed in 0.06s
```

- **필수**: 도메인 16 + `SendUserUtterance` 1 + `StartConversation` 1 + `ListActiveTools` 1 = **19 passed** (Fake 리팩터링은 개수 변화 없음)
- 선택 가드까지 하면 → **20 passed**

여기에 더해 `uv run ruff check src/voice_agent` 이 **All checks passed!** 면 게이트 통과입니다.

---

**다음 교시 예고 — 4교시**: 이 교시에 만든 `RealtimeSessionPort`의 **첫 진짜 구현**인 OpenAI Realtime 어댑터를 만듭니다. 텍스트로 한 턴을 실제로 왕복합니다(여기서 `SessionConfig`가 쓰입니다). 통신은 모킹으로 테스트해 비용 0을 유지합니다.
> **선행**: 위 유즈케이스 계층 완성 게이트(최소 19 passed + ruff clean) 통과 상태.
