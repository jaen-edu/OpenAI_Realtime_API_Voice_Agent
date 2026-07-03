import json                                  # 결과를 JSON 문자열로 만들기 위해
from datetime import datetime                # 실제 현재 시각을 얻기 위해

from voice_agent.domain.tool_spec import ToolSpec   # 도구 명세(2교시 값객체)


def get_current_time() -> str:
    """지금 시각을 사람이 읽는 문자열로 돌려준다(예: '오후 3시 12분')."""
    now = datetime.now()                     # 실행 순간의 실제 시각
    return now.strftime("%p %I시 %M분")       # %p=오전/오후, %I=12시간제 시, %M=분


def get_weather(city: str) -> str:
    """(데모) 주어진 도시의 날씨를 돌려준다. 실제 API 대신 고정 문구를 쓴다."""
    # 실제 서비스라면 여기서 날씨 API를 호출한다(선택 미션에서 교체).
    return f"{city}의 날씨는 맑고 기온은 22도입니다. (데모 데이터)"


# 이름 → 실제 함수 로 이어주는 표. run_tool이 여기서 함수를 찾아 부른다.
TOOL_HANDLERS = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
}


# 모델에게 알려줄 '도구 명세' 목록. name/description/parameters로 구성.
#  - description: 모델이 '언제 이 도구를 쓸지' 판단하는 근거.
#  - parameters: 입력 형식(여기선 property 이름 → 타입).
TOOL_SPECS = [
    ToolSpec(
        name="get_current_time",
        description="현재 시각을 알려준다. 사용자가 지금 몇 시인지 물을 때 사용.",
        parameters={},                       # 입력 없음
    ),
    ToolSpec(
        name="get_weather",
        description="특정 도시의 현재 날씨를 알려준다. 날씨를 물을 때 사용.",
        parameters={"city": {"type": "string"}},   # city: 문자열 하나
    ),
]


def run_tool(name: str, arguments: dict) -> str:
    """이름으로 함수를 찾아 arguments로 실행하고, 결과를 JSON 문자열로 돌려준다."""
    handler = TOOL_HANDLERS.get(name)        # 이름에 해당하는 함수 찾기
    if handler is None:                      # 없으면 에러를 담아 안전하게 반환
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    # arguments(dict)를 함수의 키워드 인자로 풀어 호출한다(**arguments).
    #  예: {"city": "부산"} → handler(city="부산")
    result = handler(**arguments)
    # 모델에 돌려줄 결과는 JSON 문자열이어야 하므로 감싼다.
    #  ensure_ascii=False: 한글이 \uXXXX로 깨지지 않게.
    return json.dumps({"result": result}, ensure_ascii=False)