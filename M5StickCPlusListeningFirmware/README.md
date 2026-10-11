# M5StickC Plus Listening 固件 v0.2

此目录只包含娃娃硬件端固件。已刷入当前 USB 连接的 M5StickC Plus 1.1（ESP32-PICO-D4、4 MB Flash）。沿用此前的软件接收协议；云端 ASR、对话和播放由软件端处理。

## 操作

1. 开机显示已选的 B 款猫咪表情。短按正面 A 键，依次切换 Happy → Curious → Sleepy → Listening。
2. 在 Listening 表情下再按 A 开始录音。当前 USB 桥接程序运行时直接经 USB 传给 Mac；桥接程序未运行时，设备使用已配置的 Wi-Fi 与接收服务。红色 LED 常亮表示麦克风正在工作。
3. 再按 A 提前结束；否则最长录音 6 秒。设备将未录满的部分补静音。屏幕显示 `Delivered` 仅表示接收端返回 HTTP 202。
4. 侧面 B 键切换猫咪、麦克风电平和状态页。状态页显示 BLE 配对 PIN、网络配置状态及最近一次上传结果。麦克风电平页会打开麦克风，红灯也会亮；离开该页即关闭。

屏幕没有触控能力，因此“点击 Listening”在这块原型板上用 A 键选择和启动。录音不写入 Flash。Wi-Fi 模式下连接失败时不会开始录音。

## BLE 配置

设备名 `M5StickC Voice`。在状态页查看当前启动周期的六位配对 PIN。使用现有伴侣端按加密配对写入以下 GATT 特征；设置保存在 NVS 的 `voice` 命名空间。

| 用途 | UUID 后缀 | 值 |
| --- | --- | --- |
| 服务 | `7000` | `8e7b7000-6e59-4a44-9c31-7bb932760001` |
| Wi-Fi SSID | `7001` | UTF-8 文本 |
| Wi-Fi 密码 | `7002` | UTF-8 文本 |
| 网关 URL | `7003` | `http://<局域网主机>:<端口>` |
| Bearer Token | `7004` | UTF-8 文本，不含 `Bearer ` 前缀 |
| 控制 | `7005` | 写入 `start` 可远程开始一次录音 |
| 状态 | `7006` | 读取或订阅通知 |
| 设备 ID | `7007` | 读取 |

## 当前 Mac 的 USB 配置方式

此 Mac 当前没有可用的蓝牙控制器，所以也提供了 USB 串口配置。连接设备后，在 Mac 的“终端”中运行：

```sh
cd /Users/ximin.wang/Documents/Codex/2026-10-09/usb-iphone-mac-asr-meta-muse
python3 outputs/M5StickCPlusListeningFirmware/configure_usb.py
```

脚本会询问 **2.4 GHz Wi-Fi 名称**、密码和网关地址。输入密码时终端不回显；无需在聊天中发送。它会生成随机网关令牌，保存在本机 `work/voice-gateway-token.txt`（文件权限 0600），并写入设备 NVS。网关地址默认使用 Mac 当前 `en0` 地址加端口 8765；如果设备和 Mac 不在同一局域网，必须先调整网络。

脚本显示 `VOICE Wi-Fi connected <设备 IP>` 后，在另一个终端运行：

```sh
cd /Users/ximin.wang/Documents/Codex/2026-10-09/usb-iphone-mac-asr-meta-muse
sh outputs/M5StickCPlusListeningFirmware/run_local_gateway.sh
```

不提供 `OPENAI_API_KEY` 时，网关使用模拟模式完成接收链路测试。它需要一直运行；完成连通测试后，再在设备 Listening 表情下按 A。设备显示 `Delivered` 代表网关接收了音频；这时还不代表 ASR 和对话已执行。实际云端对话需要在网关所在的 Mac 上配置云端密钥，密钥不写入设备。Mac 防火墙若提示 Python 接受入站连接，应允许当前可信网络上的连接。

USB 串口配置命令以 `@` 开始，支持 `@ssid=...`、`@pass=...`、`@url=...`、`@token=...`、`@connect`、`@scan` 和 `@status`。`@scan` 只报告当前目标 Wi-Fi 是否出现在设备的 2.4 GHz 扫描结果中。请优先使用脚本，以免终端历史记录留下密码。

## VPN 环境下的 USB 音频桥接

当 VPN 接管局域网路由时，固件可临时切换成 USB 音频传输；按键和 Listening 表情不变。先启动本机网关，再运行桥接程序：

```sh
cd /Users/ximin.wang/Documents/Codex/2026-10-09/usb-iphone-mac-asr-meta-muse
sh outputs/M5StickCPlusListeningFirmware/run_local_gateway.sh
python3 outputs/M5StickCPlusListeningFirmware/usb_bridge.py
```

网关和桥接程序分别占用一个终端窗口。桥接程序连接设备后会把猫咪调到 Listening；按设备正面 A 键开始，第二次按 A 可提前结束，最长 6 秒。屏幕录音时显示 `Recording USB` 且红灯亮；Mac 接收完整音频、校验后发送给软件网关，网关返回 HTTP 202 才向设备回报 `Delivered`。`--test-once` 参数可由串口模拟一次 A 键进行诊断，然后退出。

硬件将 16 kHz 单声道 PCM16 流实时编码为 4-bit IMA ADPCM，六秒共 48000 字节；桥接程序只在 RAM 中解码成 WAV 并以原有 Bearer Token 提交 `POST /v1/utterances`。音频不写入设备 Flash 或 Mac 文件。桥接程序运行期间串口被它独占；退出后设备恢复 Wi-Fi 传输模式。当前网关无云端密钥时处于 mock 模式，HTTP 202 只证明音频进入软件端，不证明 ASR 已执行。

当前 Mac 的 GlobalProtect VPN 接管了已测试的热点和普通局域网路由，导致设备到 Mac 的 Wi-Fi TCP 音频上传阻塞。USB 桥接避开此问题，测试期间无需修改 VPN 或系统路由。

### 首场景新后端模式

`backend/` 已提供新的 ASR/同伴事件接口。按 [后端说明](../../backend/README.md) 启动 8766 端口后，在仓库根目录运行：

```sh
python3 outputs/M5StickCPlusListeningFirmware/usb_bridge.py \
  --api-mode scene --gateway http://127.0.0.1:8766
```

此模式发送 `POST /v1/device/segments`，附带随机片段 ID；只有后端完成 ASR 和写入后才给设备回报 `Delivered`。数字静音录音会在后端留下 `unreadable` 状态，桥接给当前固件发送通用的失败提示，不显示 `Delivered`；当前固件屏幕仍会写 `Bridge failed`，更准确的“未听清”文案需后续固件更新。需要在后端进程本机设置云端 ASR 密钥；缺少密钥时返回 `503`，不生成模拟结果。现有固件的 Wi-Fi 直连仍使用旧 `/v1/utterances` 协议，新后端模式当前只适用于 USB 桥接。尚未完成新后端的真机 ASR 联调。

新后端现要求先在家长模式配置孩子档案、绑定设备 ID、开启按键留言。桥接第一次收到录音会打印 `Device ID for parent binding`；未绑定时该次录音被拒绝，不会做 ASR。绑定设置和示例命令见[后端说明](../../backend/README.md)。

## 软件端接口

固件在 Wi-Fi 模式下、Mac 桥接程序在 USB 模式下，均发送 `POST /v1/utterances`。请求头有 `Authorization: Bearer <token>`、`X-Device-ID: stickc-<MAC>`、`Content-Type: audio/wav`。请求体是 16 kHz、单声道、16-bit PCM WAV；Wi-Fi 模式下 WAV 固定 192044 字节，USB 模式下提前结束的录音可更短。当前网关以 HTTP 202 表示接受请求；其他状态显示为服务端错误。此原型只支持局域网 HTTP，生产部署需要 TLS、设备身份管理和凭据轮换。

## 构建与验证记录

`platformio.ini` 使用此工作区内已安装的本地 PlatformIO 包。构建成功，固件占约 1.65 MB Flash。USB 刷写和哈希校验成功，芯片识别为 ESP32-PICO-D4 rev 1.1。真机诊断录制了 6.00 秒音频，经 USB 传输和校验后还原为 192044 字节 WAV；本机网关返回 HTTP 202，任务状态为 `done`，麦克风峰值 2972。网关目前是 mock 模式，这项验证不包含真实 ASR 或对话。
