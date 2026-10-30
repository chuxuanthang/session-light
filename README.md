# session-light

Plugin Claude Code điều khiển đèn USB báo trạng thái từng session. Thanh LED có 8 đèn RGB, mỗi session được gán một đèn (tối đa 8 session cùng lúc), nhìn đèn là biết session nào đang chạy, session nào đang chờ bạn.

| Màu | Trạng thái |
|---|---|
| Xanh lá | Sẵn sàng, Claude đã trả lời xong |
| Cam | Đang chạy |
| Đỏ nhấp nháy | Chờ bạn trả lời câu hỏi hoặc duyệt quyền |
| Tắt | Chưa có session nào gắn vào đèn |

## Cách hoạt động
Hook của Claude Code gọi `code/scripts/light.py` mỗi khi có sự kiện (gửi prompt, chạy tool, xin quyền, trả lời xong, thoát). Script gửi một dòng `<đèn>:<trạng thái>` qua cổng serial xuống board RP2040 chạy CircuitPython.

Session mới mở sẽ tự lấy đèn còn trống đầu tiên. Đèn đang có session khác giữ thì session mới không có đèn, không giành đèn của session đang chạy. Muốn chuyển đèn thì gõ `/session-light:usb-connect`.

## Cần có
- Board RP2040 chạy CircuitPython (đang dùng RP2040-Zero, CircuitPython 10.3.1) và thanh 8 LED WS2812 (đang dùng CJMCU-2812-8), chân dữ liệu nối vào GP29. Chỉ có LED onboard (GP16) thì vẫn chạy được với 1 đèn, xem [`code/README.md`](code/README.md).
- Thư viện `neopixel.mpy` trong thư mục `lib/` trên ổ CIRCUITPY.
- Máy tính có `python3` và `pyserial` (`pip install pyserial`). Đã chạy thật trên WSL2 qua usbipd-win; Linux và macOS dùng cùng mã nên sẽ chạy được nhưng chưa thử.

## Cài đặt
1. Chép `code/firmware/code.py` vào ổ CIRCUITPY. Thanh LED nháy 3 màu rồi tắt là firmware đã chạy.
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
| `/session-light:usb-connect [n]` | Gán session hiện tại vào đèn `n` (0–7, mặc định 0), đẩy session đang giữ đèn đó ra |
| `/session-light:usb-disconnect` | Bỏ gán và tắt đèn; thư mục này không tự gán lại đến khi `usb-connect` |
| `/session-light:usb-status` | In từng đèn đang gán cho session nào, theo tên session trên tab terminal |

Cấu hình nằm ở `~/.claude-light/config.json`: `port`, `num_leds` (mặc định 8), `auto_assign`, `debug`.

## Hạn chế
- Sau khi duyệt quyền, đèn vẫn đỏ đến khi tool đó chạy xong.

Claude Code không có sự kiện hook nào cho trường hợp này.

Bấm Esc hoặc Ctrl+C giữa chừng cũng không có hook nào chạy. Plugin xử lý bằng cách mỗi lượt chạy một tiến trình nhỏ ở nền đọc file trạng thái Claude Code ghi cho từng phiên (`~/.claude/sessions/<pid>.json`): trạng thái về `idle` thì đưa đèn về xanh rồi thoát. File này là file nội bộ của Claude Code; bản nào không có thì đèn kẹt cam như trước, đến prompt sau.

## Phát triển
- Test các ca biên, không cần board: `python3 tests/light-edge-cases.py`
- Claude Code chạy bản chép trong `~/.claude/plugins/cache/`. Sửa code xong phải tăng `version` trong `code/.claude-plugin/plugin.json` rồi cập nhật plugin, chi tiết trong [`code/README.md`](code/README.md).
- Ghi chú phần cứng, quyết định thiết kế và việc còn dở: [`HANDOVER.md`](HANDOVER.md).

## Giấy phép
[MIT](LICENSE)
