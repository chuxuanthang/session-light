# session-light

Đèn USB báo trạng thái session Claude Code: xanh lá = sẵn sàng, cam = đang chạy, đỏ nhấp nháy = cần bạn xác nhận. Đèn chưa gắn session chạy hiệu ứng nền, mặc định là một chấm xanh lơ quét qua lại.

## 1. Board (một lần)
1. Chép `firmware/code.py` vào ổ CIRCUITPY (ghi đè code.py cũ). Thanh LED nháy 3 màu rồi chạy hiệu ứng quét là firmware chạy. Nếu báo chống ghi ("write protected"), rút board ra cắm lại rồi chép ngay bên Windows.
2. Firmware lái thanh 8 bóng ở GP29, đèn 1 nằm bên trái ngoài cùng khi đầu IN của thanh ở bên phải (lắp ngược thì đặt `FLIP = False` trong code.py), khớp với `num_leds` mặc định là 8 trong `~/.claude-light/config.json`. Máy đã cài bản trước 0.2.7 thì config đã lưu `num_leds: 1`, sửa tay thành 8. Chỉ dùng LED onboard thì sửa 2 dòng đầu code.py thành `PIN = board.GP16`, `NUM_LEDS = 1` và đặt `num_leds` là 1.

## 2. Máy tính
```
pip install pyserial
python3 scripts/light.py test     # LED phải đổi màu xanh lá -> cam -> đỏ -> về hiệu ứng nền
python3 scripts/light.py status
```
Nếu `test` không đổi màu: đóng Thonny / serial monitor (đang giữ cổng), hoặc ghi cứng cổng vào `~/.claude-light/config.json`: `"port": "COM5"` (Linux/WSL: `"/dev/ttyACM0"`).
Chạy Claude Code thẳng trên Windows (không qua WSL): đổi `python3` thành `python` hoặc `py` trong `hooks/hooks.json` và 3 file trong `commands/`.

### WSL2
WSL2 không thấy COM port, cần [usbipd-win](https://github.com/dorssel/usbipd-win):
```powershell
winget install --exact dorssel.usbipd-win
usbipd list                                   # tìm BUSID của dòng 2e8a:101f
usbipd bind --busid <BUSID>                   # PowerShell Admin, chỉ làm một lần
```
Sau khi bind, không cần tự attach: lúc mở session (và khi chạy `test`, `/session-light:usb-connect`), nếu chưa thấy cổng thì `light.py` tự gọi `usbipd.exe attach --wsl --hardware-id 2e8a:101f`, mất khoảng 3 giây. Board rời WSL giữa chừng (rút USB cắm lại, hoặc kết nối usbip tự đứt) thì tiến trình nền `light.py keep` (bật lúc mở session) gọi lại `usbipd attach` mỗi 5 giây; cổng có lại sau khi mất (plugin gắn hay bạn tự gắn) thì nó gửi lại màu cả thanh, không cần đợi session nào có sự kiện. Windows chạy thẳng (không fcntl) thì không có tiến trình này, hook đầu tiên sau khi cắm lại mới gửi lại. Board hiện ra ở `/dev/ttyACM0`. User cần thuộc group `dialout`.
Khi gắn vào WSL, ổ CIRCUITPY chỉ đọc được, và `usbipd detach` về Windows cũng vẫn chống ghi. Muốn sửa firmware thì rút board ra cắm lại rồi chép file vào ổ CIRCUITPY bên Windows, làm trước khi mở session mới vì session mới sẽ tự gắn board lại vào WSL. Đừng chạy `usbipd attach --auto-attach`: nó sẽ giành lại board ngay sau khi detach.

## 3. Cài plugin vào Claude Code
Thư mục gốc repo (chứa `.claude-plugin/marketplace.json`) là marketplace `chuxuanthang-plugins`, repo GitHub `chuxuanthang/session-light`. Cài một lần ở cấp user, từ đó mọi lần chạy `claude` đều có plugin:
```
claude plugin marketplace add chuxuanthang/session-light   # đang phát triển thì dùng đường dẫn thư mục repo
claude plugin install session-light@chuxuanthang-plugins
```
Claude Code chạy bản chép trong `~/.claude/plugins/cache/`, không đọc thẳng thư mục nguồn. Sửa code xong (kể cả marketplace local) phải tăng `version` trong `plugin.json`, chạy `claude plugin marketplace update chuxuanthang-plugins` rồi `claude plugin update session-light@chuxuanthang-plugins`, sau đó mở lại `claude`.

Lúc phát triển, thử nhanh mà không cài: `claude --plugin-dir /duong/dan/claude-light/code`. Đã cài rồi thì đừng thêm cờ này, vì hook sẽ bắn hai lần.

## 4. Dùng
- Mặc định `auto_assign: true`: session mới tự lấy đèn trống đầu tiên, không cần làm gì. Hết đèn trống thì session mới không có đèn, không giành đèn của session đang chạy.
- `/session-light:usb-connect 2` gán session ở thư mục hiện tại vào đèn 2 (đẩy session cũ ra nếu đèn đang bận). Số đèn từ 1 đến 8 với thanh 8 bóng, đèn 1 bên trái ngoài cùng; bỏ trống thì gán vào đèn 1.
- `/session-light:usb-disconnect` gỡ đèn của session hiện tại và tắt. Thư mục đó sẽ không được tự gán lại đến khi bạn `usb-connect` lần nữa.
- `/session-light:usb-disconnect 3` gỡ đèn 3 dù đang thuộc session nào, gõ từ terminal nào cũng được; `/session-light:usb-disconnect 0` gỡ hết. Session bị gỡ không tự lấy đèn khác đến khi gõ `usb-connect` trong chính session đó; thư mục của nó thì không bị chặn, session mới mở ở đó vẫn tự lấy đèn.
- `/session-light:usb-status` xem đèn nào gán cho session nào: in tên session (đúng tên trên tab terminal, tên đặt bằng `/rename` được ưu tiên) kèm thư mục. Session chưa có tên thì chỉ in thư mục.
- `/session-light:usb-blink` nháy xanh lá 3 lần đèn đang gắn session hiện tại rồi trả về màu trạng thái, đồng thời in số đèn. Dùng khi không nhớ terminal nào đang dùng đèn nào. Cần firmware từ bản 0.2.20.
- `/session-light:usb-sort` dồn các đèn đang gán về liền nhau từ đèn 1, giữ nguyên thứ tự (đang sáng 1 3 5 6 8 thì thành 1 2 3 4 5), rồi in đèn nào chuyển sang đèn nào. Session đã tắt ngang (không có `SessionEnd`) được bỏ gán trước, nên không chiếm chỗ.
- `/session-light:usb-swap 2 5` đổi đèn 2 và đèn 5 cho nhau (gõ `2 5`, `2,5` hay `2-5` đều được). Một trong hai đèn đang trống thì session ở đèn kia chuyển sang. Màu từng đèn theo trạng thái thật của session, nên đèn đang đỏ vẫn đỏ ở chỗ mới.
- `/session-light:usb-brightness 20` đặt độ sáng các đèn có session 20%. Mặc định 5%, dưới 5% thì màu bị lệch (cam dễ lẫn với đỏ), 0 là tắt hẳn các đèn này. Đèn chạy hiệu ứng luôn giữ 5%. Bỏ trống số để xem độ sáng hiện tại.
- `/session-light:usb-fx 1` (hoặc `/session-light:usb-fx scan`) đổi hiệu ứng của đèn chưa gắn session, gõ số hoặc tên: `0` `none` (tắt), rồi từ `1`: `scan` (chấm sáng quét qua lại, mặc định), `rainbow` (cầu vồng xoay, có lúc ra đỏ/cam/xanh lá nên dễ lẫn với đèn trạng thái), `breathe` (thở màu xanh dương, tím), `chase` (đèn Noel: cứ 3 bóng sáng 1, chạy dần, xen kẽ xanh dương / tím), `comet` (sao băng kéo đuôi chạy một chiều), `wave` (sóng màu chỉ trong dải xanh lơ, xanh dương, tím), `heart` (nhịp tim tím hồng, hai nhịp rồi nghỉ). Số 1–7 theo đúng thứ tự này. Bỏ trống để xem danh sách kèm số.
- Hai giá trị trên lưu ở `brightness` và `idle_fx` trong config. Board quên chúng mỗi lần cắm lại, nên `SessionStart` gửi lại kèm lệnh trạng thái.
- Bật `"debug": true` trong config để ghi `~/.claude-light/log.txt` khi cần soi.

Bấm Esc hoặc Ctrl+C giữa chừng thì Claude Code không chạy hook nào (`Stop` không chạy); duyệt quyền xong cũng không có hook nào cho đến khi tool chạy xong. Vì vậy mỗi lượt (`UserPromptSubmit`), `light.py` bật một tiến trình nền `light.py watch` đọc `~/.claude/sessions/<pid>.json`, file Claude Code ghi trạng thái phiên, và đổi đèn theo mỗi lần trạng thái đổi sau lúc gửi prompt: `waiting` (trừ `dialog open`, tức hộp thoại bạn tự mở như `/model`) thì đỏ, `busy` thì cam, `idle` thì xanh rồi thoát. Có lượt mới hoặc session đã đóng thì cũng thoát.


## Giao thức xuống board
Mỗi dòng `<đèn>:<trạng thái>`, số đèn tính từ 0 (đèn 1 trên lệnh slash là `0:`): `0:ready`, `0:busy`, `0:wait`, `0:off`, `all:off`, `0:#ff00ff`, `ping`. Đèn `off` chạy hiệu ứng nền, đổi bằng `fx:none | scan | rainbow | breathe | chase | comet | wave | heart`. Độ sáng các đèn có session: `bri:<0–100>`, đèn hiệu ứng giữ 5%. `flash:<đèn>` nháy xanh lá 3 lần (1,8 s) đè lên màu đang hiện, xong tự trả về.
