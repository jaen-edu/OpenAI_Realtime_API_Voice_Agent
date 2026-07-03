import json

from voice_agent.adapter.tools import get_current_time, get_weather, run_tool


def test_get_current_time_returns_string():
    # 시각 함수는 사람이 읽을 수 있는 문자열을 돌려준다(정확한 값은 실행 시각마다 다름).
    out = get_current_time()
    assert isinstance(out, str)
    assert len(out) > 0


def test_get_weather_returns_city_info():
    # 데모 날씨는 도시 이름을 담은 설명 문자열을 돌려준다.
    out = get_weather(city="서울")
    assert "서울" in out


def test_run_tool_dispatches_by_name():
    # run_tool은 이름으로 함수를 찾아 실행하고, 결과를 'JSON 문자열'로 돌려준다.
    #  (모델에 돌려줄 function_call_output이 JSON 문자열이어야 하기 때문)
    out = run_tool("get_weather", {"city": "부산"})
    parsed = json.loads(out)          # 문자열을 다시 dict로 되돌려 확인
    assert "부산" in parsed["result"]


def test_run_tool_unknown_name_is_safe():
    # 등록 안 된 이름이 와도 죽지 않고, 에러를 담은 JSON을 돌려준다.
    out = run_tool("no_such_tool", {})
    parsed = json.loads(out)
    assert "error" in parsed