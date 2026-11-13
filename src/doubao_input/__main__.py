"""Entry point: `python -m doubao_input`."""
from __future__ import annotations

import logging
import sys

from doubao_input.app import DoubaoInputApp


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # .desktop 的「显示控制窗口」动作会传 --show;Gtk.Application 不认识
    # 这个选项,会以「未知选项 --show」直接退出。这里吞掉它,让
    # GApplication 走默认的 activate 路径(唤起/前置控制面板)。
    # --show 同时意味着「即使开了静默启动也要弹出窗口」。
    argv = [arg for arg in sys.argv if arg != "--show"]
    app = DoubaoInputApp(force_show="--show" in sys.argv)
    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
