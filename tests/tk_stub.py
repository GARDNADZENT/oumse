"""Headless smoke test: build the full UI with a stubbed tkinter.

Tkinter is unavailable in headless CI containers, so this test installs a fake
``tkinter`` module, constructs every page, and drives the main operation paths.
It catches AttributeError/NameError in first-party widget code, which a plain
import check cannot.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


class TclError(Exception):
    pass


class FakeWidget:
    """Minimal tk widget stand-in that also works as a subclass base."""

    def __init__(self, master=None, *args, **kwargs):
        self._master = master
        self._config = dict(kwargs)
        self._kids: list = []

    def __getattr__(self, name):
        mock = MagicMock(name=name)
        setattr(self, name, mock)
        return mock

    def configure(self, **kwargs):
        self._config.update(kwargs)

    def __setitem__(self, key, value):
        self._config[key] = value

    def __getitem__(self, key):
        return self._config.get(key, "normal")


class FakeTk(FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(None, *args, **kwargs)
        self._job = 0

    def after(self, delay, callback=None, *args):
        self._job += 1
        if callback is not None:
            callback()
        return "job%d" % self._job

    def after_cancel(self, job):
        return None

    def mainloop(self, *args, **kwargs):
        return None

    def destroy(self):
        return None


class FakeVar:
    default = ""

    def __init__(self, value=None, *args, **kwargs):
        self._value = self.default if value is None else value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        return "trace"


class FakeBoolVar(FakeVar):
    default = False


class FakeIntVar(FakeVar):
    default = 0


class FakeText(FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._content = ""

    def insert(self, index, text, *tags):
        self._content += text

    def delete(self, *args):
        self._content = ""

    def get(self, *args):
        return self._content


def _module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def install_fake_tkinter() -> None:
    """Install a stub ``tkinter`` package if the real one is missing."""

    try:
        import tkinter  # noqa: F401

        return
    except Exception:
        pass

    widgets = {
        name: FakeWidget
        for name in (
            "Frame",
            "Label",
            "Button",
            "Entry",
            "Canvas",
            "Checkbutton",
            "Radiobutton",
            "Listbox",
            "Scrollbar",
            "LabelFrame",
            "Toplevel",
            "Menu",
        )
    }
    tk = _module(
        "tkinter",
        Tk=FakeTk,
        TclError=TclError,
        StringVar=FakeVar,
        BooleanVar=FakeBoolVar,
        IntVar=FakeIntVar,
        DoubleVar=FakeVar,
        Text=FakeText,
        END="end",
        LEFT="left",
        RIGHT="right",
        TOP="top",
        BOTTOM="bottom",
        BOTH="both",
        X="x",
        Y="y",
        N="n",
        S="s",
        E="e",
        W="w",
        NSEW="nsew",
        HORIZONTAL="horizontal",
        VERTICAL="vertical",
        **widgets,
    )

    class FakeStyle:
        def __init__(self, *args, **kwargs):
            self.options = {}

        def __getattr__(self, name):
            def _call(*args, **kwargs):
                if name == "theme_use":
                    return "clam"
                return None

            return _call

    ttk = _module(
        "tkinter.ttk",
        Style=FakeStyle,
        Treeview=FakeWidget,
        Combobox=FakeWidget,
        Progressbar=FakeWidget,
        Scrollbar=FakeWidget,
        Notebook=FakeWidget,
        Frame=FakeWidget,
        Label=FakeWidget,
        Button=FakeWidget,
        Entry=FakeWidget,
    )
    filedialog = _module(
        "tkinter.filedialog",
        askopenfilename=lambda **kwargs: "/tmp/smoke/image.bin",
        asksaveasfilename=lambda **kwargs: "/tmp/smoke/out.bin",
        askdirectory=lambda **kwargs: "/tmp/smoke/dir",
        askopenfilenames=lambda **kwargs: ("/tmp/smoke/boot.img",),
    )
    messagebox = _module(
        "tkinter.messagebox",
        WARNING="warning",
        QUESTION="question",
        INFO="info",
        ERROR="error",
        askokcancel=lambda *a, **k: True,
        showinfo=lambda *a, **k: None,
        showerror=lambda *a, **k: None,
        showwarning=lambda *a, **k: None,
    )
    scrolledtext = _module("tkinter.scrolledtext", ScrolledText=FakeText)
    simpledialog = _module("tkinter.simpledialog", askstring=lambda *a, **k: "value")

    tk.ttk = ttk
    tk.filedialog = filedialog
    tk.messagebox = messagebox
    tk.scrolledtext = scrolledtext
    tk.simpledialog = simpledialog
    sys.modules["tkinter.ttk"] = ttk
    sys.modules["tkinter.filedialog"] = filedialog
    sys.modules["tkinter.messagebox"] = messagebox
    sys.modules["tkinter.scrolledtext"] = scrolledtext
    sys.modules["tkinter.simpledialog"] = simpledialog
