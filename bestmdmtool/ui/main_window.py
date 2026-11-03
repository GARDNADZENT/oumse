"""Main application window for BestMDMTool.

Layout follows the OumseGSM workspace: a tall tool list on the left, the
operations for the selected tool in the middle, and the live page with its
action strip and console on the right. The title bar carries the local session
card, the language switch and the clock.
"""

from __future__ import annotations

import re
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Any

from servicecore.adb import find_adb, find_fastboot

from .. import applog
from . import theme
from .controller import Controller
from .i18n import LANGUAGE_LABELS, LANGUAGES, normalize, t
from .pages import PAGES
from .pages.notice import NoticePage
from .sections import (
    QUICK_ACTIONS,
    SECTIONS_BY_KEY,
    VISIBLE_SECTIONS,
    Section,
    sections_for_group,
)
from .widgets import ActionButton, LogConsole

# Kept for callers that still want the page -> English label map.
NAV_LABELS = {
    "dashboard": "Dashboard",
    "partitions": "Partition Manager",
    "flasher": "Firmware Flasher",
    "advanced": "Advanced Tools",
    "bootloader": "Bootloader",
    "adb": "ADB & Fastboot",
    "spd": "SPD Toolkit",
    "pac": "SPD Firmware",
    "diag": "SPD DIAG",
    "chipsets": "Chipsets",
    "settings": "Settings",
    "about": "About",
}

NOTICE_PAGES = {
    "mdm": "notice.mdm.body",
    "bypass": "notice.bypass.body",
    "permanent": "notice.permanent.body",
    "frp": "notice.frp.body",
    "no_adb_off": "notice.adb_disable.body",
}

CARD_TITLES = {
    "partitions": "Partitions",
    "bootloader": "Bootloader",
    "spd": "SPD partitions",
    "diag": "DIAG console",
    "pac": "PAC firmware",
    "adb": "ADB & Fastboot",
    "dashboard": "Device overview",
    "flasher": "Firmware flasher",
    "advanced": "Advanced tools",
    "chipsets": "Chipset database",
    "settings": "Settings",
    "about": "About",
}

TICK_GUARD = 0.6  # seconds; stops the headless stub from recursing forever


class MainWindow(tk.Tk):
    """Shell: tool list + operations + workspace, with a shared console."""

    def __init__(
        self,
        *,
        product_name: str,
        product_title: str,
        product_version: str,
        product_subtitle: str,
        authorized_use: str,
    ) -> None:
        super().__init__()
        self.product_name = product_name
        self.product_version = product_version
        self.authorized_use = authorized_use
        self.product_subtitle = product_subtitle

        self.title(product_title)
        self.configure(bg=theme.BG)
        self.geometry("1280x840")
        self.minsize(1120, 760)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        theme.configure_theme(self)
        self.shell_chrome = True
        self._started_at = time.time()
        self._last_tick = 0.0
        self._nav_rows: dict[str, tk.Frame] = {}
        self._pages: dict[str, Any] = {}
        self._quick_row: tk.Frame | None = None
        self._current = ""
        self._active_section = ""
        self._log_visible = True
        self._static_labels: list[tuple[tk.Misc, str]] = []

        self.controller = Controller(
            log=self.log,
            on_device=self._on_device,
            on_disconnect=self._on_disconnect,
            on_progress=self._on_progress,
            on_busy=self._on_busy,
            schedule=self._ui_call,
        )
        self.controller.bind_scheduler(self.after, self.after_cancel)
        self.language = normalize(getattr(self.controller.settings, "language", "en"))

        self._build_ui()
        self._restore_window_state()
        self._apply_language(save=False)
        self.show_section("partitions")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._startup_diagnostics)
        self.after(400, self._tick)
        self.bind("<F5>", lambda _event: self.controller.refresh_partitions(self._on_partitions_refreshed))
        self.bind("<Control-l>", lambda _event: self._clear_log())
        for index, section in enumerate(VISIBLE_SECTIONS[:9], start=1):
            self.bind(
                "<Control-Key-%d>" % index,
                lambda _event, key=section.key: self.show_section(key),
            )

    # -- construction ------------------------------------------------------
    def _build_ui(self) -> None:
        self._build_header()
        self._build_footer()
        self._build_body()

    def _label(self, master: tk.Misc, key: str, **kwargs) -> tk.Label:
        """Create a label whose text follows the selected language."""

        widget = tk.Label(master, text=t(key, self.language), **kwargs)
        self._static_labels.append((widget, key))
        return widget

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=theme.PANEL, height=92)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=theme.PANEL)
        brand.pack(side="left", padx=(18, 12), pady=16)
        title_row = tk.Frame(brand, bg=theme.PANEL)
        title_row.pack(anchor="w")
        tk.Label(
            title_row,
            text="●",
            bg=theme.PANEL,
            fg=theme.ACCENT,
            font=("Segoe UI", 15),
        ).pack(side="left", padx=(0, 9))
        tk.Label(
            title_row,
            text=self.product_name,
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.FONT_TITLE,
        ).pack(side="left")
        tk.Label(
            title_row,
            text=self.product_version,
            bg=theme.PANEL_ALT,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            padx=7,
            pady=3,
        ).pack(side="left", padx=(10, 0))
        self.subtitle_label = tk.Label(
            brand,
            text=self.product_subtitle,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=(3, 0))

        # -- local session card -------------------------------------------
        card = tk.Frame(
            header,
            bg=theme.PANEL_ALT,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            padx=14,
            pady=8,
        )
        card.pack(side="left", padx=(4, 12), pady=14)

        top = tk.Frame(card, bg=theme.PANEL_ALT)
        top.pack(anchor="w")
        tk.Label(top, text="●", bg=theme.PANEL_ALT, fg=theme.SUCCESS, font=("Segoe UI", 10)).pack(
            side="left", padx=(0, 7)
        )
        self.session_title = self._label(
            top,
            "app.session",
            bg=theme.PANEL_ALT,
            fg=theme.TEXT,
            font=theme.FONT_UI_BOLD,
        )
        self.session_title.pack(side="left")
        self.badge = self._label(
            top,
            "app.unlimited",
            bg=theme.ACCENT_DIM,
            fg=theme.ACCENT,
            font=theme.FONT_BADGE,
            padx=7,
            pady=1,
        )
        self.badge.pack(side="left", padx=(10, 0))

        bottom = tk.Frame(card, bg=theme.PANEL_ALT)
        bottom.pack(anchor="w", pady=(4, 0))
        self.session_detail = tk.Label(
            bottom,
            text="",
            bg=theme.PANEL_ALT,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            anchor="w",
        )
        self.session_detail.pack(side="left")
        self.uptime_label = tk.Label(
            bottom,
            text="00:00:00",
            bg=theme.PANEL_ALT,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            padx=8,
        )
        self.uptime_label.pack(side="left")

        # -- right hand controls ------------------------------------------
        right = tk.Frame(header, bg=theme.PANEL)
        right.pack(side="right", padx=(10, 16), pady=14)

        clock = tk.Frame(
            right,
            bg=theme.PANEL_ALT,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            padx=14,
            pady=6,
        )
        clock.pack(side="right")
        self.clock_time = tk.Label(
            clock, text="--:--:--", bg=theme.PANEL_ALT, fg=theme.TEXT, font=("Segoe UI Semibold", 14)
        )
        self.clock_time.pack(anchor="e")
        self.clock_date = tk.Label(
            clock, text="", bg=theme.PANEL_ALT, fg=theme.TEXT_DIM, font=theme.FONT_BADGE
        )
        self.clock_date.pack(anchor="e")

        self.notes_button = ActionButton(
            right, "≡", self._note, variant="ghost", font=theme.FONT_UI, width=3
        )
        self.notes_button.pack(side="right", padx=(6, 10))
        self.theme_button = ActionButton(
            right, "☀", self._toggle_density, variant="ghost", font=theme.FONT_UI, width=3
        )
        self.theme_button.pack(side="right", padx=6)

        language_group = tk.Frame(right, bg=theme.PANEL)
        language_group.pack(side="right", padx=(0, 8))
        self._language_buttons: dict[str, ActionButton] = {}
        for code in LANGUAGES:
            button = ActionButton(
                language_group,
                LANGUAGE_LABELS[code],
                lambda target=code: self.set_language(target),
                variant="ghost",
                font=theme.FONT_BADGE,
                width=3,
            )
            button.pack(side="left", padx=2)
            self._language_buttons[code] = button

        self.btn_disconnect = ActionButton(
            right, t("app.disconnect", self.language), self.disconnect_device, variant="ghost"
        )
        self.btn_disconnect.pack(side="right", padx=(0, 8))
        self.btn_disconnect.configure(state="disabled")
        self.btn_connect = ActionButton(
            right, t("app.connect", self.language), self.connect_device, variant="accent"
        )
        self.btn_connect.pack(side="right", padx=(0, 8))

        tk.Frame(self, bg=theme.BORDER, height=1).pack(side="top", fill="x")

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=theme.BG)
        body.pack(side="top", fill="both", expand=True, padx=12, pady=12)

        # -- tool list ----------------------------------------------------
        self.nav = tk.Frame(
            body,
            bg=theme.SIDE,
            width=248,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)
        self._build_nav()

        # -- operations ---------------------------------------------------
        ops = tk.Frame(
            body,
            bg=theme.PANEL,
            width=300,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        ops.pack(side="left", fill="y", padx=12)
        ops.pack_propagate(False)
        self.ops_title = self._label(
            ops,
            "app.ops_mtk",
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_BADGE,
            anchor="w",
        )
        self.ops_title.pack(fill="x", padx=16, pady=(16, 8))
        self.ops_body = tk.Frame(ops, bg=theme.PANEL)
        self.ops_body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # -- workspace ----------------------------------------------------
        self.work = tk.Frame(
            body,
            bg=theme.PANEL,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        self.work.pack(side="left", fill="both", expand=True)
        self._build_work()

    def _build_nav(self) -> None:
        self._nav_rows.clear()
        for child in list(self._nav_inner_children()):
            child.destroy()
        for group, title_key in (("tools", "app.tools"), ("workspace", "app.workspace")):
            heading = self._label(
                self.nav,
                title_key,
                bg=theme.SIDE,
                fg=theme.TEXT_DIM,
                font=theme.FONT_BADGE,
                anchor="w",
            )
            heading.pack(fill="x", padx=16, pady=(12, 4))
            for section in sections_for_group(group):
                self._nav_rows[section.key] = self._make_nav_row(section)

    def _nav_inner_children(self) -> list[Any]:
        try:
            return list(self.nav.winfo_children())
        except TypeError:  # pragma: no cover - headless stub
            return []

    def _make_nav_row(self, section: Section) -> tk.Frame:
        row = tk.Frame(self.nav, bg=theme.SIDE, cursor="hand2")
        row.pack(fill="x", padx=(0, 8), pady=1)
        bar = tk.Frame(row, bg=theme.SIDE, width=3)
        bar.pack(side="left", fill="y")
        chevron = tk.Label(
            row, text="▸", bg=theme.SIDE, fg=theme.TEXT_DIM, font=("Segoe UI", 8), padx=8
        )
        chevron.pack(side="left")
        label = tk.Label(
            row,
            text=t(section.label, self.language),
            bg=theme.SIDE,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_NAV,
            anchor="w",
            justify="left",
            wraplength=214,
            padx=2,
            pady=6,
            cursor="hand2",
        )
        label.pack(side="left", fill="x", expand=True)
        row._bar = bar  # type: ignore[attr-defined]
        row._text = label  # type: ignore[attr-defined]
        row._chevron = chevron  # type: ignore[attr-defined]
        row._label_key = section.label  # type: ignore[attr-defined]

        def _enter(_event=None) -> None:
            if self._active_section != section.key:
                for widget in (row, bar, chevron):
                    widget.configure(bg=theme.PANEL_ALT)
                label.configure(bg=theme.PANEL_ALT, fg=theme.TEXT)

        def _leave(_event=None) -> None:
            if self._active_section != section.key:
                for widget in (row, bar, chevron):
                    widget.configure(bg=theme.SIDE)
                label.configure(bg=theme.SIDE, fg=theme.TEXT_MUTED)

        for widget in (row, label, chevron):
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)
            widget.bind("<Button-1>", lambda _event, key=section.key: self.show_section(key))
        return row

    def _build_work(self) -> None:
        head = tk.Frame(self.work, bg=theme.PANEL)
        head.pack(fill="x", padx=16, pady=(14, 10))
        titles = tk.Frame(head, bg=theme.PANEL)
        titles.pack(side="left", fill="x", expand=True)
        self.card_title = tk.Label(
            titles, text="", bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT_SUBTITLE, anchor="w"
        )
        self.card_title.pack(fill="x")
        self.card_sub = tk.Label(
            titles,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="w",
            justify="left",
        )
        self.card_sub.pack(fill="x", pady=(2, 0))

        self.btn_select_all = ActionButton(
            head, t("app.select_all", self.language), self._select_all, variant="ghost"
        )
        self.btn_select_all.pack(side="right", padx=(6, 0))
        self.btn_select_none = ActionButton(
            head, t("app.select_none", self.language), self._select_none, variant="ghost"
        )
        self.btn_select_none.pack(side="right", padx=(6, 0))

        tk.Frame(self.work, bg=theme.BORDER, height=1).pack(fill="x")

        self.page_container = tk.Frame(self.work, bg=theme.PANEL)
        self.page_container.pack(fill="both", expand=True, padx=2, pady=(2, 0))

        # Every page is built once and raised on demand.
        for key, page_class in PAGES.items():
            page = page_class(self.page_container, self)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._pages[key] = page
        for name, body_key in NOTICE_PAGES.items():
            section = SECTIONS_BY_KEY.get(name)
            page = NoticePage(
                self.page_container,
                self,
                body_key=body_key,
                alt=section.alt if section else None,
            )
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._pages["notice:" + name] = page

        tk.Frame(self.work, bg=theme.BORDER, height=1).pack(fill="x", pady=(6, 0))
        self._quick_row = tk.Frame(self.work, bg=theme.PANEL)
        self._quick_row.pack(fill="x", padx=12, pady=(10, 8))

        progress_row = tk.Frame(self.work, bg=theme.PANEL)
        progress_row.pack(fill="x", padx=14, pady=(0, 8))
        self.progress = ttk.Progressbar(
            progress_row, style="Svc.Horizontal.TProgressbar", mode="determinate", length=240
        )
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = tk.Label(
            progress_row, text="", bg=theme.PANEL, fg=theme.TEXT_DIM, font=theme.FONT_BADGE
        )
        self.progress_label.pack(side="right", padx=(8, 0))

        self.console = LogConsole(self.work, height=7, minimal=True)
        self.console.pack(fill="x", padx=12, pady=(0, 12))

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=theme.PANEL, height=40)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(self, bg=theme.BORDER, height=1).pack(side="bottom", fill="x")

        tk.Label(footer, text="●", bg=theme.PANEL, fg=theme.ACCENT, font=("Segoe UI", 11)).pack(
            side="left", padx=(16, 6)
        )
        self.status_label = tk.Label(
            footer,
            text=t("app.ready", self.language),
            bg=theme.PANEL,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_UI_SMALL,
            anchor="w",
        )
        self.status_label.pack(side="left", pady=8)

        self.stop_button = ActionButton(
            footer, "■  " + t("app.stop", self.language), self.stop_all, variant="danger"
        )
        self.stop_button.pack(side="right", padx=14, pady=7)

        self.log_toggle = ActionButton(
            footer, "▤", self.toggle_log, variant="ghost", font=theme.FONT_BADGE, width=3
        )
        self.log_toggle.pack(side="right", padx=6, pady=7)

        self.env_label = tk.Label(
            footer,
            text="checking tools...",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.FONT_BADGE,
            anchor="e",
        )
        self.env_label.pack(side="right", padx=(10, 10))

    # -- language and chrome ----------------------------------------------
    def set_language(self, code: str) -> None:
        """Switch the shell language and remember it for next launch."""

        language = normalize(code)
        if language == self.language:
            return
        self.language = language
        try:
            self.controller.settings.language = language
            self.controller.settings.save()
        except Exception:  # pragma: no cover - settings are optional
            pass
        self._apply_language()

    def _apply_language(self, *, save: bool = True) -> None:
        language = self.language
        for widget, key in self._static_labels:
            try:
                widget.configure(text=t(key, language))
            except Exception:  # pragma: no cover - widget already gone
                pass
        self.btn_connect.configure(text=t("app.connect", language))
        self.btn_disconnect.configure(text=t("app.disconnect", language))
        self.btn_select_all.configure(text=t("app.select_all", language))
        self.btn_select_none.configure(text=t("app.select_none", language))
        self.stop_button.configure(text="■  " + t("app.stop", language))
        for code, button in self._language_buttons.items():
            active = code == language
            button.configure(
                bg=theme.ACCENT if active else theme.PANEL,
                fg=theme.ACCENT_TEXT if active else theme.TEXT_MUTED,
                highlightbackground=theme.ACCENT if active else theme.BORDER,
            )
        for section in VISIBLE_SECTIONS:
            row = self._nav_rows.get(section.key)
            if row is not None:
                row._text.configure(text=t(section.label, language))  # type: ignore[attr-defined]
        self._render_ops(self._current_section())
        self._render_card_header(self._current_section(), self._current)
        if save:
            self._update_session_card()

    def _note(self) -> None:
        settings = self.controller.settings
        self.log(
            "Engine %s · MTK transport %s · SPD transport %s %s"
            % (
                getattr(settings, "engine", "auto").upper(),
                getattr(settings, "transport", "auto"),
                getattr(settings, "spd_transport", "auto"),
                ("· port " + settings.spd_port) if getattr(settings, "spd_port", "") else "",
            ),
            "INFO",
        )
        self.set_status(t("app.ready_line", self.language), "idle")

    def _toggle_density(self) -> None:
        """Collapse or expand the console strip (the sun/moon control)."""

        self.toggle_log()

    # -- operations column -------------------------------------------------
    def _current_section(self) -> Section | None:
        if self._active_section:
            return SECTIONS_BY_KEY.get(self._active_section)
        for section in VISIBLE_SECTIONS:
            if section.page == self._current:
                return section
        return None

    def _render_ops(self, section: Section | None) -> None:
        for child in list(self._ops_children()):
            child.destroy()
        language = self.language
        engine = section.engine if section else ""
        title_key = {"mtk": "app.ops_mtk", "spd": "app.ops_spd"}.get(engine, "app.ops_any")
        self.ops_title.configure(text=t(title_key, language))

        if section is None:
            tk.Label(
                self.ops_body,
                text=t("app.no_tool", language),
                bg=theme.PANEL,
                fg=theme.TEXT_DIM,
                font=theme.FONT_BADGE,
                wraplength=250,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=4, pady=8)
            return

        if section.notice:
            tk.Label(
                self.ops_body,
                text=t(section.note, language) if section.note else "",
                bg=theme.PANEL,
                fg=theme.TEXT_MUTED,
                font=theme.FONT_UI_SMALL,
                wraplength=248,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=4, pady=(4, 12))
            if section.alt:
                alt_key, alt_section = section.alt
                ActionButton(
                    self.ops_body,
                    t("notice.open_instead", language) % t(alt_key, language),
                    lambda key=alt_section: self.show_section(key),
                    variant="accent",
                ).pack(fill="x", pady=4)
            return

        for op in section.ops:
            if op.kind == "group":
                tk.Label(
                    self.ops_body,
                    text="— %s —" % t(op.label, language),
                    bg=theme.PANEL,
                    fg=theme.TEXT_DIM,
                    font=theme.FONT_BADGE,
                ).pack(fill="x", pady=(12, 6))
                continue
            if op.kind == "primary":
                button = ActionButton(
                    self.ops_body,
                    t(op.label, language),
                    (lambda action=op.action: action(self)) if op.action else None,
                    variant="accent",
                    font=theme.FONT_UI,
                )
                button.pack(fill="x", pady=(2, 8), ipady=6)
                continue
            button = ActionButton(
                self.ops_body,
                t(op.label, language),
                (lambda action=op.action: action(self)) if op.action else None,
                variant="outline",
                font=theme.FONT_UI_SMALL,
            )
            button.pack(fill="x", pady=3, ipady=3)

    def _ops_children(self) -> list[Any]:
        try:
            return list(self.ops_body.winfo_children())
        except TypeError:  # pragma: no cover - headless stub
            return []

    # -- workspace ---------------------------------------------------------
    def _render_card_header(self, section: Section | None, page_key: str) -> None:
        if section is not None and section.notice:
            title = t("notice.title", self.language)
        else:
            title = CARD_TITLES.get(page_key, page_key.replace("notice:", "").title())
        self.card_title.configure(text=title)
        page = self._pages.get(page_key)
        description = getattr(page, "description", "") or ""
        self.card_sub.configure(text=description)

    def _render_quick_actions(self, page_key: str) -> None:
        if self._quick_row is None:
            return
        for child in self._quick_children():
            child.destroy()
        actions = QUICK_ACTIONS.get(page_key)
        if not actions:
            tk.Label(
                self._quick_row,
                text=t("app.no_tool", self.language),
                bg=theme.PANEL,
                fg=theme.TEXT_DIM,
                font=theme.FONT_BADGE,
            ).pack(side="left")
            return
        for label_key, action, variant in actions:
            button = ActionButton(
                self._quick_row,
                t(label_key, self.language),
                lambda act=action: act(self),
                variant=variant,
                font=theme.FONT_UI_SMALL,
            )
            button.pack(side="left", fill="x", expand=True, padx=3, ipady=4)

    def _quick_children(self) -> list[Any]:
        try:
            return list(self._quick_row.winfo_children())
        except TypeError:  # pragma: no cover - headless stub
            return []

    def _selected_tree(self):
        page = self._pages.get(self._current)
        tree = getattr(page, "tree", None)
        return tree if tree is not None and hasattr(tree, "selection_set") else None

    def _select_all(self) -> None:
        tree = self._selected_tree()
        if tree is None:
            self.log("This page has no list to select.", "DEBUG")
            return
        try:
            items = tree.get_children()
            if items:
                tree.selection_set(items)
        except Exception as exc:
            self.log("Could not select rows: %s" % exc, "WARN")

    def _select_none(self) -> None:
        tree = self._selected_tree()
        if tree is None:
            self.log("This page has no list to select.", "DEBUG")
            return
        try:
            tree.selection_remove(tree.selection())
        except Exception as exc:
            self.log("Could not clear the selection: %s" % exc, "WARN")

    # -- page handling -----------------------------------------------------
    def show_page(self, key: str) -> None:
        self._show(key, None)

    def show_section(self, key: str) -> None:
        section = SECTIONS_BY_KEY.get(key)
        if section is None:
            return
        self._show(section.page, section)

    def _show(self, page_key: str, section: Section | None) -> None:
        if page_key not in self._pages:
            return
        self._current = page_key
        if section is None:
            for candidate in VISIBLE_SECTIONS:
                if candidate.page == page_key:
                    section = candidate
                    break
        self._active_section = section.key if section is not None else ""
        self._pages[page_key].tkraise()
        self._paint_nav()
        self._render_ops(section)
        self._render_card_header(section, page_key)
        self._render_quick_actions(page_key)
        page = self._pages[page_key]
        if hasattr(page, "on_show"):
            page.on_show()

    def _paint_nav(self) -> None:
        for key, row in self._nav_rows.items():
            active = key == self._active_section
            background = theme.ACCENT if active else theme.SIDE
            foreground = theme.ACCENT_TEXT if active else theme.TEXT_MUTED
            row.configure(bg=background)
            row._bar.configure(bg=theme.ACCENT if active else theme.SIDE)  # type: ignore[attr-defined]
            row._chevron.configure(  # type: ignore[attr-defined]
                bg=background, fg=theme.ACCENT_TEXT if active else theme.TEXT_DIM
            )
            row._text.configure(bg=background, fg=foreground, font=(  # type: ignore[attr-defined]
                "Segoe UI Semibold" if active else "Segoe UI", 8
            ))

    # -- shared services for pages ----------------------------------------
    def log(self, message: str, level: str = "INFO") -> None:
        self.console.write(message, level)
        applog.record(message, level)

    def set_status(self, text: str, kind: str = "idle") -> None:
        colors = {
            "idle": theme.TEXT_MUTED,
            "ok": theme.SUCCESS,
            "busy": theme.INFO,
            "warn": theme.WARNING,
            "error": theme.DANGER,
        }
        self.status_label.configure(text=text, fg=colors.get(kind, theme.TEXT_MUTED))

    def set_progress(self, value: float, total: float = 0, suffix: str = "") -> None:
        if total > 0:
            self.progress.configure(mode="determinate", maximum=total, value=min(value, total))
            self.progress_label.configure(text="%.0f%% %s" % (100.0 * min(value, total) / total, suffix))
        else:
            self.progress.configure(mode="determinate", maximum=100, value=value % 100)
            self.progress_label.configure(text=suffix)

    def clear_progress(self) -> None:
        self.progress.configure(value=0)
        self.progress_label.configure(text="")

    def toggle_log(self) -> None:
        if self._log_visible:
            self.console.pack_forget()
            self._log_visible = False
        else:
            self.console.pack(fill="x", padx=12, pady=(0, 12))
            self._log_visible = True

    def _clear_log(self) -> None:
        try:
            self.console.clear()
        except Exception:
            pass

    def stop_all(self) -> None:
        """Cancel the running job and close the session."""

        self.log("Stop requested.", "WARN")
        self.set_status("Stopping...", "warn")
        self.clear_progress()
        if self.controller.connected:
            self.controller.disconnect()
        else:
            self.set_status(t("app.ready", self.language), "idle")

    def ask_open(self, title: str, filetypes=None) -> str:
        path = filedialog.askopenfilename(title=title, filetypes=filetypes or [("All files", "*.*")])
        return path or ""

    def ask_save(
        self, title: str, defaultextension: str = "", filetypes=None, initialfile: str = ""
    ) -> str:
        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=defaultextension,
            filetypes=filetypes or [("All files", "*.*")],
            initialfile=initialfile,
        )
        return path or ""

    def ask_directory(self, title: str) -> str:
        path = filedialog.askdirectory(title=title)
        return path or ""

    def ask_dir(self, title: str) -> str:
        path = filedialog.askdirectory(title=title)
        return path or ""

    def confirm(self, title: str, message: str, *, danger: bool = False) -> bool:
        if danger and not self.controller.settings.confirm_destructive:
            return True
        icon = messagebox.WARNING if danger else messagebox.QUESTION
        return bool(messagebox.askokcancel(title, message, icon=icon))

    # -- device lifecycle --------------------------------------------------
    def connect_device(self) -> None:
        settings = self.controller.settings
        self.controller.connect(
            mode=settings.mode,
            transport=settings.transport,
            loader=settings.loader,
            auth=settings.auth,
            debug=settings.debug_log,
            engine=getattr(settings, "engine", "auto"),
            spd_transport=getattr(settings, "spd_transport", "auto"),
            spd_port=getattr(settings, "spd_port", ""),
        )

    def disconnect_device(self) -> None:
        self.controller.disconnect()

    def _on_busy(self, busy: bool, text: str) -> None:
        state = "disabled" if busy else "normal"
        self.btn_connect.configure(state=state)
        self.btn_disconnect.configure(state="normal" if self.controller.connected or busy else "disabled")
        if busy:
            self.set_status(text or "Working...", "busy")
            self.session_detail.configure(text=text or "Working...")
        elif self.controller.connected:
            self.set_status("Idle — session open", "ok")
            self._update_session_card()
        else:
            self.set_status(t("app.ready", self.language), "idle")
            self._update_session_card()
        for page in self._pages.values():
            if hasattr(page, "on_busy"):
                page.on_busy(busy)

    def _update_session_card(self) -> None:
        settings = self.controller.settings
        chosen = str(getattr(settings, "engine", "auto") or "auto").lower()
        # "auto" resolves per device, so show the engine actually in use.
        resolved = str(getattr(self.controller, "engine", "") or "").lower()
        engine = (chosen if chosen in ("mtk", "spd") else (resolved or "auto")).upper()
        device = self.controller.device or {}
        chip = str(device.get("chip") or "")
        parts = len(self.controller.partitions or [])
        language = self.language
        if self.controller.connected and (chip or parts):
            detail = t("app.connected_as", language) % (chip or engine, parts)
        elif self.controller.connected:
            detail = "%s · %s" % (t("app.session_open", language), engine)
        else:
            detail = "%s: %s · %s" % (t("app.engine", language), engine, t("app.no_session", language))
        self.session_detail.configure(text=detail)

    def _on_device(self, device: dict[str, Any]) -> None:
        self.btn_disconnect.configure(state="normal")
        self._update_session_card()
        for page in self._pages.values():
            if hasattr(page, "on_device"):
                page.on_device(device)
        self.set_status("Session open — device ready.", "ok")

    def _on_disconnect(self, reason: str) -> None:
        self.btn_disconnect.configure(state="disabled")
        self.set_status(
            "Connection failed." if reason == "connection failed" else t("app.ready", self.language),
            "error" if reason == "connection failed" else "idle",
        )
        self.clear_progress()
        self._update_session_card()
        for page in self._pages.values():
            if hasattr(page, "on_device"):
                page.on_device({})

    def _on_progress(self, value: int, total: int) -> None:
        if total:
            self.set_progress(value, total)
        else:
            megabytes = value / (1024 * 1024)
            self.progress.configure(value=0)
            self.progress_label.configure(text="%.1f MB" % megabytes)

    def _on_partitions_refreshed(self, partitions) -> None:
        if partitions:
            self.log("Partition table refreshed: %d entries." % len(partitions), "OK")
            self._update_session_card()

    # -- misc --------------------------------------------------------------
    def _ui_call(self, callback: Callable[[], None]) -> None:
        try:
            self.after(0, callback)
        except tk.TclError:
            pass

    def _tick(self) -> None:
        now = time.time()
        self.clock_time.configure(text=time.strftime("%H:%M:%S"))
        self.clock_date.configure(text=time.strftime("%d/%m/%Y"))
        elapsed = int(max(0.0, now - self._started_at))
        hours, rest = divmod(elapsed, 3600)
        minutes, seconds = divmod(rest, 60)
        uptime = "%02d:%02d:%02d" % (hours, minutes, seconds)
        self.uptime_label.configure(text=uptime)
        if now - self._last_tick >= TICK_GUARD:
            self._last_tick = now
            self.after(1000, self._tick)

    def _startup_diagnostics(self) -> None:
        adb = find_adb()
        fastboot = find_fastboot()
        self.env_label.configure(
            text="ADB: %s  ·  Fastboot: %s  ·  %s"
            % (
                "found" if adb else "missing",
                "found" if fastboot else "missing",
                self.controller.settings.mode.upper(),
            )
        )
        self.log("%s %s ready." % (self.product_name, self.product_version), "OK")
        self.log("No login required — opens directly to the device workspace.", "INFO")
        self.log(self.authorized_use, "WARN")
        self._update_session_card()
        # Say what USB looks like right now, so a plugged-in phone is never a
        # silent no-op. The full breakdown lives behind the Connection doctor.
        self.controller.usb_snapshot()

    def _restore_window_state(self) -> None:
        settings = self.controller.settings
        geometry = (getattr(settings, "window_geometry", "") or "").strip()
        if geometry and re.fullmatch(r"\d+x\d+(?:[+-]\d+[+-]\d+)?", geometry):
            try:
                self.geometry(geometry)
            except Exception:
                pass
        if not getattr(settings, "log_expanded", True) and self._log_visible:
            self.toggle_log()

    def _on_close(self) -> None:
        try:
            settings = self.controller.settings
            settings.window_geometry = self.geometry()
            settings.log_expanded = self._log_visible
            settings.language = self.language
            settings.save()
        except Exception:
            pass
        try:
            if self.controller.connected:
                self.controller.disconnect()
        finally:
            self.after(150, self.destroy)
