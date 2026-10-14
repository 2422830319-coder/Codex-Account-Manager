# -*- coding: utf-8 -*-
"""GUI 冒烟测试：offscreen 模式构建主窗口并自动关闭，不弹真实窗口。"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent))
import core

tmp = Path(tempfile.mkdtemp(prefix="butler-gui-"))
codex_dir = tmp / ".codex"
butler_dir = tmp / ".codex-butler"
codex_dir.mkdir(parents=True)
core.configure(codex_dir=codex_dir, butler_dir=butler_dir)
core.ensure_dirs()

# 预置一个账号，避免首次运行弹窗阻塞
fake = {
    "tokens": {
        "id_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJndWktdGVzdCJ9.sig",
        "access_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJndWktdGVzdCJ9.sig",
        "refresh_token": "rt.gui.test.value",
        "account_id": "11111111-1111-1111-1111-111111111111",
    },
    "email": "gui-test@example.com",
    "source_type": "selftest",
    "expired": "",
    "found_accounts": 1,
}
core.save_account(fake)

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

import app as appmod

qapp = QApplication([])
qapp.setStyle("Fusion")
qapp.setStyleSheet(appmod.STYLE_SHEET)
qapp.setFont(QFont("Microsoft YaHei UI", 9))

win = appmod.MainWindow()
win.show()

# 检查关键部件
assert win.cards, "账号卡片应已构建"
assert win.btn_switch is not None
print("窗口标题:", win.windowTitle())
print("卡片数量:", len(win.cards))
print("选中按钮可用:", win.btn_switch.isEnabled())
print("日志行数:", len(core.read_log_tail(999)))

QTimer.singleShot(600, qapp.quit)
qapp.exec()
print("GUI 冒烟测试通过 ✓ (offscreen)")
