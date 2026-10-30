---
allowed-tools: Bash(python3:*)
description: Gán session này vào đèn USB số N (0 là đèn đầu tiên, bỏ trống = 0)
argument-hint: [số đèn, mặc định 0]
---
Kết quả lệnh:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/light.py" connect $ARGUMENTS`

Trả lời người dùng đúng một dòng, nhắc lại nguyên văn kết quả ở trên. Không làm gì khác.
