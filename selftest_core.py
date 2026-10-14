# -*- coding: utf-8 -*-
"""自检脚本：在隔离的临时目录里测试核心逻辑，不触碰真实环境。
所有测试数据均为动态生成的样例，不含任何真实凭据。
运行：python selftest_core.py（需要 PySide6 无关，仅标准库）
"""
import base64
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import core


def make_jwt(payload: dict) -> str:
    """生成一个结构合法（签名段为占位）的测试 JWT。"""
    def seg(d):
        raw = json.dumps(d, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return seg({"alg": "RS256", "typ": "JWT"}) + "." + seg(payload) + ".sig"


tmp = Path(tempfile.mkdtemp(prefix="butler-selftest-"))
codex_dir = tmp / ".codex"
butler_dir = tmp / ".codex-butler"
codex_dir.mkdir(parents=True)

core.configure(codex_dir=codex_dir, butler_dir=butler_dir)
core.ensure_dirs()

print("== 1. 解析样例 CPA 文件 ==")
sample = {
    "type": "codex",
    "email": "sample@example.com",
    "access_token": make_jwt({"sub": "sample", "exp": 2524608000}),
    "refresh_token": "rt.sample.example-value",
    "id_token": make_jwt({
        "sub": "sample",
        "https://api.openai.com/profile": {"email": "sample@example.com"},
    }),
    "account_id": "11111111-2222-3333-4444-555555555555",
    "expired": "2050-01-01T00:00:00+08:00",
}
sample_path = tmp / "sample-cpa.json"
sample_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

parsed = core.parse_config_file(sample_path)
print("   source_type:", parsed["source_type"])
print("   email      :", parsed["email"])
print("   account_id :", parsed["account_id"])
assert parsed["source_type"] == "CPA"
assert parsed["email"] == "sample@example.com"
assert parsed["tokens"]["account_id"] == "11111111-2222-3333-4444-555555555555"
print("   OK")

print("== 2. 入库 ==")
meta1 = core.save_account(parsed)
print("   saved key:", meta1["key"][:16], "...")
assert core.list_accounts()[0]["key"] == meta1["key"]
print("   OK")

print("== 3. 模拟当前账号（另一份样例数据作为切换前状态）==")
fake = {
    "auth_mode": "chatgpt",
    "OPENAI_API_KEY": None,
    "tokens": {
        "id_token": make_jwt({"sub": "old-account"}),
        "access_token": make_jwt({"sub": "old-account", "exp": 2524608000}),
        "refresh_token": "rt.old.example-value",
        "account_id": "00000000-0000-0000-0000-000000000000",
    },
    "last_refresh": "2026-01-01T00:00:00.000Z",
}
core.AUTH_PATH.write_text(json.dumps(fake, ensure_ascii=False, indent=2), encoding="utf-8")
assert core.current_account_id() == "00000000-0000-0000-0000-000000000000"
print("   OK")

print("== 4. 切换账号 ==")
result = core.switch_to_account(meta1["key"])
print("   备份目录:", Path(result["backup_dir"]).name)
assert core.current_account_id() == parsed["account_id"]
assert core.verify_auth_file(core.AUTH_PATH)
print("   OK")

print("== 5. 还原 ==")
latest = core.restore_latest_backup()
assert core.current_account_id() == "00000000-0000-0000-0000-000000000000"
print("   已还原至备份:", latest["name"])
print("   OK")

print("== 6. 邮箱脱敏 ==")
masked = core.mask_email("sample@example.com")
print("  ", masked)
assert masked.startswith("sam") and "***" in masked
print("   OK")

print("== 7. 异常输入测试 ==")
bad = tmp / "bad.json"
bad.write_text("{not-valid-json", encoding="utf-8")
try:
    core.parse_config_file(bad)
    raise SystemExit("   ERROR: 应该抛错但没有")
except core.ButlerError as e:
    print("   正确拒绝(坏JSON):", str(e).splitlines()[0][:50])

bad2 = tmp / "incomplete.json"
bad2.write_text(json.dumps({"access_token": "abc"}), encoding="utf-8")
try:
    core.parse_config_file(bad2)
    raise SystemExit("   ERROR: 应该抛错但没有")
except core.ButlerError as e:
    print("   正确拒绝(缺字段):", str(e).splitlines()[0][:50])

print()
print("全部通过. 临时目录:", tmp)
