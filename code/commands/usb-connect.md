---
allowed-tools: Bash(python3:*)
description: Gán session này vào đèn USB số N (1–8, 1 là đèn bên trái ngoài cùng, bỏ trống = 1)
argument-hint: [số đèn 1–8, mặc định 1]
---
Kết quả lệnh:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/light.py" connect $ARGUMENTS`

Trả lời người dùng đúng một dòng, nhắc lại nguyên văn kết quả ở trên. Không làm gì khác.
