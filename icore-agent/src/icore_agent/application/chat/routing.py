"""Routing policy for chat turns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ChatIntent(str, Enum):
    """High-level intent classes for chat routing."""

    CHAT = "chat"
    TASK = "task"


_CHAT_PATTERNS = re.compile(
    r"^("
    r"你好|您好|嗨|hi|hello|hey|哈喽"
    r"|早上好|下午好|晚上好|早安|晚安"
    r"|谢谢|谢谢你|谢谢您|感谢|多谢|thx|thanks|thank you"
    r"|好的|好|明白|收到|了解|知道了|好的好的|嗯|哦|哈哈|哈"
    r"|再见|拜拜|byebye|bye|886|88"
    r"|你是谁|你叫什么|你叫什么名字|你是什么|介绍一下你自己|自我介绍"
    r"|你能做什么|你有什么功能|你的功能是什么|你会什么"
    r"|没问题|没事|可以|行|好啊|没关系|不用了|不用谢"
    r"|good morning|good afternoon|good evening|good night"
    r"|who are you|what are you|what can you do|tell me about yourself"
    r"|ok|okay|got it|sure|alright|no problem|never mind"
    r")$",
    re.IGNORECASE,
)

_TASK_KEYWORDS = re.compile(
    r"搜索|查询|查找|查一下|帮我搜|帮我找|帮我查|帮我分析|帮我写|帮我生成"
    r"|总结.*文|翻译.*成|生成.*代码|写.*代码|写.*程序|写.*脚本|编写"
    r"|文档|知识库|政策|规定|合同|手册|上传|下载"
    r"|look up|web search|fetch|scrape"
    r"|summarize.*(document|file|text|report|article|page|content)"
    r"|summarise.*(document|file|text|report|article|page|content)"
    r"|translate.*(into|to) [a-z]"
    r"|write.*code|generate.*code|write.*script|write.*program"
    r"|analyze.*data|analyse.*data"
    r"|document|policy|contract|manual|upload",
    re.IGNORECASE,
)

_CHAT_LIKE_PATTERNS = re.compile(
    r"should|could|would you|what.*think|what.*opinion|what.*focus"
    r"|how.*improve|how.*better|tell me about|explain|describe|what is|what are"
    r"|why.*is|why.*do|why.*should|how does|how do"
    r"|你觉得|你认为|怎么看|有什么建议|怎么理解|解释一下|介绍.*一下|什么是|为什么",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ChatRoutingDecision:
    """Resolved routing decision for one chat turn."""

    intent: ChatIntent


def resolve_routing(message: str) -> ChatRoutingDecision:
    """Classify the message for turn metadata without controlling tools."""
    intent = classify_intent(message)
    return ChatRoutingDecision(intent=intent)


def classify_intent(message: str) -> ChatIntent:
    """Classify a user message as conversational chat or task execution."""
    stripped = message.strip()
    if _CHAT_PATTERNS.fullmatch(stripped):
        return ChatIntent.CHAT
    if _TASK_KEYWORDS.search(stripped):
        return ChatIntent.TASK
    if len(stripped) <= 6:
        return ChatIntent.CHAT
    if _CHAT_LIKE_PATTERNS.search(stripped):
        return ChatIntent.CHAT
    return ChatIntent.CHAT
