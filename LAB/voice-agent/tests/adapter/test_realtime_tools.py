from voice_agent.adapter.realtime_tools import to_realtime_tool, build_tools
from voice_agent.domain.tool_spec import ToolSpec


def test_to_realtime_tool_shape():
    spec = ToolSpec(
        name="get_weather",
        description="날씨를 알려준다",
        parameters={"city": {"type": "string"}},
    )
    tool = to_realtime_tool(spec)

    # Realtime 함수 정의의 표준 모양인지 확인한다.
    assert tool["type"] == "function"
    assert tool["name"] == "get_weather"
    assert tool["description"] == "날씨를 알려준다"
    # parameters는 JSON 스키마(object) 형태로 감싸진다.
    assert tool["parameters"]["type"] == "object"
    assert tool["parameters"]["properties"] == {"city": {"type": "string"}}
    assert tool["parameters"]["required"] == ["city"]   # 인자가 있으면 필수로 표시


def test_build_tools_from_specs():
    specs = [
        ToolSpec(name="get_current_time", description="시각", parameters={}),
        ToolSpec(name="get_weather", description="날씨", parameters={"city": {"type": "string"}}),
    ]
    tools = build_tools(specs)

    assert len(tools) == 2
    assert [t["name"] for t in tools] == ["get_current_time", "get_weather"]
    # 인자 없는 도구는 properties가 비고 required도 빈 목록.
    assert tools[0]["parameters"]["properties"] == {}
    assert tools[0]["parameters"]["required"] == []