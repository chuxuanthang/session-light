# session-light

Plugin Claude Code điều khiển đèn USB báo trạng thái từng session. Mỗi session được gán một đèn RGB, nhìn đèn là biết session nào đang chạy, session nào đang chờ bạn.

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
- Board RP2040 chạy CircuitPython (đang dùng RP2040-Zero, CircuitPython 10.3.1) và LED WS2812: LED onboard ở GP16 hoặc một thanh WS2812 nối vào chân GP khác.
- Thư viện `neopixel.mpy` trong thư mục `lib/` trên ổ CIRCUITPY.
- Máy tính có `python3` và `pyserial` (`pip install pyserial`). Đã chạy thật trên WSL2 qua usbipd-win; Linux và macOS dùng cùng mã nên sẽ chạy được nhưng chưa thử.

## Cài đặt
1. Chép `code/firmware/code.py` vào ổ CIRCUITPY. LED nháy 3 màu rồi tắt là firmware đã chạy.
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
| `/session-light:usb-connect [n]` | Gán session hiện tại vào đèn `n` (mặc định 0), đẩy session đang giữ đèn đó ra |
| `/session-light:usb-disconnect` | Bỏ gán và tắt đèn; thư mục này không tự gán lại đến khi `usb-connect` |
| `/session-light:usb-status` | In từng đèn đang gán cho session nào, theo tên session trên tab terminal |

Cấu hình nằm ở `~/.claude-light/config.json`: `port`, `num_leds`, `auto_assign`, `debug`.

## Hạn chế
- Bấm Esc giữa chừng thì đèn kẹt màu cam đến prompt sau.
- Sau khi duyệt quyền, đèn vẫn đỏ đến khi tool đó chạy xong.

Claude Code không có sự kiện hook nào cho hai trường hợp này.

## Phát triển
- Test các ca biên, không cần board: `python3 tests/light-edge-cases.py`
- Claude Code chạy bản chép trong `~/.claude/plugins/cache/`. Sửa code xong phải tăng `version` trong `code/.claude-plugin/plugin.json` rồi cập nhật plugin, chi tiết trong [`code/README.md`](code/README.md).
- Ghi chú phần cứng, quyết định thiết kế và việc còn dở: [`HANDOVER.md`](HANDOVER.md).

## Giấy phép
[MIT](LICENSE)
