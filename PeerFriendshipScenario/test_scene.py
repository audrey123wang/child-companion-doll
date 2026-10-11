import unittest
from dataclasses import replace
from datetime import date, datetime, timezone

from scene import child_reply, daily_report, extract_event, story_for_age, weekly_report


NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


class PeerSceneTests(unittest.TestCase):
    def test_example_does_not_store_names_or_infer_feeling(self):
        event = extract_event("今天为什么甜甜不跟我玩儿，去跟裙裙玩儿了", child_id="demo", occurred_at=NOW)
        self.assertIsNotNone(event)
        self.assertNotIn("甜甜", str(event.json()))
        self.assertNotIn("裙裙", str(event.json()))
        self.assertIsNone(event.explicit_feeling)
        self.assertEqual(event.attribution, "unconfirmed")

    def test_daily_does_not_claim_whole_day(self):
        event = extract_event("朋友不跟我玩儿，去跟别的小朋友玩了", child_id="demo", occurred_at=NOW)
        report = daily_report([event], child_id="demo", day=date(2026, 10, 11))
        self.assertEqual(report["event_count"], 1)
        self.assertIn("无法判断", report["overall"])
        self.assertNotIn("难过", "".join(report["observations"]))

    def test_weekly_counts_days_and_ignores_deleted(self):
        first = extract_event("朋友不跟我玩，去跟别人玩", child_id="demo", occurred_at=NOW)
        second = extract_event("同学不带我一起玩", child_id="demo", occurred_at=NOW)
        deleted = replace(first, review_state="deleted")
        report = weekly_report([first, second, deleted], child_id="demo", week_end=date(2026, 10, 11))
        self.assertEqual(report["days_mentioned"], 1)
        self.assertEqual(report["event_count"], 2)

    def test_unknown_input_is_not_forced_into_peer_topic(self):
        self.assertIsNone(extract_event("我今天吃了苹果", child_id="demo", occurred_at=NOW))

    def test_child_can_stop_and_no_mind_reading(self):
        self.assertIn("停在这里", child_reply("我不想聊了"))
        self.assertIn("不知道", child_reply("甜甜是不是讨厌我"))

    def test_story_age_boundary(self):
        self.assertEqual(story_for_age(5)["age_band"], "5-7")
        self.assertEqual(story_for_age(12)["age_band"], "11-12")
        with self.assertRaises(ValueError):
            story_for_age(4)


if __name__ == "__main__":
    unittest.main()
