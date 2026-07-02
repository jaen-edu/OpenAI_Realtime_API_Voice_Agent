# 2교시 — 도메인 계층 만들기 (Test-First TDD)

> **이 교시가 끝나면** 외부에 전혀 의존하지 않는 **순수한 도메인 모델**이 완성되고, 그에 대한 테스트가 모두 초록불이 됩니다. 보이스 에이전트의 "심장"을 가장 먼저, 가장 단단하게 만듭니다.

---

## 0. 이 교시에 만드는 것 (한눈에)

대화(`Conversation`)는 여러 개의 발화 턴(`Turn`)으로 이루어집니다. 그리고 어떤 도구가 켜져 있는지(`ToolToggleState`)를 기억합니다. 이 교시에는 이 **개념들을 코드로** 옮깁니다.

```
Conversation
 ├─ Turn(role=USER,      text="오늘 날씨 어때?")
 ├─ Turn(role=ASSISTANT, text="맑고 따뜻해요.")
 └─ ...

ToolToggleState(enabled={"weather"})   ← '날씨' 도구만 켜진 상태
```

**중요한 규칙 하나**: 이 파일들은 `openai`, `fastrtc`, `fastapi` 같은 걸 **절대 import 하지 않습니다.** 오직 파이썬 표준 기능만 씁니다.

---

## 🧭 잠깐, 배경지식

이 교시에 계속 나오는 파이썬 개념 몇 가지를 짚고 갑니다.

**① 클래스와 객체.** **클래스**는 "데이터의 틀(설계도)"이고, 그 틀로 실제로 찍어낸 하나하나가 **객체(인스턴스)**입니다. 예를 들어 `Turn`은 "역할 + 텍스트"라는 틀이고, `Turn(role=USER, text="안녕")`은 그 틀로 만든 구체적인 객체 하나입니다.

**② 값객체(value object).** 도메인에서 다루는 데이터 묶음을 담는 객체입니다. 핵심 성질은 **"값이 같으면 같은 것으로 취급"**하고, 보통 한 번 만들면 **바꾸지 않는다(불변)**는 점입니다. 이미 일어난 한 번의 발화(`Turn`)는 나중에 내용이 바뀌면 안 되니 값객체로 만듭니다.

**③ 타입 힌트(type hint).** `text: str`, `sample_rate: int`처럼 **"이 자리에 어떤 종류의 값이 오는지"**를 적어두는 표기입니다. 실행 속도에는 영향이 없지만, 코드를 읽기 쉽게 하고 편집기가 실수를 잡아줍니다. `str | None`은 "문자열이거나 None", `list[Turn]`은 "Turn들의 리스트"를 뜻합니다.

**④ 왜 테스트를 먼저 쓰나(TDD).** "무엇을 만들지"를 테스트로 먼저 약속하고, 그걸 만족시키는 코드를 나중에 씁니다. 만들려는 것이 명확해지고, 나중에 코드를 고쳐도 테스트가 깨지면 바로 알 수 있어 안심하고 수정할 수 있습니다.

> 💡 이 개념들은 아래에서 코드로 직접 만들며 자연스럽게 익힙니다. 지금은 단어와 대략의 뜻만 눈에 익혀두면 됩니다.

---

## 1. 개념 빠르게 잡기

### 양파 그림으로 보는 Clean Architecture

> 코드를 양파라고 생각해 보세요.
>
> ```
> [ infra ]  ← 바깥: OpenAI, 브라우저, DB 등 "세상"과 연결
>  [ adapter ]
>   [ usecase ]
>    [ domain ]  ← 가장 안쪽: 순수한 규칙과 데이터. 아무것도 의존하지 않음
> ```
>
> **바깥은 안쪽을 알아도 되지만, 안쪽은 바깥을 몰라야 합니다.** 도메인은 OpenAI가 뭔지, 브라우저가 뭔지 전혀 모릅니다. 그래서 가장 **안정적**이고 **테스트하기 쉽습니다.**

💡 **왜 도메인을 제일 먼저?** 외부에 의존하지 않으니 인터넷도, API 키도, 가짜 객체도 필요 없습니다. `Turn(role, text)` 만들고 값만 확인하면 끝. **테스트가 가장 쉬운 곳부터 시작**해서 토대를 다지는 전략입니다.

### TDD 3박자: 🔴 RED → 🟢 GREEN → 🔵 REFACTOR

> 1. 🔴 **RED**: 아직 없는 기능의 **테스트를 먼저** 씁니다. 당연히 실패(빨강).
> 2. 🟢 **GREEN**: 테스트를 통과하는 **최소한의 코드**를 씁니다. 통과(초록).
> 3. 🔵 **REFACTOR**: 통과를 유지한 채 코드를 깔끔하게 정리합니다.
>
> "테스트 → 코드" 순서가 핵심입니다. **무엇을 만들지 먼저 약속하고, 그걸 만족시키는** 방식입니다.

---

## STEP 1 — 🔴 첫 테스트 쓰기: `Turn`

발화 한 번을 표현하는 `Turn`을 만들 겁니다. 코드보다 **테스트를 먼저** 씁니다.

`tests/domain/__init__.py`를 만들고(폴더를 패키지로 인식시키기), 테스트 파일을 작성합니다.

```powershell
New-Item -ItemType File -Force -Path tests/domain/__init__.py | Out-Null
notepad tests/domain/test_turn.py
```

아래를 붙여넣고 저장합니다.

```python
from voice_agent.domain.turn import Turn, Role


def test_turn_holds_role_and_text():
    # Turn 객체를 USER 역할과 텍스트로 생성
    turn = Turn(role=Role.USER, text="오늘 날씨 어때?")

    # Turn 객체의 role이 USER인지 확인
    assert turn.role == Role.USER
    # Turn 객체의 text가 올바르게 저장되었는지 확인
    assert turn.text == "오늘 날씨 어때?"
```

지금 테스트를 돌리면 **실패**합니다 (`turn.py`가 아직 없으니까요).

```powershell
uv run pytest tests/domain/test_turn.py
```

**예상 출력** (🔴 빨강, 이게 정상입니다):

```text
ModuleNotFoundError: No module named 'voice_agent.domain.turn'
```

> 💡 **실패를 봐야 하는 이유**: 테스트가 "제대로 실패"하는 걸 확인해야, 나중에 초록불이 떴을 때 그게 **진짜 통과**임을 믿을 수 있습니다.

---

## STEP 2 — 🟢 `Turn` 구현해서 통과시키기

이제 테스트를 만족하는 **최소한의 코드**를 씁니다.

```powershell
notepad src/voice_agent/domain/turn.py
```

```python
from dataclasses import dataclass   # 데이터 보관용 클래스를 짧게 정의하는 표준 도구
from enum import Enum               # 정해진 선택지만 허용하는 '열거형'을 만드는 표준 도구


class Role(str, Enum):
    """발화 주체: 사용자 또는 어시스턴트.

    (str, Enum)을 함께 상속하면 '문자열이면서 선택지'가 된다.
    → Role.USER == "user" 처럼 문자열로도 비교할 수 있어 편리하다.
    """
    USER = "user"            # 사용자의 발화를 나타내는 선택지
    ASSISTANT = "assistant"  # 어시스턴트의 발화를 나타내는 선택지


@dataclass(frozen=True)   # frozen=True: 한 번 만들면 값을 못 바꾸는 불변 객체로
class Turn:
    """대화의 한 턴(발화 한 번)."""
    role: Role   # 이 발화의 주체 (Role.USER 또는 Role.ASSISTANT)
    text: str    # 이 발화의 내용(문자열)
    # ↑ @dataclass가 위 두 필드를 받는 __init__을 자동으로 만들어 준다.
    #   그래서 Turn(role=..., text=...) 형태로 바로 생성할 수 있다.
```

테스트를 다시 돌립니다.

```powershell
uv run pytest tests/domain/test_turn.py
```

**예상 출력** (🟢 초록):

```text
tests/domain/test_turn.py .              [100%]
1 passed in 0.01s
```

✅ 첫 TDD 한 바퀴 완료.

> 💡 **`@dataclass(frozen=True)`가 뭐죠?**
> - `@dataclass`: `__init__` 같은 걸 자동으로 만들어 줘서, 데이터를 담는 클래스를 짧게 쓸 수 있습니다.
> - `frozen=True`: 한 번 만들면 **값을 못 바꾸는** 객체가 됩니다. 이미 한 발화는 바뀌면 안 되니까요(불변).
> - `class Role(str, Enum)`: 정해진 값(`user`/`assistant`)만 쓰도록 강제하는 "선택지 목록"입니다. 오타로 `"usr"` 같은 걸 넣는 실수를 막아줍니다.

---

## STEP 3 — 🔴 `Conversation` 테스트 쓰기

여러 턴을 모으는 `Conversation`을 만듭니다. 역시 테스트 먼저.

```powershell
notepad tests/domain/test_conversation.py
```

```python
from voice_agent.domain.conversation import Conversation
from voice_agent.domain.turn import Turn, Role


def test_new_conversation_is_empty():
    # 새로운 대화는 빈 상태로 초기화되어야 함
    convo = Conversation()
    assert convo.turns == []


def test_add_turn_appends():
    # add_turn 메서드가 턴을 리스트에 추가하는지 확인
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="안녕"))

    assert len(convo.turns) == 1
    assert convo.turns[0].text == "안녕"


def test_last_user_text_returns_most_recent_user_utterance():
    # last_user_text 메서드가 가장 최근의 사용자 발화를 반환하는지 확인
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="첫 질문"))
    convo.add_turn(Turn(role=Role.ASSISTANT, text="답변"))
    convo.add_turn(Turn(role=Role.USER, text="두 번째 질문"))

    assert convo.last_user_text() == "두 번째 질문"
```

돌려서 **빨강**을 확인합니다.

```powershell
uv run pytest tests/domain/test_conversation.py
```

**예상 출력** (🔴):

```text
ModuleNotFoundError: No module named 'voice_agent.domain.conversation'
```

---

## STEP 4 — 🟢 `Conversation` 구현

```powershell
notepad src/voice_agent/domain/conversation.py
```

```python
from dataclasses import dataclass, field

from voice_agent.domain.turn import Turn, Role


@dataclass
class Conversation:
    """여러 턴을 순서대로 담는 대화."""
    # 대화 구성 턴들의 리스트
    turns: list[Turn] = field(default_factory=list)

    def add_turn(self, turn: Turn) -> None:
        """대화 끝에 턴을 추가한다."""
        # 새로운 턴을 turns 리스트에 추가
        self.turns.append(turn)

    def last_user_text(self) -> str | None:
        """가장 최근 사용자 발화의 텍스트. 없으면 None."""
        # 뒤에서 앞으로 턴을 반복 순회
        for turn in reversed(self.turns):
            # 사용자 역할인 턴을 찾으면
            if turn.role == Role.USER:
                # 해당 턴의 텍스트 반환
                return turn.text
        # 사용자 턴이 없으면 None 반환
        return None
```

테스트를 돌립니다.

```powershell
uv run pytest tests/domain/test_conversation.py
```

**예상 출력** (🟢):

```text
tests/domain/test_conversation.py ...    [100%]
3 passed in 0.01s
```

✅ 통과.

> 💡 **`field(default_factory=list)`는 왜?** 기본값으로 그냥 `[]`를 쓰면 모든 `Conversation`이 **같은 리스트 하나를 공유**하는 유명한 버그가 생깁니다. `default_factory=list`는 객체를 만들 때마다 **새 빈 리스트**를 줍니다.
>
> 💡 **`str | None`은?** "문자열이거나 None일 수 있다"는 뜻입니다. 사용자 발화가 아직 없으면 `None`을 돌려줍니다.

---

## STEP 5 — 🔵 도구 토글 상태 추가 (`ToolToggleState`)

토글 버튼으로 켜고 끄는 **도구의 on/off 상태**를 도메인에 담습니다. 한 바퀴를 빠르게 돕니다.

**🔴 먼저 테스트:**

```powershell
notepad tests/domain/test_tool_toggle.py
```

```python
from voice_agent.domain.tool_toggle import ToolToggleState


def test_new_state_has_nothing_enabled():
    """새로운 상태에서는 모든 도구가 비활성화되어 있는지 확인"""
    state = ToolToggleState()
    assert state.is_enabled("weather") is False


def test_toggle_turns_on_then_off():
    """토글 기능이 도구를 켜고 끌 수 있는지 확인"""
    state = ToolToggleState()

    state.toggle("weather")      # 켜기
    assert state.is_enabled("weather") is True

    state.toggle("weather")      # 다시 끄기
    assert state.is_enabled("weather") is False


def test_multiple_tools_independent():
    """여러 도구들이 독립적으로 관리되는지 확인"""
    state = ToolToggleState()
    state.toggle("weather")
    state.toggle("search")

    assert state.is_enabled("weather") is True
    assert state.is_enabled("search") is True
    assert state.is_enabled("booking") is False
```

**🟢 그다음 구현:**

```powershell
notepad src/voice_agent/domain/tool_toggle.py
```

```python
from dataclasses import dataclass, field


@dataclass
class ToolToggleState:
    """현재 켜져 있는 도구 이름들의 집합."""
    # 활성화된 도구 이름들을 저장하는 집합
    enabled: set[str] = field(default_factory=set)

    def toggle(self, name: str) -> None:
        """켜져 있으면 끄고, 꺼져 있으면 켠다."""
        # 도구가 이미 활성화되어 있으면 제거
        if name in self.enabled:
            self.enabled.discard(name)
        # 도구가 비활성화되어 있으면 추가
        else:
            self.enabled.add(name)

    def is_enabled(self, name: str) -> bool:
        # 도구가 활성화 상태인지 확인
        return name in self.enabled
```

확인:

```powershell
uv run pytest tests/domain/test_tool_toggle.py
```

**예상 출력**: `3 passed`

---

## STEP 6 — 전체 도메인 테스트 한 번에 돌리기

지금까지 만든 걸 모두 검사합니다.

```powershell
uv run pytest
```

**예상 출력** (1교시 smoke 테스트 포함):

```text
tests/domain/test_conversation.py ...
tests/domain/test_tool_toggle.py ...
tests/domain/test_turn.py .
tests/test_smoke.py .
==== 7 passed in 0.03s ====
```

🔵 **REFACTOR 점검**: 지금 코드는 충분히 단순해 정리할 게 없습니다. 나중에 중복이 생기면 "초록불을 유지한 채" 정리하면 됩니다.

---

## 🧪 이 교시 TDD 테스트 목록 (체크리스트)

이 교시에 작성한 테스트입니다. 모두 초록이어야 합니다.

- [x] `test_turn_holds_role_and_text`
- [x] `test_new_conversation_is_empty`
- [x] `test_add_turn_appends`
- [x] `test_last_user_text_returns_most_recent_user_utterance`
- [x] `test_new_state_has_nothing_enabled`
- [x] `test_toggle_turns_on_then_off`
- [x] `test_multiple_tools_independent`

**🎯 필수 미션 테스트 (다음 교시 진행 전 반드시 완성)** — 직접 RED→GREEN으로 채웁니다. 막히면 아래 접이식 풀이를 펼쳐 끝까지 완성하세요.
- [ ] `ToolSpec` 값 보관 테스트 (2개) — *8교시 도구 토글에서 사용*
- [ ] `SessionConfig` 기본값 테스트 (2개) — *4교시 Realtime 세션에서 사용*
- [ ] `AudioFrame` 유효성 테스트 (3개) — *5·6교시 오디오에서 사용*
- [ ] `Turn.audio` 선택 필드 테스트 (2개) — *5·6교시 음성 턴에서 사용 · AudioFrame 선행*

**🟦 선택 (여유 있으면)**
- [ ] `Conversation.assistant_replies()` 테스트 (1개) — *7교시 전사 패널에서 활용*

> 💡 막히면 맨 아래 **🧩 필수 미션 — 풀이** 를 펼쳐 보세요. 풀이가 있으니 아무도 막혀서 멈추지 않습니다.

---

## ✅ 완성 체크포인트 (= 도메인 계층 완성 게이트)

아래가 **모두 충족되어야 다음 교시로 진행**합니다.

- [ ] `src/voice_agent/domain/` 에 6개 파일 존재: `turn.py`, `conversation.py`, `tool_toggle.py`, `tool_spec.py`, `session_config.py`, `audio_frame.py`
- [ ] 도메인 파일들이 **외부 라이브러리를 import 하지 않음** (오직 표준 `dataclasses`, `enum`, `typing`)
- [ ] `uv run pytest` → **최소 16 passed** (필수 미션 포함. 선택 과제까지 하면 17)
- [ ] `uv run ruff check src/voice_agent/domain` → **All checks passed!**

> **계층 규칙 자가 점검**: `src/voice_agent/domain/` 안의 어떤 파일이든 `import openai`, `import fastrtc`, `import fastapi`가 **하나도 없어야** 합니다. 있으면 도메인이 오염된 것 — 즉시 걷어내세요.

---

## ⚠️ 자주 나는 오류 & 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: voice_agent.domain.turn` | 파일 경로/이름 오타 또는 `__init__.py` 누락 | 경로가 `src/voice_agent/domain/turn.py` 인지, `__init__.py`가 있는지 확인 |
| `ModuleNotFoundError: voice_agent` (전체) | 1교시 `pythonpath=["src"]` 미설정 | `pyproject.toml`의 `[tool.pytest.ini_options]` 확인 |
| `ImportError: cannot import name 'Role'` | `turn.py`에 `Role`을 안 만듦 | STEP 2 코드 다시 확인 |
| `FrozenInstanceError` | `frozen=True`인 `Turn`의 값을 바꾸려 함 | 턴은 불변. 바꾸지 말고 새 `Turn`을 만들 것 |
| 한글 assert 메시지가 깨짐 | 터미널 인코딩 | 1교시 STEP 2(UTF-8) 재확인 |
| 테스트가 0개 수집됨(`no tests ran`) | 함수 이름이 `test_`로 시작 안 함 | pytest는 `test_`로 시작하는 함수만 인식 |

---

## 📖 용어 사전 (이 교시 신규)

- **도메인(domain)**: 앱의 핵심 개념과 규칙. 외부 기술과 무관한 가장 안쪽 계층.
- **클래스 / 객체(인스턴스)**: 데이터의 틀(클래스)과, 그 틀로 만든 실제 하나(객체).
- **엔티티 / 값객체**: 데이터를 담는 도메인 객체. 값객체는 "값이 같으면 같음"으로 보고 보통 불변.
- **dataclass**: 데이터 보관용 클래스를 짧게 정의하는 파이썬 기능. `__init__` 등을 자동 생성.
- **`field(default_factory=list)`**: 객체를 만들 때마다 **새 빈 리스트/집합/딕셔너리**를 기본값으로 준다. `= []`처럼 쓰면 모든 객체가 하나를 공유하는 버그가 생긴다.
- **`__post_init__`**: dataclass가 필드를 다 채운 직후 자동 호출되는 검증 훅. 잘못된 객체 생성을 막는 데 쓴다.
- **불변(immutable / frozen)**: 한 번 만들면 값이 바뀌지 않는 객체.
- **Enum(열거형)**: 정해진 선택지(예: USER/ASSISTANT)만 허용하는 타입. 오타를 막아준다.
- **타입 힌트(type hint)**: `text: str`처럼 값의 종류를 적는 표기. `str | None`=문자열이거나 없음, `list[Turn]`=Turn들의 목록.
- **집합(set)**: 중복 없는 값들의 모음. "켜진 도구 이름들"처럼 있음/없음만 중요할 때 쓴다.
- **리스트 컴프리헨션**: `[x for x in 목록 if 조건]` — 목록을 돌며 조건에 맞는 것만 골라 새 리스트를 만드는 짧은 문법.
- **TDD (Test-Driven Development)**: 테스트를 먼저 쓰고 그걸 통과시키는 개발 방식.
- **RED/GREEN/REFACTOR**: 실패 → 통과 → 정리의 3박자.
- **`pytest.raises`**: "이 블록에서 이 에러가 나야 정상"임을 검사하는 테스트 도구.
- **린터(linter)**: 코드를 실행하지 않고도 스타일·간단한 오류를 찾아주는 검사기(여기선 ruff).

---

## 🎯 필수 미션 — 다음 교시로 가기 전 반드시 완성

아래는 **"있으면 좋은" 추가 과제가 아니라, 뒤 교시가 돌아가기 위한 부품**입니다. 각 미션 옆에 *어느 교시가 이걸 필요로 하는지* 적어 두었습니다. 직접 🔴RED → 🟢GREEN 으로 만들고, **막히면 아래 접이식 풀이를 펼쳐** 끝까지 완성하세요.

### 1) 반드시 완성해야 하는 도메인 객체

| 미션 | 무엇 | 이게 없으면 막히는 교시 |
|---|---|---|
| `ToolSpec` | 도구 명세 값객체 | **8교시** — 도구 토글이 도구를 정의할 수 없음 |
| `SessionConfig` | 세션 설정 + 기본값 | **4교시** — Realtime 세션을 어떤 설정으로 열지 못 정함 |
| `AudioFrame` | 오디오 조각 + 유효성 | **5·6교시** — 음성 데이터를 도메인에서 다룰 수 없음 |
| `Turn.audio` | 턴에 음성 첨부(선택 필드) | **5·6교시** — 음성이 실린 턴을 표현 불가 (AudioFrame 선행) |

> 풀이는 모두 아래 **🧩 필수 미션 — 풀이** 에 접이식으로 있습니다.

### 2) 반드시 한 번은 실행 — `ruff`

도메인 코드를 린터로 검사해 **경고 0 (`All checks passed!`)** 상태를 만듭니다. 깨끗한 코드 습관을 첫날부터 들입니다.

```powershell
uv run ruff check src/voice_agent/domain
```

자동으로 고칠 수 있는 항목은 `--fix`로 정리합니다.

```powershell
uv run ruff check --fix src/voice_agent/domain
```

### 🟦 선택 (여유 있으면)

- `Conversation.assistant_replies()` — 어시스턴트 발화만 모으는 메서드. 7교시 전사 패널에서 쓰입니다. (풀이 4 참고)

---

## 🧩 필수 미션 — 풀이 (막히면 펼치기)

> 위 **필수 미션**의 풀이입니다. **먼저 스스로 🔴RED → 🟢GREEN 으로 시도한 뒤, 아래 각 풀이 제목을 클릭해 펼쳐 보세요.** (기본은 접혀 있습니다.) 모든 코드에 줄별 주석을 달았습니다. 여기 나오는 객체들은 8교시(도구)·4교시(세션 설정)·5·6교시(오디오)에서 실제로 다시 등장합니다 — 지금 만들어 두면 그때 수월합니다.

<details>
<summary><strong>📂 풀이 1 — <code>ToolSpec</code> (도구 명세 값객체)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>


**무엇 / 왜**: 에이전트가 호출할 수 있는 도구 "하나"가 어떤 이름·설명·입력을 갖는지 적어두는 **설명서**입니다. 실제 실행 코드가 아니라 메타데이터만 담으므로 순수 도메인에 둡니다. (8교시 ToolRegistry의 기본 재료)

**🔴 테스트** — `tests/domain/test_tool_spec.py`

```python
from voice_agent.domain.tool_spec import ToolSpec


def test_tool_spec_holds_name_and_description():
    # 이름과 설명만으로 ToolSpec을 만들 수 있어야 한다
    spec = ToolSpec(name="weather", description="도시의 현재 날씨를 알려준다")

    assert spec.name == "weather"                    # 이름이 그대로 보관되는가
    assert spec.description == "도시의 현재 날씨를 알려준다"  # 설명이 그대로 보관되는가
    assert spec.parameters == {}                     # 파라미터를 안 주면 빈 dict가 기본


def test_tool_spec_holds_parameters():
    # 파라미터 스펙(JSON 스키마 형태)도 담을 수 있어야 한다
    spec = ToolSpec(
        name="weather",
        description="날씨 조회",
        parameters={"city": {"type": "string"}},     # city는 문자열 입력이라는 스펙
    )

    # 중첩된 dict 안의 값까지 잘 들어갔는지 확인
    assert spec.parameters["city"]["type"] == "string"
```

**🟢 구현** — `src/voice_agent/domain/tool_spec.py`

```python
from dataclasses import dataclass, field
from typing import Any  # "아무 타입이나"를 뜻하는 표기. 파라미터 스펙 값이 자유로워서 사용


@dataclass(frozen=True)  # frozen: 한 번 정의한 도구 명세는 바뀌지 않음(불변)
class ToolSpec:
    """에이전트가 호출할 수 있는 '도구 하나'의 명세(설명서)."""

    name: str          # 도구 이름. 모델이 이 이름으로 도구를 지목한다 (예: "weather")
    description: str   # 도구 설명. 모델이 '언제 이 도구를 쓸지' 판단하는 근거가 된다

    # 파라미터 스펙: { "인자이름": { "type": "string" ... } } 형태의 dict.
    # default_factory=dict → 객체를 만들 때마다 '새 빈 dict'를 준다 (리스트 때와 같은 공유 버그 방지)
    parameters: dict[str, Any] = field(default_factory=dict)
```

```powershell
uv run pytest tests/domain/test_tool_spec.py
```

**예상 출력**: `2 passed`

> 💡 **`dict[str, Any]`?** "키는 문자열, 값은 무엇이든"이라는 뜻입니다. 파라미터 스펙의 값 모양이 도구마다 달라서 `Any`로 열어 둡니다.

</details>

---

<details>
<summary><strong>📂 풀이 2 — <code>SessionConfig</code> (세션 설정 + 기본값)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>


**무엇 / 왜**: 보이스 세션을 시작할 때 쓰는 설정 묶음입니다. 기본값을 도메인에 박아두면, 매번 일일이 지정하지 않아도 됩니다. (4교시 Realtime 어댑터가 이 값을 읽어 세션을 엽니다)

**🔴 테스트** — `tests/domain/test_session_config.py`

```python
from voice_agent.domain.session_config import SessionConfig


def test_defaults():
    # 아무 인자 없이 만들면 '약속된 기본값'이 들어가야 한다
    cfg = SessionConfig()

    assert cfg.model == "gpt-realtime"    # 접근성 넓은 GA 실시간 모델
    assert cfg.voice == "alloy"           # 기본 음성
    assert cfg.reasoning_effort == "low"  # 1교시에서 정한 비용·지연 절약 기본값


def test_override():
    # 일부만 바꿔도, 나머지는 기본값을 유지해야 한다
    cfg = SessionConfig(voice="verse", reasoning_effort="medium")

    assert cfg.voice == "verse"            # 바꾼 값은 반영
    assert cfg.reasoning_effort == "medium"
    assert cfg.model == "gpt-realtime"     # 안 바꾼 값은 그대로 기본값
```

**🟢 구현** — `src/voice_agent/domain/session_config.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)  # 설정값은 한 세션 동안 바뀌지 않으므로 불변으로
class SessionConfig:
    """보이스 세션을 시작할 때 쓰는 설정값 묶음."""

    # 아래는 모두 '기본값(= 뒤의 값)'을 가진 필드.
    # 호출 시 생략하면 이 기본값이 자동으로 쓰인다.
    model: str = "gpt-realtime"     # 접근성 넓은 GA 실시간 모델 (대부분 계정에서 바로 사용 가능)
    voice: str = "alloy"            # 합성 음성 종류 (실제 사용 가능한 이름은 4교시 어댑터에서 검증)
    reasoning_effort: str = "low"   # 추론 강도. low=빠르고 저렴 → 비용 가드의 핵심
```

```powershell
uv run pytest tests/domain/test_session_config.py
```

**예상 출력**: `2 passed`

> 💡 **기본값이 있는 필드**는 `이름: 타입 = 기본값` 으로 적습니다. 객체를 만들 때 그 인자를 생략하면 기본값이 쓰입니다.
>
> 💡 **모델 선택**: 기본값 `gpt-realtime`은 첫 GA 실시간 모델로 대부분의 계정에서 바로 됩니다. 계정에 **`gpt-realtime-2`** 접근 권한이 있다면 `SessionConfig(model="gpt-realtime-2")`로 올릴 수 있고, 이 모델은 `reasoning_effort`(추론 강도) 조절을 지원합니다. 접근 권한이 없으면 "model does not exist or you do not have access" 오류가 나므로 **기본은 `gpt-realtime`**으로 둡니다.

</details>

---

<details>
<summary><strong>📂 풀이 3 — <code>AudioFrame</code> (오디오 조각 + 유효성 검사)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>


**무엇 / 왜**: 음성 한 조각을 표현합니다. "샘플레이트가 0이거나 데이터가 비면 잘못된 프레임"이라는 **규칙(유효성)**을 도메인이 직접 지킵니다. 잘못된 값은 만들어지는 순간 막습니다.

**🔴 테스트** — `tests/domain/test_audio_frame.py`

```python
import pytest  # 예외(에러) 발생을 테스트하는 도구

from voice_agent.domain.audio_frame import AudioFrame


def test_valid_frame():
    # 올바른 값이면 그대로 만들어져야 한다
    frame = AudioFrame(sample_rate=24000, data=b"\x00\x01")

    assert frame.sample_rate == 24000
    assert frame.data == b"\x00\x01"


def test_zero_sample_rate_is_rejected():
    # 샘플레이트가 0이면 만들 때 ValueError가 나야 한다
    # pytest.raises(...) 블록 안에서 '그 에러가 발생하는지'를 검사
    with pytest.raises(ValueError):
        AudioFrame(sample_rate=0, data=b"\x00")


def test_empty_data_is_rejected():
    # 데이터가 비어 있으면 ValueError가 나야 한다
    with pytest.raises(ValueError):
        AudioFrame(sample_rate=24000, data=b"")
```

**🟢 구현** — `src/voice_agent/domain/audio_frame.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioFrame:
    """오디오 한 조각: 샘플레이트 + 실제 음성 바이트.

    도메인은 numpy 같은 외부 라이브러리에 의존하지 않으므로,
    데이터는 파이썬 표준 타입인 bytes로 받는다.
    (numpy 배열 <-> bytes 변환은 바깥 계층인 어댑터의 몫 — 5교시)
    """

    sample_rate: int  # 1초당 샘플 수. 예: 24000 = 24kHz
    data: bytes       # PCM 오디오 원본 바이트

    def __post_init__(self) -> None:
        # __post_init__: dataclass가 필드를 다 채운 '직후' 자동으로 한 번 호출되는 검증 훅.
        # 여기서 규칙을 어기면 객체 생성 자체를 막는다(에러를 던진다).
        if self.sample_rate <= 0:
            raise ValueError("sample_rate는 0보다 커야 합니다")
        if len(self.data) == 0:
            raise ValueError("data는 비어 있을 수 없습니다")
```

```powershell
uv run pytest tests/domain/test_audio_frame.py
```

**예상 출력**: `3 passed`

> 💡 **`__post_init__`** 는 "객체가 막 만들어진 직후 검사하고 싶을 때" 쓰는 특별한 메서드입니다. 덕분에 **잘못된 데이터를 가진 객체는 애초에 존재할 수 없게** 됩니다.
>
> 💡 **`with pytest.raises(ValueError):`** 는 "이 블록 안에서 `ValueError`가 나야 정상"이라는 뜻입니다. 에러가 안 나면 테스트가 실패합니다.

</details>

---

<details>
<summary><strong>📂 풀이 4 — <code>Conversation.assistant_replies()</code></strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>


**무엇 / 왜**: 대화에서 **어시스턴트가 말한 텍스트만** 순서대로 뽑아 줍니다. (전사 화면이나 로그에서 응답만 보고 싶을 때)

**🔴 테스트** — `tests/domain/test_conversation.py` 에 함수 추가

```python
def test_assistant_replies_returns_only_assistant_texts():
    # 사용자/어시스턴트가 섞인 대화에서, 어시스턴트 발화만 모이는지 확인
    convo = Conversation()
    convo.add_turn(Turn(role=Role.USER, text="안녕"))
    convo.add_turn(Turn(role=Role.ASSISTANT, text="네 안녕하세요"))
    convo.add_turn(Turn(role=Role.USER, text="날씨는?"))
    convo.add_turn(Turn(role=Role.ASSISTANT, text="맑아요"))

    # 어시스턴트 발화 텍스트만, 말한 순서대로
    assert convo.assistant_replies() == ["네 안녕하세요", "맑아요"]
```

**🟢 구현** — `src/voice_agent/domain/conversation.py` 의 `Conversation` 클래스에 메서드 추가

```python
    def assistant_replies(self) -> list[str]:
        """어시스턴트가 말한 텍스트만 순서대로 모아 돌려준다."""
        # 리스트 컴프리헨션 읽는 법(뒤에서부터):
        #   self.turns 를 하나씩 turn 으로 꺼내서(for turn in self.turns)
        #   role 이 ASSISTANT 인 것만 남기고(if turn.role == Role.ASSISTANT)
        #   그 turn 의 text 를 모아 새 리스트로 만든다([turn.text ...])
        return [turn.text for turn in self.turns if turn.role == Role.ASSISTANT]
```

```powershell
uv run pytest tests/domain/test_conversation.py
```

**예상 출력**: `4 passed` (기존 3개 + 새 1개)

> 💡 **리스트 컴프리헨션** `[x for x in 목록 if 조건]` 은 "목록을 돌면서 조건에 맞는 것만 골라 새 리스트를 만드는" 짧은 문법입니다. `for`문으로 풀어 써도 결과는 같습니다.

</details>

---

<details>
<summary><strong>📂 풀이 5 — <code>Turn</code>에 선택적 <code>audio</code> 필드 추가</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>


**무엇 / 왜**: 한 발화에 음성 데이터(`AudioFrame`)를 **있으면 담고 없으면 비워두게** 합니다. 텍스트만 있는 턴, 음성까지 있는 턴을 한 타입으로 다룹니다.

> ⚠️ **풀이 3(`AudioFrame`)을 먼저** 만들어야 이 풀이가 동작합니다.

**🔴 테스트** — `tests/domain/test_turn.py` 에 함수 추가

```python
from voice_agent.domain.audio_frame import AudioFrame  # 파일 맨 위 import에 추가


def test_turn_can_carry_optional_audio():
    # 음성 데이터를 함께 담은 턴을 만들 수 있어야 한다
    frame = AudioFrame(sample_rate=24000, data=b"\x00\x01")
    turn = Turn(role=Role.USER, text="안녕", audio=frame)

    assert turn.audio is frame  # 넣어준 그 프레임이 그대로 들어 있는가


def test_turn_audio_defaults_to_none():
    # audio를 안 주면 기본은 None(없음)이어야 한다
    turn = Turn(role=Role.ASSISTANT, text="네")
    assert turn.audio is None
```

**🟢 구현** — `src/voice_agent/domain/turn.py` 수정

```python
from dataclasses import dataclass
from enum import Enum

from voice_agent.domain.audio_frame import AudioFrame  # 같은 도메인 안의 값객체를 가져온다


class Role(str, Enum):
    """발화 주체: 사용자 또는 어시스턴트."""
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Turn:
    """대화의 한 턴(발화 한 번)."""
    role: Role  # 발화 주체
    text: str   # 발화 내용

    # audio: 음성 데이터가 있을 수도(AudioFrame), 없을 수도(None) 있다.
    # 기본값 None 을 줬으므로 audio 를 생략하면 자동으로 '없음' 처리된다.
    # ※ 기본값 있는 필드(audio)는 기본값 없는 필드(role, text) '뒤에' 와야 한다(파이썬 규칙).
    audio: AudioFrame | None = None
```

```powershell
uv run pytest tests/domain/test_turn.py
```

**예상 출력**: `3 passed` (기존 1개 + 새 2개)

> 💡 **기본값 있는 필드는 항상 뒤에**: dataclass에서 `text`(기본값 없음) 뒤에 `audio = None`(기본값 있음)을 두는 순서를 지켜야 합니다. 반대로 두면 `TypeError`가 납니다.

</details>

---

<details>
<summary><strong>📂 풀이 6 — <code>ruff</code>로 도메인 코드 검사</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>


`ruff`는 코드의 스타일·간단한 오류(안 쓰는 import 등)를 빠르게 잡아 줍니다.

```powershell
uv run ruff check src/voice_agent/domain
```

**예상 출력** (문제가 없을 때):

```text
All checks passed!
```

만약 안 쓰는 import 같은 게 있으면 이렇게 알려 줍니다(예시):

```text
src/voice_agent/domain/turn.py:1:1: F401 [*] `os` imported but unused
```

자동으로 고칠 수 있는 항목은 `--fix`로 정리합니다.

```powershell
uv run ruff check --fix src/voice_agent/domain
```

> 💡 **린터(linter)** 는 "코드를 실행하지 않고도 미리 문제를 찾아 주는 검사기"입니다. 사람이 놓치기 쉬운 사소한 실수를 잡아 줍니다.

</details>

---

### ✅ 미션 완료 확인 (= 진행 게이트)

필수 미션까지 끝내고 전체 테스트를 돌립니다.

```powershell
uv run pytest
```

**예상 출력** (대략):

```text
... 16 passed in 0.05s
```

- **필수**: 기본 7 + ToolSpec 2 + SessionConfig 2 + AudioFrame 3 + Turn.audio 2 = **16 passed**
- 선택 과제 `assistant_replies`까지 하면 → **17 passed**

여기에 더해 `uv run ruff check src/voice_agent/domain` 이 **All checks passed!** 면, 도메인 계층 완성 게이트를 통과한 것입니다. 이제 3교시로 갑니다.

---

**다음 교시 예고 — 3교시**: 도메인을 사용하는 **유즈케이스**와, 외부 세계로 통하는 문인 **포트(인터페이스)**를 만듭니다. 아직 OpenAI 없이, "가짜(Fake) 객체"로 시나리오를 테스트합니다.
> **선행**: 위 도메인 계층 완성 게이트(최소 16 passed + ruff clean) 통과 상태.
