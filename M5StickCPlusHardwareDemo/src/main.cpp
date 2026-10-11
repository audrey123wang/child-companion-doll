#include <Arduino.h>
#include <M5StickCPlus.h>
#include <driver/i2s.h>

// Local-only hardware tour. Audio is reduced to a level in RAM; no recording or radio.
enum Page : uint8_t { FACE, MIC, PAGE_STATUS };
static Page page = FACE;
static uint8_t emotion = 0;
static bool micReady = false;
static uint32_t lastPaint = 0;
static constexpr uint16_t BG = 0x10A2;
static constexpr uint16_t INK = 0x18E3;

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
    M5.Lcd.print("A mood       B pages");
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
    return true;
}

static void micPage() {
    header("Mic level");
    M5.Lcd.setCursor(12, 43);
    M5.Lcd.print(micReady ? "Speak near the mic" : "MIC ERROR");
    M5.Lcd.drawRoundRect(13, 64, 214, 32, 5, WHITE);
    M5.Lcd.setCursor(12, 104);
    M5.Lcd.print("RAM meter; nothing saved/sent");
    Serial.printf("PAGE MIC ready=%d\n", micReady);
}

static void statusPage() {
    header("Board status");
    M5.Lcd.setTextSize(1);
    M5.Lcd.setCursor(10, 39);
    M5.Lcd.printf("Battery: %.2f V", M5.Axp.GetBatVoltage());
    M5.Lcd.setCursor(10, 55);
    M5.Lcd.print("Wi-Fi/BLE: OFF in demo");
    M5.Lcd.setCursor(10, 71);
    M5.Lcd.print("Flash: 4 MB  Display: 135x240");
    M5.Lcd.setCursor(10, 87);
    M5.Lcd.print("Audio: passive buzzer");
    M5.Lcd.setCursor(10, 103);
    M5.Lcd.print("A: play short tone");
    Serial.printf("PAGE STATUS battery=%.2fV\n", M5.Axp.GetBatVoltage());
}

static void enterPage(Page next) {
    if (micReady) {
        i2s_driver_uninstall(I2S_NUM_0);
        micReady = false;
    }
    page = next;
    if (page == MIC) micReady = startMic();
    if (page == FACE) face();
    else if (page == MIC) micPage();
    else statusPage();
    lastPaint = millis();
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
    digitalWrite(10, HIGH); // Red LED off; this is not a recording indicator.
    Serial.println("M5StickC Plus hardware demo v0.1; no Wi-Fi, BLE or audio upload");
    enterPage(FACE);
    M5.Beep.tone(1200, 70);
}

void loop() {
    M5.update();
    // Serial n/a are diagnostic mirrors of the two hardware buttons.
    char command = Serial.available() ? Serial.read() : 0;
    if (M5.BtnB.wasPressed() || command == 'n') {
        M5.Beep.tone(900, 55);
        enterPage(static_cast<Page>((page + 1) % 3));
    }
    if (M5.BtnA.wasPressed() || command == 'a') {
        if (page == FACE) {
            emotion = (emotion + 1) % 4;
            face();
            M5.Beep.tone(1300, 65);
        } else if (page == PAGE_STATUS) {
            M5.Beep.tone(1500, 140);
            statusPage();
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
