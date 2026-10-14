# -*- coding: utf-8 -*-
"""
Codex 账号管家 · 界面层（PySide6）
一个把 Codex 配置文件"丢进去就配置好"的小工具。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTextEdit, QMessageBox, QFileDialog,
    QInputDialog, QMenu, QSizePolicy,
)

import core


# ---------------------------------------------------------------------------
# 样式（固定浅色主题）
# ---------------------------------------------------------------------------

STYLE_SHEET = """
* { font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif; }
QMainWindow { background: #f6f7f9; }
QWidget#central { background: #f6f7f9; }

QLabel#appTitle { font-size: 18px; font-weight: 600; color: #1a1c1f; }
QLabel#appSub { font-size: 12px; color: #8a8f98; }
QLabel#sectionLabel { font-size: 12px; color: #8a8f98; }
QLabel#footerHint { font-size: 11px; color: #a0a6ae; }
QLabel#emptyHint { font-size: 13px; color: #8a8f98; padding: 30px 0; }

QFrame#accountCard { background: #ffffff; border: 1px solid #e3e6ea; border-radius: 10px; }
QFrame#accountCard:hover { border: 1px solid #c9cfd6; }
QFrame#accountCard[selected="true"] { border: 2px solid #378ADD; }
QLabel#cardTitle { font-size: 14px; font-weight: 600; color: #1a1c1f; }
QLabel#cardSub { font-size: 12px; color: #6b7280; }
QLabel#cardAvatar { border-radius: 20px; background: #E6F1FB; color: #185FA5; font-size: 15px; font-weight: 600; }
QLabel#cardBadge { font-size: 12px; padding: 3px 10px; border-radius: 10px; }
QLabel#cardBadge[state="current"] { background: #E1F5EE; color: #0F6E56; }
QLabel#cardBadge[state="idle"] { background: #F1EFE8; color: #5F5E5A; }

QPushButton { font-size: 13px; }
QPushButton#primaryBtn { background: #378ADD; color: #ffffff; border: none; border-radius: 8px; padding: 9px 18px; font-weight: 600; }
QPushButton#primaryBtn:hover { background: #2f7bc4; }
QPushButton#primaryBtn:pressed { background: #276da9; }
QPushButton#primaryBtn:disabled { background: #b9cfe6; color: #eef4fb; }
QPushButton#ghostBtn { background: #ffffff; color: #1a1c1f; border: 1px solid #d5d9de; border-radius: 8px; padding: 9px 18px; }
QPushButton#ghostBtn:hover { background: #f1f3f5; }
QPushButton#ghostBtn:pressed { background: #e8ebee; }
QPushButton#ghostBtn:disabled { color: #9aa1a9; background: #f4f5f7; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #cdd3da; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #b3bac3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QTextEdit#logView { background: #f1f3f5; border: none; border-radius: 10px; font-family: Consolas, "Courier New", monospace; font-size: 12px; color: #4b5563; padding: 8px; }
QMessageBox { background: #ffffff; }
QMessageBox QLabel { font-size: 13px; color: #1a1c1f; }
QMessageBox QPushButton { background: #ffffff; border: 1px solid #d5d9de; border-radius: 6px; padding: 6px 16px; min-width: 64px; }
QMessageBox QPushButton:hover { background: #f1f3f5; }
QMenu { background: #ffffff; border: 1px solid #e3e6ea; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 6px; font-size: 13px; }
QMenu::item:selected { background: #E6F1FB; color: #185FA5; }
QInputDialog { background: #ffffff; }
QInputDialog QLabel { font-size: 13px; }
QInputDialog QLineEdit { border: 1px solid #d5d9de; border-radius: 6px; padding: 6px 8px; font-size: 13px; }
"""


# ---------------------------------------------------------------------------
# 账号卡片
# ---------------------------------------------------------------------------

class AccountCard(QFrame):
    clicked = Signal(str)
    double_clicked = Signal(str)
    context_menu = Signal(str, object)

    def __init__(self, meta: dict, is_current: bool, parent=None):
        super().__init__(parent)
        self.key = meta.get("key", "")
        self.meta = meta
        self.is_current = is_current
        self.selected = False
        self.setObjectName("accountCard")
        self.setCursor(Qt.PointingHandCursor)
        self._build()
        self.refresh(meta, is_current)

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        self.avatar = QLabel()
        self.avatar.setObjectName("cardAvatar")
        self.avatar.setFixedSize(40, 40)
        self.avatar.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.avatar)

        col = QVBoxLayout()
        col.setSpacing(3)
        self.title = QLabel()
        self.title.setObjectName("cardTitle")
        self.sub = QLabel()
        self.sub.setObjectName("cardSub")
        col.addWidget(self.title)
        col.addWidget(self.sub)
        lay.addLayout(col, 1)

        self.badge = QLabel()
        self.badge.setObjectName("cardBadge")
        lay.addWidget(self.badge, 0, Qt.AlignVCenter)

    def refresh(self, meta: dict, is_current: bool):
        self.meta = meta
        self.is_current = is_current
        note = meta.get("note", "") or "（未命名）"
        email = meta.get("email", "")
        src = meta.get("source_type", "")
        imp = meta.get("imported_at", "")

        self.title.setText(note)
        sub_parts = [core.mask_email(email)]
        if src:
            sub_parts.append(src)
        if imp:
            sub_parts.append("导入于 " + imp[5:16])
        self.sub.setText("　·　".join(sub_parts))

        head = (note.strip()[:1] or "?").upper()
        self.avatar.setText(head)

        if is_current:
            self.badge.setText("使用中")
            self.badge.setProperty("state", "current")
        else:
            self.badge.setText("备用")
            self.badge.setProperty("state", "idle")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

        tip = (
            "备注：%s\n邮箱：%s\n账号 ID：%s\n来源格式：%s\n导入时间：%s\n令牌参考到期：%s\n\n单击选中 · 双击改备注 · 右键更多操作"
            % (note, email or "（未识别）", meta.get("account_id", "—") or "—",
               src or "—", imp or "—", meta.get("expired_hint", "") or "—")
        )
        self.setToolTip(tip)

    def set_selected(self, sel: bool):
        self.selected = sel
        self.setProperty("selected", "true" if sel else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self.key)
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e):
        self.clicked.emit(self.key)
        self.context_menu.emit(self.key, e.globalPos())


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(core.APP_NAME)
        self.resize(780, 680)
        self.setMinimumSize(640, 560)
        self.setAcceptDrops(True)
        self.selected_key = ""
        self.cards = {}
        self._build_ui()
        self._bootstrap()
        self.refresh_all()

    # ---------------- UI 构建 ----------------

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 14)
        root.setSpacing(12)

        head = QHBoxLayout()
        head_col = QVBoxLayout()
        head_col.setSpacing(2)
        title = QLabel(core.APP_NAME)
        title.setObjectName("appTitle")
        sub = QLabel("本地运行 · 不上传任何数据 · 支持 CPA / Sub2 / 原生 auth.json")
        sub.setObjectName("appSub")
        head_col.addWidget(title)
        head_col.addWidget(sub)
        head.addLayout(head_col, 1)
        root.addLayout(head)

        sec1 = QLabel("账号库")
        sec1.setObjectName("sectionLabel")
        root.addWidget(sec1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_host = QWidget()
        self.card_layout = QVBoxLayout(self.card_host)
        self.card_layout.setContentsMargins(0, 0, 6, 0)
        self.card_layout.setSpacing(8)
        self.card_layout.addStretch(1)
        self.scroll.setWidget(self.card_host)
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.scroll, 1)

        self.empty_hint = QLabel()
        self.empty_hint.setObjectName("emptyHint")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setText(
            "账号库是空的\n\n把 Codex 配置文件（.json）直接拖进窗口，\n或点击下方「导入配置」按钮"
        )
        self.empty_hint.hide()
        root.addWidget(self.empty_hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_import = QPushButton("导入配置…")
        self.btn_import.setObjectName("ghostBtn")
        self.btn_import.clicked.connect(self.on_import)

        self.btn_switch = QPushButton("切换到选中账号")
        self.btn_switch.setObjectName("primaryBtn")
        self.btn_switch.clicked.connect(self.on_switch)

        self.btn_restore = QPushButton("还原上一次")
        self.btn_restore.setObjectName("ghostBtn")
        self.btn_restore.setToolTip("把账号恢复到最近一次切换前的状态")
        self.btn_restore.clicked.connect(self.on_restore)

        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_switch)
        btn_row.addWidget(self.btn_restore)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        sec2 = QLabel("操作日志")
        sec2.setObjectName("sectionLabel")
        root.addWidget(sec2)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(150)
        root.addWidget(self.log_view)

        footer = QLabel("备份与数据仅保存在本机：%s" % core.BUTLER_DIR)
        footer.setObjectName("footerHint")
        root.addWidget(footer)

    # ---------------- 启动初始化 ----------------

    def _bootstrap(self):
        accounts = core.list_accounts()
        if accounts:
            return
        result = core.bootstrap_import()
        if result["imported"]:
            names = "\n".join(
                "· " + (m.get("note") or core.mask_email(m.get("email", "")))
                for m in result["imported"]
            )
            QMessageBox.information(
                self, "首次运行",
                "已自动发现并导入 %d 个账号：\n\n%s\n\n"
                "以后可以用「导入配置」按钮，或直接把 JSON 文件拖进窗口。" % (
                    len(result["imported"]), names),
            )
        elif result["errors"]:
            QMessageBox.warning(
                self, "首次运行",
                "本机暂无可导入的账号。\n\n" + "\n".join(result["errors"][:5]),
            )

    # ---------------- 刷新 ----------------

    def refresh_all(self):
        # 清空旧卡片
        while self.card_layout.count() > 1:
            item = self.card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards = {}

        accounts = core.list_accounts()
        current_id = core.current_account_id()

        if not accounts:
            self.empty_hint.show()
            self.scroll.hide()
        else:
            self.empty_hint.hide()
            self.scroll.show()
            for acc in accounts:
                is_current = bool(
                    acc.get("account_id") and acc["account_id"] == current_id)
                card = AccountCard(acc, is_current)
                card.clicked.connect(self.on_card_clicked)
                card.double_clicked.connect(self.on_card_double)
                card.context_menu.connect(self.on_card_context)
                self.card_layout.insertWidget(self.card_layout.count() - 1, card)
                self.cards[acc["key"]] = card

        if self.selected_key not in self.cards:
            self.selected_key = ""
        for key, card in self.cards.items():
            card.set_selected(key == self.selected_key)

        self.btn_switch.setEnabled(bool(self.selected_key))
        self.refresh_log()

    def refresh_log(self):
        lines = core.read_log_tail(300)
        self.log_view.setPlainText("\n".join(lines))
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---------------- 卡片交互 ----------------

    def on_card_clicked(self, key: str):
        self.selected_key = key
        for k, card in self.cards.items():
            card.set_selected(k == key)
        self.btn_switch.setEnabled(bool(key))

    def on_card_double(self, key: str):
        accounts = {a["key"]: a for a in core.list_accounts()}
        acc = accounts.get(key)
        if not acc:
            return
        text, ok = QInputDialog.getText(
            self, "修改备注名",
            "给这个账号起个名字（例如：我的主账号 / 临时应急 1 号）：",
            text=acc.get("note", ""),
        )
        if ok and text.strip():
            core.rename_account(key, text.strip())
            core.log("备注已更新：%s → 「%s」" % (
                core.mask_email(acc.get("email", "")), text.strip()))
            self.refresh_all()

    def on_card_context(self, key: str, pos):
        menu = QMenu(self)
        act_rename = menu.addAction("修改备注名…")
        menu.addSeparator()
        act_delete = menu.addAction("从账号库删除…")
        chosen = menu.exec(pos)
        if chosen is act_rename:
            self.on_card_double(key)
        elif chosen is act_delete:
            accounts = {a["key"]: a for a in core.list_accounts()}
            acc = accounts.get(key)
            if not acc:
                return
            if QMessageBox.question(
                self, "删除账号",
                "确定要把账号 %s 从账号库移除吗？\n\n"
                "（只删除账号库里的副本，不影响 Codex 当前正在使用的账号）"
                % core.mask_email(acc.get("email", "")),
            ) == QMessageBox.Yes:
                core.delete_account(key)
                core.log("已从账号库移除：%s" % core.mask_email(acc.get("email", "")))
                if self.selected_key == key:
                    self.selected_key = ""
                self.refresh_all()

    # ---------------- 导入 ----------------

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Codex 配置文件",
            str(Path.home() / "Downloads"),
            "JSON 文件 (*.json);;所有文件 (*.*)",
        )
        if path:
            self.import_file(path)

    def import_file(self, path: str):
        try:
            self.setCursor(Qt.WaitCursor)
            parsed = core.parse_config_file(path)
        except core.ButlerError as e:
            core.log("导入失败：%s（%s）" % (Path(path).name, str(e).splitlines()[0]))
            self.refresh_log()
            QMessageBox.warning(self, "导入失败", str(e))
            return
        except Exception as e:
            QMessageBox.warning(self, "导入失败", "发生意外错误：%s" % e)
            return
        finally:
            self.setCursor(Qt.ArrowCursor)

        target_key = core._account_key(parsed.get("account_id", ""), parsed.get("email", ""))
        existing = None
        for a in core.list_accounts():
            if a.get("key") == target_key:
                existing = a
                break
        if existing:
            if QMessageBox.question(
                self, "更新账号",
                "账号 %s 已在账号库中。\n\n是否用本次文件更新它的凭据？"
                % core.mask_email(parsed.get("email", "")),
            ) != QMessageBox.Yes:
                return

        meta = core.save_account(parsed)
        core.log("导入成功：%s（%s · %s）" % (
            core.mask_email(meta.get("email", "")),
            parsed.get("source_type", ""), Path(path).name))

        tip = (
            "导入成功！\n\n账号：%s\n格式：%s\n令牌：access / refresh / id_token 齐全"
            % (core.mask_email(parsed.get("email", "")), parsed.get("source_type", ""))
        )
        if parsed.get("found_accounts", 1) > 1:
            tip += "\n\n（该文件包含 %d 个账号，已导入第 1 个）" % parsed["found_accounts"]
        QMessageBox.information(self, "导入成功", tip)

        self.selected_key = meta["key"]
        self.refresh_all()

    # ---------------- 切换 / 还原 ----------------

    def _ensure_app_closed(self) -> bool:
        """确保 Codex 应用已关闭。返回 True=继续，False=用户取消。"""
        while True:
            procs = core.detect_codex_processes()
            if not procs:
                return True
            box = QMessageBox(self)
            box.setWindowTitle("建议先关闭 Codex 应用")
            box.setIcon(QMessageBox.Warning)
            box.setText(
                "检测到 Codex 相关进程正在运行：\n\n%s\n\n"
                "为保证切换生效，请先完全退出 Codex 应用。\n"
                "（如果已经关闭，可点击「重新检测」）" % "、".join(procs)
            )
            b_retry = box.addButton("重新检测", QMessageBox.AcceptRole)
            b_force = box.addButton("仍要继续", QMessageBox.DestructiveRole)
            box.addButton("取消", QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is b_retry:
                continue
            if clicked is b_force:
                return True
            return False

    def on_switch(self):
        if not self.selected_key:
            QMessageBox.information(self, "提示", "请先在列表中点击选中要切换到的账号。")
            return
        accounts = {a["key"]: a for a in core.list_accounts()}
        target = accounts.get(self.selected_key)
        if not target:
            QMessageBox.warning(self, "提示", "选中的账号不存在，请下拉刷新后重试。")
            return

        if target.get("account_id") and target["account_id"] == core.current_account_id():
            QMessageBox.information(self, "提示", "该账号就是当前使用中的账号，无需切换。")
            return

        if not self._ensure_app_closed():
            return

        confirm = "即将切换到：\n\n%s\n%s\n\n当前账号会自动备份，之后可随时「还原上一次」。" % (
            target.get("note", ""), core.mask_email(target.get("email", "")))
        if QMessageBox.question(self, "确认切换", confirm) != QMessageBox.Yes:
            return

        try:
            self.setCursor(Qt.WaitCursor)
            result = core.switch_to_account(self.selected_key)
        except core.ButlerError as e:
            core.log("切换失败：%s" % str(e).splitlines()[0])
            self.refresh_log()
            QMessageBox.critical(self, "切换失败", str(e))
            return
        finally:
            self.setCursor(Qt.ArrowCursor)

        backup_name = Path(result["backup_dir"]).name if result["backup_dir"] else "无"
        core.log("已切换到 %s（原账号已备份：%s）" % (
            core.mask_email(target.get("email", "")), backup_name))
        self.refresh_all()

        box = QMessageBox(self)
        box.setWindowTitle("切换成功")
        box.setIcon(QMessageBox.Information)
        box.setText(
            "已切换到：\n\n%s\n%s\n\n"
            "原账号已备份，随时可以「还原上一次」。\n"
            "如果 Codex 应用正开着，请重启它后再使用。"
            % (target.get("note", ""), core.mask_email(target.get("email", "")))
        )
        b_open = box.addButton("打开 Codex 应用", QMessageBox.AcceptRole)
        box.addButton("关闭", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is b_open:
            if not core.launch_codex_app():
                QMessageBox.information(self, "提示", "无法自动打开，请手动打开 Codex 应用。")

    def on_restore(self):
        backups = core.list_backups()
        if not backups:
            QMessageBox.information(self, "提示", "还没有可用的备份（先进行一次切换才会有备份）。")
            return
        latest = backups[0]
        desc = (
            "将恢复到最近一次切换前的账号：\n\n"
            "备份时间：%s\n账号：%s"
            % (latest.get("backed_up_at", latest.get("name", "")),
               core.mask_email(latest.get("email", "")))
        )
        box = QMessageBox(self)
        box.setWindowTitle("还原上一次")
        box.setIcon(QMessageBox.Question)
        box.setText(desc + "\n\n继续吗？")
        b_yes = box.addButton("确认还原", QMessageBox.AcceptRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not b_yes:
            return

        if not self._ensure_app_closed():
            return

        try:
            self.setCursor(Qt.WaitCursor)
            result = core.restore_latest_backup()
        except core.ButlerError as e:
            core.log("还原失败：%s" % str(e).splitlines()[0])
            self.refresh_log()
            QMessageBox.critical(self, "还原失败", str(e))
            return
        finally:
            self.setCursor(Qt.ArrowCursor)

        core.log("已还原到备份 %s（账号 %s）" % (
            result.get("name", ""), core.mask_email(result.get("email", ""))))
        self.refresh_all()
        QMessageBox.information(
            self, "还原完成",
            "已恢复为：\n\n%s\n\n请重启 Codex 应用后使用。" % core.mask_email(result.get("email", "")))

    # ---------------- 拖拽 ----------------

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            for u in e.mimeData().urls():
                f = u.toLocalFile()
                if f and f.lower().endswith(".json"):
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            f = u.toLocalFile()
            if f and f.lower().endswith(".json"):
                self.import_file(f)
                break


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE_SHEET)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    core.ensure_dirs()
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
