#include <Arduino.h>
#include <M5StickCPlus.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <BLESecurity.h>
#include <driver/i2s.h>
#include <esp_gatt_defs.h>

// The screen is not touch sensitive. A selects Listening and starts/stops capture.
enum Page : uint8_t { FACE, MIC, PAGE_STATUS };
static Page page = FACE;
static uint8_t emotion = 0;
static bool micReady = false;
static uint32_t lastPaint = 0;
static constexpr uint16_t BG = 0x10A2;
static constexpr uint16_t INK = 0x18E3;
static constexpr int SAMPLE_RATE = 16000;
static constexpr int RECORD_SECONDS = 6;
static constexpr int PCM_SIZE = SAMPLE_RATE * RECORD_SECONDS * 2;
static constexpr int USB_AUDIO_BYTES = SAMPLE_RATE * RECORD_SECONDS / 2;
static const char *SERVICE_UUID = "8e7b7000-6e59-4a44-9c31-7bb932760001";
static const char *SSID_UUID    = "8e7b7001-6e59-4a44-9c31-7bb932760001";
static const char *PASS_UUID    = "8e7b7002-6e59-4a44-9c31-7bb932760001";
static const char *URL_UUID     = "8e7b7003-6e59-4a44-9c31-7bb932760001";
static const char *TOKEN_UUID   = "8e7b7004-6e59-4a44-9c31-7bb932760001";
static const char *CONTROL_UUID = "8e7b7005-6e59-4a44-9c31-7bb932760001";
static const char *STATUS_UUID  = "8e7b7006-6e59-4a44-9c31-7bb932760001";
static const char *ID_UUID      = "8e7b7007-6e59-4a44-9c31-7bb932760001";
static Preferences prefs;
static BLECharacteristic *statusCharacteristic = nullptr;
static String ssid, password, gatewayURL, gatewayToken, deviceID;
static uint32_t blePin = 0;
static volatile bool startRequested = false;
static volatile bool configChanged = false;
static bool recording = false;
static bool usbTransport = false;
static String lastResult = "Ready";
static String serialConfigLine;
static bool serialConfigActive = false;

static void report(const String &state, const String &detail = "") {
    lastResult = state;
    Serial.printf("VOICE %s %s\n", state.c_str(), detail.c_str());
    if (statusCharacteristic) {
        String message = state + ":" + detail;
        statusCharacteristic->setValue(message.c_str());
        statusCharacteristic->notify();
    }
}

static void resultScreen(const String &title, const String &detail) {
    M5.Lcd.fillScreen(BG);
    M5.Lcd.setTextColor(WHITE, BG);
    M5.Lcd.setTextSize(2);
    M5.Lcd.setCursor(10, 15);
    M5.Lcd.println(title);
    M5.Lcd.setTextSize(1);
    M5.Lcd.setCursor(10, 60);
    M5.Lcd.println(detail);
    report(title, detail);
}

static void header(const char *title) {
    M5.Lcd.fillScreen(BG);
    M5.Lcd.fillRoundRect(5, 4, 230, 25, 8, INK);
    M5.Lcd.setTextColor(WHITE, INK);
    M5.Lcd.setTextSize(2);
    M5.Lcd.setCursor(13, 8);
    M5.Lcd.print(title);
    M5.Lcd.setTextColor(WHITE, BG);
    M5.Lcd.setTextSize(1);
    M5.Lcd.setCursor(8, 121);
    M5.Lcd.print("A: action     B: next page");
}

static void face() {
    const char *names[] = {"Happy", "Curious", "Sleepy", "Listening"};
    const uint16_t mint = M5.Lcd.color565(221, 239, 229);
    const uint16_t cream = M5.Lcd.color565(255, 245, 225);
    const uint16_t earPink = M5.Lcd.color565(239, 199, 141);
    const uint16_t blush = M5.Lcd.color565(247, 184, 173);
    const uint16_t faceInk = M5.Lcd.color565(88, 66, 68);
    M5.Lcd.fillScreen(mint);
    M5.Lcd.fillTriangle(68, 49, 76, 26, 96, 44, cream);
    M5.Lcd.fillTriangle(144, 44, 164, 26, 172, 49, cream);
    M5.Lcd.fillTriangle(75, 41, 77, 33, 85, 41, earPink);
    M5.Lcd.fillTriangle(155, 41, 163, 33, 165, 41, earPink);
    M5.Lcd.fillCircle(120, 79, 43, cream);
    M5.Lcd.fillCircle(87, 91, 6, blush);
    M5.Lcd.fillCircle(153, 91, 6, blush);
    if (emotion == 2) {
        M5.Lcd.drawFastHLine(95, 71, 15, faceInk);
        M5.Lcd.drawFastHLine(130, 71, 15, faceInk);
        M5.Lcd.drawLine(97, 72, 100, 74, faceInk);
        M5.Lcd.drawLine(140, 74, 143, 72, faceInk);
    } else {
        const int radius = emotion == 1 ? 9 : 7;
        M5.Lcd.fillCircle(102, 71, radius, faceInk);
        M5.Lcd.fillCircle(138, 71, radius, faceInk);
        M5.Lcd.fillCircle(99, 68, 2, WHITE);
        M5.Lcd.fillCircle(135, 68, 2, WHITE);
        if (emotion == 1) {
            M5.Lcd.drawLine(94, 56, 107, 54, faceInk);
            M5.Lcd.drawLine(133, 54, 146, 56, faceInk);
        }
    }
    M5.Lcd.fillTriangle(115, 88, 125, 88, 120, 94, faceInk);
    M5.Lcd.drawLine(120, 94, 120, 98, faceInk);
    M5.Lcd.drawLine(120, 98, 113, 101, faceInk);
    M5.Lcd.drawLine(120, 98, 127, 101, faceInk);
    if (emotion == 0) M5.Lcd.drawFastHLine(115, 105, 10, faceInk);
    if (emotion == 3) {
        M5.Lcd.drawCircle(188, 65, 5, faceInk);
        M5.Lcd.drawCircle(188, 65, 10, faceInk);
    }
    M5.Lcd.setTextColor(faceInk, mint);
    M5.Lcd.setTextSize(2);
    M5.Lcd.setCursor(9, 8);
    M5.Lcd.print(names[emotion]);
    M5.Lcd.setTextSize(1);
    M5.Lcd.setCursor(9, 124);
    M5.Lcd.print(emotion == 3 ? "A record     B pages" : "A mood       B pages");
    Serial.printf("PAGE FACE emotion=%s\n", names[emotion]);
}

static bool startMic() {
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM);
    cfg.sample_rate = 16000;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_ALL_RIGHT;
    cfg.communication_format = I2S_COMM_FORMAT_I2S;
    cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
    cfg.dma_buf_count = 4;
    cfg.dma_buf_len = 256;
    if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK) return false;
    i2s_pin_config_t pins = {};
    pins.bck_io_num = I2S_PIN_NO_CHANGE;
    pins.ws_io_num = 0;
    pins.data_out_num = I2S_PIN_NO_CHANGE;
    pins.data_in_num = 34;
    if (i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK ||
        i2s_set_clk(I2S_NUM_0, 16000, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO) != ESP_OK) {
        i2s_driver_uninstall(I2S_NUM_0);
        return false;
    }
    i2s_zero_dma_buffer(I2S_NUM_0);
    micReady = true;
    digitalWrite(10, LOW); // The red LED stays on whenever the microphone is active.
    return true;
}

static void stopMic() {
    if (micReady) i2s_driver_uninstall(I2S_NUM_0);
    micReady = false;
    digitalWrite(10, HIGH);
}

static void micPage() {
    header("Mic level");
    M5.Lcd.setCursor(12, 43);
    M5.Lcd.print(micReady ? "Speak near the mic" : "MIC ERROR");
    M5.Lcd.drawRoundRect(13, 64, 214, 32, 5, WHITE);
    M5.Lcd.setCursor(12, 104);
    M5.Lcd.print("Live meter; not uploaded");
    Serial.printf("PAGE MIC ready=%d\n", micReady);
}

static void statusPage() {
    header("Board status");
    M5.Lcd.setTextSize(1);
    M5.Lcd.setCursor(10, 39);
    M5.Lcd.printf("Battery: %.2f V", M5.Axp.GetBatVoltage());
    M5.Lcd.setCursor(10, 55);
    M5.Lcd.printf("Wi-Fi: %s  Config: %s", WiFi.status() == WL_CONNECTED ? "on" : "off",
                  (!ssid.isEmpty() && !gatewayURL.isEmpty() && !gatewayToken.isEmpty()) ? "yes" : "no");
    M5.Lcd.setCursor(10, 71);
    M5.Lcd.printf("Transport: %s", usbTransport ? "USB bridge" : "Wi-Fi");
    M5.Lcd.setCursor(10, 87);
    M5.Lcd.printf("BLE PIN: %06lu", (unsigned long)blePin);
    M5.Lcd.setCursor(10, 103);
    M5.Lcd.print(lastResult.substring(0, 28));
    Serial.printf("PAGE STATUS battery=%.2fV\n", M5.Axp.GetBatVoltage());
}

static void enterPage(Page next) {
    stopMic();
    page = next;
    if (page == MIC) micReady = startMic();
    if (page == FACE) face();
    else if (page == MIC) micPage();
    else statusPage();
    lastPaint = millis();
}

static void put16(uint8_t *p, uint16_t value) {
    p[0] = value & 255;
    p[1] = (value >> 8) & 255;
}

static void put32(uint8_t *p, uint32_t value) {
    for (int i = 0; i < 4; ++i) p[i] = (value >> (8 * i)) & 255;
}

static void wavHeader(uint8_t *header) {
    memcpy(header, "RIFF", 4); put32(header + 4, PCM_SIZE + 36);
    memcpy(header + 8, "WAVEfmt ", 8); put32(header + 16, 16);
    put16(header + 20, 1); put16(header + 22, 1);
    put32(header + 24, SAMPLE_RATE); put32(header + 28, SAMPLE_RATE * 2);
    put16(header + 32, 2); put16(header + 34, 16);
    memcpy(header + 36, "data", 4); put32(header + 40, PCM_SIZE);
}

static bool parseGateway(String &host, uint16_t &port) {
    if (!gatewayURL.startsWith("http://") || gatewayURL.indexOf('\r') >= 0 ||
        gatewayURL.indexOf('\n') >= 0 || gatewayToken.indexOf('\r') >= 0 ||
        gatewayToken.indexOf('\n') >= 0) return false;
    String authority = gatewayURL.substring(7);
    int slash = authority.indexOf('/');
    if (slash >= 0) authority = authority.substring(0, slash);
    int colon = authority.lastIndexOf(':');
    if (colon < 0) { host = authority; port = 80; }
    else {
        host = authority.substring(0, colon);
        long parsed = authority.substring(colon + 1).toInt();
        if (parsed < 1 || parsed > 65535) return false;
        port = static_cast<uint16_t>(parsed);
    }
    return !host.isEmpty() && host.indexOf(' ') < 0;
}

static bool connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return true;
    resultScreen("Wi-Fi", "Connecting...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());
    const uint32_t started = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) delay(100);
    return WiFi.status() == WL_CONNECTED;
}

static bool writeAll(WiFiClient &client, const uint8_t *data, size_t size) {
    size_t written = 0;
    const uint32_t started = millis();
    while (written < size && client.connected() && millis() - started < 4000) {
        size_t n = client.write(data + written, size - written);
        if (n) written += n;
        else delay(5);
    }
    if (written != size) {
        Serial.printf("TCP_WRITE failed wanted=%u written=%u connected=%d wifi=%d elapsed=%lu\n",
                      (unsigned)size, (unsigned)written, client.connected(),
                      WiFi.status(), (unsigned long)(millis() - started));
    }
    return written == size;
}

static void recordAndUpload() {
    if (recording) return;
    recording = true;
    String host; uint16_t port = 0;
    if (ssid.isEmpty() || gatewayToken.isEmpty() || !parseGateway(host, port)) {
        resultScreen("Config needed", "Set Wi-Fi, URL and token via BLE");
        recording = false;
        return;
    }
    if (!connectWiFi()) {
        resultScreen("Wi-Fi failed", "Check network in setup");
        recording = false;
        return;
    }
    WiFiClient client;
    client.setTimeout(12000);
    if (!client.connect(host.c_str(), port)) {
        resultScreen("Server failed", "Check gateway URL and server");
        recording = false;
        return;
    }
    String request = "POST /v1/utterances HTTP/1.0\r\nHost: " + host +
        "\r\nAuthorization: Bearer " + gatewayToken +
        "\r\nX-Device-ID: " + deviceID +
        "\r\nContent-Type: audio/wav\r\nContent-Length: " + String(PCM_SIZE + 44) +
        "\r\nConnection: close\r\n\r\n";
    uint8_t header[44]; wavHeader(header);
    if (!writeAll(client, reinterpret_cast<const uint8_t *>(request.c_str()), request.length()) ||
        !writeAll(client, header, sizeof(header))) {
        client.stop();
        resultScreen("Upload failed", "Connection ended before audio");
        recording = false;
        return;
    }
    if (!startMic()) {
        client.stop();
        resultScreen("Mic failed", "Restart the device");
        recording = false;
        return;
    }
    resultScreen("Recording", "A: stop  |  max 6 seconds");
    uint8_t pcm[1024];
    int sent = 0;
    bool stopRequested = false;
    bool uploadOK = true;
    const uint32_t started = millis();
    while (sent < PCM_SIZE) {
        M5.update();
        if (millis() - started > 300 && M5.BtnA.wasPressed()) stopRequested = true;
        if (millis() - started >= RECORD_SECONDS * 1000UL) stopRequested = true;
        size_t wanted = min(sizeof(pcm), static_cast<size_t>(PCM_SIZE - sent));
        size_t count = 0;
        if (stopRequested) {
            stopMic();
            memset(pcm, 0, wanted);
            count = wanted;
        } else {
            esp_err_t readResult = i2s_read(I2S_NUM_0, pcm, wanted, &count, pdMS_TO_TICKS(200));
            if (readResult != ESP_OK || count == 0) {
                Serial.printf("MIC_READ failed result=%d count=%u sent=%d\n",
                              readResult, (unsigned)count, sent);
                uploadOK = false;
                break;
            }
        }
        if (!writeAll(client, pcm, count)) { uploadOK = false; break; }
        sent += count;
    }
    stopMic();
    if (uploadOK && sent == PCM_SIZE) {
        String response = client.readStringUntil('\n');
        response.trim();
        uploadOK = response.indexOf(" 202 ") >= 0;
        resultScreen(uploadOK ? "Delivered" : "Server error", response);
    } else {
        resultScreen("Upload failed", String(sent) + " / " + String(PCM_SIZE) + " bytes");
    }
    client.stop();
    recording = false;
    delay(1200);
    face();
}

// IMA ADPCM halves each 16-bit sample to four bits so six seconds of audio can
// stream over the board's reliable 115200 baud USB serial connection in real time.
static const int16_t ADPCM_STEPS[89] = {
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,
    80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,
    449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,
    1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,
    6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,
    20350,22385,24623,27086,29794,32767
};
static const int8_t ADPCM_INDEX[16] = {-1,-1,-1,-1,2,4,6,8,-1,-1,-1,-1,2,4,6,8};

struct AdpcmState { int predictor = 0; int index = 0; };

static uint8_t encodeAdpcm(int16_t sample, AdpcmState &state) {
    int step = ADPCM_STEPS[state.index];
    int difference = static_cast<int>(sample) - state.predictor;
    uint8_t code = 0;
    if (difference < 0) { code = 8; difference = -difference; }
    int adjustment = step >> 3;
    if (difference >= step) { code |= 4; difference -= step; adjustment += step; }
    if (difference >= (step >> 1)) { code |= 2; difference -= step >> 1; adjustment += step >> 1; }
    if (difference >= (step >> 2)) { code |= 1; adjustment += step >> 2; }
    state.predictor += (code & 8) ? -adjustment : adjustment;
    state.predictor = constrain(state.predictor, -32768, 32767);
    state.index = constrain(state.index + ADPCM_INDEX[code], 0, 88);
    return code;
}

static void recordAndStreamUSB() {
    if (recording) return;
    recording = true;
    if (!startMic()) {
        resultScreen("Mic failed", "Restart the device");
        recording = false;
        return;
    }
    resultScreen("Recording USB", "A: stop  |  max 6 seconds");
    Serial.printf("USB_AUDIO_BEGIN 1 %d %d %s\n", USB_AUDIO_BYTES,
                  SAMPLE_RATE, deviceID.c_str());
    AdpcmState state;
    uint32_t sumA = 1, sumB = 0;
    uint32_t captured = 0;
    bool stopped = false;
    bool captureOK = true;
    const uint32_t started = millis();
    int16_t samples[256];
    uint8_t encoded[128];
    for (int block = 0; block < USB_AUDIO_BYTES / 128; ++block) {
        M5.update();
        if (millis() - started > 300 && M5.BtnA.wasPressed()) stopped = true;
        if (millis() - started >= RECORD_SECONDS * 1000UL) stopped = true;
        if (!stopped && captureOK) {
            size_t count = 0;
            esp_err_t err = i2s_read(I2S_NUM_0, samples, sizeof(samples), &count,
                                     pdMS_TO_TICKS(200));
            if (err != ESP_OK || count == 0) captureOK = false;
            else {
                captured += count / sizeof(int16_t);
                if (count < sizeof(samples))
                    memset(reinterpret_cast<uint8_t *>(samples) + count, 0,
                           sizeof(samples) - count);
            }
        }
        if (stopped || !captureOK) {
            stopMic();
            memset(samples, 0, sizeof(samples));
        }
        for (int i = 0; i < 128; ++i) {
            encoded[i] = (encodeAdpcm(samples[2 * i], state) << 4) |
                          encodeAdpcm(samples[2 * i + 1], state);
            sumA = (sumA + encoded[i]) % 65521;
            sumB = (sumB + sumA) % 65521;
        }
        size_t written = 0;
        while (written < sizeof(encoded)) {
            size_t n = Serial.write(encoded + written, sizeof(encoded) - written);
            if (n == 0) delay(1);
            written += n;
        }
    }
    stopMic();
    Serial.printf("\nUSB_AUDIO_END %08lx %lu %d\n",
                  (unsigned long)((sumB << 16) | sumA),
                  (unsigned long)captured, captureOK ? 1 : 0);
    Serial.flush();
    resultScreen(captureOK ? "USB sent" : "Mic failed", "Waiting for software");
    recording = false;
    delay(900);
    face();
}

static void recordSelected() {
    if (usbTransport) recordAndStreamUSB();
    else recordAndUpload();
}

class ConfigWrite : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *characteristic) override {
        String value = String(characteristic->getValue().c_str());
        String id = characteristic->getUUID().toString().c_str();
        if (id.equalsIgnoreCase(SSID_UUID)) { ssid = value; prefs.putString("ssid", ssid); WiFi.disconnect(); }
        else if (id.equalsIgnoreCase(PASS_UUID)) { password = value; prefs.putString("pass", password); WiFi.disconnect(); }
        else if (id.equalsIgnoreCase(URL_UUID)) { gatewayURL = value; prefs.putString("url", gatewayURL); }
        else if (id.equalsIgnoreCase(TOKEN_UUID)) { gatewayToken = value; prefs.putString("token", gatewayToken); }
        else if (id.equalsIgnoreCase(CONTROL_UUID) && value == "start") startRequested = true;
        configChanged = true;
    }
};

class ConnectionEvents : public BLEServerCallbacks {
    void onDisconnect(BLEServer *) override { BLEDevice::startAdvertising(); }
};

static void setupBLE() {
    BLEDevice::init("M5StickC Voice");
    BLEDevice::setMTU(247);
    auto *security = new BLESecurity();
    security->setAuthenticationMode(ESP_LE_AUTH_REQ_SC_MITM_BOND);
    security->setCapability(ESP_IO_CAP_OUT);
    blePin = 100000 + (esp_random() % 900000);
    security->setStaticPIN(blePin);
    auto *server = BLEDevice::createServer();
    server->setCallbacks(new ConnectionEvents());
    auto *service = server->createService(SERVICE_UUID);
    auto *callback = new ConfigWrite();
    const char *configUUIDs[] = {SSID_UUID, PASS_UUID, URL_UUID, TOKEN_UUID, CONTROL_UUID};
    for (const char *uuid : configUUIDs) {
        auto *c = service->createCharacteristic(uuid, BLECharacteristic::PROPERTY_WRITE);
        c->setAccessPermissions(ESP_GATT_PERM_WRITE_ENC_MITM);
        c->setCallbacks(callback);
    }
    statusCharacteristic = service->createCharacteristic(STATUS_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
    statusCharacteristic->addDescriptor(new BLE2902());
    statusCharacteristic->setValue("Ready");
    auto *id = service->createCharacteristic(ID_UUID, BLECharacteristic::PROPERTY_READ);
    id->setValue(deviceID.c_str());
    service->start();
    auto *advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(SERVICE_UUID);
    advertising->start();
}

static void handleSerialConfig(const String &line) {
    if (line == "status") {
        Serial.printf("CONFIG ssid=%d url=%d token=%d wifi=%d ip=%s\n",
                      !ssid.isEmpty(), !gatewayURL.isEmpty(), !gatewayToken.isEmpty(),
                      WiFi.status() == WL_CONNECTED, WiFi.localIP().toString().c_str());
        return;
    }
    if (line == "connect") {
        bool connected = !ssid.isEmpty() && connectWiFi();
        report(connected ? "Wi-Fi connected" : "Wi-Fi failed",
               connected ? WiFi.localIP().toString() : "Check SSID/password");
        face();
        return;
    }
    if (line == "scan") {
        WiFi.mode(WIFI_STA);
        int networks = WiFi.scanNetworks(false, true);
        bool found = false;
        int strength = 0;
        int security = -1;
        for (int i = 0; i < networks; ++i) {
            if (WiFi.SSID(i) == ssid) {
                found = true;
                strength = WiFi.RSSI(i);
                security = static_cast<int>(WiFi.encryptionType(i));
                break;
            }
        }
        Serial.printf("SCAN target_found=%d rssi=%d security=%d networks=%d\n",
                      found, strength, security, networks);
        WiFi.scanDelete();
        return;
    }
    int equal = line.indexOf('=');
    if (equal <= 0) { report("Config command error"); return; }
    String key = line.substring(0, equal);
    String value = line.substring(equal + 1);
    if (key == "transport" && (value == "usb" || value == "wifi")) {
        usbTransport = value == "usb";
        enterPage(FACE);
        emotion = 3;
        face();
        Serial.printf("CONFIG transport=%s\n", value.c_str());
        return;
    }
    if (key == "bridge" && (value == "delivered" || value == "failed")) {
        resultScreen(value == "delivered" ? "Delivered" : "Bridge failed",
                     value == "delivered" ? "Software accepted audio" : "Check Mac bridge");
        delay(1200);
        face();
        return;
    }
    if (key == "ssid" && value.length() <= 32) {
        ssid = value; prefs.putString("ssid", ssid); WiFi.disconnect();
    } else if (key == "pass" && value.length() <= 64) {
        password = value; prefs.putString("pass", password); WiFi.disconnect();
    } else if (key == "url" && value.length() <= 150) {
        gatewayURL = value; prefs.putString("url", gatewayURL);
    } else if (key == "token" && value.length() <= 128) {
        gatewayToken = value; prefs.putString("token", gatewayToken);
    } else { report("Config command error"); return; }
    configChanged = true;
    Serial.printf("CONFIG saved %s\n", key.c_str());
}

static char readSerialCommand() {
    char command = 0;
    while (Serial.available()) {
        char c = Serial.read();
        if (!serialConfigActive) {
            if (c == '@') { serialConfigActive = true; serialConfigLine = ""; }
            else if (c == 'a' || c == 'n') command = c;
        } else if (c == '\n') {
            serialConfigLine.trim();
            handleSerialConfig(serialConfigLine);
            serialConfigActive = false;
            serialConfigLine = "";
        } else if (c != '\r') {
            if (serialConfigLine.length() < 256) serialConfigLine += c;
            else { serialConfigActive = false; serialConfigLine = ""; report("Config too long"); }
        }
    }
    return command;
}

void setup() {
    Serial.begin(115200);
    M5.begin();
    M5.Lcd.setRotation(1);
    // M5StickCPlus 0.1.1 initializes LEDC at 0 Hz, which Arduino-ESP32 2.0.16 rejects.
    ledcSetup(0, 1000, 13);
    ledcAttachPin(2, 0);
    M5.Beep.setVolume(2);
    pinMode(10, OUTPUT);
    digitalWrite(10, HIGH);
    prefs.begin("voice", false);
    ssid = prefs.getString("ssid", "");
    password = prefs.getString("pass", "");
    gatewayURL = prefs.getString("url", "");
    gatewayToken = prefs.getString("token", "");
    char id[28];
    snprintf(id, sizeof(id), "stickc-%012llx", (unsigned long long)ESP.getEfuseMac());
    deviceID = id;
    setupBLE();
    Serial.println("M5StickC Plus Listening firmware v0.2");
    enterPage(FACE);
    M5.Beep.tone(1200, 70);
}

void loop() {
    M5.update();
    if (configChanged) {
        configChanged = false;
        report("Configured");
        if (page == PAGE_STATUS) statusPage();
    }
    // Serial n/a are diagnostic mirrors of the two hardware buttons.
    char command = readSerialCommand();
    if (M5.BtnB.wasPressed() || command == 'n') {
        M5.Beep.tone(900, 55);
        enterPage(static_cast<Page>((page + 1) % 3));
    }
    if (M5.BtnA.wasPressed() || command == 'a' || startRequested) {
        bool remoteStart = startRequested;
        startRequested = false;
        if (page == FACE) {
            if (emotion == 3 || remoteStart) {
                emotion = 3;
                recordSelected();
            } else {
                emotion = (emotion + 1) % 4;
                face();
                M5.Beep.tone(1300, 65);
            }
        } else if (page == PAGE_STATUS) {
            if (remoteStart) { enterPage(FACE); emotion = 3; recordSelected(); }
            else { M5.Beep.tone(1500, 140); statusPage(); }
        } else if (remoteStart) {
            enterPage(FACE);
            emotion = 3;
            recordSelected();
        }
    }
    if (page == MIC && micReady) {
        int16_t samples[256];
        size_t count = 0;
        if (i2s_read(I2S_NUM_0, samples, sizeof(samples), &count, pdMS_TO_TICKS(20)) == ESP_OK && count) {
            const size_t sampleCount = count / 2;
            int32_t sum = 0;
            for (size_t i = 0; i < sampleCount; ++i) sum += samples[i];
            const int32_t mean = sum / static_cast<int32_t>(sampleCount);
            uint32_t deviation = 0;
            for (size_t i = 0; i < sampleCount; ++i) deviation += abs((int32_t)samples[i] - mean);
            uint32_t level = deviation / sampleCount;
            uint32_t bars = min((uint32_t)208, level / 4);
            M5.Lcd.fillRect(16, 67, 208, 26, BG);
            if (bars) M5.Lcd.fillRect(16, 67, bars, 26, bars > 145 ? ORANGE : GREEN);
            if (millis() - lastPaint > 500) {
                Serial.printf("MIC level=%lu\n", (unsigned long)level);
                lastPaint = millis();
            }
        }
    }
    if (page == PAGE_STATUS && millis() - lastPaint > 5000) {
        statusPage();
        lastPaint = millis();
    }
    delay(15);
}
