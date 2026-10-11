# 同伴相处场景业务逻辑样例

这份 Python 标准库样例仅用于使用合成语句验证首个场景的事件抽取、日报、周报、故事和儿童回复。它不是生产 ASR、说话人识别、儿童安全模型或 App 服务端；不接收真实儿童音频，也不保存输入文本。

运行测试：

```sh
cd PeerFriendshipScenario
python3 -m unittest -v test_scene.py
```

运行一条合成语句：

```sh
python3 - <<'PY'
from datetime import datetime, timezone
from scene import extract_event, daily_report
now = datetime.now(timezone.utc)
event = extract_event('今天为什么甜甜不跟我玩儿，去跟裙裙玩儿了', child_id='demo', occurred_at=now)
print(event.json())
print(daily_report([event], child_id='demo', day=now.date()))
PY
```

下一步接入要补：ASR 质量检查、设备与家庭鉴权、按家庭时区归档、去重、家长纠错/删除、持久化事件与保留期限、正式故事审核、iPhone/iPad 同一 App 双模式权限、儿童对话安全评测。完整流程见[场景开发规格](../同伴相处首个场景开发规格.md)。
