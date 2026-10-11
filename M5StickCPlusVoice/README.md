# M5StickC Plus 1.1 voice prototype

This prototype implements button → built-in microphone → Wi-Fi → gateway →
ASR → text reply → TTS → iPhone/Mac playback. Bluetooth LE is used for pairing,
configuration and a remote start command. The M5StickC Plus has a buzzer rather
than a speech speaker, so replies play on the companion device.

## Status

- Target hardware: M5StickC Plus 1.1, ESP32-PICO-D4, 4 MB flash.
- Firmware: PlatformIO / Arduino source in `firmware/`.
- Firmware compiled and flashed to the connected board on 2026-10-09. The
  serial boot log confirms board initialization and a six-digit BLE PIN.
- The merged flash image is kept locally and is not published because compiled device images may contain configuration data. Build from source for a fresh image.
- Gateway: Python standard library only, in `gateway/`.
- Companion: one SwiftUI source file for iOS and macOS, in `companion/`. The
  macOS app was built and code-signed in `companion/M5StickC Voice.app`.
- The device firmware version prior to flashing was not identified. USB's
  `bcdDevice 0x0500` is **not** an application firmware version.

## Start the gateway on the Mac

The phone, Mac and device must share a Wi-Fi LAN. Find the Mac's LAN IP address
and allow incoming connections to TCP port 8765 if macOS prompts.

```sh
cd gateway
export OPENAI_API_KEY='set-this-locally-in-your-terminal'
./run-gateway.sh
```

The script prints a freshly generated gateway token. Enter it into the
companion app; it is not the OpenAI API key. With no OpenAI key, the gateway
runs in mock mode and returns a short tone to verify transport and playback.
Run a real cloud test only after setting `OPENAI_API_KEY`. The key stays on
the Mac gateway and is never written to the ESP32 or app.

The default models are `gpt-transcribe`, `gpt-4o-mini`, and
`gpt-4o-mini-tts`. Override `VOICE_ASR_MODEL`, `VOICE_TEXT_MODEL`,
`VOICE_TTS_MODEL` and `VOICE_TTS_VOICE` as needed. The gateway does not retain
recordings or transcriptions after its process exits; completed jobs remain
in process memory while it runs.

## Build the companion

On this Mac, the command line Swift compiler can build the macOS app:

```sh
sh companion/build-macos.sh
open "companion/M5StickC Voice.app"
```

For iPhone, install full Xcode and XcodeGen, run `xcodegen generate` in
`companion/`, select the iOS target, sign it with your Apple development team,
and run it on the phone. The iOS target has not been built in this workspace
because only Xcode Command Line Tools are installed here.

In the app, connect to **M5StickC Voice**. When writing configuration for the
first time, enter the six-digit BLE PIN shown on the device screen. Enter the
2.4 GHz Wi-Fi SSID and password, gateway URL such as
`http://192.168.1.2:8765`, and the gateway token. Tap **写入设备配置**.
Use the front button or **开始录音**. The device records five seconds. When the
gateway finishes, the companion polls for the answer and plays it.

## Build and flash firmware

Use PlatformIO from this directory:

```sh
cd firmware
pio run
pio run -t upload --upload-port /dev/cu.usbserial-59526C1D38
```

The upload command replaces the current application. Confirm the serial port
again if reconnecting the device changes its name. No Wi-Fi password or API key
is embedded in the compiled image. The BLE configuration is saved in ESP32 NVS.

The original 4 MB flash was backed up before flashing. Its SHA-256 is
`0b8b29e35b61c73473ed5ddcbed6328e6265e9ec16a14a5130efd3788615def1`.
The backup stays in the local `work/` directory because it could contain old
Wi-Fi credentials; it is not included with these deliverables.

## Protocol

The firmware advertises GATT service
`8e7b7000-6e59-4a44-9c31-7bb932760001`. Write characteristics ending in
`7001`–`7004` hold SSID, Wi-Fi password, gateway URL, and gateway token.
The characteristic ending in `7005` accepts `start`; `7006` sends status and
`7007` gives the device ID. Configuration writes require an encrypted BLE
connection. The device posts mono PCM16 WAV at 16 kHz to `/v1/utterances`.

## Current prototype limits

- Five-second, push-to-talk recordings; no wake word or interruption.
- HTTP and the gateway token travel over the local Wi-Fi network. Use a
  trusted LAN for this prototype; use TLS before exposure beyond it.
- On this Mac, `system_profiler` reports no Bluetooth controller and the app
  reports Bluetooth unauthorized, so BLE discovery and pairing could not be
  tested here. Check macOS Bluetooth availability and app permission on a Mac
  with a controller.
- Wi-Fi and BLE radio coexistence, microphone levels, iOS pairing and iPhone
  playback still require testing with network configuration on the device.
- Audio output on the device requires an external speaker/codec or another board.
- This is a prototype gateway without persistent queues or OTA updates.

Official references: [M5StickC Plus hardware](https://docs.m5stack.com/en/core/StickC-Plus),
[OpenAI voice architectures](https://developers.openai.com/api/docs/guides/voice-agents),
[OpenAI transcription](https://developers.openai.com/api/docs/guides/speech-to-text),
[OpenAI speech generation](https://developers.openai.com/api/docs/guides/text-to-speech).
