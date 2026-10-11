"""Synthetic-data-only reference logic for the first peer-interaction scene.

This is not an ASR system, a child-safety classifier, or a production service.
No raw input text is saved into the returned event.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional
import uuid


TOPIC = "peer_play"
STORY_TOPIC = "friendship_and_inclusion"


@dataclass(frozen=True)
class PeerEvent:
    event_id: str
    child_id: str
    occurred_at: str
    source: str
    topic: str
    summary: str
    explicit_feeling: Optional[str]
    attribution: str
    story_topic: str
    review_state: str = "unreviewed"

    def json(self) -> dict:
        return asdict(self)


def extract_event(
    text: str, *, child_id: str, occurred_at: datetime,
    source: str = "button", event_id: Optional[str] = None,
) -> Optional[PeerEvent]:
    """Recognize a narrow sample pattern; return None rather than guess.

    A production flow needs ASR quality checks and reviewed extraction. Device
    use does not prove the voice belongs to the child, so attribution remains
    unconfirmed until a separate confirmation process exists.
    """
    if source not in {"button", "ambient"}:
        raise ValueError("source must be button or ambient")
    if not child_id or occurred_at.tzinfo is None:
        raise ValueError("child_id and timezone-aware occurred_at are required")
    normalized = "".join(text.split())
    peer_words = ("朋友", "同学", "小朋友", "跟我玩", "和我玩", "一起玩")
    separation_words = ("不跟我", "不和我", "不带我", "不让我", "去跟", "去和", "不陪我")
    if not (any(word in normalized for word in peer_words)
            and any(word in normalized for word in separation_words)):
        return None

    feeling = next((word for word in ("难过", "伤心", "生气", "孤单", "委屈")
                    if word in normalized), None)
    # Deliberately do not copy the transcript or names into the event.
    summary = "孩子提到一位同伴转去和另一位同伴玩，并对此表示不理解。"
    if "不让我" in normalized or "不带我" in normalized:
        summary = "孩子提到一次未能加入同伴游戏的经历。"
    return PeerEvent(
        event_id=event_id or uuid.uuid4().hex,
        child_id=child_id,
        occurred_at=occurred_at.isoformat(),
        source=source,
        topic=TOPIC,
        summary=summary,
        explicit_feeling=feeling,
        attribution="unconfirmed",
        story_topic=STORY_TOPIC,
    )


def _events_on_day(events: Iterable[PeerEvent], child_id: str, day: date) -> list[PeerEvent]:
    return [event for event in events
            if event.child_id == child_id and event.review_state != "deleted"
            and datetime.fromisoformat(event.occurred_at).date() == day]


def daily_report(events: Iterable[PeerEvent], *, child_id: str, day: date) -> dict:
    selected = _events_on_day(events, child_id, day)
    if not selected:
        return {
            "date": day.isoformat(), "event_count": 0,
            "headline": "今天没有可用于总结的同伴相处记录",
            "overall": "记录不足，无法判断孩子今天的整体情况。",
            "observations": [], "parent_prompts": [], "story_topic": None,
        }
    feelings = sorted({event.explicit_feeling for event in selected if event.explicit_feeling})
    observations = [
        "孩子通过娃娃主动提到一次同伴相处的困惑。"
        if any(event.source == "button" for event in selected)
        else "设备在获准时段收到一条可能与同伴相处有关的表达，尚待确认。",
        "现有记录无法说明其他孩子当时的想法或完整经过。",
    ]
    if feelings:
        observations.append("孩子明确说到的感受：" + "、".join(feelings) + "。")
    has_button = any(event.source == "button" for event in selected)
    return {
        "date": day.isoformat(), "event_count": len(selected),
        "headline": "今天有同伴相处方面的主动表达" if has_button else "今天有待确认的同伴相处观察",
        "overall": "仅凭现有留言，无法判断孩子全天的心情或整体相处情况。",
        "observations": observations,
        "parent_prompts": [
            "你当时想和他们玩什么？",
            "后来发生了什么？",
            "你希望我听你说，还是一起想想明天可以怎样邀请朋友？",
        ],
        "story_topic": STORY_TOPIC,
    }


def weekly_report(events: Iterable[PeerEvent], *, child_id: str, week_end: date) -> dict:
    week_start = week_end - timedelta(days=6)
    selected = [event for event in events
                if event.child_id == child_id and event.review_state != "deleted"
                and week_start <= datetime.fromisoformat(event.occurred_at).date() <= week_end]
    days = {datetime.fromisoformat(event.occurred_at).date() for event in selected}
    return {
        "start": week_start.isoformat(), "end": week_end.isoformat(),
        "days_mentioned": len(days), "event_count": len(selected),
        "summary": (
            f"过去 7 天，孩子有 {len(days)} 天、共 {len(selected)} 次提到同伴相处的困惑。"
            "这些记录不足以判断是否长期被排斥或推断情绪趋势。"
            if selected else "过去 7 天没有可用于总结的同伴相处记录；不能据此判断没有困扰。"
        ),
    }


STORY = {
    "id": "mimi-new-game-circle-v1",
    "title": "小猫米米和新的游戏圈",
    "topic": STORY_TOPIC,
    "age_bands": ["5-7", "8-10", "11-12"],
    "text": (
        "小猫米米带着纸飞机去找小兔。小兔正在和小熊搭城堡。"
        "米米心想：他们是不是不想和我玩了？可是米米还不知道发生了什么。"
        "米米走近一点，问：我可以帮你们做一扇门吗？"
        "小兔说：城堡快搭好了，明天我们也可以一起飞纸飞机。"
        "米米想了想，今天可以等一会儿，也可以先去找小松鼠飞纸飞机。"
        "它选了自己喜欢的游戏，决定明天再邀请小兔。"
    ),
    "questions": ["米米一开始知道小兔为什么在搭城堡吗？", "如果是你，你还会想到什么办法？"],
}


def story_for_age(age: int) -> dict:
    if not 5 <= age <= 12:
        raise ValueError("age must be 5 to 12")
    # The same text is a demo asset; the content team must produce age-specific editions.
    return {**STORY, "age_band": "5-7" if age <= 7 else "8-10" if age <= 10 else "11-12"}


def child_reply(text: str) -> str:
    """Small reviewed-style demo replies; never sends raw text to an LLM."""
    normalized = "".join(text.split())
    if any(word in normalized for word in ("不想聊", "不想讲", "停", "换话题")):
        return "好呀，我们可以停在这里。想再听一段故事，还是休息一下？"
    if any(word in normalized for word in ("受伤", "打我", "欺负我", "害怕", "每天都不让我")):
        return "这听起来很难受。请找爸爸妈妈、老师或其他信任的大人说一说，我也可以陪你想想怎么开口。"
    if any(word in normalized for word in ("讨厌我", "为什么不跟我", "为什么不和我")):
        return "我不知道其他小朋友是怎么想的。你愿意说说，当时你看到和听到了什么吗？"
    if any(word in normalized for word in ("难过", "伤心", "委屈")):
        return "听起来你有点难过。你想让我先听你说，还是一起想想下一次可以怎么邀请朋友？"
    return "米米也遇到过想一起玩的时候。你愿意聊聊自己最想玩的游戏吗？不想聊也可以。"
