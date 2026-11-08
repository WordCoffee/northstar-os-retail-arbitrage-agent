"""Input control with a kill switch that actually stops it.

Work order §2 rule 5 and V7: a visible indicator while Ty holds mouse and keyboard, a
global kill hotkey (default Ctrl+Alt+Shift+Pause), and `state/vision/PAUSE` which, if
present, blocks all control.

The contract is narrow on purpose: every input call goes through `Control.act()`, and
`act()` asks `can_act()` first. A kill switch that only sets a flag somebody else might
check is not a kill switch.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "vision"
PAUSE = STATE / "PAUSE"
INDICATOR = STATE / "indicator.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def paused(*, pause: Optional[Path] = None) -> bool:
    return Path(pause or PAUSE).exists()


class Control:
    """Holds the kill switch, the indicator and the one gate every action passes."""

    def __init__(self, *, pause: Optional[Path] = None,
                 indicator: Optional[Path] = None) -> None:
        self.pause_path = Path(pause or PAUSE)
        self.indicator_path = Path(indicator or INDICATOR)
        self._killed = threading.Event()
        self._listener: Any = None
        self._installed_at = 0.0

    # -- state ------------------------------------------------------------
    def killed(self) -> bool:
        return self._killed.is_set()

    def can_act(self) -> Dict[str, Any]:
        """The only question an input call is allowed to ask."""
        if self._killed.is_set():
            return {"allow": False, "reason": "kill_switch"}
        if paused(pause=self.pause_path):
            return {"allow": False, "reason": "pause_file"}
        return {"allow": True, "reason": ""}

    def act(self, action: Callable[[], Any]) -> Dict[str, Any]:
        verdict = self.can_act()
        if not verdict["allow"]:
            return {"ok": False, "blocked": True, "reason": verdict["reason"]}
        self.indicator(True)
        try:
            return {"ok": True, "result": action()}
        except Exception as exc:  # noqa: BLE001 - an input failure is reported, not hidden
            return {"ok": False, "blocked": False, "error": f"{type(exc).__name__}: {exc}"}
        finally:
            self.indicator(False)

    # -- kill switch ------------------------------------------------------
    def trigger_kill(self) -> Dict[str, Any]:
        self._killed.set()
        self.indicator(False)
        return {"ok": True, "killed": True, "at": _now()}

    def reset(self) -> Dict[str, Any]:
        self._killed.clear()
        return {"ok": True, "killed": False}

    def arm_hotkey(self, hotkey: str = "") -> Dict[str, Any]:
        """Register the global hotkey. Failure is reported, never assumed away."""
        try:
            from pynput import keyboard  # noqa: PLC0415

            if hotkey:
                combo = {part.strip() for part in hotkey.split("+") if part.strip()}
                keys = set()
                for part in combo:
                    low = part.lower()
                    if low in ("ctrl", "control"):
                        keys.add(keyboard.Key.ctrl)
                    elif low == "alt":
                        keys.add(keyboard.Key.alt)
                    elif low == "shift":
                        keys.add(keyboard.Key.shift)
                    elif low in ("pause", "break"):
                        keys.add(keyboard.Key.pause)
                    else:
                        keys.add(keyboard.KeyCode.from_char(part))
                hotkey_obj = keyboard.HotKey(keyboard.HotKey.parse(
                    "+".join("Key.%s" % k.name if hasattr(k, "name") else str(k)
                             for k in keys)), self._on_hotkey)
                self._listener = keyboard.Listener(on_press=hotkey_obj.press,
                                                   on_release=hotkey_obj.release)
                self._listener.start()
            self._installed_at = time.time()
            return {"ok": True, "armed": bool(self._listener), "hotkey": hotkey or "(none)"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "armed": False,
                    "error": f"{type(exc).__name__}: {exc}"}

    def _on_hotkey(self) -> None:
        self.trigger_kill()

    def disarm(self) -> Dict[str, Any]:
        try:
            if self._listener is not None:
                self._listener.stop()
        except Exception:  # noqa: BLE001
            pass
        self._listener = None
        return {"ok": True, "armed": False}

    # -- visible indicator ------------------------------------------------
    def indicator(self, on: bool) -> None:
        self.indicator_path.parent.mkdir(parents=True, exist_ok=True)
        self.indicator_path.write_text(
            json.dumps({"on": bool(on), "at": _now()}, indent=2) + "\n",
            encoding="utf-8")


DEFAULT = Control()
