"""Conservative, synthetic-only rules for the first peer scene."""

from __future__ import annotations

import re
from typing import Any


def extract_sample_event(text: str) -> dict[str, Any] | None:
    compact = "".join(text.split())
    # A narrow first-scene recognizer. Only concrete play/social wording qualifies;
    # a name, a negative sentence, or an emotion alone is not enough evidence.
    play = "玩" in compact or "游戏" in compact
    exclusion = bool(re.search(r"(?:不|没|没有)(?:跟|和|陪|带|让)我(?:一起|去|来)?玩|不让我(?:参加|加入)|不带我(?:玩|一起)", compact))
    moved = bool(re.search(r"(?:去|跑去|转去)(?:跟|和|找).{0,12}玩", compact))
    invited = bool(re.search(r"(?:我(?:想|要|能不能)|怎么|怎样)(?:跟|和|加入).{0,12}(?:玩|游戏)", compact))
    peer_context = any(x in compact for x in ("朋友", "同学", "小朋友", "同伴"))
    if not play or not (exclusion or (invited and peer_context)):
        return None
    feeling = next((word for word in ("难过", "伤心", "生气", "孤单", "委屈")
                    if re.search(rf"我(?:今天|现在|当时)?(?:觉得|感觉|感到)?(?:有点|很|好|非常|真的|有些|特别|太)?{word}", compact)), None)
    if exclusion and moved:
        situation = "peer_changed_playmate"
        summary = "收到一条按键留言，提到一位同伴没有一起玩，转去和其他同伴玩。"
    elif exclusion:
        situation = "not_playing_together"
        summary = "收到一条按键留言，提到没有和同伴一起玩。"
    else:
        situation = "wants_to_join_play"
        summary = "收到一条按键留言，提到想加入同伴的游戏。"
    return {
        "topic": "peer_play",
        "situation": situation,
        "summary": summary,
        "explicit_feeling": feeling,
        "attribution": "unconfirmed",
        "review_state": "unreviewed",
    }


def reply_sample(text: str, turn_number: int = 1) -> tuple[str, str]:
    compact = "".join(text.split())
    if any(x in compact for x in ("受伤", "打我", "害怕", "每天都不让我")):
        return "support", "这听起来很难受。请找爸爸妈妈、老师或其他信任的大人说一说。"
    if any(x in compact for x in ("不想聊", "不想讲", "停止", "停下", "换话题")):
        return "stopped", "好呀，我们先停在这里。想休息一下也可以。"
    if "讨厌我" in compact or "为什么不跟我" in compact:
        return "conversation", "我不知道其他小朋友当时怎么想。你愿意说说，你看到什么了吗？"
    if any(x in compact for x in ("米米好像我", "和米米一样", "我也像米米")):
        return "conversation", "原来你也有过像米米这样的时刻。你愿意说说，当时最想和朋友做什么吗？不想说也可以。"
    if any(x in compact for x in ("我很难过", "我有点难过", "我很伤心", "我很生气")):
        return "conversation", "谢谢你告诉我你的感受。你想让我先听你说，还是一起想想可以找谁聊聊？"
    if "怎么问" in compact or "想问朋友" in compact:
        return "conversation", "可以先说自己看到的事，再问一句：我能一起玩吗？对方怎么想，我们要听过才知道。"
    if "想一起玩" in compact or "想加入" in compact:
        return "conversation", "想加入游戏很自然。你想像米米一样先问问，还是先玩自己喜欢的游戏？"
    prompts = {
        1: "米米也遇到过想一起玩的时候。你最想玩什么游戏呢？不想聊也可以。",
        2: "听起来你很在意这件事。你愿意说说，你当时看到的事情是什么吗？",
        3: "米米在故事里试着问一问。你想先自己想想，还是找信任的大人一起聊聊？",
    }
    return "conversation", prompts.get(turn_number, "谢谢你告诉我。我们不用急着弄明白所有事情，可以先休息一下。")
