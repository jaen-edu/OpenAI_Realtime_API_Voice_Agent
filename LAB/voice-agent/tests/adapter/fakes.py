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
