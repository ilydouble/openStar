"""手动测试脚本 — 测试 icore-agent 各个接口

用法:
    cd icore-agent
    python scripts/test_chat.py
"""

import httpx
import json

BASE = "http://localhost:8080"


def test_health():
    print("\n== 1. 健康检查 ==")
    r = httpx.get(f"{BASE}/health")
    print(r.json())


def test_chat_sync():
    print("\n== 2. 非流式对话 ==")
    r = httpx.post(
        f"{BASE}/api/v1/agent/chat",
        json={"message": "用一句话介绍你自己", "stream": False},
        timeout=60,
    )
    data = r.json()
    print(f"session_id: {data['session_id']}")
    print(f"reply: {data['reply']}")
    return data["session_id"]


def test_chat_stream():
    print("\n== 3. 流式对话（SSE）==")
    with httpx.stream(
        "POST",
        f"{BASE}/api/v1/agent/chat",
        json={"message": "帮我写一个 Python 冒泡排序，加注释", "stream": True},
        timeout=120,
    ) as r:
        print("streaming: ", end="", flush=True)
        for line in r.iter_lines():
            if line.startswith("data: "):
                token = line[6:]
                if token == "[DONE]":
                    break
                print(token, end="", flush=True)
        print()


def test_multiturn(session_id: str):
    print("\n== 4. 多轮对话（复用 session_id）==")
    r = httpx.post(
        f"{BASE}/api/v1/agent/chat",
        json={
            "message": "刚才那个排序，帮我改成从大到小",
            "session_id": session_id,
            "stream": False,
        },
        timeout=60,
    )
    print(r.json()["reply"][:300], "...")


def test_sequential():
    print("\n== 5. 序列化任务（mini-SWE-agent）==")
    r = httpx.post(
        f"{BASE}/api/v1/agent/sequential",
        json={"task": "用 echo 命令创建一个文件 hello.txt，写入 Hello iCore，然后用 cat 读出来"},
        timeout=120,
    )
    data = r.json()
    print(f"status: {data['status']}, steps: {data['steps']}")
    print(f"output: {data['output']}")


def test_clear_session(session_id: str):
    print("\n== 6. 清除会话 ==")
    r = httpx.delete(f"{BASE}/api/v1/agent/session/{session_id}")
    print(r.json())


if __name__ == "__main__":
    test_health()
    session_id = test_chat_sync()
    test_chat_stream()
    test_multiturn(session_id)
    test_sequential()
    test_clear_session(session_id)
    print("\n✅ 全部测试完成")
