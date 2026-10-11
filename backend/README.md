# 同伴相处首场景后端（本机实验）

本机已配置密钥时，从项目根目录运行 `backend/run_local.sh` 即可启动后端。脚本读取仅供本机使用、已被 `.gitignore` 排除的 `backend/.env`；前端与固件不读取此文件。

当前工程提供两条本机链路：娃娃按键录音 → Mac USB 桥接 → ASR → 当日逐字稿/事件/家长日报；以及平板端短录音 → ASR → DeepSeek V4 同伴相处问答 → 先展示文字 → 按需 TTS。首页自由问答与故事后讨论使用独立入口；首页问答不要求当晚已有故事推荐。前端位于 `outputs/ChildCompanion`，故事仍是待审核原创草稿。**此工程仅用于本机授权成人样音与合成数据的功能验证；不要用于真实儿童数据或对外网开放。**

## 运行

Python 3.11+，本机已有虚拟环境与 `backend/.env` 时，从项目根目录运行：

```sh
backend/run_local.sh
```

`VOLC_API_KEY` 需在本机环境中设置；不要写入仓库、固件或聊天。此密钥同时传给火山引擎流式语音识别 2.0 与语音合成 2.0，但对应账号必须分别开通两项服务及所选资源。ASR 默认资源为 `volc.seedasr.sauc.duration`（小时版），可用 `VOLC_ASR_RESOURCE_ID=volc.seedasr.sauc.concurrent` 改为并发版。TTS 默认资源为 `seed-tts-2.0`，默认音色 `zh_female_vv_uranus_bigtts`，可用 `VOLC_TTS_SPEAKER` 配置账号已开通的 2.0 音色。ASR 通过 WebSocket 将录好的 WAV 按每包约 200 毫秒音频分包上传，逐包等待服务端响应，不再额外等待 200 毫秒；当前接口不向前端实时推送中间转写。TTS 通过 HTTP Chunked 收取并拼接 MP3 片段，然后返回完整音频。未设置密钥时 `/v1/device/segments` 返回 `503`，不会生成假转写。若不使用 USB 桥接，可省略 `LOCAL_DEVICE_TOKEN_FILE`，用 `LOCAL_DEVICE_TOKEN` 配置本机演示令牌。`LOCAL_SQLITE_PATH` 可省略；省略后记录仅在内存中。SQLite 文件未加密，当前仅适合成人样音实验。接口文档：`http://127.0.0.1:8766/docs`。

`DEEPSEEK_API_KEY` 只用于文字问答，独立于语音密钥；默认模型为 `deepseek-v4-pro`，可用 `DEEPSEEK_MODEL` 改为账号可用的其他模型。未设置该密钥时，真实问答接口返回 `503`。模型按同伴相处主题接收孩子当前输入、当天最多三条同伴事件摘要及本次会话最近几轮文字。模型失败返回 `502`，不会消耗会话轮次。使用模型前需确认对应账号已开通该模型；本机模拟测试不会验证账号权限或实际计费。

在另一个终端、仓库根目录运行 USB 桥接：

```sh
python3 outputs/M5StickCPlusListeningFirmware/usb_bridge.py \
  --api-mode scene --gateway http://127.0.0.1:8766
```

设备切到 `Listening` 表情，按正面 A 键录音，再按 A 键结束，最长六秒。桥接收到后会校验 ADPCM 数据、在内存中还原 WAV 并同步提交；后端完成 ASR 和记录后，桥接才向设备回报 `Delivered`。2026-10-11 已用连接的设备验证一次火山引擎 ASR 2.0 成功入库并显示 `Delivered`；此前也出现过转写为空，尚需核对逐字准确度和连续调用稳定性。

新后端模式要求先在家长端建立孩子档案、绑定设备，并开启按键留言。当前还没有新 App 界面，可用本机接口配置：

```sh
curl -X PUT http://127.0.0.1:8766/v1/parent/profile \
  -H 'Authorization: Bearer local-parent-token' -H 'Content-Type: application/json' \
  -d '{"child_id":"demo-child","age":7,"school_stage":"grade_1","listening_start":"08:00","listening_end":"20:00"}'
curl -X PUT http://127.0.0.1:8766/v1/parent/device-binding \
  -H 'Authorization: Bearer local-parent-token' -H 'Content-Type: application/json' \
  -d '{"child_id":"demo-child","device_id":"stickc-替换为实际设备ID"}'
curl -X PUT http://127.0.0.1:8766/v1/parent/button-recording \
  -H 'Authorization: Bearer local-parent-token' -H 'Content-Type: application/json' \
  -d '{"child_id":"demo-child","enabled":true}'
```

实际设备 ID 可从 BLE 的设备 ID 特征读取；USB 桥接在第一次收到录音时也会打印 `Device ID for parent binding`，首次未绑定时该录音会被拒绝，不会进入 ASR。示例令牌只用于本机实验。

## API 与行为

- `PUT/GET /v1/parent/profile`：家长设置一个本机孩子档案、年龄、学段和监听时间。时间目前只存为配置，`scheduled_listening_status=configuration_only`，**不会让固件自动常开麦克风**。`PUT /v1/parent/device-binding` 绑定娃娃；`PUT /v1/parent/button-recording` 开启或暂停按键留言。默认关闭，暂停后拒收新的设备录音。
- `POST /v1/device/segments`：`audio/wav`，16 kHz、单声道、PCM16、0.25–6 秒、最多 220 KB；请求头 `Authorization: Bearer ...`、`X-Device-ID`、`X-Segment-ID`。孩子 ID 由后端设备绑定确定，不能通过请求头指定。成功返回逐字稿、状态与事件 ID；数字静音返回 `unreadable`（无逐字稿、无事件，不调用 ASR），仍作为一条未听清的输入供家长查看。同一设备的同一片段 ID 幂等。设备未绑定/按键留言暂停 `403`，ASR 未配置 `503`，供应商失败 `502`，格式错误、录音过短或不完整 `422`。该静音门槛不等于语音活动检测，背景噪声仍可能进入 ASR。
- `GET /v1/parent/inputs?child_id=...&date=YYYY-MM-DD`：家长当天可见未经脱敏的 ASR 逐字稿和 `transcript_revision`；家庭时区次日 00:00 后接口不再返回正文，持久库在读取或下次启动时清空字段。
- `PATCH /v1/parent/inputs/{device_id}/{segment_id}`：家长在当天核对并改正 ASR 文本，传 `child_id`、`text`、`expected_revision`。服务端重新识别同伴事件并重算日报/故事；较旧版本返回 `409`，跨日返回 `410`。`DELETE` 同一路径，带 `child_id` 与 `expected_revision` 查询参数，可删除输入及对应事件，原文从数据库字段清除。删除历史日的输入仍允许，但不能重新写入过期逐字稿。
- `GET /v1/parent/reports/daily`：当日 19:00 后返回规则报告。`input_counts` 分别给出有效输入、已识别、未归类和未听清的数量；`coverage_note` 说明哪些输入未用于同伴事件判断。每条观察均带来源事件 ID；只有留言明确表达的感受才会单独列出，单条留言会说明无法判断是否反复发生或代表全天。任一有效输入新增、更正或删除都会更新报告修订号；旧版缓存报告自动重建。服务启动后每分钟检查到期报告并写入 SQLite；进程未运行时，下次读取或启动会补生成。当前尚无自然语言模型总结；家长在 App 内查看报告。
- `GET /v1/parent/today?child_id=...`：家长今日概览，提供主动输入数、未听清数、未归类数、同伴事件数、日报状态和修订号；不返回逐字稿。本轮不做手机系统推送。
- `PATCH/DELETE /v1/parent/events/{event_id}`：更正或删除同伴事件并增加当日日报修订号。本轮不提供七日报告接口。
- `GET /v1/child/story/today?child_id=...`：家庭时区 19:00 后，当天有未删除的同伴事件才推荐故事；年龄从家长设置的档案读取。未配置档案的纯合成测试仍需传 `age`。故事标为 `approved=false`、`demo_only=true`，目前只供本机成人审核。不会返回设备逐字稿、同伴姓名或家长报告。
- `GET /v1/child/story/today/audio?child_id=...&age=7`：以 MP3 朗读当日适龄故事的标题和正文；需要 TTS 密钥，响应标明 AI 合成声音。前端需同步显示“这段声音由 AI 生成”。
- `POST /v1/child/story-sessions`：故事播放完后提交 `child_id`、`story_id`，未配置家长档案的纯本机实验还需传 `age`。返回 20 分钟会话 ID、适龄开场问题及其 MP3 Base64 配音；TTS 失败时仍返回文字问题和会话 ID，`tts_status=failed`。`DELETE /v1/child/story-sessions/{session_id}?child_id=...` 供儿童端退出按钮直接结束会话；过期会话自动清理。
- `POST /v1/child/chat-turns/transcribe`：平板端发送 16 kHz 单声道 PCM16 WAV（0.25–15 秒、最多 500 KB），请求头带 `X-Child-ID`、`Content-Type: audio/wav`；只返回 `heard_text`，由儿童端先展示并允许确认，不写入家长记录。
- `POST /v1/child/conversations/turns`：首页直接问答，提交 `child_id`、`text` 和可选 `session_id`；无需故事 ID，不受 19:00 推荐故事条件限制。仍使用当天最多三条同伴事件摘要作为可选背景，若没有摘要则仅按孩子当下说的话回答。返回文字及 `reply_id`，配音继续通过 `/v1/child/chat-turns/{reply_id}/speech` 获取。
- `POST /v1/child/chat-turns`：故事后讨论入口，提交 `child_id`、`story_id`、`text` 和可选 `session_id`，仍须满足当晚故事推荐条件。调用 DeepSeek V4 后立即返回 `reply_text`、`reply_id` 和 `tts_status=pending`（已配置 TTS 时）；客户端先展示文字。每次会话最多六轮，停止语句立即结束；会话只在内存中保留 20 分钟，不写入家长记录。`ALLOW_SYNTHETIC_INPUT=1` 的本机测试允许无模型时使用规则回复。
- `POST /v1/child/chat-turns/{reply_id}/speech?child_id=...`：文字展示后由客户端请求 MP3 并播放。语音合成失败返回 `502`，不影响已返回的文字；回复 ID 仅在内存中保存 20 分钟。
- `POST /v1/child/story-narration`：给前端保留的本地故事逐页生成 MP3；提交 `child_id`、允许的本地 `story_id`、页号和最多 1500 字正文。仅限本机实验，返回 `audio/mpeg` 和 AI 配音标记。
- `POST /v1/child/chat-turns/audio`：旧版一体化短语音接口，仍支持 ASR→模型→TTS，一次返回文字与 MP3 Base64；新客户端应使用上述三步调用以保证先展示文字。静音、过短或不完整录音返回 `422`。
- `POST /v1/dev/segments/text`：合成文本测试入口，只有设置 `ALLOW_SYNTHETIC_INPUT=1` 才启用。

本机演示令牌默认 `local-device-token`、`local-parent-token`、`local-child-token`，可用相应 `LOCAL_*_TOKEN` 环境变量覆盖；这不是正式的账号和家庭级鉴权。当前只支持一个本机孩子档案，并在其存在时拒绝跨档案查询。所有 HTTP 请求限制为本机环回地址。原始音频只在桥接和后端请求内存中存在，不写入数据库；SQLite 会保存当日 ASR 原文到次日本地零点。生产前还需正式账号与模式切换验证、数据库加密、定时清理与备份策略、监护人授权/撤回、故事审核、儿童安全评测和 HTTPS 设备身份。

儿童端推荐调用顺序：取 `/v1/child/story/today` 展示标题、正文和 AI 配音提示 → 播放 `/v1/child/story/today/audio` 的 MP3（客户端负责暂停/继续）→ 播完后创建 `/v1/child/story-sessions`，显示并播放开场问题 → 后续每轮录音依次调用 `transcribe`、`chat-turns`、`{reply_id}/speech`，先展示识别文字与回答文字，再播放回答配音。后续文字轮次传上次返回的 `session_id`。收到 `route=stopped` 或 `support` 时结束会话；用户点退出按钮可直接删除会话。当前故事仍是未审核草稿，只供本机成人模拟。

## 验证

独立验证火山引擎 TTS 2.0（终端安全输入密钥，短句生成后由 Mac 播放，临时 MP3 随后删除）：

```sh
cd backend
.venv/bin/python scripts/verify_tts.py
```

2026-10-11 用户已确认上述 TTS 短句生成及播放成功；完整故事和儿童对话流程仍需联调。


```sh
cd backend
APP_ENV=local .venv/bin/python -m pytest -q
```

测试覆盖 WAV 接入、数字静音/过短/损坏录音拦截、火山引擎 ASR 2.0 二进制分包及 TTS 2.0 流式响应模拟、设备绑定及暂停、请求头伪造孩子 ID、跨档案隔离、重启恢复、当日逐字稿纠错/版本冲突/跨日拒写、输入删除与报告/故事重算、旧版 SQLite 迁移、19:00 报告修订和未听清日的定时生成、常见同伴相处表达识别、明确感受与事件引用、家长今日概览、儿童故事 TTS→开场问题→语音问答→退出、DeepSeek V4 请求格式与文字先于 TTS 的模拟链路；不调用真实云端服务。接口定义保存在 [openapi.json](openapi.json)。
