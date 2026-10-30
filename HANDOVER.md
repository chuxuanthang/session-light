# HANDOVER — claude-light

Đèn USB báo trạng thái từng session Claude Code. Tài liệu này để Claude Code CLI (hoặc người khác) tiếp quản dự án mà không cần đọc lại lịch sử trò chuyện.

## 1. Mục tiêu
- Một thiết bị USB cắm vào máy, mỗi đèn RGB ứng với một session Claude Code.
- Màu: **xanh lá** = sẵn sàng (không có luồng chạy) · **cam** = đang chạy (đổi từ xanh dương, 30/10/2026) · **tắt** = chưa có session nào gắn · **đỏ nhấp nháy** = bị block, có câu hỏi/xin quyền cần người xử lý.
- Đóng gói thành plugin Claude Code: hooks tự bắn trạng thái, slash command để gán đèn thủ công, ngắt tự động khi session kết thúc.
- 8 đèn: dùng cả 8 bóng của thanh CJMCU-2812-8.

## 2. Phần cứng
| Thành phần | Chi tiết | Trạng thái |
|---|---|---|
| Board | RP2040-Zero (clone Waveshare), USB-C, LED WS2812 onboard ở GP16 | Đã có, chạy CircuitPython 10.3.1 |
| Thanh LED | CJMCU-2812-8 (8 × WS2812B 5050), pad đầu vào ghi `GND / IN / VCC / GND` | Đã hàn, dữ liệu ở GP29, sáng đủ 8 bóng (30/10/2026) |
| Đầu chuyển | USB-A đực → USB-C đực (30 × 12 × 7 mm) | Đã đặt |
| Ống co nhiệt | Trong suốt Φ20 mm | Đã đặt |
| Dây nối | Lõi đơn cáp mạng 24 AWG, 3 sợi ~15 mm | Có sẵn |

Sơ đồ nối dây (Zero úp dưới đầu IN của thanh, lùi 2 mm so với mép để tránh cấn đầu chuyển):
- Zero `5V` → thanh `VCC`
- Zero `GND` → thanh `GND`
- Zero `GP29` → thanh `IN` (có thể đổi chân GP khác, chỉnh `PIN` trong firmware)

Sự cố đã gặp: pad `VCC` ở đầu IN **đã bong mất**. Giải pháp: hàn 5V vào pad `VCC` ở đầu OUT (cùng đường điện), dây dài ~50 mm chạy dọc lưng thanh. Trước khi hàn xong, LED onboard được dùng tạm làm 1 slot; từ 30/10/2026 firmware lái thanh 8 bóng, LED onboard không dùng nữa.

Lưu ý kỹ thuật: Zero chạy logic 3.3 V lái WS2812 5 V; thường chạy ổn với dây ngắn, nếu nhấp nháy loạn thì cấp VCC của thanh từ `3V3` thay vì `5V`.

## 3. Phần mềm
```
claude-light/                   # marketplace "chuxuanthang-plugins", repo public github.com/chuxuanthang/session-light
├── .claude-plugin/marketplace.json   # liệt kê plugin session-light, source ./code
├── HANDOVER.md                 # file này
├── README.md                   # trang giới thiệu trên GitHub, chi tiết trỏ sang code/README.md
├── LICENSE                     # MIT
├── tests/light-edge-cases.py   # test các ca biên của light.py, không cần board: python3 tests/light-edge-cases.py
└── code/                       # plugin "session-light" (= ${CLAUDE_PLUGIN_ROOT})
    ├── firmware/code.py        # CircuitPython, chép vào ổ CIRCUITPY
    ├── .claude-plugin/plugin.json
    ├── hooks/hooks.json        # SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PermissionRequest, Notification, Stop, StopFailure, SessionEnd
    ├── scripts/light.py        # host script: hook | connect | disconnect | status | test | send
    ├── commands/usb-connect.md, usb-disconnect.md, usb-status.md
    └── README.md               # hướng dẫn cài & dùng
```
Thư viện cần trên board: `lib/neopixel.mpy` (đã chép). Trên máy: `pip install pyserial`. Hook và command gọi `python3`.

### Giao thức serial (host → board)
Mỗi dòng `<đèn>:<trạng thái>\n`. Trạng thái: `ready | busy | wait | off | #RRGGBB`. Đã thử màu trắng cho đèn chưa gắn session nhưng chói quá nên bỏ. `all:<state>` cho mọi đèn. `ping` → `pong`. Board trả `ok` / `err` (host không cần đọc). Dùng cổng serial console của CircuitPython (không có boot.py, 1 cổng COM). Board nhận diện qua VID `0x2E8A` hoặc mô tả chứa "CircuitPython".

### Firmware (`code.py`)
- Hằng số đầu file: `PIN = board.GP29`, `NUM_LEDS = 8`, `BRIGHTNESS = 0.25`. Chỉ dùng LED onboard: `board.GP16`, `1`.
- `COLORS` / `BLINK` ngay đầu file để đổi màu và nhấp nháy. `wait` nhấp nháy chu kỳ 0,5 s. `busy` là cam `(255, 90, 0)`: `(255, 60, 0)` trên thanh LED trông gần như đỏ, nhiều xanh lá hơn nữa thì ngả vàng.
- Vòng lặp đọc `sys.stdin` không chặn qua `supervisor.runtime.serial_bytes_available`.

### Host (`scripts/light.py`)
- Trạng thái lưu ở `~/.claude-light/`: `config.json` (`port`, `num_leds`, `auto_assign`, `debug`), `map.json` (`session_id → {led, cwd}`), `pending.json` (`cwd → led`), `muted.json` (cwd và session_id đã disconnect), `lock`, `log.txt` khi `debug: true`.
- Mọi lần đọc-ghi map/pending/muted đều nằm trong `locked()` (`fcntl.flock` trên file `lock`), nên nhiều session mở cùng lúc không ghi đè map của nhau. Windows không có `fcntl` nên chạy không khóa.
- Mỗi hook cập nhật `cwd` của session trong map, nên session `cd` sang thư mục khác thì slash command vẫn tìm thấy.
- Ánh xạ sự kiện → trạng thái: `SessionStart`→ready, `UserPromptSubmit`/`PreToolUse`/`PostToolUse`→busy, `PermissionRequest`→wait, `PreToolUse` của `AskUserQuestion`→wait, `Notification`→wait chỉ khi `notification_type` là `permission_prompt`/`elicitation_dialog` (bỏ `idle_prompt`), `Stop`/`StopFailure`→ready, `SessionEnd`→off + bỏ gán (bỏ qua nếu session chưa gán đèn). `SessionEnd` có `reason: clear` thì ghi đèn vào `pending` theo cwd, để session mới do `/clear` tạo ra (session_id mới) nhận lại đúng đèn đó.
- Gán đèn qua hook: ưu tiên `pending` theo cwd (từ `/usb-connect` hoặc `/clear`), nếu không và `auto_assign` bật thì lấy đèn trống đầu tiên. Hook **không bao giờ đẩy session khác ra**: `pending` chỉ dùng một lần, trỏ vào đèn đang có người giữ thì bị bỏ. Chỉ `/usb-connect` mới giành đèn đang bận (last-wins), cũng là cách gỡ khi `SessionEnd` không kịp chạy và để lại session chết trong map.
- Gửi serial: mở cổng → ghi 1 dòng → đóng, thử lại 4 lần cách 80 ms khi cổng bận. Mọi lỗi nuốt im lặng, luôn `exit 0` để không làm hỏng session.
- Slash command dùng `!` để chạy script lúc gõ lệnh và `$ARGUMENTS`, có `allowed-tools: Bash(python3:*)` (thiếu quyền allow thì Claude Code hủy lệnh). Tên lệnh có tiền tố plugin: `/session-light:usb-connect`. Plugin đổi tên từ `claude-light` vì `claude plugin validate` từ chối tên bắt đầu bằng `claude-`. Thư mục trạng thái vẫn là `~/.claude-light/`.
- Slash command không nhận JSON của hook, nên `connect`/`disconnect` lấy session_id từ biến môi trường `CLAUDE_CODE_SESSION_ID` và gán/bỏ gán thẳng trong map. Thiếu biến này thì đoán theo cwd: hai session cùng thư mục sẽ bị coi là một, và `connect` khi chưa có session nào ở cwd thì ghi `pending` để hook kế tiếp chốt.
- `status` in tên session lấy từ transcript `~/.claude/projects/*/<session_id>.jsonl` (hoặc `$CLAUDE_CONFIG_DIR/projects`): dòng cuối loại `custom-title` (`/rename`) nếu có, không thì `ai-title`. Đó là tên hiện trên tab terminal.
- `disconnect` ghi cả cwd và session_id vào `muted.json`, nên `auto_assign` bỏ qua thư mục đó và cả session đó dù nó `cd` đi đâu. `connect` xoá cả hai khỏi danh sách, `SessionEnd` xoá session_id. `disconnect` khi session chưa gán đèn thì báo "chưa gán đèn nào" (trước đây vẫn báo đã bỏ gán).

## 4. Trạng thái hiện tại
- [x] Board nạp CircuitPython 10.3.1, LED onboard test OK.
- [x] Firmware + plugin viết xong.
- [x] Firmware dự án đã nạp lên board (trước đó board chạy code.py test nháy 3 màu). `ping`→`pong`, `0:ready` sáng xanh lá: OK (30/10/2026, trong WSL).
- [x] Mô phỏng chuỗi sự kiện hook bằng JSON giả: đèn ra đúng trạng thái ở cả 12 ca.
- [x] Nạp plugin vào Claude Code (`claude --plugin-dir ~/code/claude-light/code`). Session thật đã tự gán đèn 0, AskUserQuestion làm đèn đỏ nhấp nháy, lệnh status chạy được.
- [x] Sửa các ca biên (30/10/2026): session `cd` thì `disconnect` báo thành công nhưng không bỏ gán, `connect` để lại `pending` treo; hai session cùng thư mục bị gán chung một đèn và bị bỏ gán cùng nhau; `/clear` làm mất hoặc đổi đèn đã chọn; nhiều session mở cùng lúc ghi đè map. `tests/light-edge-cases.py` có 15 ca, trước khi sửa 12 ca lỗi, sau khi sửa pass hết.
- [x] Sửa lỗi session mới giành đèn đang bận (30/10/2026): `pending` bị treo (vd `/clear` sau khi `cd`, `SessionEnd` ghi theo thư mục con) khiến session mới mở ở thư mục đó đẩy session đang chạy ra. Thêm ca thứ 16 vào test. Bản cài nằm ở `~/.claude/plugins/cache/chuxuanthang-plugins/session-light/<version>/`, không đọc thẳng thư mục nguồn: sửa code phải tăng `version` trong `plugin.json` rồi chạy `claude plugin marketplace update chuxuanthang-plugins && claude plugin update session-light@chuxuanthang-plugins`. Hiện là 0.2.6 (0.2.2–0.2.3 thêm tên session vào `status`, 0.2.4–0.2.5 in tiếng Việt có dấu, kể cả mô tả lệnh và plugin; 0.2.6 `status` chỉ in trạng thái từng đèn, bỏ dòng chờ gán và không tự gán).
- [ ] Kiểm chứng trên session thật: lệnh `!` trong slash command có thấy `CLAUDE_CODE_SESSION_ID` không, sau `/clear` biến này có đổi sang id mới không, và `SessionStart` sau `/clear` có cùng cwd với `SessionEnd` không. Nếu không thấy biến thì code đoán theo cwd như cũ.
- [x] Đã cài qua marketplace local ở cấp user: `claude plugin marketplace add ~/code/claude-light` rồi `claude plugin install session-light@chuxuanthang-plugins` (trước 30/10/2026 tên marketplace là `thangcx-plugins`). Session `claude` thường, không cờ, gọi được `/session-light:usb-status`.
- [x] Đưa lên GitHub: repo public `chuxuanthang/session-light`, dùng tài khoản cá nhân `chuxuanthang`, không dùng `thangcx-3383`. Git cấu hình riêng cho repo (`git config --local`): user `chuxuanthang`, email `tl.thang244@gmail.com`. Remote `git@github-per:chuxuanthang/session-light.git`: `github-per` là alias SSH trong `~/.ssh/config` dùng key `chuxuanthang`. `gh` trên máy đăng nhập `thangcx-3383` nên repo được tạo trên web. Máy khác cài bằng `claude plugin marketplace add chuxuanthang/session-light`.
- [ ] Hook gọi `python3`, nên người chạy Claude Code thẳng trên Windows sẽ lỗi. Cần làm hook chạy được trên nhiều hệ điều hành nếu chia sẻ rộng.
- [x] Hàn thanh LED (30/10/2026). Lái thẳng GP29 từ REPL sáng đủ 8 bóng, đúng màu. Firmware đổi sang `PIN = board.GP29`, `NUM_LEDS = 8`, đã nạp lên board; `~/.claude-light/config.json` đặt `num_leds: 8`.
- [ ] `light.py` vẫn để mặc định `num_leds: 1` (trong `cfg()` và docstring), lệch với firmware 8 bóng: máy mới cài chỉ dùng đèn 0 cho đến khi sửa config. Đổi mặc định thì phải tăng `version` plugin.
- [ ] Lệnh đầu tiên gửi ngay sau `usbipd attach` bị rơi (30/10/2026: gắn lại xong gửi liền `1:`, `2:`, `3:` thì bóng 1 không sáng, 2 và 3 sáng; gửi lại thì đủ). `wsl_attach()` trả về ngay khi `/dev/ttyACM*` hiện ra, nên đèn `ready` của `SessionStart` có thể không lên. Hướng sửa: sau khi thấy cổng thì gửi `ping` chờ `pong` rồi mới gửi lệnh thật.
- [ ] Bọc ống co nhiệt, gắn đầu chuyển.

## 5. Kết quả đối chiếu docs Claude Code (code.claude.com, 30/10/2026)
- Đúng: các trường `hook_event_name`, `session_id`, `cwd` có ở mọi sự kiện; nạp plugin bằng `--plugin-dir`; `hooks/hooks.json` có cùng dạng với `hooks` trong settings.json; bỏ `matcher` nghĩa là bắt mọi trường hợp; `${CLAUDE_PLUGIN_ROOT}` và `$ARGUMENTS` dùng được trong command.
- Đã sửa: `idle_prompt` bắn khoảng 60 s sau khi Claude trả lời xong, làm đèn rảnh chuyển đỏ, nên giờ lọc theo `notification_type`. `permission_prompt` chỉ bắn sau khi chờ khoảng 6 s, nên thêm `PermissionRequest` (bắn ngay). Lỗi API bắn `StopFailure` chứ không bắn `Stop`, nên đã thêm.
- Hạn chế đã biết (docs không có sự kiện tương ứng):
  - Bấm Esc thì `Stop` không chạy, đèn kẹt màu cam đến prompt sau.
  - Không có sự kiện nào báo người dùng vừa duyệt quyền. Đèn đỏ đến khi tool chạy xong (`PostToolUse`), tool dài thì đỏ lâu.
  - Từ chối quyền thì có thể đèn đỏ đến prompt sau (chưa kiểm chứng).
- Chưa kiểm chứng: gọi lệnh không tiền tố `/usb-connect` có chạy không; `idle_prompt` có bắn khi đang chờ duyệt quyền không (nếu có thì dùng được để gỡ lỗi Esc).

## 5b. Môi trường WSL2
- WSL2 không thấy COM port. Dùng usbipd-win 5.3 (đã cài, board `2e8a:101f` đã `bind`). `light.py` tự attach: hàm `wsl_attach()` chạy ở `SessionStart`, `connect`, `test`. Nếu có `/mnt/c/Program Files/usbipd-win/usbipd.exe` mà chưa thấy cổng thì gọi `attach --wsl --hardware-id 2e8a:101f` (không cần Admin), mất khoảng 3 s. Đã kiểm chứng: board đang ở Windows thì `test` tự gắn lại được. Cổng là `/dev/ttyACM0`, user đã nằm trong group `dialout`.
- Board rút ra cắm lại giữa chừng thì session đang chạy không tự gắn lại. Mở session mới hoặc gõ `/session-light:usb-connect 0`.
- Không chạy `usbipd attach --auto-attach` bằng tay: nó giành lại board ngay sau khi detach.
- Ổ CIRCUITPY báo chống ghi khi gắn vào WSL. Sau khi detach về Windows cũng vẫn chống ghi: thử lại trong 30 s và reset bằng `microcontroller.reset()` qua COM4 đều không ăn. Rút board ra cắm lại rồi chép bên Windows thì được (2 lần). Giả thuyết chưa kiểm chứng: CircuitPython chỉ cho máy đầu tiên được ghi rồi khóa ổ, và usbipd chuyển qua lại không reset USB thật.
- 30/10/2026, thêm bằng chứng: ổ ở WSL báo `Write Protect is on` nên mount chỉ ra `ro`. Ghi từ REPL bằng `storage.remount("/", readonly=False)` bị từ chối (`Cannot remount path when visible via USB`), kể cả với `disable_concurrent_write_protection=True`. `usbipd detach` về Windows vẫn chống ghi (`The media is write protected`). Chỉ khi board rời WSL hẳn (`vhci_hcd: connection closed`, nhiều khả năng do rút cắm) thì ổ `D:` mới ghi được; chép từ WSL bằng `powershell.exe Copy-Item` vào `D:\code.py` được. Khớp giả thuyết trên: phải rút cắm thật.
- Quy trình nạp firmware: rút board ra cắm lại → chép `code.py` vào ổ CIRCUITPY trên Windows → mở session (hoặc chạy `light.py test`) để tự gắn lại vào WSL. Chép xong mới mở session mới.
- Mỗi lần gửi lệnh mất khoảng 0,03 s, nên hook chạy đồng bộ, không cần `async`.
- Bản sao lưu trước khi sửa: `code.bak-251030/`.

## 6. Hướng phát triển sau
- Daemon giữ cổng serial, hook gửi qua socket local (tránh tranh cổng khi nhiều session).
- `boot.py` ẩn ổ CIRCUITPY và mở cổng data riêng (`usb_cdc.enable(data=True)`), đặt VID/PID riêng để nhận diện chắc chắn.
- Đèn hệ thống (LED onboard) báo kết nối OK / session chưa gán, khi 8 bóng thanh làm slot.
- Timeout: `wait` quá lâu thì tăng tốc nhấp nháy.
