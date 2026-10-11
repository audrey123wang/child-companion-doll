"""Small LangGraph workflows with no checkpointer or content tracing."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .domain import extract_sample_event, reply_sample
from .deepseek_chat import ChatProvider
from .stories import STORY_VARIANTS, age_band


class IngestState(TypedDict, total=False):
    raw_text: str
    transcript: str
    event: dict[str, Any] | None


def _prepare_transcript(state: IngestState) -> IngestState:
    # The current functional experiment deliberately displays ASR text as-is.
    return {"transcript": state["raw_text"], "raw_text": ""}


def _extract(state: IngestState) -> IngestState:
    return {"event": extract_sample_event(state["transcript"])}


ingest_builder = StateGraph(IngestState)
ingest_builder.add_node("prepare_transcript", _prepare_transcript)
ingest_builder.add_node("extract", _extract)
ingest_builder.add_edge(START, "prepare_transcript")
ingest_builder.add_edge("prepare_transcript", "extract")
ingest_builder.add_edge("extract", END)
INGEST_GRAPH = ingest_builder.compile()


class ReportState(TypedDict, total=False):
    events: list[dict[str, Any]]
    input_counts: dict[str, int]
    report: dict[str, Any]


def _build_report(state: ReportState) -> ReportState:
    events = [e for e in state["events"] if e["review_state"] != "deleted"]
    counts = state["input_counts"]
    coverage_note = "仅基于娃娃按键留言，不能代表全天情况。"
    if counts["unreadable_count"]:
        coverage_note += f"其中 {counts['unreadable_count']} 条未听清，未用于同伴事件判断。"
    if counts["unclassified_count"]:
        coverage_note += f"另有 {counts['unclassified_count']} 条未归入同伴相处主题。"
    if not events:
        return {"report": {
            "status": "insufficient", "observations": [],
            "unknowns": ["今天没有足够的可用同伴相处信息，不能判断孩子的整体情况。"],
            "parent_prompts": [], "story_topic": None, "event_count": 0,
            "input_counts": counts, "coverage_note": coverage_note,
        }}
    observations = []
    for event in events:
        observations.append({"text": event["summary"], "event_ids": [event["event_id"]]})
        if event.get("explicit_feeling"):
            observations.append({
                "text": f"这条留言明确提到自己感到{event['explicit_feeling']}。",
                "event_ids": [event["event_id"]],
            })
    unknowns = ["不知道其他孩子当时的想法或完整经过。", "现有留言不能代表孩子全天的心情。"]
    if len(events) == 1:
        unknowns.append("今天只有一条同伴相处留言，不能判断是否反复发生。")
    return {"report": {
        "status": "ready",
        "observations": observations,
        "unknowns": unknowns,
        "parent_prompts": ["你当时最想玩什么？", "后来发生了什么？", "你希望我先听你说，还是一起想想明天怎么办？"],
        "story_topic": "friendship_and_inclusion",
        "event_count": len(events),
        "input_counts": counts,
        "coverage_note": coverage_note,
    }}


report_builder = StateGraph(ReportState)
report_builder.add_node("build_report", _build_report)
report_builder.add_edge(START, "build_report")
report_builder.add_edge("build_report", END)
REPORT_GRAPH = report_builder.compile()


class ChatState(TypedDict, total=False):
    text: str
    turn_number: int
    age: int
    daily_facts: list[str]
    history: list[dict[str, str]]
    model: ChatProvider | None
    route: str
    reply: str
    fallback_reply: str


def _chat_route(state: ChatState) -> ChatState:
    route, fallback = reply_sample(state["text"], state.get("turn_number", 1))
    return {"route": route, "fallback_reply": fallback, "reply": fallback if route != "conversation" else ""}


def _chat_generate(state: ChatState) -> ChatState:
    model = state.get("model")
    if model is None:
        return {"reply": state["fallback_reply"]}
    story = STORY_VARIANTS[age_band(state["age"])]
    facts = "；".join(state.get("daily_facts", [])[:3]) or "今天没有可用的同伴事件摘要"
    system = (
        "你是儿童故事角色小猫米米，正在和一位 5-12 岁儿童聊如何与朋友相处。"
        f"孩子年龄：{state['age']} 岁。故事：{story['title']}。故事主旨：遇到朋友换了玩伴时，先区分看到的事实和自己的猜测，"
        "可以温和地问一问，也可以找可信任的大人聊。"
        f"今天可用的同伴事件摘要：{facts}。这些只是孩子主动留言的片段，不能代表全天情况。"
        "只依据这些摘要和孩子当前主动说的话回应，不提设备收音、家长报告、其他孩子姓名或未提供的事实。"
        "不要猜测其他孩子的动机，不做诊断，不承诺保密，不要求儿童提供住址、学校等个人信息。"
        "用温柔自然的中文回复一到两句，不超过 100 个汉字；先接住感受或复述问题，最多问一个开放问题，给孩子不回答的选择。"
        "只输出要展示给儿童的回复文字，不输出分析、标签或 Markdown。"
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(state.get("history", [])[-6:])
    messages.append({"role": "user", "content": state["text"]})
    return {"reply": model.complete(messages)}


def _chat_review(state: ChatState) -> ChatState:
    reply = state["reply"].strip()
    forbidden = ("他们讨厌你", "她讨厌你", "他讨厌你", "肯定是", "一定是", "不要告诉家长", "不要告诉爸爸妈妈", "替你保密")
    if not reply or len(reply) > 180 or any(term in reply for term in forbidden):
        reply = state["fallback_reply"]
    return {"reply": reply}


chat_builder = StateGraph(ChatState)
chat_builder.add_node("route", _chat_route)
chat_builder.add_node("generate", _chat_generate)
chat_builder.add_node("review", _chat_review)
chat_builder.add_edge(START, "route")
chat_builder.add_conditional_edges("route", lambda state: "generate" if state["route"] == "conversation" else "end", {"generate": "generate", "end": END})
chat_builder.add_edge("generate", "review")
chat_builder.add_edge("review", END)
CHAT_GRAPH = chat_builder.compile()
