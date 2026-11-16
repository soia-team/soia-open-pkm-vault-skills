from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path

OVERRIDE_CONFIG_NAME = "SOIA_PKM_CLIP_WECHAT_ACCOUNT_CONFIG_FILE"
OVERRIDE_ENV_NAME = "SOIA_PKM_CLIP_GZH_ENV_FILE"
DEFAULT_CONFIG_FILE = "~/.config/soia-skills/soia-pkm-clip-wechat-account/config.yml"

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALIAS_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
PATH_LIKE_KEYS = {
    "OBSIDIAN_VAULT",
    "OBSIDIAN_GZH_OUT",
    "vault",
    "out",
}

ACCOUNT_TO_ENV_KEYS = {
    "app_id": "WECHAT_APP_ID",
    "WECHAT_APP_ID": "WECHAT_APP_ID",
    "app_secret": "WECHAT_APP_SECRET",
    "WECHAT_APP_SECRET": "WECHAT_APP_SECRET",
    "name": "WECHAT_ACCOUNT_NAME",
    "account_name": "WECHAT_ACCOUNT_NAME",
    "WECHAT_ACCOUNT_NAME": "WECHAT_ACCOUNT_NAME",
    "out": "OBSIDIAN_GZH_OUT",
    "OBSIDIAN_GZH_OUT": "OBSIDIAN_GZH_OUT",
    "vault": "OBSIDIAN_VAULT",
    "OBSIDIAN_VAULT": "OBSIDIAN_VAULT",
    "mp_token": "WECHAT_MP_TOKEN",
    "WECHAT_MP_TOKEN": "WECHAT_MP_TOKEN",
    "mp_cookie": "WECHAT_MP_COOKIE",
    "WECHAT_MP_COOKIE": "WECHAT_MP_COOKIE",
    "mp_fakeid": "WECHAT_MP_FAKEID",
    "WECHAT_MP_FAKEID": "WECHAT_MP_FAKEID",
    "biz": "WECHAT_BIZ",
    "WECHAT_BIZ": "WECHAT_BIZ",
    "key": "WECHAT_KEY",
    "WECHAT_KEY": "WECHAT_KEY",
    "pass_ticket": "WECHAT_PASS_TICKET",
    "WECHAT_PASS_TICKET": "WECHAT_PASS_TICKET",
    "appmsg_token": "WECHAT_APPMSG_TOKEN",
    "WECHAT_APPMSG_TOKEN": "WECHAT_APPMSG_TOKEN",
    "cookie": "WECHAT_COOKIE",
    "WECHAT_COOKIE": "WECHAT_COOKIE",
    "uin": "WECHAT_UIN",
    "WECHAT_UIN": "WECHAT_UIN",
}


def _config_home_default() -> Path:
    custom_root = os.environ.get("SOIA_SKILLS_CONFIG_HOME")
    if custom_root:
        return Path(custom_root).expanduser() / "soia-pkm-clip-wechat-account" / "config.yml"
    xdg_root = os.environ.get("XDG_CONFIG_HOME")
    if xdg_root:
        return Path(xdg_root).expanduser() / "soia-skills" / "soia-pkm-clip-wechat-account" / "config.yml"
    return Path(DEFAULT_CONFIG_FILE).expanduser()


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    configured_config = os.environ.get(OVERRIDE_CONFIG_NAME)
    if configured_config:
        paths.append(Path(configured_config).expanduser())
    configured = os.environ.get(OVERRIDE_ENV_NAME)
    if configured:
        paths.append(Path(configured).expanduser())
    paths.append(_config_home_default())
    return paths


def resolve_explicit_config_path(config_file: str) -> Path:
    """Resolve --config path: supports full path or filename inside the skill config dir."""
    raw = Path(config_file).expanduser()
    if raw.is_file():
        return raw
    if not raw.is_absolute() and len(raw.parts) == 1:
        base_dir = _config_home_default().parent
        for candidate in (base_dir / raw.name, base_dir / "accounts" / raw.name):
            if candidate.is_file():
                return candidate
    raise ValueError(f"找不到指定的配置文件：{config_file}")


def find_config_path(config_file: str | None = None) -> Path | None:
    if config_file:
        return resolve_explicit_config_path(config_file)
    return next((p for p in _candidate_paths() if p.is_file()), None)


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if not value or value in {"null", "~"}:
        return ""
    if value[0] in {"'", '"'} and value[-1:] == value[0]:
        inner = value[1:-1]
        if value[0] == "'" or "\\" not in inner:
            return inner
        try:
            # 只在含反斜杠时展开 \n/\t 等转义；latin-1+backslashreplace 往返
            # 保住非 ASCII 字符（直接 utf-8→unicode_escape 会把中文毁成 mojibake）
            return inner.encode("latin-1", "backslashreplace").decode("unicode_escape")
        except UnicodeDecodeError:
            return inner
    return value.split(" #", 1)[0].strip()


def _normalize_value(key: str, raw_val: str) -> str:
    parsed = _parse_scalar(raw_val)
    if key in PATH_LIKE_KEYS and parsed:
        parsed = os.path.expandvars(os.path.expanduser(parsed))
    return parsed


def parse_config_file(path: Path) -> dict[str, object]:
    """Parse minimal YAML subset (`env:`, `default_account:`, `accounts:`, or top-level keys)."""
    env: dict[str, str] = {}
    accounts: dict[str, dict[str, str]] = {}
    default_account: str | None = None
    top_meta: dict[str, str] = {}

    section: str | None = None
    current_alias: str | None = None
    alias_indent: int | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if indent == 0:
            current_alias = None
            alias_indent = None
            if stripped == "env:":
                section = "env"
                continue
            if stripped == "accounts:":
                section = "accounts"
                continue
            section = None
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                k = key.strip()
                parsed = _normalize_value(k, value)
                if k == "default_account":
                    default_account = parsed or None
                elif KEY_RE.match(k):
                    top_meta[k] = parsed
            continue

        if section == "env" and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            if KEY_RE.match(key):
                env[key] = _normalize_value(key, value)
            continue

        if section == "accounts" and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            val_stripped = value.strip()
            if current_alias is None or (alias_indent is not None and indent <= alias_indent):
                if (val_stripped == "" or val_stripped.startswith("#")) and ALIAS_RE.match(key):
                    current_alias = key
                    alias_indent = indent
                    accounts.setdefault(current_alias, {})
                continue
            if current_alias is not None and KEY_RE.match(key):
                accounts[current_alias][key] = _normalize_value(key, value)

    for k, v in top_meta.items():
        env.setdefault(k, v)

    return {
        "env": env,
        "default_account": default_account,
        "accounts": accounts,
        "meta": top_meta,
    }


def _load_config_env(path: Path) -> dict[str, str]:
    parsed = parse_config_file(path)
    return dict(parsed["env"])  # type: ignore[arg-type]


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    return not v or (v.startswith("<") and v.endswith(">")) or v.startswith("YOUR_")


def _profile_to_env(profile: dict[str, str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for src_key, val in profile.items():
        env_key = ACCOUNT_TO_ENV_KEYS.get(src_key)
        if not env_key:
            continue
        cleaned = val.strip()
        if _is_placeholder(cleaned):
            continue
        mapped[env_key] = cleaned
    return mapped


def _configured_routes(env_map: dict[str, str]) -> list[str]:
    routes: list[str] = []
    if env_map.get("WECHAT_APP_ID") and env_map.get("WECHAT_APP_SECRET"):
        routes.append("api")
    if env_map.get("WECHAT_MP_TOKEN") and env_map.get("WECHAT_MP_COOKIE"):
        routes.append("mp")
    if (
        env_map.get("WECHAT_BIZ")
        and env_map.get("WECHAT_KEY")
        and env_map.get("WECHAT_PASS_TICKET")
        and env_map.get("WECHAT_COOKIE")
        and env_map.get("WECHAT_APPMSG_TOKEN")
    ):
        routes.append("cookie")
    return routes


def _is_example_file(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".example.yml") or lower == "example.yml" or lower == "config.example.yml"


def _discover_sidecar_account_files(config_dir: Path) -> dict[str, tuple[Path, dict[str, str]]]:
    """Discover per-account YAML files: `config.<alias>.yml`, `config-<alias>.yml`, `accounts/<alias>.yml`."""
    discovered: dict[str, tuple[Path, dict[str, str]]] = {}
    if not config_dir.is_dir():
        return discovered

    candidates: list[tuple[str, Path]] = []
    for child in sorted(config_dir.iterdir(), key=lambda p: p.name):
        if not child.is_file() or child.suffix.lower() not in {".yml", ".yaml"}:
            continue
        if child.name == "config.yml" or _is_example_file(child.name):
            continue
        stem = child.stem
        alias: str | None = None
        if stem.startswith("config.") and len(stem) > len("config."):
            alias = stem[len("config."):]
        elif stem.startswith("config-") and len(stem) > len("config-"):
            alias = stem[len("config-"):]
        if alias and ALIAS_RE.match(alias):
            candidates.append((alias, child))

    accounts_dir = config_dir / "accounts"
    if accounts_dir.is_dir():
        for child in sorted(accounts_dir.iterdir(), key=lambda p: p.name):
            if not child.is_file() or child.suffix.lower() not in {".yml", ".yaml"} or _is_example_file(child.name):
                continue
            alias = child.stem
            if ALIAS_RE.match(alias):
                candidates.append((alias, child))

    for alias, file_path in candidates:
        parsed = parse_config_file(file_path)
        env_map: dict[str, str] = parsed["env"]  # type: ignore[assignment]
        profile = dict(env_map)
        accounts_map: dict[str, dict[str, str]] = parsed["accounts"]  # type: ignore[assignment]
        if alias in accounts_map:
            profile.update(accounts_map[alias])
        elif len(accounts_map) == 1:
            profile.update(next(iter(accounts_map.values())))
        discovered[alias] = (file_path, profile)

    return discovered


def _collect_all_accounts(
    config_path: Path | None,
    *,
    include_sidecars: bool = True,
) -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str], str | None]:
    env_map: dict[str, str] = {}
    accounts: dict[str, dict[str, str]] = {}
    sources: dict[str, str] = {}
    default_account: str | None = None

    if config_path is not None and config_path.is_file():
        parsed = parse_config_file(config_path)
        env_map = dict(parsed["env"])  # type: ignore[arg-type]
        default_account = parsed["default_account"]  # type: ignore[assignment]
        inline_accounts: dict[str, dict[str, str]] = parsed["accounts"]  # type: ignore[assignment]
        for alias, profile in inline_accounts.items():
            accounts[alias] = dict(profile)
            sources[alias] = f"{config_path.name}#accounts"

    config_dirs: list[Path] = [_config_home_default().parent]
    if config_path is not None and config_path.parent != config_dirs[0]:
        config_dirs.append(config_path.parent)

    if include_sidecars:
        for scan_dir in config_dirs:
            for alias, (side_path, side_profile) in _discover_sidecar_account_files(scan_dir).items():
                if alias in accounts:
                    inline_id = _profile_to_env(accounts[alias]).get("WECHAT_APP_ID", "")
                    side_id = _profile_to_env(side_profile).get("WECHAT_APP_ID", "")
                    if inline_id and side_id and inline_id != side_id:
                        raise ValueError(
                            f"账号 {alias!r} 同时存在于 {sources[alias]} 和 {side_path.name} 且 app_id 冲突，请保留一处。"
                        )
                merged = dict(accounts.get(alias, {}))
                merged.update(side_profile)
                accounts[alias] = merged
                sources[alias] = side_path.name

    return accounts, sources, env_map, default_account


def _match_account(accounts: dict[str, dict[str, str]], selector: str) -> str | None:
    if selector in accounts:
        return selector
    needle = selector.strip().lower()
    matches = []
    for alias, profile in accounts.items():
        candidates = {
            alias.lower(),
            profile.get("wechat_id", "").strip().lower(),
            (profile.get("name") or profile.get("account_name") or profile.get("WECHAT_ACCOUNT_NAME", "")).strip().lower(),
        }
        if needle in candidates:
            matches.append(alias)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"账号标识 {selector!r} 命中多个配置（{', '.join(matches)}），请改用精确 alias。")
    return None


def list_accounts(config_path: Path | None = None, config_file: str | None = None) -> list[dict[str, object]]:
    """Return non-secret metadata for all configured accounts."""
    explicit = config_path is not None or bool(config_file)
    path = config_path or find_config_path(config_file=config_file)
    accounts, sources, _, default_account = _collect_all_accounts(path, include_sidecars=not explicit)
    result: list[dict[str, object]] = []
    for alias, profile in accounts.items():
        env_mapped = _profile_to_env(profile)
        result.append(
            {
                "alias": alias,
                "name": env_mapped.get("WECHAT_ACCOUNT_NAME", ""),
                "wechat_id": profile.get("wechat_id", ""),
                "out": env_mapped.get("OBSIDIAN_GZH_OUT", ""),
                "source": sources.get(alias, ""),
                "is_default": alias == default_account,
                "routes": _configured_routes(env_mapped),
            }
        )
    return result


def load_account_env(
    account: str | None = None,
    config_file: str | None = None,
    config_path: Path | None = None,
) -> tuple[Path | None, str | None]:
    """Load shared env plus selected account overrides into os.environ (fail-closed)."""
    explicit = config_path is not None or bool(config_file)
    path = config_path or find_config_path(config_file=config_file)
    accounts, _, base_env, default_account = _collect_all_accounts(path, include_sidecars=not explicit)

    # 先载入主 config.yml 的共享 env（不覆盖外部显式注入的进程环境变量）
    for key, value in base_env.items():
        if not _is_placeholder(value):
            os.environ.setdefault(key, value)

    if account:
        matched = _match_account(accounts, account) if accounts else None
        if matched is None:
            available = ", ".join(accounts.keys()) if accounts else "无"
            raise ValueError(f"未找到指定公众号账号 {account!r}（已配置 accounts: {available}）。")
        for key, value in _profile_to_env(accounts[matched]).items():
            os.environ[key] = value
        return path, matched

    if explicit and path is not None and not accounts:
        for key, value in _profile_to_env(base_env).items():
            os.environ[key] = value
        return path, path.stem

    if accounts:
        if default_account:
            matched_default = _match_account(accounts, default_account)
            if matched_default is None:
                raise ValueError(
                    f"default_account {default_account!r} 不在 accounts 列表中（可选: {', '.join(accounts.keys())}）。"
                )
            for key, value in _profile_to_env(accounts[matched_default]).items():
                os.environ[key] = value
            return path, matched_default
        if len(accounts) == 1:
            sole_alias = next(iter(accounts))
            for key, value in _profile_to_env(accounts[sole_alias]).items():
                os.environ[key] = value
            return path, sole_alias
        raise ValueError(
            f"检测到多个公众号账号（{', '.join(accounts.keys())}），但未指定 --account / --config 且未设置 default_account。"
        )

    return path, None


def load_private_env(required: bool = False) -> Path | None:
    """Load private config env values without overriding the process environment.

    Secrets must stay outside the vault and outside the open-source skill repo.
    """
    path = find_config_path()
    if path is not None:
        try:
            for key, value in _load_config_env(path).items():
                if not _is_placeholder(value):
                    os.environ.setdefault(key, value)
            return path
        except OSError as exc:
            print(f"⚠️ Could not read private config.yml: {exc}", file=sys.stderr)
    if required:
        checked = ", ".join(str(p) for p in _candidate_paths())
        raise SystemExit(f"Missing private config file. Checked: {checked}")
    return None


def print_accounts(config_file: str | None = None) -> int:
    accounts = list_accounts(config_file=config_file)
    if not accounts:
        print("当前未在 config.yml 或分账号 .yml 中发现命名账号配置（单账号可直接使用 `env:`）。")
        return 0
    print("已配置公众号账号（已脱敏）：")
    for item in accounts:
        default_mark = " [默认]" if item["is_default"] else ""
        routes = ",".join(item["routes"]) if item["routes"] else "未配凭据"
        display = item["name"] or item["alias"]
        wid = f" ({item['wechat_id']})" if item["wechat_id"] else ""
        out_hint = f" -> out={item['out']}" if item["out"] else ""
        src = f" <- {item['source']}" if item.get("source") else ""
        print(f"- {item['alias']}: {display}{wid} [路线: {routes}]{out_hint}{default_mark}{src}")
    return 0


def env_source_hint() -> str:
    return f"{OVERRIDE_CONFIG_NAME}, {OVERRIDE_ENV_NAME}, or {DEFAULT_CONFIG_FILE}"


def main() -> int:
    path = find_config_path()
    if not path:
        return 1
    for key, value in _load_config_env(path).items():
        print(f"export {key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
