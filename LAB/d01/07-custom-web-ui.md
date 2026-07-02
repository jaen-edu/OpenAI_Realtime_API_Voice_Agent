# 7교시 — 커스텀 웹 UI 셸 (기본 UI 벗어나기)

> **이 교시가 끝나면** FastRTC의 기본 Gradio UI(`/ui`) 대신 **우리만의 웹 페이지**에서 보이스 에이전트가 돕니다. 시작/중지 버튼, 연결 상태 표시가 있는 **제품 느낌의 셸**을 갖춥니다. (선택 미션으로 자막을 브라우저에 띄웁니다.)

---

## 0. 이 교시의 성격 — "실행·관찰" 중심

지금까지는 도메인·어댑터를 **TDD**로 쌓았습니다. 7교시는 **프론트엔드 결선**이 중심이라, 대부분 **"실행해서 화면에서 확인"**하는 방식입니다. (파이썬 쪽 새 로직이 적어, 유닛테스트 개수는 그대로 유지됩니다. 선택 미션에서 테스트 가능한 작은 서버 로직이 하나 등장합니다.)

### 이 교시에 만드는 것

```
지금:      브라우저 → FastRTC 기본 UI(/ui, Gradio)
이 교시:   브라우저 → 우리 index.html(/)  ──WebRTC──▶  FastRTC 서버(/webrtc/offer)
                                                     └─▶ (5·6교시) OpenAI Realtime
```

> ⚠️ **핵심 구분**: 브라우저는 **우리 서버**에만 붙습니다. OpenAI와 대화하는 건 서버(우리 핸들러)라, **브라우저엔 OpenAI 키가 없습니다.** (인터넷의 많은 예제는 브라우저가 OpenAI에 직접 붙는 다른 구조이니 혼동하지 마세요.)

---

## 🧭 잠깐, 배경지식

이 교시는 브라우저에서 WebRTC 연결을 **직접** 맺습니다(1교시엔 FastRTC 기본 UI가 대신 해줬죠). 그 과정에 나오는 용어를 짚습니다.

**① 시그널링(signaling).** 두 지점이 실시간 통화를 시작하려면, 먼저 "어떤 코덱·어떤 네트워크 경로로 연결할지"를 서로 알려주는 **사전 협상**이 필요합니다. 이 협상 과정을 시그널링이라 합니다. 전화 걸기 전에 번호를 누르고 신호가 오가는 단계에 해당합니다.

**② SDP(Session Description Protocol) / offer·answer.** 시그널링에서 주고받는 "내 연결 사양서"가 **SDP**입니다. 브라우저가 먼저 제안서(**offer**)를 만들어 서버에 보내고, 서버가 응답서(**answer**)를 돌려주면 협상이 끝납니다. 우리 코드에선 offer를 `/webrtc/offer`로 POST하고 answer를 받습니다.

**③ ICE(Interactive Connectivity Establishment) 후보 / 트리클(trickle).** 두 지점 사이 실제 통신 경로(내 IP·포트 등)의 후보들을 **ICE 후보**라 합니다. 브라우저는 이 후보를 시간차를 두고 하나씩 찾아내는데, 찾는 족족 서버로 흘려보내는 방식이 **트리클(trickle, 물이 졸졸 흐르듯)**입니다.

**④ 데이터 채널(data channel).** 오디오·영상과 별개로, 임의의 데이터를 주고받는 통로입니다. FastRTC는 핸드셰이크에 이 채널(`"text"`)을 **반드시** 요구합니다 — 없으면 연결이 시작조차 안 됩니다(이 교시의 대표 함정).

> 💡 이 과정 대부분은 브라우저 표준 API(`RTCPeerConnection`)가 처리합니다. 우리는 "offer 만들어 보내고 → answer 받고 → ICE 흘려보내기"만 코드로 엮으면 됩니다.

---

---

## 1. 개념 빠르게 잡기

### `stream.mount(app)`가 주는 것

> 6교시에서 이미 썼던 `stream.mount(app)`는 **`/webrtc/offer`** 라는 WebRTC 핸드셰이크 엔드포인트를 앱에 붙여 줍니다. 우리 프론트엔드는 여기로 SDP offer를 POST하면 됩니다.

### 브라우저 WebRTC 핸드셰이크 (4단계)

> 1. **마이크 얻기** — `getUserMedia({audio})`로 마이크 스트림을 받아 연결에 추가(`addTrack`).
> 2. **데이터 채널 만들기** — `createDataChannel("text")`. **FastRTC 필수** 단계(없으면 연결이 시작 안 됨).
> 3. **offer 보내기 + ICE 트리클** — `createOffer()`로 SDP를 만들어 `/webrtc/offer`로 POST하고, 이후 생기는 ICE 후보도 같은 엔드포인트로 흘려보냄.
> 4. **answer 받기** — 서버가 준 SDP answer를 `setRemoteDescription`으로 설정. 이후 `track` 이벤트로 **서버가 보내는 음성을 스피커에 연결**.

💡 이게 전부입니다. 오디오 스트리밍·재생·바지인은 이미 서버(5·6교시)가 처리하니, 프론트엔드는 "연결만" 맺으면 됩니다.

---

## STEP 1 — 커스텀 `index.html` 만들기

프로젝트에 `static` 폴더를 만들고 그 안에 `index.html`을 둡니다.

```powershell
New-Item -ItemType Directory -Force -Path static | Out-Null
notepad static/index.html
```

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>보이스 에이전트</title>
  <style>
    :root { --bg:#0f1220; --card:#191d2e; --accent:#ff7a45; --text:#e8eaf2; --muted:#8b90a5; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: system-ui, -apple-system, sans-serif; background:var(--bg);
           color:var(--text); min-height:100vh; display:flex; align-items:center; justify-content:center; }
    .card { background:var(--card); padding:44px 40px; border-radius:20px; width:min(92vw,440px);
            text-align:center; box-shadow:0 20px 60px rgba(0,0,0,.45); }
    h1 { font-size:20px; margin:0 0 4px; }
    .sub { color:var(--muted); font-size:13px; margin-bottom:30px; }
    button { border:none; border-radius:999px; padding:14px 30px; font-size:15px; font-weight:600;
             cursor:pointer; transition:.15s; color:#fff; background:var(--accent); }
    button.on { background:#e5484d; }
    #status { font-size:13px; color:var(--muted); margin-top:20px; min-height:18px; }
    .dot { display:inline-block; width:10px; height:10px; border-radius:50%; background:var(--muted);
           margin-right:7px; vertical-align:middle; transition:.2s; }
    .dot.live { background:#3ddc84; box-shadow:0 0 10px #3ddc84; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🎙️ 보이스 에이전트</h1>
    <div class="sub">버튼을 누르고 말을 걸어 보세요</div>
    <button id="toggle">대화 시작</button>
    <div id="status"><span class="dot" id="dot"></span><span id="statusText">대기 중</span></div>
    <audio id="audio" autoplay></audio>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

> 💡 색·여백은 취향대로 바꾸세요. 핵심은 **버튼 하나 + 상태 표시 + `<audio>` 요소**입니다. `<audio autoplay>`가 서버가 보내는 음성을 재생할 자리입니다.

---

## STEP 2 — WebRTC 클라이언트 JS

같은 폴더에 `app.js`를 만듭니다. 여기가 핸드셰이크의 핵심입니다.

```powershell
notepad static/app.js
```

```javascript
const toggle = document.getElementById("toggle");
const audioEl = document.getElementById("audio");
const statusText = document.getElementById("statusText");
const dot = document.getElementById("dot");

let pc = null;
let localStream = null;

function setStatus(text, live = false) {
  statusText.textContent = text;
  dot.classList.toggle("live", live);
}

async function start() {
  setStatus("연결 중...");
  // RTCPeerConnection: 브라우저의 WebRTC 연결 객체. 이 안에서 협상·미디어가 오간다.
  pc = new RTCPeerConnection();
  // webrtc_id: 이 연결을 식별하는 임의의 문자열. offer·ICE를 서버가 같은 연결로 묶는 데 쓴다.
  const webrtc_id = Math.random().toString(36).substring(7);

  // 1) 서버(FastRTC)가 보내는 음성 트랙이 도착하면(track 이벤트) <audio>에 연결해 재생.
  pc.addEventListener("track", (evt) => {
    if (audioEl.srcObject !== evt.streams[0]) {   // 중복 설정 방지
      audioEl.srcObject = evt.streams[0];         // 받은 스트림을 스피커로
    }
  });

  // 2) 마이크 입력을 얻어 연결에 추가한다(send-receive: 보내고+받고).
  //    echoCancellation/noiseSuppression: 되울림·잡음을 줄여 피드백 루프를 막는다.
  localStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });
  // 마이크의 각 트랙을 연결에 얹는다 → 서버로 내 음성이 전송된다.
  localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));

  // 3) 데이터 채널 — FastRTC 핸드셰이크에 필수! (없으면 연결이 시작되지 않음)
  //    이름은 반드시 "text". 실제로 이 채널로 데이터를 보내지 않아도, 존재 자체가 필요하다.
  const dataChannel = pc.createDataChannel("text");

  // 연결 상태가 바뀔 때마다 화면 표시를 갱신한다.
  pc.onconnectionstatechange = () => {
    if (pc.connectionState === "connected") setStatus("대화 중", true);   // 연결됨 → 초록
    else if (["failed", "disconnected", "closed"].includes(pc.connectionState))
      setStatus("연결 종료");
  };

  // 4) ICE 후보를 찾는 족족 서버로 '트리클' 전송(방화벽 뒤에서도 경로를 찾게).
  //    브라우저가 후보를 하나 찾을 때마다 onicecandidate가 호출된다.
  pc.onicecandidate = ({ candidate }) => {
    if (candidate) {   // candidate가 null이면 '수집 끝' 신호이므로 무시
      fetch("/webrtc/offer", {                        // offer와 같은 엔드포인트로 보낸다
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate: candidate.toJSON(),              // 후보를 JSON으로 직렬화
          webrtc_id: webrtc_id,                       // 어느 연결의 후보인지 식별
          type: "ice-candidate",                      // 이 POST가 'ICE 후보'임을 표시
        }),
      });
    }
  };

  // 5) SDP offer(내 연결 사양서)를 만들고 → 서버로 POST → 서버의 answer를 설정.
  const offer = await pc.createOffer();               // 제안서 생성
  await pc.setLocalDescription(offer);                // 내 쪽 사양으로 확정(이때부터 ICE 수집 시작)
  const res = await fetch("/webrtc/offer", {          // 서버로 offer 전송
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sdp: offer.sdp,                                 // 실제 사양서 본문
      type: offer.type,                               // "offer"
      webrtc_id: webrtc_id,                           // 연결 식별자
    }),
  });
  const answer = await res.json();                    // 서버의 응답서(answer)를 받아
  await pc.setRemoteDescription(answer);              // 상대 쪽 사양으로 설정 → 핸드셰이크 완료, 오디오 흐름 시작
}

function stop() {
  if (pc) { pc.close(); pc = null; }                  // 연결을 닫고 비운다
  if (localStream) { localStream.getTracks().forEach((t) => t.stop()); localStream = null; }  // 마이크 해제
  setStatus("대기 중");
}

toggle.addEventListener("click", async () => {
  if (toggle.classList.contains("on")) {
    stop();
    toggle.classList.remove("on");
    toggle.textContent = "대화 시작";
  } else {
    toggle.classList.add("on");
    toggle.textContent = "중지";
    try {
      await start();
    } catch (err) {
      setStatus("오류: " + err.message);
      toggle.classList.remove("on");
      toggle.textContent = "대화 시작";
    }
  }
});
```

> 💡 **놓치기 쉬운 두 가지 (FastRTC 필수)**. 첫째, **`pc.createDataChannel("text")`** 를 offer 만들기 전에 반드시 만들어야 합니다 — 이게 없으면 핸드셰이크가 시작되지 않아 화면이 "연결 중"에서 멈춥니다. 둘째, **ICE 후보를 트리클 전송**합니다(`onicecandidate`에서 `/webrtc/offer`로 `type:"ice-candidate"`). FastRTC 기본 UI도 정확히 이 방식이라, 커스텀 UI도 이대로 맞춰야 붙습니다.

---

## STEP 3 — 정적 파일 서빙 + 커스텀 페이지 라우트

`voice_app.py`에서 `static` 폴더를 서빙하고, `/`가 우리 `index.html`을 주도록 바꿉니다. (기본 `/ui`는 비교용으로 남겨둬도 됩니다.)

```python
import gradio as gr
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse       # HTML 문자열을 응답으로 돌려주는 도구
from fastapi.staticfiles import StaticFiles      # 폴더의 파일을 그대로 서빙하는 도구
from pathlib import Path                         # 파일 경로를 다루는 표준 도구

from fastrtc import Stream
from voice_agent.infra.voice_handler import RealtimeVoiceHandler

load_dotenv()   # .env의 OPENAI_API_KEY 로딩

# 5·6교시에서 만든 핸들러로 오디오 스트림을 구성(양방향 오디오).
stream = Stream(
    handler=RealtimeVoiceHandler(),
    modality="audio",
    mode="send-receive",
)

app = FastAPI()
stream.mount(app)                                    # /webrtc/offer 등 WebRTC 엔드포인트를 붙인다
app.mount("/static", StaticFiles(directory="static"), name="static")   # /static/* → static 폴더의 파일(app.js 등)
app = gr.mount_gradio_app(app, stream.ui, path="/ui")   # (선택) 기본 Gradio UI를 /ui 에 남겨 비교용


@app.get("/")        # 루트(/)로 접속하면
def index():
    # static/index.html 파일을 읽어 그대로 브라우저에 돌려준다(UTF-8로 읽어 한글 안 깨지게).
    html = Path("static/index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
```

> 💡 `app.mount("/static", ...)`가 있어야 `index.html`이 부르는 `/static/app.js`가 로딩됩니다.

---

## STEP 4 — 실행하고 커스텀 UI에서 대화 (관찰형 완성)

```powershell
uv run uvicorn voice_app:app --host 127.0.0.1 --port 7860
```

이번엔 **`http://127.0.0.1:7860/`** (기본 UI `/ui`가 아니라 루트)를 엽니다. 우리 카드형 화면이 뜨면 **"대화 시작"**을 누르고 → 마이크 허용 → 말을 겁니다.

확인할 것:
- 상태가 **"연결 중..." → "대화 중"**(초록 점)으로 바뀐다.
- 말하면 **음성 응답이 스피커로 재생**된다(6교시 재생·바지인 그대로).
- 터미널엔 여전히 `[연결됨]`과 자막이 흐른다.
- **"중지"**를 누르면 연결이 끊기고 상태가 "대기 중"으로.

> ⚠️ **관찰형 확인**: WebRTC 핸드셰이크는 브라우저·네트워크가 얽혀 순수 단위테스트 대상이 아닙니다. **"내 화면에서 대화가 되는지"**로 확인하고, 문제가 있으면 아래 진단 순서를 따르세요.

---

## ✅ 완성 체크포인트 (= 커스텀 UI 게이트)

- [ ] `static/index.html`, `static/app.js` 존재, `voice_app.py`가 `/`와 `/static`을 서빙
- [ ] `uv run pytest` → **여전히 34 passed** (프론트엔드 결선이라 백엔드 테스트 수 변화 없음)
- [ ] `uv run ruff check src/voice_agent` → **All checks passed!**
- [ ] **실행 관찰**: `/`(루트)의 커스텀 화면에서 **대화가 되고 음성이 재생**된다

---

## ⚠️ 자주 나는 오류 & 해결 (+ 진단 순서)

| 증상 | 원인 | 해결 |
|---|---|---|
| **"대화 시작" 눌러도 아무 반응 없음 / "연결 중"에서 멈춤** | 데이터 채널 누락 또는 ICE 미전송 | `pc.createDataChannel("text")` 추가(필수) + `onicecandidate`로 ICE 트리클 전송 확인 |
| 화면은 뜨는데 `app.js`가 404 | `/static` 미마운트 | `app.mount("/static", StaticFiles(...))` 확인 |
| `/webrtc/offer`가 200인데 연결 안 됨 | ICE 후보가 서버에 안 감 | `onicecandidate`에서 `type:"ice-candidate"`로 POST하는지 확인 |
| 마이크 권한 팝업이 안 뜸 / 거부 | 브라우저 권한 | 주소가 `127.0.0.1`/`localhost`인지 확인(원격 IP는 보안 컨텍스트 막힘), 권한 허용 |
| 소리가 안 남 | 6교시 재생 미완성 or `<audio>` 미연결 | 6교시 게이트 통과 확인, `track` 이벤트가 `audioEl.srcObject`에 연결되는지 확인 |
| 콘솔에 `connectionState: failed` | ICE/네트워크 | localhost로 접속, 방화벽 확인. 원격이면 STUN 서버를 `new RTCPeerConnection({iceServers:[...]})`에 추가 |

**진단 순서**: (1) F12 콘솔의 에러 메시지 → (2) Network 탭에서 `/webrtc/offer`가 200 + SDP answer를 주는지 → (3) `pc.connectionState`를 콘솔에 찍어 어디서 멈추는지 → (4) 기본 `/ui`에선 되는데 `/`에서만 안 되면 프론트엔드(app.js) 문제로 좁혀짐.

---

## 📖 용어 사전 (이 교시 신규)

- **시그널링(signaling)**: 실시간 연결을 시작하기 전, 코덱·경로 등을 서로 알려주는 사전 협상.
- **SDP(Session Description Protocol)**: 두 지점이 주고받는 "이런 코덱·경로로 통신하자"는 연결 사양서.
- **offer / answer**: 클라이언트가 만든 제안(offer)과 서버의 응답(answer). 이걸 교환하면 연결이 성립.
- **ICE 후보(Interactive Connectivity Establishment)**: NAT(Network Address Translation)/방화벽을 넘어 연결할 실제 네트워크 경로 후보(내 IP·포트 등).
- **트리클 ICE(trickle)**: ICE 후보를 찾는 족족 하나씩 서버로 흘려보내는 방식.
- **데이터 채널(data channel)**: 오디오와 별개로 임의 데이터를 주고받는 통로. FastRTC 핸드셰이크에 필수(`"text"`).
- **`RTCPeerConnection`**: 브라우저의 WebRTC 연결 객체. 협상·미디어를 관리.
- **`getUserMedia`**: 브라우저에서 마이크·카메라 접근을 요청하는 API.
- **`track` 이벤트 / `ontrack`**: 상대가 보낸 미디어(음성) 트랙이 도착했을 때 발생.
- **`/webrtc/offer`**: `stream.mount(app)`가 만드는 FastRTC의 WebRTC 핸드셰이크 엔드포인트.
- **`StaticFiles`**: FastAPI에서 폴더의 파일(app.js 등)을 그대로 제공하는 도구.
- **SSE(Server-Sent Events) / `EventSource`**: 서버가 브라우저로 데이터를 계속 밀어보내는 단방향 스트림(선택 미션의 자막 표시에 사용).

---

## 🎯 필수 미션 — 다음 교시로 가기 전 완성

### 미션 1 (필수) — 마이크 거부를 친절하게 처리

사용자가 마이크 권한을 거부하면 지금은 "오류: ..." 원문이 뜹니다. 이를 **알기 쉬운 안내**로 바꾸고 버튼을 원래대로 되돌리세요.
- **어디에**: `static/app.js`의 `start()` 또는 toggle 핸들러의 `catch`
- **왜**: 실제 사용자는 권한을 자주 거부/실수합니다. 안내가 없으면 "고장 났다"고 느낌

### 미션 2 (선택·심화) — 자막을 브라우저에 표시

지금 자막은 터미널에만 나옵니다. 이를 **화면의 자막 패널**에 흐르게 하세요. 서버가 자막을 SSE로 흘려보내고, 브라우저가 받아 표시하는 구조입니다.
- **어디에**: 서버(자막 방송 + SSE 라우트) + `static/`(패널 + EventSource)
- **왜**: "제품 느낌"의 UI에 대화 내용이 보이면 완성도가 올라감

> 풀이는 아래 **🧩 필수 미션 — 풀이** 에 접이식으로 있습니다.

---

## 🧩 필수 미션 — 풀이 (막히면 펼치기)

<details>
<summary><strong>📂 풀이 1 — 마이크 거부 친절 처리</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

`app.js`의 toggle 핸들러 `catch`를 오류 종류에 따라 안내하도록 바꿉니다.

```javascript
    } catch (err) {
      let msg = "연결에 실패했어요. 잠시 후 다시 시도해 주세요.";
      if (err.name === "NotAllowedError") msg = "마이크 권한이 필요해요. 브라우저 주소창의 🎙️ 아이콘에서 허용해 주세요.";
      else if (err.name === "NotFoundError") msg = "마이크를 찾을 수 없어요. 장치 연결을 확인해 주세요.";
      setStatus(msg);
      toggle.classList.remove("on");
      toggle.textContent = "대화 시작";
    }
```

> 💡 `getUserMedia`는 거부 시 `NotAllowedError`, 장치 없음 시 `NotFoundError`를 던집니다. 이름으로 갈라 안내하면 사용자가 스스로 해결할 수 있습니다.

</details>

---

<details>
<summary><strong>📂 풀이 2 (심화) — 자막 브라우저 표시 (SSE)</strong> &nbsp;<sub>(클릭하여 펼치기)</sub></summary>

**설계**: 핸들러가 자막을 "방송(publish)"하고, 우리 SSE 라우트가 그걸 "구독(subscribe)"해 브라우저로 흘립니다. 오디오 `emit`과 충돌하지 않는 **독립 경로**라 안전합니다. 방송 로직은 순수해서 **테스트도 가능**합니다.

**① 자막 버스** — `src/voice_agent/infra/transcript_bus.py`

```python
import asyncio

_subscribers: list[asyncio.Queue] = []


def publish(text: str) -> None:
    """모든 구독자에게 자막 한 조각을 보낸다."""
    for q in _subscribers:
        q.put_nowait(text)


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)
```

**🔴 테스트**(선택이지만 권장) — `tests/infra/test_transcript_bus.py`

```python
from voice_agent.infra import transcript_bus


def test_publish_reaches_subscriber():
    q = transcript_bus.subscribe()
    transcript_bus.publish("안녕")
    assert q.get_nowait() == "안녕"
    transcript_bus.unsubscribe(q)


def test_unsubscribe_stops_delivery():
    q = transcript_bus.subscribe()
    transcript_bus.unsubscribe(q)
    transcript_bus.publish("여기")
    assert q.empty()
```

**② 핸들러에서 방송** — `voice_handler.py`의 `_read_events`에서 자막 출력 옆에 한 줄 추가

```python
from voice_agent.infra import transcript_bus
...
                text = extract_transcript_delta(event)
                if text:
                    print(text, end="", flush=True)
                    transcript_bus.publish(text)   # ← 브라우저로도 방송
                    continue
```

**③ SSE 라우트** — `voice_app.py`

```python
from fastapi.responses import StreamingResponse
from voice_agent.infra import transcript_bus


@app.get("/transcript")
async def transcript_stream():
    async def gen():
        q = transcript_bus.subscribe()
        try:
            while True:
                text = await q.get()
                yield f"data: {text}\n\n"
        finally:
            transcript_bus.unsubscribe(q)
    return StreamingResponse(gen(), media_type="text/event-stream")
```

**④ 프론트엔드** — `index.html`에 자막 패널 추가

```html
    <div id="transcript" style="margin-top:22px; font-size:14px; line-height:1.7;
         color:var(--text); text-align:left; max-height:180px; overflow-y:auto;"></div>
```

`app.js`의 `start()`에서 EventSource로 구독

```javascript
  // 자막 스트림 구독 (서버 → 브라우저)
  const es = new EventSource("/transcript");
  const box = document.getElementById("transcript");
  es.onmessage = (e) => { box.textContent += e.data; };
  // stop()에서 es.close()도 호출하도록 es를 바깥 변수로 두면 더 깔끔합니다.
```

```powershell
uv run pytest tests/infra/test_transcript_bus.py
```

**예상 출력**: `2 passed`

> ⚠️ 이 구조는 **단일 사용자 데모 기준**입니다. 여러 사용자를 구분하려면 `webrtc_id`별로 큐를 키잉해야 합니다(8교시 이후 규모 확장 시 고려). 실행해서 **화면에 자막이 흐르는지**로 확인하세요.

</details>

---

**다음 교시 예고 — 8교시**: 드디어 **도구(툴)**입니다. 지금 모델은 날씨·시간·경기결과를 **지어냅니다**(로그에서 확인했죠). 8교시에선 툴 프레임워크를 만들고 첫 토글 도구(날씨/시간)를 붙여, 모델이 상상 대신 **실제 함수를 호출**하게 합니다.
> **선행**: 커스텀 UI 게이트(34 passed + ruff clean + 커스텀 화면에서 대화 관찰) 통과 상태.
