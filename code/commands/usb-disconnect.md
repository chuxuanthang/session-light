---
allowed-tools: Bash(python3:*)
description: Bỏ gán đèn USB: bỏ trống là đèn của session này, số N là đèn N (1–8), 0 là bỏ gán hết
argument-hint: [số đèn 1–8, 0 = bỏ gán hết, bỏ trống = đèn của session này]
---
Kết quả lệnh:
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/light.py" disconnect $ARGUMENTS`

Trả lời người dùng đúng một dòng, nhắc lại nguyên văn kết quả ở trên. Không làm gì khác.
