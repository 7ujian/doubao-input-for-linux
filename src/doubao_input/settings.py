"""用户偏好：静默启动 + 开机自动启动。

偏好保存在 ``~/.config/doubao-input/settings.json``::

    {"silent_start": false}

开机自启沿用系统的 ``systemd --user`` 服务。注意 ``.deb`` 在
``/etc/systemd/user/*.wants`` 里建的启用链接属于 root,普通用户
``systemctl --user disable`` 删不掉;所以「关闭自启」用用户级的
``mask``(``~/.config/systemd/user/doubao-input.service -> /dev/null``)
覆盖它,「开启」再 ``unmask`` + ``enable``。全程不需要 root。
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from doubao_input.doubao.config import get_config_dir

logger = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"
SERVICE_UNIT = "doubao-input.service"
_SYSTEMCTL_TIMEOUT = 5


@dataclass
class Settings:
    """持久化的用户偏好。"""

    silent_start: bool = False


def get_settings_path() -> Path:
    return get_config_dir() / SETTINGS_FILE


def load_settings() -> Settings:
    path = get_settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except Exception as e:  # 坏 JSON / 权限问题:回退默认值,不阻塞启动
        logger.warning("settings: failed to read %s: %s", path, e)
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    return Settings(silent_start=bool(data.get("silent_start", False)))


def save_settings(settings: Settings) -> bool:
    path = get_settings_path()
    try:
        path.write_text(
            json.dumps({"silent_start": settings.silent_start}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return True
    except Exception as e:
        logger.warning("settings: failed to write %s: %s", path, e)
        return False


def _run_systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        timeout=_SYSTEMCTL_TIMEOUT,
    )


def is_autostart_enabled() -> bool:
    """服务是否为 enabled(mask 时返回 False)。"""
    try:
        result = _run_systemctl("is-enabled", SERVICE_UNIT)
        return result.stdout.strip() == "enabled"
    except Exception as e:
        logger.warning("settings: is-enabled failed: %s", e)
        return False


def set_autostart(enabled: bool) -> bool:
    try:
        if enabled:
            _run_systemctl("unmask", SERVICE_UNIT)
            result = _run_systemctl("enable", SERVICE_UNIT)
        else:
            result = _run_systemctl("mask", SERVICE_UNIT)
        if result.returncode != 0:
            logger.warning(
                "settings: autostart=%s failed: %s",
                enabled,
                (result.stderr or result.stdout).strip(),
            )
            return False
        logger.info("settings: autostart=%s (now %s)", enabled, is_autostart_enabled())
        return True
    except Exception as e:
        logger.warning("settings: autostart=%s failed: %s", enabled, e)
        return False
