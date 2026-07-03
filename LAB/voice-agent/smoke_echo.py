# fastrtc에서 두 가지를 가져온다.
# - Stream: 오디오 스트림(마이크↔스피커 배관) 전체를 관리하는 핵심 객체
# - ReplyOnPause: "사용자가 말을 멈추면" 그때 내 함수를 불러주는 도우미
from fastrtc import Stream, ReplyOnPause


def echo(audio):
    """사용자가 말을 멈추면 호출된다. 받은 오디오를 그대로 되돌려준다(메아리).

    audio: (sample_rate, numpy배열) 형태의 튜플.
           - sample_rate: 초당 샘플 수 (예: 24000)
           - numpy배열: 실제 소리 크기를 담은 숫자들
    """
    # yield(내보내기)로 오디오를 돌려주면, FastRTC가 그걸 스피커로 재생한다.
    # return이 아니라 yield인 이유: 오디오는 '조각조각 흘려보내는' 스트림이라,
    #   여러 번 나눠 내보낼 수 있어야 하기 때문이다(제너레이터).
    yield audio


# Stream 객체를 만든다 = 오디오 배관 전체를 조립한다.
stream = Stream(
    handler=ReplyOnPause(echo),  # 말이 멈추면 echo 함수를 실행하도록 연결
    modality="audio",            # 다루는 미디어 종류: 오디오 (영상 아님)
    mode="send-receive",         # 받기(마이크)+보내기(스피커) 양방향
)

# 이 파일을 직접 실행했을 때만 아래를 수행한다(파이썬 관용구).
if __name__ == "__main__":
    # FastRTC가 제공하는 기본 테스트용 웹 UI를 띄운다.
    # 실행하면 브라우저로 접속할 주소(http://127.0.0.1:7860)가 출력된다.
    stream.ui.launch()