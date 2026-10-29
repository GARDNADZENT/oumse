"""BSL command numbers and defaults for Spreadtrum/Unisoc devices.

These constants describe the Boot Strap Loader command set shared by SPD
service tools. They are deliberately isolated here: if a device refuses a
command, this file is the only place that has to change.

Two stages exist on this platform:

* **BSL** - the ROM bootloader. Small, fixed command set: connect, read/write
  flash, read chip type, execute code at an address.
* **FDL** - a loader the host uploads into RAM (FDL1, then FDL2) that adds
  partition tables, erasing, NV access and the actual flashing speed.

Stage handshake: ``CONNECT`` -> download FDL1 with ``START_DATA``/``MID_DATA``/
``END_DATA`` -> ``EXEC_DATA`` at the FDL entry -> the device re-enumerates or
keeps the same port -> repeat for FDL2.
"""

from __future__ import annotations

#: Command byte sent by the host.
CMD_CONNECT = 0x00
CMD_START_DATA = 0x01
CMD_MID_DATA = 0x02
CMD_END_DATA = 0x03
CMD_NORMAL_RESET = 0x04
CMD_READ_FLASH = 0x05
CMD_READ_CHIP_TYPE = 0x06
CMD_READ_NVITEM = 0x08
CMD_CHANGE_BAUD = 0x09
CMD_ERASE_FLASH = 0x0A
CMD_CHECK_ROOT = 0x0F
CMD_READ_VERSION = 0x10
CMD_CHECK_BAUD = 0x11
CMD_READ_FLASH_START = 0x12
CMD_READ_FLASH_MIDST = 0x13
CMD_READ_FLASH_END = 0x14
CMD_WRITE_FLASH_START = 0x15
CMD_EXEC_DATA = 0x16
CMD_KEEP_CHARGE = 0x17
CMD_EXEC_FLASH = 0x18
CMD_READ_START = 0x19
CMD_READ_MIDST = 0x1A
CMD_READ_END = 0x1B
CMD_POWER_OFF = 0x1C
CMD_NV_READ = 0x1D
CMD_NV_WRITE = 0x1E

#: FDL2 extensions used by service tools: the partition table and flash ids.
#: A device whose FDL does not implement these answers NACK, and the caller
#: falls back to the partition list inside a PAC file.
CMD_READ_PARTITION = 0x2E
CMD_READ_FLASH_INFO = 0x2F

#: Partition table payload: ``count(u16)`` then per entry
#: ``name[16] + offset(u32) + size(u32)``, all little-endian.
PART_NAME_LEN = 16

#: Response is ``request | 0x80``.
RESPONSE_BIT = 0x80
ACK = 0x00
NACK = 0x01

#: Data block tags inside a payload.
TAG_LOAD = 0x00
TAG_EXEC = 0x01

#: Flash block size for reads and writes. The length field on the wire is 16
#: bits, so a block can never be 0x10000 bytes.
BLOCK_SIZE = 0x8000
#: Smaller block for the ROM BSL, which has tighter buffers.
ROM_BLOCK_SIZE = 0x2000

#: Timeouts in seconds.
CONNECT_TIMEOUT = 6.0
COMMAND_TIMEOUT = 5.0
READ_TIMEOUT = 12.0
ERASE_TIMEOUT = 40.0
EXEC_TIMEOUT = 8.0
RESET_SETTLE = 2.5

#: Spreadtrum USB vendor id. Product ids differ per chip family.
SPD_USB_VID = 0x1782
SPD_USB_PIDS = {
    0x4D00: "SPD BSL (generic)",
    0x5D00: "SPD FDL (generic)",
    0x4D01: "SC/UMTS BSL",
    0x5D01: "SC/UMTS FDL",
}

#: Common BSL baud rate.
BSL_BAUD = 115200
SPL_BAUD = 921600

#: Default addresses used when a device does not advertise its own.
DEFAULT_FDL1_ADDR = 0x5000
DEFAULT_FDL2_ADDR = 0x14000000
