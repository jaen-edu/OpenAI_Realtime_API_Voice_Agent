import os                          # 환경변수(os.environ)에 접근하기 위한 표준 라이브러리
from dotenv import load_dotenv     # .env 파일을 읽어주는 도구 (python-dotenv)

load_dotenv()  # .env 파일을 찾아 읽고, 그 안의 값들을 환경변수로 올린다.
               # 이 한 줄 덕분에 아래에서 os.environ으로 키를 꺼낼 수 있다.

# 환경변수에서 OPENAI_API_KEY를 꺼낸다. 없으면 빈 문자열("")을 기본값으로.
key = os.environ.get("OPENAI_API_KEY", "")

# 키가 있으면 앞 7글자만 보여주고(전체 노출 방지), 없으면 실패 메시지를 출력.
# key[:7]은 문자열의 앞 7글자를 의미한다.
print("키 로딩됨:", key[:7] + "..." if key else "❌ 키를 찾지 못함")