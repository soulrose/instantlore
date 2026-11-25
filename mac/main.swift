// GameSubTH — แปลซับเกมเป็นภาษาไทย (หรือภาษาอื่น) แบบ realtime บน macOS
// ผู้พัฒนา: Soulrose
// อ่านจอ (ScreenCaptureKit) → OCR (Vision) → แปล (Apple Translation ออฟไลน์ / Google ออนไลน์) → แสดงซับลอยทับเกม

import Cocoa
import Carbon.HIToolbox
import ScreenCaptureKit
import Vision
import Translation

// MARK: - App info / languages

let appName = "InstantLore"
let appVersion = "1.4.0"
let developer = "Soulrose"

/// code = รหัส Google, vision = ภาษาสำหรับ OCR ([] = ตรวจอัตโนมัติ), apple = รหัส Apple Translation (nil = ใช้ไม่ได้)
struct Lang {
    let code: String; let en: String; let th: String; let vision: [String]; let apple: String?
    var name: String { L(en, th, zh: langNamesZH[code], ja: langNamesJA[code]) }
}

/// ข้อความในโปรแกรม: เริ่มต้นตามภาษาของเครื่อง (ไม่ใช่ภาษาที่มีให้ = อังกฤษ) เปลี่ยนได้ในเมนู
/// จีน/ญี่ปุ่น: ส่ง zh:/ja: มาเอง หรือหาจากตาราง ZH / JA ด้วยข้อความภาษาอังกฤษ
func L(_ en: String, _ th: String, zh: String? = nil, ja: String? = nil) -> String {
    switch Settings.uiLang {
    case "th": return th
    case "zh": return zh ?? ZH[en] ?? en
    case "ja": return ja ?? JA[en] ?? en
    default: return en
    }
}

let uiLangs: [(String, String)] = [("en", "English"), ("th", "ไทย"), ("zh", "中文"), ("ja", "日本語")]

func systemUILang() -> String {
    let code = String((Locale.preferredLanguages.first ?? "en").prefix(2))
    return uiLangs.contains { $0.0 == code } ? code : "en"
}

let ZH: [String: String] = [
    "About InstantLore": "关于 InstantLore",
    "Allow Screen Recording, then reopen the app": "请允许“屏幕录制”，然后重新打开应用",
    "Apple (offline, private)": "Apple（离线，不上传数据）",
    "Background box": "背景框",
    "Couldn't find the screen to capture": "找不到要截取的屏幕",
    "Edit capture area": "编辑字幕读取区域",
    "Edit subtitle position": "编辑译文位置",
    "Fast": "快",
    "Game language": "游戏语言",
    "Google (online) will be used instead.": "将改用 Google（在线）。",
    "Google (online)": "Google（在线）",
    "Interface language": "界面语言",
    "Larger text": "放大文字",
    "Light": "省电",
    "Normal": "标准",
    "OK": "好",
    "Open Settings": "打开设置",
    "Original subtitle appears here": "原文将显示在这里",
    "Quit": "退出",
    "Screen reading": "屏幕读取",
    "Show original text": "显示原文",
    "Show subtitles": "显示译文",
    "Smaller text": "缩小文字",
    "Start translating": "开始翻译",
    "Stop translating": "停止翻译",
    "Stopped": "已停止",
    "Text size": "字号",
    "The capture area is not on any screen": "字幕读取区域不在任何屏幕上",
    "Translate to": "翻译为",
    "Translated subtitle appears here": "译文将显示在这里",
    "Translator": "翻译引擎",
    "Unexpected reply from Google": "Google 返回了异常结果",
    "Use Google for now": "暂时使用 Google",
    "① Capture area: drag over the game's subtitles · ⌃⌥R when done": "① 字幕读取区域：拖动框住游戏字幕 · 完成后按 ⌃⌥R",
    "② Subtitle position: drag to move, corner to resize · ⌃⌥M when done": "② 译文位置：拖动移动，拖动角落调整大小 · 完成后按 ⌃⌥M",
    "● Translating": "● 翻译中"
]

let JA: [String: String] = [
    "About InstantLore": "InstantLore について",
    "Allow Screen Recording, then reopen the app": "画面収録を許可してから、アプリを開き直してください",
    "Apple (offline, private)": "Apple（オフライン・データ送信なし）",
    "Background box": "背景ボックス",
    "Couldn't find the screen to capture": "キャプチャする画面が見つかりません",
    "Edit capture area": "読み取りエリアを編集",
    "Edit subtitle position": "翻訳の表示位置を編集",
    "Fast": "高速",
    "Game language": "ゲームの言語",
    "Google (online) will be used instead.": "代わりに Google（オンライン）を使います。",
    "Google (online)": "Google（オンライン）",
    "Interface language": "表示言語",
    "Larger text": "文字を大きく",
    "Light": "省電力",
    "Normal": "標準",
    "OK": "OK",
    "Open Settings": "設定を開く",
    "Original subtitle appears here": "ここに原文が表示されます",
    "Quit": "終了",
    "Screen reading": "画面の読み取り",
    "Show original text": "原文を表示",
    "Show subtitles": "翻訳を表示",
    "Smaller text": "文字を小さく",
    "Start translating": "翻訳を開始",
    "Stop translating": "翻訳を停止",
    "Stopped": "停止中",
    "Text size": "文字サイズ",
    "The capture area is not on any screen": "読み取りエリアがどの画面にもありません",
    "Translate to": "翻訳先",
    "Translated subtitle appears here": "ここに翻訳が表示されます",
    "Translator": "翻訳エンジン",
    "Unexpected reply from Google": "Google から予期しない応答がありました",
    "Use Google for now": "今は Google を使う",
    "① Capture area: drag over the game's subtitles · ⌃⌥R when done": "① 読み取りエリア：ゲームの字幕に重ねてドラッグ · 完了したら ⌃⌥R",
    "② Subtitle position: drag to move, corner to resize · ⌃⌥M when done": "② 翻訳の表示位置：ドラッグで移動、角でサイズ変更 · 完了したら ⌃⌥M",
    "● Translating": "● 翻訳中"
]

let langNamesZH: [String: String] = [
    "auto": "自动检测", "en": "英语", "ja": "日语", "zh-CN": "中文（简体）", "zh-TW": "中文（繁体）", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "it": "意大利语", "pt": "葡萄牙语", "ru": "俄语", "th": "泰语",
    "vi": "越南语", "id": "印尼语", "ms": "马来语", "lo": "老挝语", "my": "缅甸语", "km": "高棉语",
]
let langNamesJA: [String: String] = [
    "auto": "自動検出", "en": "英語", "ja": "日本語", "zh-CN": "中国語（簡体字）", "zh-TW": "中国語（繁体字）",
    "ko": "韓国語", "fr": "フランス語", "de": "ドイツ語", "es": "スペイン語", "it": "イタリア語", "pt": "ポルトガル語",
    "ru": "ロシア語", "th": "タイ語", "vi": "ベトナム語", "id": "インドネシア語", "ms": "マレー語", "lo": "ラオ語",
    "my": "ビルマ語", "km": "クメール語",
]

let sourceLangs: [Lang] = [
    Lang(code: "auto", en: "Auto detect", th: "อัตโนมัติ", vision: [], apple: nil),
    Lang(code: "en", en: "English", th: "อังกฤษ", vision: ["en-US"], apple: "en"),
    Lang(code: "ja", en: "Japanese", th: "ญี่ปุ่น", vision: ["ja-JP"], apple: "ja"),
    Lang(code: "zh-CN", en: "Chinese (Simplified)", th: "จีน (ตัวย่อ)", vision: ["zh-Hans"], apple: "zh-Hans"),
    Lang(code: "zh-TW", en: "Chinese (Traditional)", th: "จีน (ตัวเต็ม)", vision: ["zh-Hant"], apple: "zh-Hant"),
    Lang(code: "ko", en: "Korean", th: "เกาหลี", vision: ["ko-KR"], apple: "ko"),
    Lang(code: "fr", en: "French", th: "ฝรั่งเศส", vision: ["fr-FR"], apple: "fr"),
    Lang(code: "de", en: "German", th: "เยอรมัน", vision: ["de-DE"], apple: "de"),
    Lang(code: "es", en: "Spanish", th: "สเปน", vision: ["es-ES"], apple: "es"),
    Lang(code: "it", en: "Italian", th: "อิตาลี", vision: ["it-IT"], apple: "it"),
    Lang(code: "pt", en: "Portuguese", th: "โปรตุเกส", vision: ["pt-BR"], apple: "pt-BR"),
    Lang(code: "ru", en: "Russian", th: "รัสเซีย", vision: ["ru-RU"], apple: "ru"),
    Lang(code: "th", en: "Thai", th: "ไทย", vision: ["th-TH"], apple: "th"),
]
let targetLangs: [Lang] = [
    Lang(code: "th", en: "Thai", th: "ไทย", vision: [], apple: "th"),
    Lang(code: "en", en: "English", th: "อังกฤษ", vision: [], apple: "en"),
    Lang(code: "ja", en: "Japanese", th: "ญี่ปุ่น", vision: [], apple: "ja"),
    Lang(code: "zh-CN", en: "Chinese (Simplified)", th: "จีน (ตัวย่อ)", vision: [], apple: "zh-Hans"),
    Lang(code: "ko", en: "Korean", th: "เกาหลี", vision: [], apple: "ko"),
    Lang(code: "vi", en: "Vietnamese", th: "เวียดนาม", vision: [], apple: "vi"),
    Lang(code: "id", en: "Indonesian", th: "อินโดนีเซีย", vision: [], apple: "id"),
    Lang(code: "ms", en: "Malay", th: "มลายู", vision: [], apple: nil),
    Lang(code: "lo", en: "Lao", th: "ลาว", vision: [], apple: nil),
    Lang(code: "my", en: "Burmese", th: "พม่า", vision: [], apple: nil),
    Lang(code: "km", en: "Khmer", th: "เขมร", vision: [], apple: nil),
    Lang(code: "fr", en: "French", th: "ฝรั่งเศส", vision: [], apple: "fr"),
    Lang(code: "es", en: "Spanish", th: "สเปน", vision: [], apple: "es"),
]
let cjk: Set<String> = ["ja", "zh-CN", "zh-TW"]

// MARK: - Settings

enum Engine: String { case apple, google }

enum Settings {
    static let d = UserDefaults.standard

    static func rect(_ key: String) -> NSRect? {
        guard let s = d.string(forKey: key) else { return nil }
        let r = NSRectFromString(s)
        return r.width > 10 && r.height > 10 ? r : nil
    }
    static func setRect(_ r: NSRect, _ key: String) { d.set(NSStringFromRect(r), forKey: key) }

    static var engine: Engine {
        get { Engine(rawValue: d.string(forKey: "engine") ?? "") ?? .apple }
        set { d.set(newValue.rawValue, forKey: "engine") }
    }
    static var fontSize: CGFloat {
        get { let v = d.double(forKey: "fontSize"); return v > 0 ? v : 30 }
        set { d.set(Double(newValue), forKey: "fontSize") }
    }
    static var showEnglish: Bool {
        get { d.object(forKey: "showEnglish") as? Bool ?? true }
        set { d.set(newValue, forKey: "showEnglish") }
    }
    static var showBox: Bool {
        get { d.object(forKey: "showBox") as? Bool ?? true }
        set { d.set(newValue, forKey: "showBox") }
    }
    static var uiLang: String {
        get { d.string(forKey: "uiLang") ?? systemUILang() }
        set { d.set(newValue, forKey: "uiLang") }
    }
    static var srcLang: String {
        get { d.string(forKey: "srcLang") ?? "en" }
        set { d.set(newValue, forKey: "srcLang") }
    }
    static var dstLang: String {
        get { d.string(forKey: "dstLang") ?? "th" }
        set { d.set(newValue, forKey: "dstLang") }
    }
    static var src: Lang { sourceLangs.first { $0.code == srcLang } ?? sourceLangs[1] }
    static var dst: Lang { targetLangs.first { $0.code == dstLang } ?? targetLangs[0] }
    static var interval: Double {
        get { let v = d.double(forKey: "interval"); return v > 0 ? v : 0.5 }
        set { d.set(newValue, forKey: "interval") }
    }
}

// MARK: - Overlay windows

final class OverlayPanel: NSPanel {
    init(frame: NSRect) {
        super.init(contentRect: frame, styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .screenSaver
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        isReleasedWhenClosed = false
        hidesOnDeactivate = false
    }
    override var canBecomeKey: Bool { true }
}

/// กล่องที่ลากย้ายได้ และลากมุมขวาล่างเพื่อปรับขนาด (เมื่ออยู่ในโหมดแก้ไข)
class BoxView: NSView {
    var editing = false { didSet { needsDisplay = true } }
    var color: NSColor = .systemYellow
    var title = ""
    var onChanged: (() -> Void)?

    private let handle: CGFloat = 22
    private var dragStart = NSPoint.zero
    private var startFrame = NSRect.zero
    private var resizing = false

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        guard editing else { return }
        color.withAlphaComponent(0.15).setFill()
        bounds.fill()
        let p = NSBezierPath(rect: bounds.insetBy(dx: 1.5, dy: 1.5))
        p.lineWidth = 3
        p.setLineDash([10, 5], count: 2, phase: 0)
        color.setStroke()
        p.stroke()
        color.setFill()
        NSBezierPath(rect: NSRect(x: bounds.maxX - handle, y: 0, width: handle, height: handle)).fill()
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.boldSystemFont(ofSize: 13),
            .foregroundColor: NSColor.black,
            .backgroundColor: color,
        ]
        (" " + title + " " as NSString).draw(at: NSPoint(x: 6, y: bounds.maxY - 22), withAttributes: attrs)
    }

    override func mouseDown(with e: NSEvent) {
        guard editing, let w = window else { return }
        let p = convert(e.locationInWindow, from: nil)
        resizing = p.x > bounds.maxX - handle && p.y < handle
        dragStart = NSEvent.mouseLocation
        startFrame = w.frame
    }

    override func mouseDragged(with e: NSEvent) {
        guard editing, let w = window else { return }
        let m = NSEvent.mouseLocation
        let dx = m.x - dragStart.x, dy = m.y - dragStart.y
        var f = startFrame
        if resizing {
            f.size.width = max(120, startFrame.width + dx)
            let h = max(40, startFrame.height - dy)
            f.origin.y = startFrame.maxY - h
            f.size.height = h
        } else {
            f.origin.x += dx
            f.origin.y += dy
        }
        w.setFrame(f, display: true)
    }

    override func mouseUp(with e: NSEvent) { if editing { onChanged?() } }
}

final class SubtitleView: BoxView {
    var en = ""
    var th = ""
    var fontSize: CGFloat = 30
    var showEnglish = true
    var showBox = true

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        var thai = th
        var eng = en
        if thai.isEmpty {
            guard editing else { return }
            thai = L("Translated subtitle appears here", "ซับแปลจะแสดงตรงนี้")
            eng = L("Original subtitle appears here", "ข้อความต้นฉบับจะแสดงตรงนี้")
        }

        let para = NSMutableParagraphStyle()
        para.alignment = .center
        para.lineBreakMode = .byWordWrapping
        let shadow = NSShadow()
        shadow.shadowColor = .black
        shadow.shadowBlurRadius = 3
        shadow.shadowOffset = NSSize(width: 1, height: -1)

        // ไม่มีกล่อง → ใส่ขอบดำรอบตัวอักษรแทน (strokeWidth ติดลบ = ทั้งเติมสีและวาดขอบ)
        let outline: [NSAttributedString.Key: Any] = showBox ? [:] : [.strokeColor: NSColor.black, .strokeWidth: -4.0]
        let text = NSMutableAttributedString()
        if showEnglish && !eng.isEmpty {
            text.append(NSAttributedString(string: eng + "\n", attributes: [
                .font: NSFont.systemFont(ofSize: max(12, fontSize * 0.55)),
                .foregroundColor: NSColor(white: 0.85, alpha: 1),
                .paragraphStyle: para, .shadow: shadow,
            ].merging(outline) { $1 }))
        }
        text.append(NSAttributedString(string: thai, attributes: [
            .font: NSFont.systemFont(ofSize: fontSize, weight: .semibold),
            .foregroundColor: NSColor.white,
            .paragraphStyle: para, .shadow: shadow,
        ].merging(outline) { $1 }))

        let padX: CGFloat = 20, padY: CGFloat = 10
        let maxW = bounds.width - padX * 2
        let size = text.boundingRect(with: NSSize(width: maxW, height: 10_000),
                                     options: [.usesLineFragmentOrigin, .usesFontLeading]).size
        let bw = min(bounds.width, ceil(size.width) + padX * 2)
        let bh = min(bounds.height, ceil(size.height) + padY * 2)
        let bg = NSRect(x: (bounds.width - bw) / 2, y: 0, width: bw, height: bh) // ชิดล่าง ข้อความยาวจะดันขึ้นข้างบน
        if showBox {
            NSColor(white: 0, alpha: 0.62).setFill()
            NSBezierPath(roundedRect: bg, xRadius: 10, yRadius: 10).fill()
        }
        text.draw(with: bg.insetBy(dx: padX, dy: padY), options: [.usesLineFragmentOrigin, .usesFontLeading])
    }
}

// MARK: - Screen capture

enum CaptureError: LocalizedError {
    case noScreen, noDisplay
    var errorDescription: String? {
        switch self {
        case .noScreen: return L("The capture area is not on any screen", "กล่องอ่านซับไม่อยู่บนจอใดเลย")
        case .noDisplay: return L("Couldn't find the screen to capture", "หาจอสำหรับจับภาพไม่เจอ")
        }
    }
}

final class Capturer {
    private var filter: SCContentFilter?
    private var displayID: CGDirectDisplayID = 0
    private var refreshed = Date.distantPast

    func capture(_ rect: NSRect) async throws -> CGImage {
        let mid = NSPoint(x: rect.midX, y: rect.midY)
        guard let screen = NSScreen.screens.first(where: { $0.frame.contains(mid) }) else { throw CaptureError.noScreen }
        let id = (screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value ?? 0

        if filter == nil || id != displayID || Date().timeIntervalSince(refreshed) > 10 {
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            guard let display = content.displays.first(where: { $0.displayID == id }) else { throw CaptureError.noDisplay }
            // ไม่จับหน้าต่างของโปรแกรมเราเอง → ซับไทยวางทับซับอังกฤษได้ แต่ OCR ยังเห็นภาษาอังกฤษข้างใต้
            let me = content.applications.filter { $0.processID == ProcessInfo.processInfo.processIdentifier }
            filter = SCContentFilter(display: display, excludingApplications: me, exceptingWindows: [])
            displayID = id
            refreshed = Date()
        }

        let local = rect.intersection(screen.frame)
        let cfg = SCStreamConfiguration()
        cfg.sourceRect = CGRect(x: local.minX - screen.frame.minX,
                                y: screen.frame.maxY - local.maxY,
                                width: local.width, height: local.height)
        let scale = screen.backingScaleFactor
        cfg.width = Int(local.width * scale)
        cfg.height = Int(local.height * scale)
        cfg.showsCursor = false
        return try await SCScreenshotManager.captureImage(contentFilter: filter!, configuration: cfg)
    }
}

// MARK: - OCR

enum OCR {
    static func recognize(_ image: CGImage, _ lang: Lang) throws -> String {
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        if lang.vision.isEmpty {
            req.automaticallyDetectsLanguage = true
        } else {
            req.recognitionLanguages = lang.vision
        }
        req.usesLanguageCorrection = true
        try VNImageRequestHandler(cgImage: image).perform([req])
        let lines: [(CGRect, String)] = (req.results ?? []).compactMap { o in
            guard let c = o.topCandidates(1).first, c.confidence > 0.35 else { return nil }
            return (o.boundingBox, c.string)
        }
        // บนลงล่าง ซ้ายไปขวา (Vision ใช้ y จากล่างขึ้นบน)
        let sorted = lines.sorted {
            abs($0.0.midY - $1.0.midY) > 0.03 ? $0.0.midY > $1.0.midY : $0.0.minX < $1.0.minX
        }
        return sorted.map(\.1).joined(separator: cjk.contains(lang.code) ? "" : " ")
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespaces)
    }
}

// MARK: - Translators

protocol Translator: AnyObject {
    func translate(_ text: String) async throws -> String
}

final class AppleTranslator: Translator {
    private let session: TranslationSession

    init(src: String, dst: String) {
        session = TranslationSession(installedSource: Locale.Language(identifier: src),
                                     target: Locale.Language(identifier: dst))
    }

    /// Apple แปลได้ไหม (ต้องรู้ภาษาต้นทาง และโหลดภาษาไว้ในเครื่องแล้ว)
    static func isInstalled(_ src: Lang, _ dst: Lang) async -> Bool {
        guard let s = src.apple, let t = dst.apple else { return false }
        return await LanguageAvailability().status(from: Locale.Language(identifier: s),
                                                   to: Locale.Language(identifier: t)) == .installed
    }

    func translate(_ text: String) async throws -> String {
        try await session.translate(text).targetText
    }
}

final class GoogleTranslator: Translator {
    struct BadResponse: LocalizedError { var errorDescription: String? { L("Unexpected reply from Google", "Google ตอบกลับผิดรูปแบบ") } }

    let sl: String, tl: String
    init(sl: String, tl: String) { self.sl = sl; self.tl = tl }

    func translate(_ text: String) async throws -> String {
        var c = URLComponents(string: "https://translate.googleapis.com/translate_a/single")!
        c.queryItems = [
            .init(name: "client", value: "gtx"), .init(name: "sl", value: sl),
            .init(name: "tl", value: tl), .init(name: "dt", value: "t"), .init(name: "q", value: text),
        ]
        var req = URLRequest(url: c.url!)
        req.timeoutInterval = 5
        let (data, _) = try await URLSession.shared.data(for: req)
        guard let arr = try JSONSerialization.jsonObject(with: data) as? [Any],
              let parts = arr.first as? [Any] else { throw BadResponse() }
        return parts.compactMap { ($0 as? [Any])?.first as? String }.joined()
    }
}

// MARK: - Text similarity (กัน OCR เพี้ยนนิดหน่อยแล้วแปลซ้ำ)

func normalized(_ s: String) -> String {
    String(s.lowercased().unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }.map(Character.init))
}

func similar(_ a: String, _ b: String) -> Bool {
    if a == b { return true }
    if a.isEmpty || b.isEmpty { return false }
    let x = Array(a), y = Array(b)
    if abs(x.count - y.count) > max(x.count, y.count) / 8 + 1 { return false }
    var prev = Array(0...y.count), cur = [Int](repeating: 0, count: y.count + 1)
    for i in 1...x.count {
        cur[0] = i
        for j in 1...y.count {
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x[i - 1] == y[j - 1] ? 0 : 1))
        }
        swap(&prev, &cur)
    }
    return Double(prev[y.count]) / Double(max(x.count, y.count)) < 0.1
}

// MARK: - Global hotkeys (Carbon: ไม่ต้องขอสิทธิ์ Accessibility)

enum HotKeys {
    static var handlers: [UInt32: () -> Void] = [:]
    static var refs: [EventHotKeyRef?] = []

    static func install() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
            var id = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID),
                              nil, MemoryLayout<EventHotKeyID>.size, nil, &id)
            DispatchQueue.main.async { HotKeys.handlers[id.id]?() }
            return noErr
        }, 1, &spec, nil, nil)
    }

    /// ทุกปุ่มลัดใช้ Control + Option + key
    static func register(_ keyCode: Int, _ handler: @escaping () -> Void) {
        let id = UInt32(handlers.count + 1)
        handlers[id] = handler
        var ref: EventHotKeyRef?
        RegisterEventHotKey(UInt32(keyCode), UInt32(controlKey | optionKey),
                            EventHotKeyID(signature: OSType(0x4753_5448), id: id),
                            GetApplicationEventTarget(), 0, &ref)
        refs.append(ref)
    }
}

// MARK: - App

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var statusLine: NSMenuItem!
    var runItem: NSMenuItem!
    var englishItem: NSMenuItem!
    var hideItem: NSMenuItem!
    var statusText = ""
    var boxItem: NSMenuItem!
    var engineItems: [Engine: NSMenuItem] = [:]
    var intervalItems: [Double: NSMenuItem] = [:]

    var regionWin: OverlayPanel!
    var regionView: BoxView!
    var subWin: OverlayPanel!
    var subView: SubtitleView!

    let capturer = Capturer()
    var translator: Translator = GoogleTranslator(sl: "en", tl: "th")
    var srcItems: [String: NSMenuItem] = [:]
    var dstItems: [String: NSMenuItem] = [:]
    var sizeItems: [Int: NSMenuItem] = [:]
    var cache: [String: String] = [:]

    var running = false
    var loopTask: Task<Void, Never>?
    var candidate = ""
    var shownKey = ""
    var emptySince: Date?
    var subHidden = false

    func applicationDidFinishLaunching(_ n: Notification) {
        NSApp.setActivationPolicy(.accessory)
        setupWindows()
        setupMenu()
        HotKeys.install()
        HotKeys.register(kVK_ANSI_T) { [weak self] in self?.toggleRun() }
        HotKeys.register(kVK_ANSI_R) { [weak self] in self?.toggleEditRegion() }
        HotKeys.register(kVK_ANSI_M) { [weak self] in self?.toggleEditSub() }
        HotKeys.register(kVK_ANSI_H) { [weak self] in self?.toggleHideSub() }
        HotKeys.register(kVK_ANSI_E) { [weak self] in self?.toggleEnglish() }
        HotKeys.register(kVK_ANSI_B) { [weak self] in self?.toggleBox() }
        HotKeys.register(kVK_ANSI_Equal) { [weak self] in self?.bigger() }
        HotKeys.register(kVK_ANSI_Minus) { [weak self] in self?.smaller() }

        if !CGPreflightScreenCaptureAccess() {
            CGRequestScreenCaptureAccess()
            setStatus(L("Allow Screen Recording, then reopen the app", "ต้องอนุญาต Screen Recording แล้วเปิดโปรแกรมใหม่"))
        }
        Task { await chooseEngine(Settings.engine) }
        // ครั้งแรก: เปิดให้วางกล่องเลย
        if Settings.rect("regionFrame") == nil { toggleEditRegion(); toggleEditSub() }
    }

    // MARK: windows

    func setupWindows() {
        let s = NSScreen.main!.visibleFrame
        let defRegion = NSRect(x: s.minX + s.width * 0.2, y: s.minY + s.height * 0.04,
                               width: s.width * 0.6, height: s.height * 0.14)
        let defSub = NSRect(x: s.minX + s.width * 0.15, y: s.minY + s.height * 0.2,
                            width: s.width * 0.7, height: s.height * 0.2)

        regionWin = OverlayPanel(frame: Settings.rect("regionFrame") ?? defRegion)
        regionView = BoxView()
        regionView.color = .systemYellow
        regionView.title = L("① Capture area: drag over the game's subtitles · ⌃⌥R when done", "① กล่องอ่านซับ: ลากครอบซับในเกม · กด ⌃⌥R เมื่อเสร็จ")
        regionView.onChanged = { [weak self] in self.map { Settings.setRect($0.regionWin.frame, "regionFrame") } }
        regionWin.contentView = regionView

        subWin = OverlayPanel(frame: Settings.rect("subFrame") ?? defSub)
        subView = SubtitleView()
        subView.color = .systemGreen
        subView.title = L("② Subtitle position: drag to move, corner to resize · ⌃⌥M when done", "② ตำแหน่งซับแปล: ลากเพื่อย้าย ลากมุมเพื่อปรับขนาด · กด ⌃⌥M เมื่อเสร็จ")
        subView.fontSize = Settings.fontSize
        subView.showEnglish = Settings.showEnglish
        subView.showBox = Settings.showBox
        subView.onChanged = { [weak self] in self.map { Settings.setRect($0.subWin.frame, "subFrame") } }
        subWin.contentView = subView
        subWin.ignoresMouseEvents = true
        subWin.orderFrontRegardless()
    }

    @objc func toggleEditRegion() {
        regionView.editing.toggle()
        if regionView.editing {
            regionWin.orderFrontRegardless()
        } else {
            Settings.setRect(regionWin.frame, "regionFrame")
            regionWin.orderOut(nil)
        }
    }

    @objc func toggleEditSub() {
        subView.editing.toggle()
        subWin.ignoresMouseEvents = !subView.editing
        if !subView.editing { Settings.setRect(subWin.frame, "subFrame") }
        subWin.orderFrontRegardless()
    }

    @objc func toggleHideSub() {
        subHidden.toggle()
        if subHidden { subWin.orderOut(nil) } else { subWin.orderFrontRegardless() }
        hideItem.state = subHidden ? .off : .on
    }

    @objc func toggleEnglish() {
        Settings.showEnglish.toggle()
        subView.showEnglish = Settings.showEnglish
        englishItem.state = Settings.showEnglish ? .on : .off
        subView.needsDisplay = true
    }

    @objc func toggleBox() {
        Settings.showBox.toggle()
        subView.showBox = Settings.showBox
        boxItem.state = Settings.showBox ? .on : .off
        subView.needsDisplay = true
    }

    @objc func bigger() { setFont(Settings.fontSize + 2) }
    @objc func smaller() { setFont(Settings.fontSize - 2) }
    func setFont(_ v: CGFloat) {
        Settings.fontSize = min(80, max(14, v))
        subView.fontSize = Settings.fontSize
        subView.needsDisplay = true
        refreshSizeChecks()
    }

    func showSub(en: String, th: String) {
        subView.en = en
        subView.th = th
        subView.needsDisplay = true
    }

    // MARK: menu

    /// สร้างเมนูใหม่ทั้งหมด (เรียกซ้ำตอนเปลี่ยนภาษาโปรแกรม)
    func setupMenu() {
        if statusItem == nil {
            statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
            statusItem.button?.image = NSImage(systemSymbolName: "captions.bubble", accessibilityDescription: appName)
        }
        srcItems = [:]; dstItems = [:]; sizeItems = [:]; intervalItems = [:]; engineItems = [:]
        let m = NSMenu()
        statusLine = NSMenuItem(title: statusText, action: nil, keyEquivalent: "")
        statusLine.isEnabled = false
        m.addItem(statusLine)
        m.addItem(.separator())
        runItem = add(m, running ? L("Stop translating", "หยุดแปล") : L("Start translating", "เริ่มแปล"), #selector(toggleRun), key: "⌃⌥T")
        add(m, L("Edit capture area", "แก้ไขกล่องอ่านซับ"), #selector(toggleEditRegion), key: "⌃⌥R")
        add(m, L("Edit subtitle position", "แก้ไขตำแหน่งซับแปล"), #selector(toggleEditSub), key: "⌃⌥M")
        hideItem = add(m, L("Show subtitles", "แสดงซับแปล"), #selector(toggleHideSub), key: "⌃⌥H")
        hideItem.state = subHidden ? .off : .on
        englishItem = add(m, L("Show original text", "แสดงข้อความต้นฉบับ"), #selector(toggleEnglish), key: "⌃⌥E")
        englishItem.state = Settings.showEnglish ? .on : .off
        boxItem = add(m, L("Background box", "กล่องพื้นหลัง"), #selector(toggleBox), key: "⌃⌥B")
        boxItem.state = Settings.showBox ? .on : .off
        add(m, L("Larger text", "ตัวอักษรใหญ่ขึ้น"), #selector(bigger), key: "⌃⌥=")
        add(m, L("Smaller text", "ตัวอักษรเล็กลง"), #selector(smaller), key: "⌃⌥-")
        let sizeMenu = NSMenu()
        for v in [16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72] {
            let it = add(sizeMenu, "\(v)", #selector(pickSize(_:)))
            it.representedObject = v
            sizeItems[v] = it
        }
        let sizeRoot = NSMenuItem(title: L("Text size", "ขนาดตัวอักษร"), action: nil, keyEquivalent: "")
        sizeRoot.submenu = sizeMenu
        m.addItem(sizeRoot)
        refreshSizeChecks()
        m.addItem(.separator())

        let srcMenu = NSMenu()
        for l in sourceLangs {
            let it = add(srcMenu, l.name, #selector(pickSrc(_:)))
            it.representedObject = l.code
            srcItems[l.code] = it
        }
        let srcRoot = NSMenuItem(title: L("Game language", "ภาษาของเกม"), action: nil, keyEquivalent: "")
        srcRoot.submenu = srcMenu
        m.addItem(srcRoot)
        let dstMenu = NSMenu()
        for l in targetLangs {
            let it = add(dstMenu, l.name, #selector(pickDst(_:)))
            it.representedObject = l.code
            dstItems[l.code] = it
        }
        let dstRoot = NSMenuItem(title: L("Translate to", "แปลเป็น"), action: nil, keyEquivalent: "")
        dstRoot.submenu = dstMenu
        m.addItem(dstRoot)
        refreshLangChecks()

        let engMenu = NSMenu()
        engineItems[.apple] = add(engMenu, L("Apple (offline, private)", "Apple (ออฟไลน์ ไม่ส่งข้อมูลออก)"), #selector(pickApple))
        engineItems[.google] = add(engMenu, L("Google (online)", "Google (ออนไลน์)"), #selector(pickGoogle))
        let engRoot = NSMenuItem(title: L("Translator", "ระบบแปล"), action: nil, keyEquivalent: "")
        engRoot.submenu = engMenu
        m.addItem(engRoot)
        engineItems.forEach { $0.value.state = $0.key == Settings.engine ? .on : .off }

        let intMenu = NSMenu()
        for (v, label) in [(0.3, L("Fast", "เร็ว")), (0.5, L("Normal", "ปกติ")), (1.0, L("Light", "ประหยัด"))] {
            let it = add(intMenu, label, #selector(pickInterval(_:)))
            it.representedObject = v
            it.state = Settings.interval == v ? .on : .off
            intervalItems[v] = it
        }
        let intRoot = NSMenuItem(title: L("Screen reading", "ความถี่อ่านจอ"), action: nil, keyEquivalent: "")
        intRoot.submenu = intMenu
        m.addItem(intRoot)

        let uiMenu = NSMenu()
        for (code, name) in uiLangs {
            let it = add(uiMenu, name, #selector(pickUILang(_:)))
            it.representedObject = code
            it.state = Settings.uiLang == code ? .on : .off
        }
        let uiRoot = NSMenuItem(title: L("Interface language", "ภาษาโปรแกรม"), action: nil, keyEquivalent: "")
        uiRoot.submenu = uiMenu
        m.addItem(uiRoot)

        m.addItem(.separator())
        add(m, L("Check for Updates…", "ตรวจหาเวอร์ชันใหม่…", zh: "检查更新…", ja: "アップデートを確認…"), #selector(checkUpdate))
        add(m, L("About \(appName)", "เกี่ยวกับ \(appName)"), #selector(about))
        add(m, L("Quit", "ออก"), #selector(quit), key: "")
        statusItem.menu = m
    }

    /// key = ปุ่มลัด แสดงชิดขวาเป็นสีจาง
    @discardableResult
    func add(_ m: NSMenu, _ title: String, _ sel: Selector, key: String = "") -> NSMenuItem {
        let it = NSMenuItem(title: title, action: sel, keyEquivalent: "")
        it.target = self
        if !key.isEmpty {
            let para = NSMutableParagraphStyle()
            para.tabStops = [NSTextTab(textAlignment: .right, location: 250)]
            let t = NSMutableAttributedString(string: title, attributes: [.font: NSFont.menuFont(ofSize: 0), .paragraphStyle: para])
            t.append(NSAttributedString(string: "\t" + key, attributes: [
                .font: NSFont.menuFont(ofSize: 0), .foregroundColor: NSColor.tertiaryLabelColor, .paragraphStyle: para]))
            it.attributedTitle = t
        }
        m.addItem(it)
        return it
    }

    func setStatus(_ s: String) {
        statusText = s
        statusLine?.title = s
    }

    func idleStatus() -> String {
        "\(L("Stopped", "หยุดอยู่")) · \(Settings.src.name) → \(Settings.dst.name) · \(Settings.engine == .apple ? "Apple" : "Google")"
    }

    @objc func pickUILang(_ sender: NSMenuItem) {
        Settings.uiLang = sender.representedObject as? String ?? "en"
        regionView.title = L("① Capture area: drag over the game's subtitles · ⌃⌥R when done", "① กล่องอ่านซับ: ลากครอบซับในเกม · กด ⌃⌥R เมื่อเสร็จ")
        subView.title = L("② Subtitle position: drag to move, corner to resize · ⌃⌥M when done", "② ตำแหน่งซับแปล: ลากเพื่อย้าย ลากมุมเพื่อปรับขนาด · กด ⌃⌥M เมื่อเสร็จ")
        regionView.needsDisplay = true
        subView.needsDisplay = true
        setStatus(running ? L("● Translating", "● กำลังแปล") : idleStatus())
        setupMenu()
    }

    @objc func pickApple() { Task { await chooseEngine(.apple) } }
    @objc func pickGoogle() { Task { await chooseEngine(.google) } }
    @objc func pickInterval(_ sender: NSMenuItem) {
        Settings.interval = sender.representedObject as? Double ?? 0.5
        intervalItems.forEach { $0.value.state = $0.key == Settings.interval ? .on : .off }
    }
    @objc func quit() { NSApp.terminate(nil) }

    /// ถามเวอร์ชันล่าสุดจากหน้า Releases บน GitHub ถ้าใหม่กว่าให้เปิดหน้าดาวน์โหลด
    @objc func checkUpdate() {
        Task { @MainActor in
            var req = URLRequest(url: URL(string: "https://api.github.com/repos/soulrose/instantlore/releases/latest")!)
            req.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
            req.timeoutInterval = 8
            let a = NSAlert()
            do {
                let (data, _) = try await URLSession.shared.data(for: req)
                guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let tag = obj["tag_name"] as? String, let page = obj["html_url"] as? String,
                      let url = URL(string: page) else { throw URLError(.badServerResponse) }
                let latest = tag.hasPrefix("v") ? String(tag.dropFirst()) : tag
                func parts(_ v: String) -> [Int] { (v.split(separator: ".").compactMap { Int($0) } + [0, 0, 0]).prefix(3).map { $0 } }
                if parts(latest).lexicographicallyPrecedes(parts(appVersion)) || parts(latest) == parts(appVersion) {
                    a.messageText = L("You have the latest version (\(appVersion))", "ใช้เวอร์ชันล่าสุดอยู่แล้ว (\(appVersion))",
                                      zh: "已是最新版本（\(appVersion)）", ja: "最新バージョンです（\(appVersion)）")
                    a.addButton(withTitle: L("OK", "ตกลง"))
                    NSApp.activate()
                    a.runModal()
                    return
                }
                a.messageText = L("Update available", "มีเวอร์ชันใหม่", zh: "有新版本", ja: "新しいバージョンがあります")
                a.informativeText = L("\(appName) \(latest) is available. You have \(appVersion).",
                                      "\(appName) \(latest) ออกแล้ว ตอนนี้ใช้ \(appVersion) อยู่",
                                      zh: "\(appName) \(latest) 已发布，当前版本为 \(appVersion)。",
                                      ja: "\(appName) \(latest) が公開されています。現在のバージョンは \(appVersion) です。")
                a.addButton(withTitle: L("Download", "ดาวน์โหลด", zh: "下载", ja: "ダウンロード"))
                a.addButton(withTitle: L("Later", "ไว้ทีหลัง", zh: "以后再说", ja: "後で"))
                NSApp.activate()
                if a.runModal() == .alertFirstButtonReturn { NSWorkspace.shared.open(url) }
            } catch {
                a.messageText = L("Couldn't check for updates", "ตรวจหาเวอร์ชันใหม่ไม่ได้", zh: "无法检查更新", ja: "アップデートを確認できません")
                a.informativeText = error.localizedDescription
                a.addButton(withTitle: L("OK", "ตกลง"))
                NSApp.activate()
                a.runModal()
            }
        }
    }

    @objc func about() {
        let a = NSAlert()
        a.messageText = "\(appName) \(appVersion)"
        a.informativeText = L("Developed by \(developer)\n\nText reading: Apple Vision, on this Mac\nTranslation: Apple Translation or Google Translate",
                              "ผู้พัฒนา: \(developer)\n\nอ่านตัวหนังสือ: Apple Vision ทำงานในเครื่อง\nแปล: Apple Translation หรือ Google Translate",
                              zh: "开发者：\(developer)\n\n文字识别：Apple Vision，在本机运行\n翻译：Apple 翻译或 Google 翻译",
                              ja: "開発者：\(developer)\n\n文字認識：Apple Vision（この Mac で動作）\n翻訳：Apple 翻訳または Google 翻訳")
        a.addButton(withTitle: L("OK", "ตกลง"))
        NSApp.activate()
        a.runModal()
    }

    @objc func pickSize(_ sender: NSMenuItem) {
        setFont(CGFloat(sender.representedObject as? Int ?? 30))
    }
    func refreshSizeChecks() {
        sizeItems.forEach { $0.value.state = $0.key == Int(Settings.fontSize) ? .on : .off }
    }

    @objc func pickSrc(_ sender: NSMenuItem) {
        Settings.srcLang = sender.representedObject as? String ?? "en"
        refreshLangChecks()
        Task { await chooseEngine(Settings.engine) }
    }
    @objc func pickDst(_ sender: NSMenuItem) {
        Settings.dstLang = sender.representedObject as? String ?? "th"
        refreshLangChecks()
        Task { await chooseEngine(Settings.engine) }
    }
    func refreshLangChecks() {
        srcItems.forEach { $0.value.state = $0.key == Settings.srcLang ? .on : .off }
        dstItems.forEach { $0.value.state = $0.key == Settings.dstLang ? .on : .off }
    }

    func chooseEngine(_ e: Engine) async {
        var e = e
        let src = Settings.src, dst = Settings.dst
        if e == .apple, !(await AppleTranslator.isInstalled(src, dst)) {
            let a = NSAlert()
            if src.apple == nil || dst.apple == nil {
                a.messageText = L("Apple can't translate \(src.name) → \(dst.name) offline", "Apple แปลคู่ภาษา \(src.name) → \(dst.name) แบบออฟไลน์ไม่ได้",
                                zh: "Apple 无法离线翻译 \(src.name) → \(dst.name)", ja: "Apple は \(src.name) → \(dst.name) をオフラインで翻訳できません")
                a.informativeText = L("Google (online) will be used instead.", "จะใช้ Google (ออนไลน์) แทน")
                a.addButton(withTitle: L("OK", "ตกลง"))
                NSApp.activate()
                a.runModal()
                e = .google
                return await finishEngine(e)
            }
            a.messageText = L("\(src.name) / \(dst.name) isn't downloaded for offline translation", "ยังไม่ได้ดาวน์โหลดภาษา \(src.name) / \(dst.name) สำหรับแปลออฟไลน์",
                              zh: "尚未下载 \(src.name) / \(dst.name) 离线翻译语言", ja: "\(src.name) / \(dst.name) のオフライン翻訳用言語がダウンロードされていません")
            a.informativeText = L("Open System Settings → General → Language & Region → Translation Languages… and download both languages.\n\nGoogle (online) will be used until then.",
                                  "ไปที่ System Settings → General → Language & Region → Translation Languages… แล้วดาวน์โหลดทั้งสองภาษา\n\nระหว่างนี้จะใช้ Google (ออนไลน์) ไปก่อน",
                                  zh: "请打开“系统设置 → 通用 → 语言与地区 → 翻译语言…”并下载这两种语言。\n\n在此之前将使用 Google（在线）。",
                                  ja: "システム設定 → 一般 → 言語と地域 → 翻訳言語… を開き、両方の言語をダウンロードしてください。\n\nそれまでは Google（オンライン）を使います。")
            a.addButton(withTitle: L("Open Settings", "เปิด Settings"))
            a.addButton(withTitle: L("Use Google for now", "ใช้ Google ไปก่อน"))
            NSApp.activate()
            if a.runModal() == .alertFirstButtonReturn,
               let url = URL(string: "x-apple.systempreferences:com.apple.Localization-Settings.extension") {
                NSWorkspace.shared.open(url)
            }
            e = .google
        }
        await finishEngine(e)
    }

    func finishEngine(_ e: Engine) async {
        let src = Settings.src, dst = Settings.dst
        translator = e == .apple
            ? AppleTranslator(src: src.apple ?? "en", dst: dst.apple ?? "th")
            : GoogleTranslator(sl: src.code, tl: dst.code)
        Settings.engine = e
        cache.removeAll()
        engineItems.forEach { $0.value.state = $0.key == e ? .on : .off }
        if !running { setStatus(idleStatus()) }
    }

    // MARK: main loop

    @objc func toggleRun() {
        running.toggle()
        runItem.title = running ? L("Stop translating", "หยุดแปล") : L("Start translating", "เริ่มแปล")
        if running {
            if regionView.editing { toggleEditRegion() }
            if subView.editing { toggleEditSub() }
            setStatus(L("● Translating", "● กำลังแปล"))
            candidate = ""; shownKey = ""; emptySince = nil
            loopTask = Task { [weak self] in await self?.loop() }
        } else {
            loopTask?.cancel()
            showSub(en: "", th: "")
            setStatus(idleStatus())
        }
    }

    func loop() async {
        while running && !Task.isCancelled {
            let start = Date()
            await tick()
            let wait = max(0.1, Settings.interval - Date().timeIntervalSince(start))
            try? await Task.sleep(nanoseconds: UInt64(wait * 1e9))
        }
    }

    func tick() async {
        do {
            let img = try await capturer.capture(regionWin.frame)
            let lang = Settings.src
            let text = try await Task.detached(priority: .userInitiated) { try OCR.recognize(img, lang) }.value
            let key = normalized(text)

            if key.count < (cjk.contains(Settings.srcLang) ? 1 : 3) {
                // ซับหายไปจากเกม → ซ่อนซับไทยหลัง 1.2 วิ
                if emptySince == nil { emptySince = Date() }
                if Date().timeIntervalSince(emptySince!) > 1.2, !shownKey.isEmpty {
                    shownKey = ""
                    showSub(en: "", th: "")
                }
                candidate = ""
                return
            }
            emptySince = nil
            if similar(key, shownKey) { return }
            // รอให้ข้อความนิ่ง 2 เฟรมก่อน (กันซับแบบพิมพ์ทีละตัว)
            if !similar(key, candidate) { candidate = key; return }

            shownKey = key
            let th: String
            if let c = cache[key] {
                th = c
            } else {
                th = try await translator.translate(text)
                cache[key] = th
                if cache.count > 500 { cache.removeAll() }
            }
            if shownKey == key { showSub(en: text, th: th) }
            setStatus(L("● Translating", "● กำลังแปล"))
        } catch {
            shownKey = ""
            setStatus("⚠️ \(error.localizedDescription)")
        }
    }
}

let app = NSApplication.shared
let delegate = MainActor.assumeIsolated { AppDelegate() }
app.delegate = delegate
app.run()
