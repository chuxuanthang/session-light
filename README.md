# session-light

Plugin Claude Code điều khiển đèn USB báo trạng thái từng session. Thanh LED có 8 đèn RGB, mỗi session được gán một đèn (tối đa 8 session cùng lúc), nhìn đèn là biết session nào đang chạy, session nào đang chờ bạn.

| Màu | Trạng thái |
|---|---|
| Xanh lá | Sẵn sàng, Claude đã trả lời xong |
| Cam | Đang chạy |
| Đỏ nhấp nháy | Chờ bạn trả lời câu hỏi hoặc duyệt quyền |
| Hiệu ứng nền (mặc định chấm xanh lơ quét qua lại) | Chưa có session nào gắn vào đèn |

## Cách hoạt động
Hook của Claude Code gọi `code/scripts/light.py` mỗi khi có sự kiện (gửi prompt, chạy tool, xin quyền, trả lời xong, thoát). Script gửi một dòng `<đèn>:<trạng thái>` qua cổng serial xuống board RP2040 chạy CircuitPython.

Đèn đánh số 1–8 từ trái sang phải. Session mới mở, kể cả mở lại bằng `claude -c`, sẽ tự lấy đèn còn trống đầu tiên tính từ bên trái, không giữ đèn cũ. Đèn đang có session khác giữ thì session mới không có đèn, không giành đèn của session đang chạy. Muốn chuyển đèn thì gõ `/session-light:usb-connect`.

Rút USB cắm lại thì board quên hết màu. Lúc mở session, plugin bật một tiến trình nền nhỏ (mỗi lúc chỉ một, tự thoát khi không còn session nào) kiểm tra board mỗi giây: board cắm lại thì vài giây sau nó tự gắn lại (trên WSL) và gửi lại màu của mọi đèn theo trạng thái thật của từng session, nên đèn đang có session không bị tối như đèn trống. Session đã tắt ngang (đóng terminal) thì được bỏ gán, trả đèn.

## Cần có
- Board RP2040 chạy CircuitPython (đang dùng RP2040-Zero, CircuitPython 10.3.1) và thanh 8 LED WS2812 (đang dùng CJMCU-2812-8), chân dữ liệu nối vào GP29. Chỉ có LED onboard (GP16) thì vẫn chạy được với 1 đèn, xem [`code/README.md`](code/README.md).
- Thư viện `neopixel.mpy` trong thư mục `lib/` trên ổ CIRCUITPY.
- Máy tính có `python3` và `pyserial` (`pip install pyserial`). Đã chạy thật trên WSL2 qua usbipd-win; Linux và macOS dùng cùng mã nên sẽ chạy được nhưng chưa thử.

## Cài đặt
1. Chép `code/firmware/code.py` vào ổ CIRCUITPY. Thanh LED nháy 3 màu rồi chạy hiệu ứng quét là firmware đã chạy.
2. Cài plugin một lần ở cấp user:
   ```
   claude plugin marketplace add chuxuanthang/session-light
   claude plugin install session-light@chuxuanthang-plugins
   ```
3. Mở lại `claude`. Session mới sẽ tự gán vào đèn trống.

WSL2, Windows chạy thẳng, đổi chân LED hay số đèn: xem [`code/README.md`](code/README.md).

## Lệnh
| Lệnh | Việc |
|---|---|
| `/session-light:usb-connect [n]` | Gán session hiện tại vào đèn `n` (1–8, mặc định 1, đèn 1 bên trái ngoài cùng), đẩy session đang giữ đèn đó ra |
| `/session-light:usb-disconnect` | Bỏ gán và tắt đèn; thư mục này không tự gán lại đến khi `usb-connect` |
| `/session-light:usb-status` | In từng đèn đang gán cho session nào, theo tên session trên tab terminal |
| `/session-light:usb-blink` | Nháy xanh lá 3 lần đèn của session hiện tại rồi trả về màu cũ, kèm in số đèn, để biết terminal này đang dùng đèn nào |
| `/session-light:usb-sort` | Dồn các đèn đang gán về liền nhau từ đèn 1, giữ nguyên thứ tự: đang sáng 1 3 5 6 8 thì thành 1 2 3 4 5 |
| `/session-light:usb-swap a b` | Đổi hai đèn cho nhau, vd `2 5`: session ở đèn 2 sang đèn 5 và ngược lại; một đèn đang trống thì là chuyển sang |
| `/session-light:usb-brightness [0–100]` | Đổi độ sáng các đèn có session theo phần trăm (mặc định 5), bỏ trống để xem độ sáng hiện tại. Đèn chạy hiệu ứng luôn giữ 5% |
| `/session-light:usb-fx [số hoặc tên]` | Đổi hiệu ứng của đèn chưa gắn session: `0` `none` (tắt), `1` `scan` (sóng quét, mặc định), `2` `rainbow` (cầu vồng), `3` `breathe` (thở màu), `4` `chase` (đèn Noel chạy), `5` `comet` (sao băng), `6` `wave` (sóng màu lạnh), `7` `heart` (nhịp tim) |

Cấu hình nằm ở `~/.claude-light/config.json`: `port`, `num_leds` (mặc định 8), `auto_assign`, `debug`, `brightness` (mặc định 5), `idle_fx` (mặc định `scan`). Board quên độ sáng và hiệu ứng mỗi lần cắm lại, nên lúc mở session plugin gửi lại hai giá trị này.

## Theo dõi trạng thái ngoài hook
Có hai lúc Claude Code không chạy hook nào: bấm Esc hoặc Ctrl+C giữa chừng (`Stop` không chạy), và lúc bạn vừa duyệt quyền (hook kế tiếp chỉ đến khi tool chạy xong). Plugin xử lý bằng cách mỗi lượt chạy một tiến trình nhỏ ở nền đọc file trạng thái Claude Code ghi cho từng phiên (`~/.claude/sessions/<pid>.json`), rồi đổi đèn theo mỗi lần trạng thái đổi: `waiting` thì đỏ, `busy` thì cam, `idle` thì xanh và thoát.

File này là file nội bộ của Claude Code. Bản nào không ghi file này thì plugin quay về chỉ dùng hook: ngắt giữa chừng thì đèn kẹt cam đến prompt sau, duyệt quyền xong thì đèn đỏ đến khi tool chạy xong.

## Phát triển
- Test các ca biên, không cần board: `python3 tests/light-edge-cases.py`
- Test firmware trên máy tính (giả lập `board`/`neopixel`): `python3 tests/firmware-effects.py`
- Claude Code chạy bản chép trong `~/.claude/plugins/cache/`. Sửa code xong phải tăng `version` trong `code/.claude-plugin/plugin.json` rồi cập nhật plugin, chi tiết trong [`code/README.md`](code/README.md).
- Ghi chú phần cứng, quyết định thiết kế và việc còn dở: [`HANDOVER.md`](HANDOVER.md).

## Giấy phép
[MIT](LICENSE)
