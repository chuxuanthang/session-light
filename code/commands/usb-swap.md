---
allowed-tools: Bash(python3:*)
description: Đổi hai đèn USB cho nhau, vd 2 5 (session đang ở đèn 2 sang đèn 5 và ngược lại)
argument-hint: <đèn> <đèn>, vd 2 5
---
Kết quả lệnh:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/light.py" swap "$ARGUMENTS"`

Trả lời người dùng đúng một dòng, nhắc lại nguyên văn kết quả ở trên. Không làm gì khác.
