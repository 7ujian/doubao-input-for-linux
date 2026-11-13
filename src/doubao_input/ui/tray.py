"""系统托盘图标（独立进程：GTK3 + Ayatana AppIndicator）。

为什么是独立进程:
    GTK3 与 GTK4 无法在同一个进程里共存(同一个 Gtk 命名空间只能加载一个
    版本),而主程序是 GTK4。所以这里跑一个轻量 GTK3 子进程,只负责画托盘
    图标和菜单,真正的动作通过 D-Bus 回主程序:

    - 「打开控制面板」-> org.freedesktop.Application.Activate
    - 「最小化到托盘」-> org.gtk.Actions.Activate("hide-panel")
    - 「退出」        -> org.gtk.Actions.Activate("quit")

    GNOME 需要 ubuntu-appindicators / appindicator 扩展才能显示图标;
    没有扩展时本进程照常退出,主程序不受影响(由 app.py 负责降级)。
"""

from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # type: ignore
from gi.repository import Gio, GLib, Gtk  # type: ignore

logger = logging.getLogger("doubao_input.tray")

APP_ID = "com.doubao.Input"
APP_PATH = "/com/doubao/Input"
INDICATOR_ID = "doubao-input"
ICON_THEME_NAME = "doubao-input"
ICON_FALLBACK = "/usr/share/icons/hicolor/128x128/apps/doubao-input.png"
DBUS_TIMEOUT_MS = 2000


def _add_unix_signal(sig: int, callback) -> None:
    """GLib >= 2.74 推荐 GLibUnix.signal_add,老版本回退到 GLib.unix_signal_add。"""
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix  # type: ignore

        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, callback)
    except (ImportError, ValueError):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, callback)


def _resolve_icon() -> str:
    """优先用绝对路径:GNOME Shell 的图标主题缓存可能要等到重新登录才更新,
    而本项目的 launcher 也正因如此用了绝对路径。"""
    if os.path.exists(ICON_FALLBACK):
        return ICON_FALLBACK
    try:
        bundled = Path(__file__).resolve().parent.parent / "resources" / "logo-128.png"
        if bundled.exists():
            return str(bundled)
    except Exception:
        pass
    return ICON_THEME_NAME


def _call(interface: str, method: str, params: GLib.Variant, quiet: bool = False) -> bool:
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            APP_ID,
            APP_PATH,
            interface,
            method,
            params,
            None,
            Gio.DBusCallFlags.NONE,
            DBUS_TIMEOUT_MS,
            None,
        )
        return True
    except Exception as e:
        if not quiet:
            logger.warning("tray: %s.%s failed: %s", interface, method, e)
        return False


def _open_panel() -> None:
    _call(
        "org.freedesktop.Application",
        "Activate",
        GLib.Variant("(a{sv})", ({},)),
    )


def _hide_panel() -> None:
    _call(
        "org.gtk.Actions",
        "Activate",
        GLib.Variant("(sava{sv})", ("hide-panel", GLib.Variant("av", []), {})),
    )


def _quit_app() -> None:
    # 主程序在处理这个请求时就会退出,回复可能来不及发出 —— 超时属正常。
    _call(
        "org.gtk.Actions",
        "Activate",
        GLib.Variant("(sava{sv})", ("quit", GLib.Variant("av", []), {})),
        quiet=True,
    )
    Gtk.main_quit()


def _build_menu() -> Gtk.Menu:
    menu = Gtk.Menu()

    open_item = Gtk.MenuItem(label="打开控制面板")
    open_item.connect("activate", lambda *_: _open_panel())
    menu.append(open_item)

    hide_item = Gtk.MenuItem(label="最小化到托盘")
    hide_item.connect("activate", lambda *_: _hide_panel())
    menu.append(hide_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="退出豆包输入法")
    quit_item.connect("activate", lambda *_: _quit_app())
    menu.append(quit_item)

    menu.show_all()
    return menu


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        indicator = AppIndicator.Indicator.new(
            INDICATOR_ID,
            _resolve_icon(),
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_title("豆包语音输入法")
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        indicator.set_menu(_build_menu())
    except Exception as e:
        logger.warning("tray: indicator unavailable: %s", e)
        return 1

    # 主程序退出/崩溃后自动收掉托盘进程
    def _on_name_vanished(_conn, _name):
        logger.info("tray: app bus name vanished; exiting")
        Gtk.main_quit()

    Gio.bus_watch_name(
        Gio.BusType.SESSION,
        APP_ID,
        Gio.BusNameWatcherFlags.NONE,
        None,
        _on_name_vanished,
    )

    for sig in (signal.SIGINT, signal.SIGTERM):
        _add_unix_signal(sig, lambda *_: Gtk.main_quit())

    logger.info("tray: indicator registered (icon=%s)", _resolve_icon())
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
