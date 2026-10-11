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

// Custom GATT service. The companion app uses these same UUIDs.
static const char *SERVICE_UUID = "8e7b7000-6e59-4a44-9c31-7bb932760001";
static const char *SSID_UUID    = "8e7b7001-6e59-4a44-9c31-7bb932760001";
static const char *PASS_UUID    = "8e7b7002-6e59-4a44-9c31-7bb932760001";
static const char *URL_UUID     = "8e7b7003-6e59-4a44-9c31-7bb932760001";
static const char *TOKEN_UUID   = "8e7b7004-6e59-4a44-9c31-7bb932760001";
static const char *CONTROL_UUID = "8e7b7005-6e59-4a44-9c31-7bb932760001";
static const char *STATUS_UUID  = "8e7b7006-6e59-4a44-9c31-7bb932760001";
static const char *ID_UUID      = "8e7b7007-6e59-4a44-9c31-7bb932760001";

static constexpr int SAMPLE_RATE = 16000;
static constexpr int RECORD_SECONDS = 5;
static constexpr int PCM_SIZE = SAMPLE_RATE * RECORD_SECONDS * 2;
static Preferences prefs;
static BLECharacteristic *statusCharacteristic = nullptr;
static String ssid, password, gatewayURL, gatewayToken, deviceID;
static volatile bool startRequested = false;
static bool recording = false;

static void show(const String &title, const String &detail = "") {
    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.setTextColor(WHITE, BLACK);
    M5.Lcd.setTextSize(2);
    M5.Lcd.setCursor(5, 10);
    M5.Lcd.println(title);
    M5.Lcd.setTextSize(1);
    M5.Lcd.setCursor(5, 55);
    M5.Lcd.println(detail);
    Serial.printf("%s: %s\n", title.c_str(), detail.c_str());
    if (statusCharacteristic) {
        String message = title + ":" + detail;
        statusCharacteristic->setValue(message.c_str());
        statusCharacteristic->notify();
    }
}

static void put32(uint8_t *p, uint32_t v) {
    p[0] = v & 255; p[1] = (v >> 8) & 255;
    p[2] = (v >> 16) & 255; p[3] = (v >> 24) & 255;
}

static void put16(uint8_t *p, uint16_t v) {
    p[0] = v & 255; p[1] = (v >> 8) & 255;
}

static void wavHeader(uint8_t *h) {
    memcpy(h, "RIFF", 4); put32(h + 4, PCM_SIZE + 36);
    memcpy(h + 8, "WAVEfmt ", 8); put32(h + 16, 16);
    put16(h + 20, 1); put16(h + 22, 1); put32(h + 24, SAMPLE_RATE);
    put32(h + 28, SAMPLE_RATE * 2); put16(h + 32, 2); put16(h + 34, 16);
    memcpy(h + 36, "data", 4); put32(h + 40, PCM_SIZE);
}

static bool parseGateway(String &host, uint16_t &port) {
    if (!gatewayURL.startsWith("http://")) return false;
    String address = gatewayURL.substring(7);
    int slash = address.indexOf('/');
    if (slash >= 0) address = address.substring(0, slash);
    int colon = address.lastIndexOf(':');
    if (colon < 0) { host = address; port = 80; }
    else { host = address.substring(0, colon); port = address.substring(colon + 1).toInt(); }
    return host.length() > 0 && port > 0;
}

static bool connectWiFi() {
    if (ssid.isEmpty()) return false;
    if (WiFi.status() == WL_CONNECTED) return true;
    show("Wi-Fi", "Connecting...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());
    unsigned long deadline = millis() + 15000;
    while (WiFi.status() != WL_CONNECTED && millis() < deadline) delay(150);
    if (WiFi.status() != WL_CONNECTED) return false;
    show("Wi-Fi OK", WiFi.localIP().toString());
    return true;
}

static bool microphoneStart() {
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM);
    cfg.sample_rate = SAMPLE_RATE;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_ALL_RIGHT;
    cfg.communication_format = I2S_COMM_FORMAT_I2S;
    cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
    cfg.dma_buf_count = 8;
    cfg.dma_buf_len = 256;
    cfg.use_apll = false;
    if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK) return false;
    i2s_pin_config_t pins = {};
    pins.bck_io_num = I2S_PIN_NO_CHANGE;
    pins.ws_io_num = 0; // SPM1423 clock
    pins.data_out_num = I2S_PIN_NO_CHANGE;
    pins.data_in_num = 34; // SPM1423 data
    if (i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK) {
        i2s_driver_uninstall(I2S_NUM_0); return false;
    }
    if (i2s_set_clk(I2S_NUM_0, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO) != ESP_OK) {
        i2s_driver_uninstall(I2S_NUM_0); return false;
    }
    i2s_zero_dma_buffer(I2S_NUM_0);
    return true;
}

static void recordAndUpload() {
    if (recording) return;
    recording = true;
    String host; uint16_t port = 0;
    if (!parseGateway(host, port) || gatewayToken.isEmpty() || !connectWiFi()) {
        show("Config error", "Set Wi-Fi, URL, token");
        recording = false; return;
    }
    WiFiClient client;
    client.setTimeout(12000);
    if (!client.connect(host.c_str(), port)) {
        show("Server error", host); recording = false; return;
    }
    if (!microphoneStart()) {
        show("Mic error"); client.stop(); recording = false; return;
    }
    client.print("POST /v1/utterances HTTP/1.0\r\nHost: " + host + "\r\n");
    client.print("Authorization: Bearer " + gatewayToken + "\r\n");
    client.print("X-Device-ID: " + deviceID + "\r\nContent-Type: audio/wav\r\n");
    client.print("Content-Length: " + String(PCM_SIZE + 44) + "\r\nConnection: close\r\n\r\n");
    uint8_t header[44]; wavHeader(header);
    client.write(header, sizeof(header));
    show("Recording", "Speak for 5 seconds");
    uint8_t pcm[1024];
    int sent = 0;
    while (sent < PCM_SIZE && client.connected()) {
        size_t count = 0;
        size_t wanted = min((int)sizeof(pcm), PCM_SIZE - sent);
        if (i2s_read(I2S_NUM_0, pcm, wanted, &count, pdMS_TO_TICKS(1000)) != ESP_OK || count == 0) break;
        size_t written = client.write(pcm, count);
        sent += written;
        if (written != count) break;
    }
    i2s_driver_uninstall(I2S_NUM_0);
    if (sent != PCM_SIZE) {
        show("Upload error", String(sent) + " bytes");
    } else {
        String first = client.readStringUntil('\n');
        first.trim();
        show(first.indexOf(" 202 ") >= 0 ? "Uploaded" : "Server error", first);
    }
    client.stop();
    recording = false;
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
        show("BLE updated", id.substring(8, 12));
    }
};

class ConnectionEvents : public BLEServerCallbacks {
    void onDisconnect(BLEServer *) override {
        BLEDevice::startAdvertising();
    }
};

static void setupBLE() {
    BLEDevice::init("M5StickC Voice");
    BLEDevice::setMTU(247);
    auto *security = new BLESecurity();
    security->setAuthenticationMode(ESP_LE_AUTH_REQ_SC_MITM_BOND);
    security->setCapability(ESP_IO_CAP_OUT);
    uint32_t pin = 100000 + (esp_random() % 900000);
    security->setStaticPIN(pin);
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
    statusCharacteristic->setValue("booting");
    auto *id = service->createCharacteristic(ID_UUID, BLECharacteristic::PROPERTY_READ);
    id->setValue(deviceID.c_str());
    service->start();
    auto *advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(SERVICE_UUID);
    advertising->start();
    show("BLE PIN", String(pin));
}

void setup() {
    Serial.begin(115200);
    M5.begin();
    M5.Lcd.setRotation(1);
    prefs.begin("voice", false);
    ssid = prefs.getString("ssid", "");
    password = prefs.getString("pass", "");
    gatewayURL = prefs.getString("url", "");
    gatewayToken = prefs.getString("token", "");
    char id[28];
    snprintf(id, sizeof(id), "stickc-%012llx", (unsigned long long)ESP.getEfuseMac());
    deviceID = id;
    setupBLE();
}

void loop() {
    M5.update();
    if (M5.BtnA.wasPressed() || startRequested) {
        startRequested = false;
        recordAndUpload();
    }
    delay(25);
}
