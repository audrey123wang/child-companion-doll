import SwiftUI
import CoreBluetooth
import AVFoundation

@MainActor private enum VoiceUUID {
    static let service = CBUUID(string: "8e7b7000-6e59-4a44-9c31-7bb932760001")
    static let ssid = CBUUID(string: "8e7b7001-6e59-4a44-9c31-7bb932760001")
    static let password = CBUUID(string: "8e7b7002-6e59-4a44-9c31-7bb932760001")
    static let gateway = CBUUID(string: "8e7b7003-6e59-4a44-9c31-7bb932760001")
    static let token = CBUUID(string: "8e7b7004-6e59-4a44-9c31-7bb932760001")
    static let control = CBUUID(string: "8e7b7005-6e59-4a44-9c31-7bb932760001")
    static let status = CBUUID(string: "8e7b7006-6e59-4a44-9c31-7bb932760001")
    static let id = CBUUID(string: "8e7b7007-6e59-4a44-9c31-7bb932760001")
}

@MainActor final class VoiceModel: NSObject, ObservableObject, @preconcurrency CBCentralManagerDelegate, @preconcurrency CBPeripheralDelegate {
    @Published var state = "等待蓝牙启动"
    @Published var found: [CBPeripheral] = []
    @Published var connectedName = "未连接"
    @Published var deviceID = ""
    @Published var ssid = ""
    @Published var password = ""
    @Published var gateway = "http://192.168.1.2:8765"
    @Published var token = ""
    @Published var transcript = ""
    @Published var answer = ""

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var characteristics: [CBUUID: CBCharacteristic] = [:]
    private var pendingWrites: [(CBUUID, Data)] = []
    private var timer: Timer?
    private var lastPlayed = ""
    private var player: AVAudioPlayer?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { scan() }
        else { state = "蓝牙不可用：\(central.state.rawValue)" }
    }

    func scan() {
        guard central.state == .poweredOn else { return }
        found.removeAll()
        state = "扫描 M5StickC Voice"
        central.scanForPeripherals(withServices: [VoiceUUID.service])
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        if !found.contains(where: { $0.identifier == peripheral.identifier }) { found.append(peripheral) }
    }

    func connect(_ device: CBPeripheral) {
        central.stopScan()
        peripheral = device
        state = "正在连接"
        central.connect(device)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        connectedName = peripheral.name ?? "M5StickC Voice"
        state = "正在读取蓝牙服务"
        peripheral.delegate = self
        peripheral.discoverServices([VoiceUUID.service])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        state = "连接失败：\(error?.localizedDescription ?? "未知错误")"
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        connectedName = "未连接"
        characteristics.removeAll()
        state = "设备已断开"
        scan()
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error { state = error.localizedDescription; return }
        for service in peripheral.services ?? [] where service.uuid == VoiceUUID.service {
            peripheral.discoverCharacteristics(nil, for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error { state = error.localizedDescription; return }
        for characteristic in service.characteristics ?? [] {
            characteristics[characteristic.uuid] = characteristic
        }
        if let id = characteristics[VoiceUUID.id] { peripheral.readValue(for: id) }
        if let status = characteristics[VoiceUUID.status] {
            peripheral.setNotifyValue(true, for: status)
            peripheral.readValue(for: status)
        }
        state = "已连接。配置 Wi-Fi 后可按设备正面按钮收音。"
        startPolling()
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, let data = characteristic.value,
              let text = String(data: data, encoding: .utf8) else { return }
        if characteristic.uuid == VoiceUUID.id { deviceID = text }
        if characteristic.uuid == VoiceUUID.status { state = text }
    }

    func configure() {
        guard !ssid.isEmpty, !gateway.isEmpty, !token.isEmpty else {
            state = "填写 Wi-Fi、网关地址和访问令牌"
            return
        }
        pendingWrites = [
            (VoiceUUID.ssid, Data(ssid.utf8)),
            (VoiceUUID.password, Data(password.utf8)),
            (VoiceUUID.gateway, Data(gateway.utf8)),
            (VoiceUUID.token, Data(token.utf8)),
        ]
        writeNext()
    }

    func startRecording() {
        pendingWrites = [(VoiceUUID.control, Data("start".utf8))]
        writeNext()
    }

    private func writeNext() {
        guard let peripheral, !pendingWrites.isEmpty else { return }
        let (uuid, data) = pendingWrites.removeFirst()
        guard let characteristic = characteristics[uuid] else {
            state = "缺少控制特征值"
            pendingWrites.removeAll()
            return
        }
        if data.count > peripheral.maximumWriteValueLength(for: .withResponse) {
            state = "配置内容超过蓝牙单次写入限制"
            pendingWrites.removeAll()
            return
        }
        peripheral.writeValue(data, for: characteristic, type: .withResponse)
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error {
            state = "蓝牙写入失败：\(error.localizedDescription)"
            pendingWrites.removeAll()
        } else { writeNext() }
    }

    private func startPolling() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.poll() }
        }
    }

    private func request(_ path: String) -> URLRequest? {
        guard let url = URL(string: gateway + path), !token.isEmpty else { return nil }
        var request = URLRequest(url: url)
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 10
        return request
    }

    private func poll() async {
        guard !deviceID.isEmpty,
              let escaped = deviceID.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let request = request("/v1/jobs?device=" + escaped) else { return }
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let jobs = root["jobs"] as? [[String: Any]],
                  let latest = jobs.first,
                  let jobID = latest["id"] as? String else { return }
            if let error = latest["error"] as? String { state = "云端处理失败：" + error }
            guard latest["status"] as? String == "done", jobID != lastPlayed else { return }
            transcript = latest["transcript"] as? String ?? ""
            answer = latest["answer"] as? String ?? ""
            lastPlayed = jobID
            await play(jobID)
        } catch {
            // Bluetooth status remains available when the gateway is offline.
        }
    }

    private func play(_ jobID: String) async {
        guard let request = request("/v1/audio/" + jobID) else { return }
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            #if os(iOS)
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
            try AVAudioSession.sharedInstance().setActive(true)
            #endif
            player = try AVAudioPlayer(data: data)
            player?.prepareToPlay()
            player?.play()
            state = "正在播放回答"
        } catch { state = "播放失败：\(error.localizedDescription)" }
    }
}

struct ContentView: View {
    @StateObject private var model = VoiceModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 15) {
                Text("M5StickC Voice").font(.title.bold())
                Text(model.state).font(.caption)
                HStack {
                    Text("设备：" + model.connectedName)
                    Spacer()
                    Button("扫描") { model.scan() }
                }
                ForEach(model.found, id: \.identifier) { device in
                    Button(device.name ?? device.identifier.uuidString) { model.connect(device) }
                }
                TextField("Wi-Fi 名称", text: $model.ssid)
                SecureField("Wi-Fi 密码", text: $model.password)
                TextField("网关地址，例如 http://192.168.1.2:8765", text: $model.gateway)
                    .textInputAutocapitalizationIfAvailable()
                SecureField("网关访问令牌", text: $model.token)
                HStack {
                    Button("写入设备配置") { model.configure() }
                    Button("开始录音") { model.startRecording() }
                }
                Text("设备 ID：" + model.deviceID).font(.caption)
                Divider()
                Text("识别：" + model.transcript)
                Text("回答：" + model.answer)
                Text("播放的是 AI 生成的语音").font(.caption)
            }
            .padding()
        }
        .frame(minWidth: 360, minHeight: 440)
    }
}

private extension View {
    @ViewBuilder func textInputAutocapitalizationIfAvailable() -> some View {
        #if os(iOS)
        self.textInputAutocapitalization(.never).keyboardType(.URL)
        #else
        self
        #endif
    }
}

@main struct VoiceCompanionApp: App {
    var body: some Scene { WindowGroup { ContentView() } }
}
