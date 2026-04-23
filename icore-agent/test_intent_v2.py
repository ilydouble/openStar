"""Verify improved intent classifier covers the diagnosed failure cases."""
import sys
sys.path.insert(0, "src")

from icore_agent.api.routers.agent import _classify_intent

cases = [
    # ── should be chat ────────────────────────────────────────────────────
    ("你好", "chat"),
    ("What capabilities should an AI agent platform like mine focus on?", "chat"),
    ("What is the main project I just told you about?", "chat"),
    ("Summarise what you know about me so far in one sentence.", "chat"),
    ("你觉得这个方案怎么样", "chat"),
    ("解释一下 RAG 是什么", "chat"),
    ("How does asyncio work?", "chat"),
    ("Why should I use Redis for session memory?", "chat"),
    ("Tell me about vector databases", "chat"),
    ("What are the best practices for AI agents?", "chat"),
    ("My name is Alex. I am building an AI agent platform called iCore.", "chat"),
    # ── should be task ────────────────────────────────────────────────────
    ("帮我搜索最新的 AI 论文", "task"),
    ("查询公司的请假政策", "task"),
    ("查找员工手册里关于年假的规定", "task"),
    ("搜索 Python asyncio 教程", "task"),
    ("look up the latest news about AI agents", "task"),
    ("summarize the document I just uploaded", "task"),
    ("translate this text into English", "task"),
    ("write code to parse a CSV file", "task"),
    ("analyze the sales data in the spreadsheet", "task"),
    ("web search for iCore agent platform", "task"),
    ("知识库里有哪些关于合同的文档", "task"),
    ("上传一份 PDF 文件", "task"),
]

passed = 0
failed = []
for msg, expected in cases:
    got = _classify_intent(msg)
    mark = "✓" if got == expected else "✗"
    print(f"  {mark} [{expected:4s}→{got:4s}]  {msg[:60]}")
    if got == expected:
        passed += 1
    else:
        failed.append((msg, expected, got))

print()
print(f"{passed}/{len(cases)} passed")
if failed:
    print("\nFAILED:")
    for msg, exp, got in failed:
        print(f"  expected={exp!r}  got={got!r}  msg={msg!r}")
else:
    print("ALL PASSED")
