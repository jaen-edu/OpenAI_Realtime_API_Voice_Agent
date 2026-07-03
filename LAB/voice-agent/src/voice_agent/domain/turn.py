# from dataclasses import dataclass   # 데이터 보관용 클래스를 짧게 정의하는 표준 도구
# from enum import Enum               # 정해진 선택지만 허용하는 '열거형'을 만드는 표준 도구


# class Role(str, Enum):
#     """발화 주체: 사용자 또는 어시스턴트.

#     (str, Enum)을 함께 상속하면 '문자열이면서 선택지'가 된다.
#     → Role.USER == "user" 처럼 문자열로도 비교할 수 있어 편리하다.
#     """
#     USER = "user"            # 사용자의 발화를 나타내는 선택지
#     ASSISTANT = "assistant"  # 어시스턴트의 발화를 나타내는 선택지


# @dataclass(frozen=True)   # frozen=True: 한 번 만들면 값을 못 바꾸는 불변 객체로
# class Turn:
#     """대화의 한 턴(발화 한 번)."""
#     role: Role   # 이 발화의 주체 (Role.USER 또는 Role.ASSISTANT)
#     text: str    # 이 발화의 내용(문자열)
#     # ↑ @dataclass가 위 두 필드를 받는 __init__을 자동으로 만들어 준다.
#     #   그래서 Turn(role=..., text=...) 형태로 바로 생성할 수 있다.

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