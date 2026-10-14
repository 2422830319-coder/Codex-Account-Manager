# -*- coding: utf-8 -*-
"""
Codex 账号管家 · 核心逻辑层
- 解析 CPA / Sub2 / 原生 auth.json 配置文件
- 账号库管理（~/.codex-butler/accounts）
- 一键切换（自动备份 + 校验 + 失败回滚）
- 还原（从最近备份恢复）
- Codex 应用进程检测
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "Codex 账号管家"
VERSION = "1.0.0"

HOME = Path.home()
CODEX_DIR = HOME / ".codex"
AUTH_PATH = CODEX_DIR / "auth.json"
BUTLER_DIR = HOME / ".codex-butler"
ACCOUNTS_DIR = BUTLER_DIR / "accounts"
BACKUPS_DIR = BUTLER_DIR / "backups"
LOG_PATH = BUTLER_DIR / "butler.log"


class ButlerError(Exception):
    """面向用户的错误（消息为中文，直接展示）"""


def configure(codex_dir: Path = None, butler_dir: Path = None) -> None:
    """覆盖默认路径（测试或特殊环境用）。"""
    global CODEX_DIR, AUTH_PATH, BUTLER_DIR, ACCOUNTS_DIR, BACKUPS_DIR, LOG_PATH
    if codex_dir:
        CODEX_DIR = Path(codex_dir)
        AUTH_PATH = CODEX_DIR / "auth.json"
    if butler_dir:
        BUTLER_DIR = Path(butler_dir)
        ACCOUNTS_DIR = BUTLER_DIR / "accounts"
        BACKUPS_DIR = BUTLER_DIR / "backups"
        LOG_PATH = BUTLER_DIR / "butler.log"


def ensure_dirs() -> None:
    for d in (BUTLER_DIR, ACCOUNTS_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _utc_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (now.microsecond // 1000)


def log(msg: str) -> None:
    ensure_dirs()
    try:
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write("[%s] %s\n" % (_now_str(), msg))
    except OSError:
        pass


def read_log_tail(lines: int = 200) -> list:
    if not LOG_PATH.exists():
        return []
    try:
        data = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return data[-lines:]
    except OSError:
        return []


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


# ---------------- JWT 解析（只解码 payload，不做签名验证） ----------------

def _jwt_payload(token: str) -> dict:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        obj = json.loads(base64.urlsafe_b64decode(part))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def jwt_email(token: str) -> str:
    pl = _jwt_payload(token)
    prof = pl.get("https://api.openai.com/profile")
    if isinstance(prof, dict) and prof.get("email"):
        return str(prof["email"])
    return ""


def jwt_exp_local(token: str) -> str:
    pl = _jwt_payload(token)
    exp = pl.get("exp")
    if isinstance(exp, (int, float)) and exp > 0:
        try:
            return datetime.fromtimestamp(float(exp)).strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            return ""
    return ""


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email or "（未识别邮箱）"
    user, _, domain = email.partition("@")
    if len(user) <= 3:
        return "%s***@%s" % (user[:1], domain)
    return "%s***@%s" % (user[:3], domain)


def short_id(account_id: str) -> str:
    if not account_id:
        return "—"
    return account_id[:8] + "…" if len(account_id) > 8 else account_id


# ---------------- 配置文件解析 ----------------

def _get_first(obj, keys):
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def parse_config_file(path) -> dict:
    """解析 CPA / Sub2 / 原生 auth.json。

    返回：
      {
        "tokens": {id_token, access_token, refresh_token, account_id?},
        "email": str,
        "account_id": str,
        "source_type": "CPA" | "Sub2" | "原生 auth.json" | ...,
        "expired": str,   # 访问令牌大致到期时间（本地时间提示）
        "found_accounts": int  # 文件里发现的账号数（Sub2 批量导出时 > 1）
      }
    失败抛 ButlerError（中文原因）。
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ButlerError("文件不是有效的 UTF-8 文本，可能不是 JSON 文件。")
    except OSError as e:
        raise ButlerError("读取文件失败：%s" % e)

    try:
        root = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ButlerError("JSON 解析失败（文件可能被截断或有格式错误）：%s" % e)

    if isinstance(root, list):
        if len(root) == 1 and isinstance(root[0], dict):
            root = root[0]
        else:
            raise ButlerError("根节点是数组（多元素），暂不支持，请检查文件格式。")
    if not isinstance(root, dict):
        raise ButlerError("文件结构无法识别：既不是账号对象也不是导出文件。")

    source_type = "未知"
    found_accounts = 1
    entry = root

    accounts = root.get("accounts")
    if isinstance(accounts, list) and accounts:
        entries = [a for a in accounts if isinstance(a, dict)]
        found_accounts = len(entries)
        if not entries:
            raise ButlerError("accounts 列表为空。")
        chosen = None
        for a in entries:
            node = a.get("credentials") if isinstance(a.get("credentials"), dict) else a
            if _get_first(node, ["access_token", "accessToken"]):
                chosen = a
                break
        if chosen is None:
            raise ButlerError("accounts 中未找到包含 access_token 的账号。")
        entry = chosen
        source_type = "Sub2"
    elif isinstance(root.get("tokens"), dict):
        source_type = "原生 auth.json"
    elif isinstance(root.get("credentials"), dict):
        source_type = "Sub2 单账号"
    elif _get_first(root, ["access_token", "accessToken"]):
        source_type = "CPA"
    else:
        raise ButlerError("未识别到 access_token 字段，无法确定文件格式。")

    node = entry.get("tokens")
    if not isinstance(node, dict):
        node = entry.get("credentials")
    if not isinstance(node, dict):
        node = entry

    access = _get_first(node, ["access_token", "accessToken"])
    refresh = _get_first(node, ["refresh_token", "refreshToken"])
    id_token = _get_first(node, ["id_token", "idToken"])
    acct = _get_first(node, ["account_id", "chatgpt_account_id", "chatgptAccountId"])
    if not acct:
        acct = _get_first(entry, ["account_id", "chatgpt_account_id", "chatgptAccountId"])
    if not acct:
        acct = _get_first(root, ["account_id", "chatgpt_account_id", "chatgptAccountId"])

    missing = []
    if not access:
        missing.append("access_token")
    if not refresh:
        missing.append("refresh_token")
    if not id_token:
        missing.append("id_token")
    if missing:
        raise ButlerError(
            "凭据不完整，缺少：%s。\n\n"
            "不完整的文件无法用于 Codex 登录（程序不会伪造缺失字段），\n"
            "请向文件提供方索取完整的授权文件。" % "、".join(missing)
        )
    if not re.match(r"^[^.\s]+\.[^.\s]+\.[^.\s]+$", id_token):
        raise ButlerError("id_token 不是标准的三段式 JWT 结构，文件可能已损坏。")

    email = _get_first(root, ["email"]) or _get_first(entry, ["email"]) or ""
    if not email:
        email = jwt_email(id_token) or jwt_email(access) or ""

    expired = _get_first(root, ["expired"]) or ""
    if not expired:
        expired = jwt_exp_local(access)

    tokens = {"id_token": id_token, "access_token": access, "refresh_token": refresh}
    if acct:
        tokens["account_id"] = acct

    return {
        "tokens": tokens,
        "email": email,
        "account_id": acct or "",
        "source_type": source_type,
        "expired": expired,
        "found_accounts": found_accounts,
    }


# ---------------- 账号库 ----------------

def _account_key(account_id: str, email: str) -> str:
    base = account_id or email or ("acc_" + datetime.now().strftime("%Y%m%d%H%M%S"))
    return re.sub(r"[^0-9a-zA-Z@._-]", "_", base)


def _default_note(email: str, account_id: str) -> str:
    if email and "@" in email:
        return email.split("@")[0]
    return "账号 " + short_id(account_id)


def save_account(parsed: dict, note: str = "") -> dict:
    """把解析结果入库（同账号则更新凭据）。返回 meta 记录。"""
    ensure_dirs()
    key = _account_key(parsed.get("account_id", ""), parsed.get("email", ""))
    auth_file = ACCOUNTS_DIR / (key + ".auth.json")
    meta_file = ACCOUNTS_DIR / (key + ".meta.json")

    auth_json = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": parsed["tokens"],
        "last_refresh": _utc_iso(),
    }
    _atomic_write(auth_file, json.dumps(auth_json, ensure_ascii=False, indent=2))

    meta = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    now = _now_str()
    meta.update({
        "key": key,
        "email": parsed.get("email", ""),
        "account_id": parsed.get("account_id", ""),
        "source_type": parsed.get("source_type", ""),
        "expired_hint": parsed.get("expired", ""),
        "imported_at": meta.get("imported_at", now),
        "updated_at": now,
    })
    if note:
        meta["note"] = note
    elif not meta.get("note"):
        meta["note"] = _default_note(meta["email"], meta["account_id"])
    _atomic_write(meta_file, json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def list_accounts() -> list:
    """列出账号库（按导入时间倒序）。"""
    ensure_dirs()
    out = []
    for m in ACCOUNTS_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
            key = meta.get("key") or m.name[:-len(".meta.json")]
            if not (ACCOUNTS_DIR / (key + ".auth.json")).exists():
                continue
            meta["key"] = key
            out.append(meta)
        except Exception:
            continue
    out.sort(key=lambda x: x.get("imported_at", ""), reverse=True)
    return out


def rename_account(key: str, note: str) -> None:
    meta_file = ACCOUNTS_DIR / (key + ".meta.json")
    if not meta_file.exists():
        raise ButlerError("账号不存在。")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["note"] = note.strip() or meta.get("note", "")
    meta["updated_at"] = _now_str()
    _atomic_write(meta_file, json.dumps(meta, ensure_ascii=False, indent=2))


def delete_account(key: str) -> None:
    for suffix in (".auth.json", ".meta.json"):
        f = ACCOUNTS_DIR / (key + suffix)
        if f.exists():
            f.unlink()


def current_account_id() -> str:
    """读取 .codex/auth.json 当前 account_id（读不到返回空串）。"""
    if not AUTH_PATH.exists():
        return ""
    try:
        d = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
        t = d.get("tokens") or {}
        return t.get("account_id", "") or ""
    except Exception:
        return ""


def verify_auth_file(path: Path) -> bool:
    """校验一个 auth.json 是否可用（结构 + 四件套）。"""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(d, dict) or d.get("auth_mode") != "chatgpt":
        return False
    t = d.get("tokens")
    if not isinstance(t, dict):
        return False
    for k in ("access_token", "refresh_token", "id_token"):
        v = t.get(k)
        if not isinstance(v, str) or not v.strip():
            return False
    return True


# ---------------- 备份 / 切换 / 还原 ----------------

def backup_current_auth(tag: str = "switch") -> str:
    """备份当前 .codex/auth.json 到备份目录。返回备份目录路径（无文件则空串）。"""
    if not AUTH_PATH.exists():
        return ""
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    dest = BACKUPS_DIR / (stamp + "_" + tag)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUTH_PATH, dest / "auth.json")
    meta = {"backed_up_at": _now_str(), "source": str(AUTH_PATH), "tag": tag}
    try:
        d = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
        t = d.get("tokens") or {}
        meta["account_id"] = t.get("account_id", "")
        meta["email"] = jwt_email(t.get("id_token") or t.get("access_token") or "")
    except Exception:
        pass
    _atomic_write(dest / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return str(dest)


def list_backups() -> list:
    if not BACKUPS_DIR.exists():
        return []
    out = []
    for d in BACKUPS_DIR.iterdir():
        if not d.is_dir():
            continue
        auth = d / "auth.json"
        if not auth.exists():
            continue
        meta = {}
        mf = d / "meta.json"
        if mf.exists():
            try:
                meta = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        meta["dir"] = str(d)
        meta["name"] = d.name
        out.append(meta)
    out.sort(key=lambda x: x.get("name", ""), reverse=True)
    return out


def switch_to_account(key: str) -> dict:
    """切换到账号库中的目标账号。

    流程：备份当前 -> 写入目标 -> 校验 -> 失败自动回滚。
    返回 {"backup_dir": str, "target": meta}
    """
    ensure_dirs()
    auth_file = ACCOUNTS_DIR / (key + ".auth.json")
    meta_file = ACCOUNTS_DIR / (key + ".meta.json")
    if not auth_file.exists():
        raise ButlerError("账号库中没有这个账号的文件，请重新导入。")
    if not verify_auth_file(auth_file):
        raise ButlerError("账号库中的该账号文件不完整，请重新导入后再试。")

    target_meta = {}
    if meta_file.exists():
        try:
            target_meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            target_meta = {}

    CODEX_DIR.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_current_auth(tag="before-switch")

    try:
        shutil.copy2(auth_file, AUTH_PATH)
    except Exception as e:
        if backup_dir:
            try:
                shutil.copy2(Path(backup_dir) / "auth.json", AUTH_PATH)
            except Exception:
                pass
        raise ButlerError("写入 auth.json 失败（已回滚原账号）：%s" % e)

    if not verify_auth_file(AUTH_PATH):
        if backup_dir:
            shutil.copy2(Path(backup_dir) / "auth.json", AUTH_PATH)
        raise ButlerError("写入后校验未通过（已回滚原账号）。")

    return {"backup_dir": backup_dir, "target": target_meta}


def restore_latest_backup() -> dict:
    """把最近一次备份恢复到 .codex/auth.json。返回该备份的 meta。"""
    ensure_dirs()
    backups = list_backups()
    if not backups:
        raise ButlerError("还没有任何备份，无法还原。")
    latest = backups[0]
    src = Path(latest["dir"]) / "auth.json"
    if not verify_auth_file(src):
        raise ButlerError("最近一次备份文件不完整，无法还原。")

    prev = AUTH_PATH.read_bytes() if AUTH_PATH.exists() else None
    try:
        CODEX_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, AUTH_PATH)
    except Exception as e:
        if prev is not None:
            try:
                AUTH_PATH.write_bytes(prev)
            except Exception:
                pass
        raise ButlerError("还原失败：%s" % e)

    if not verify_auth_file(AUTH_PATH):
        if prev is not None:
            AUTH_PATH.write_bytes(prev)
        raise ButlerError("还原后校验未通过（已恢复原状态）。")
    return latest


# ---------------- 进程检测 ----------------

_APP_PROCESS_NAMES = {
    "chatgpt.exe",
    "codex.exe",
    "codex-desktop.exe",
    "codex app.exe",
    "openai.codex.exe",
}


def detect_codex_processes() -> list:
    """返回正在运行的 Codex 应用相关进程名（不含沙箱服务等辅助进程）。"""
    names = set()
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line.startswith('"'):
                continue
            name = line.split('"')[1].lower()
            if name in _APP_PROCESS_NAMES:
                names.add(name)
    except Exception:
        return []
    return sorted(names)


def app_running() -> bool:
    return bool(detect_codex_processes())


def launch_codex_app() -> bool:
    """尝试通过 codex:// 协议启动 Codex 桌面应用。"""
    try:
        os.startfile("codex://")
        return True
    except Exception:
        return False


# ---------------- 首次启动的自动导入 ----------------

def bootstrap_import() -> dict:
    """首次运行（账号库为空）时：自动导入当前账号 + 本机历史备份里的账号。

    返回 {"imported": [meta...], "errors": [str...]}
    """
    ensure_dirs()
    imported = []
    errors = []

    sources = []  # (path, note_prefix)
    if AUTH_PATH.exists():
        sources.append((AUTH_PATH, "当前账号"))

    for pat in ("backup-restore-gpt-login/*/auth.json",):
        for f in sorted(CODEX_DIR.glob(pat)):
            sources.append((f, "历史备份"))

    for f in sorted(HOME.glob("codex-emergency-*/auth.json")):
        sources.append((f, "隔离环境"))

    seen = set()
    for path, prefix in sources:
        try:
            parsed = parse_config_file(path)
            aid = parsed.get("account_id", "") or parsed.get("email", "")
            if aid and aid in seen:
                continue
            seen.add(aid)
            meta = save_account(parsed, note="")
            meta["_from"] = prefix
            imported.append(meta)
        except ButlerError as e:
            errors.append("%s：%s" % (Path(path).parent.name, str(e).splitlines()[0]))
        except Exception as e:
            errors.append("%s：%s" % (Path(path).parent.name, e))

    if imported:
        log("首次运行：自动导入 %d 个账号" % len(imported))
    return {"imported": imported, "errors": errors}
