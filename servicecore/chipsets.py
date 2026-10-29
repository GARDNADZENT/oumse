"""Chipset database for MediaTek and Spreadtrum/Unisoc devices.

The service workspace shows both families, because the same shop handles both.
The data is deliberately plain (no imports, no I/O at module import) so the UI
can search it and the runner can ship it into a JSON reply.

Fields:

``name``      marketing/part number as printed on the device or box
``family``    grouping shown in the UI (Helio, Dimensity, SC98xx, T-series...)
``vendor``    ``"MTK"`` or ``"SPD"``
``protocol``  ``"brom"`` (MediaTek) or ``"bsl"`` (Spreadtrum)
``usb``       ``(vid, pid)`` pairs that identify the chip in download mode
``notes``     what a technician should expect (loader, DA/SLA, quirks)
"""

from __future__ import annotations

from dataclasses import dataclass

MTK_VID = 0x0E8D
SPD_VID = 0x1782


@dataclass(frozen=True, slots=True)
class Chip:
    name: str
    vendor: str
    family: str
    protocol: str
    usb: tuple[tuple[int, int], ...] = ()
    notes: str = ""
    year: int = 0

    @property
    def display(self) -> str:
        return "%s %s" % (self.vendor, self.name)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "family": self.family,
            "protocol": self.protocol,
            "usb": ["%04X:%04X" % pair for pair in self.usb],
            "notes": self.notes,
            "year": self.year,
        }


def _mtk(name: str, family: str, pids: tuple[int, ...] = (0x0003, 0x2000), *, notes: str = "", year: int = 0) -> Chip:
    return Chip(
        name=name,
        vendor="MTK",
        family=family,
        protocol="brom",
        usb=tuple((MTK_VID, pid) for pid in pids),
        notes=notes,
        year=year,
    )


def _spd(name: str, family: str, pids: tuple[int, ...] = (0x4D00, 0x5D00), *, notes: str = "", year: int = 0) -> Chip:
    return Chip(
        name=name,
        vendor="SPD",
        family=family,
        protocol="bsl",
        usb=tuple((SPD_VID, pid) for pid in pids),
        notes=notes,
        year=year,
    )


MTK_CHIPS: tuple[Chip, ...] = (
    _mtk("MT6572", "Legacy", notes="Very old, preloader-only, needs a matching DA", year=2013),
    _mtk("MT6580", "Legacy", notes="Common in budget phones and tablets", year=2015),
    _mtk("MT6582", "Legacy", year=2013),
    _mtk("MT6592", "Legacy", year=2013),
    _mtk("MT6735", "Entry", notes="DA v5, SLA/DAA often required", year=2015),
    _mtk("MT6737", "Entry", notes="DA v5", year=2016),
    _mtk("MT6739", "Entry", notes="DA v5", year=2018),
    _mtk("MT6750", "Entry", year=2016),
    _mtk("MT6753", "Entry", year=2015),
    _mtk("MT6761", "Helio A", notes="DA v5", year=2019),
    _mtk("MT6762", "Helio P", notes="DA v5/v6 depending on build", year=2018),
    _mtk("MT6763", "Helio P", year=2018),
    _mtk("MT6765", "Helio P/G", notes="DA v6, UsbDk recommended", year=2019),
    _mtk("MT6768", "Helio P/G", notes="DA v6", year=2020),
    _mtk("MT6771", "Helio P60", notes="DA v6", year=2018),
    _mtk("MT6781", "Helio G", notes="DA v6", year=2020),
    _mtk("MT6785", "Helio G90", notes="DA v6", year=2019),
    _mtk("MT6833", "Dimensity 700", notes="DA v6, BROM + preloader", year=2020),
    _mtk("MT6853", "Dimensity 720", year=2020),
    _mtk("MT6873", "Dimensity 800", year=2020),
    _mtk("MT6877", "Dimensity 900", year=2021),
    _mtk("MT6893", "Dimensity 1200", year=2021),
    _mtk("MT6983", "Dimensity 9000", notes="Newer DA, may require auth file", year=2022),
    _mtk("MT6985", "Dimensity 9200", year=2023),
    _mtk("MT6989", "Dimensity 9300", year=2023),
    _mtk("MT8163", "Tablet", year=2016),
    _mtk("MT8168", "Tablet", year=2014),
    _mtk("MT8183", "Chromebook/Tablet", year=2019),
    _mtk("MT8666", "Automotive/IoT", year=2020),
)

SPD_CHIPS: tuple[Chip, ...] = (
    _spd("SC6531E", "Feature phone", notes="BSL only, tiny flash, no FDL2 partition table", year=2014),
    _spd("SC6531F", "Feature phone", year=2015),
    _spd("SC7731", "SC77xx", notes="FDL1/FDL2 required", year=2014),
    _spd("SC7731E", "SC77xx", year=2016),
    _spd("SC9820", "SC98xx", year=2015),
    _spd("SC9820E", "SC98xx", notes="KaiOS devices", year=2017),
    _spd("SC9832", "SC98xx", notes="Very common in Android Go phones", year=2015),
    _spd("SC9832E", "SC98xx", year=2017),
    _spd("SC9850", "SC98xx", year=2016),
    _spd("SC9853I", "SC98xx", notes="Intel fab, distinct FDL", year=2017),
    _spd("SC9863A", "SC98xx", notes="FDL2 with partition table support", year=2018),
    _spd("SC9863A1", "SC98xx", year=2019),
    _spd("UMS9117", "Unisoc feature", notes="Unisoc branded SC98xx follow-up", year=2019),
    _spd("UMS312", "Unisoc entry", year=2020),
    _spd("UMS512", "T-series", notes="Sold as T610/T612", year=2021),
    _spd("T310", "T-series", notes="Unisoc Tanggula entry", year=2021),
    _spd("T606", "T-series", notes="Widely used, FDL2 flasher", year=2021),
    _spd("T610", "T-series", year=2021),
    _spd("T612", "T-series", year=2021),
    _spd("T616", "T-series", year=2021),
    _spd("T618", "T-series", year=2021),
    _spd("T700", "T-series", year=2021),
    _spd("T760", "T-series", notes="5G, newer FDL handshake", year=2022),
    _spd("T770", "T-series", year=2022),
    _spd("T820", "T-series", notes="5G premium", year=2023),
    _spd("T9100", "T-series", year=2024),
)

ALL_CHIPS: tuple[Chip, ...] = MTK_CHIPS + SPD_CHIPS

_BY_USB: dict[tuple[int, int], Chip] = {}
for _chip in ALL_CHIPS:
    for _pair in _chip.usb:
        _BY_USB.setdefault(_pair, _chip)


def by_name(name: str) -> Chip | None:
    wanted = (name or "").strip().lower()
    for chip in ALL_CHIPS:
        if chip.name.lower() == wanted:
            return chip
    return None


def identify(vid: int, pid: int) -> Chip | None:
    """Map a USB vendor/product pair to a chip, when it is unambiguous."""
    return _BY_USB.get((int(vid), int(pid)))


def search(text: str, vendor: str | None = None) -> list[Chip]:
    needle = (text or "").strip().lower()
    results = []
    for chip in ALL_CHIPS:
        if vendor and chip.vendor != vendor:
            continue
        haystack = " ".join((chip.name, chip.family, chip.vendor, chip.notes)).lower()
        if not needle or needle in haystack:
            results.append(chip)
    return results


def vendors() -> list[str]:
    return ["MTK", "SPD"]


def families(vendor: str | None = None) -> list[str]:
    seen: list[str] = []
    for chip in ALL_CHIPS:
        if vendor and chip.vendor != vendor:
            continue
        if chip.family not in seen:
            seen.append(chip.family)
    return seen


def protocols() -> dict[str, str]:
    return {
        "brom": "MediaTek Boot ROM - DA/DA2 loaders, partition read/write/erase",
        "bsl": "Spreadtrum Boot Strap Loader - FDL1/FDL2 loaders, PAC firmware",
    }


def summary() -> dict[str, object]:
    return {
        "total": len(ALL_CHIPS),
        "mtk": len(MTK_CHIPS),
        "spd": len(SPD_CHIPS),
        "families": {vendor: families(vendor) for vendor in vendors()},
    }


def scan_usb() -> list[dict[str, object]]:
    """Return connected devices that match the database (needs pyusb)."""
    try:
        import usb.core  # noqa: PLC0415 - optional dependency
    except Exception:
        return []
    try:
        devices = list(usb.core.find(find_all=True) or [])
    except Exception:
        return []
    found: list[dict[str, object]] = []
    for device in devices:
        vid = int(getattr(device, "idVendor", 0) or 0)
        pid = int(getattr(device, "idProduct", 0) or 0)
        chip = identify(vid, pid)
        if chip is None and vid not in (MTK_VID, SPD_VID):
            continue
        found.append(
            {
                "vid": vid,
                "pid": pid,
                "usb": "%04X:%04X" % (vid, pid),
                "vendor": chip.vendor if chip else ("MTK" if vid == MTK_VID else "SPD"),
                "chip": chip.name if chip else "unknown",
                "family": chip.family if chip else "",
                "protocol": chip.protocol if chip else ("brom" if vid == MTK_VID else "bsl"),
            }
        )
    return found
