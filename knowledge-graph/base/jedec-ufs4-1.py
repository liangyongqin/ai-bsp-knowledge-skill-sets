"""
UFS 4.1 storage subsystem — seed knowledge ingestion.

Adds UFS 4.1 (JEDEC JESD220G, Jan 8 2025) and UFSHCI 4.1 (JESD223F)
components that extend the existing UFS 4.0 coverage. UFS 4.1 shipped in
production devices starting mid-2025 (Kioxia automotive UFS 4.1 launched
Jul 2025).

Key differences vs UFS 4.0 (relevant for BSP bring-up):
  - M-PHY v5.0 physical layer (vs M-PHY Gen4 in UFS 4.0)
  - UniPro v2.0 transport layer
  - ~4.2 GB/s peak read/write (sustained, not just burst)
  - Host-Initiated Defragmentation (HID) — new mechanism for read-tail latency
  - WriteBooster Buffer Resize (WBBR) + Partial Flush (WBPF)
  - Permanent Bootable Logical Units (bBootLunEn = 0xFF)
  - RPMB Authentication — extended for vendor-specific command security

Sources:
  - JEDEC JESD220G UFS 4.1 Standard (press release 2025-01-08)
    https://www.jedec.org/news/pressreleases/jedec-announces-updates-universal-flash-storage
  - JEDEC JESD223F UFSHCI 4.1 Host Controller Interface
  - KIOXIA UFS 4.1 automotive product brief (public, Jul 2025)
  - Linux drivers/ufs/core/ tree (UFS 4.1 support prep patches, kernel 6.14+)

Namespace: base (open-source only)
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _HERE)

import kuzu
import schema as _schema
from _ingest_helpers import upsert_node, create_rel

# ---------------------------------------------------------------------------
# Components — UFS 4.1 subsystem
# ---------------------------------------------------------------------------

_UFS41_COMPONENTS = [
    ("UFS-4.1-HCI",           "storage-controller", "JEDEC",
     "UFS 4.1 Host Controller Interface (UFSHCI v4.1) — JEDEC JESD223F; "
     "~4.2 GB/s peak read AND write (UFS 4.0 was burst-only); HS-G5 gear "
     "retained; backward compatible with UFS 3.1 / 3.0 devices; "
     "Linux support prep in drivers/ufs/core/ (kernel 6.14+)",
     "base"),
    ("UFS-4.1-M-PHY-v5",      "phy",                "MIPI",
     "MIPI M-PHY v5.0 — physical layer for UFS 4.1; retains HS-G5 (23.4 Gbps) "
     "but adds improved reference-clock jitter tolerance; longer trace-length "
     "margin enables wider PCB layouts on automotive mainboards; mandatory "
     "feature set defined in JESD220G §8",
     "base"),
    ("UFS-4.1-UniPro-v2",     "protocol",           "MIPI",
     "MIPI UniPro v2.0 — transport layer for UFS 4.1; extends MCQ (Multi-"
     "Circular Queue) semantics; adds explicit queue-depth negotiation to "
     "avoid submission-queue overflow; host and device advertise max-QD via "
     "DME_GETSET during link startup",
     "base"),
    ("UFS-4.1-HID",           "storage-feature",    "JEDEC",
     "UFS 4.1 Host-Initiated Defragmentation (HID) — NEW in UFS 4.1; host "
     "issues vendor-defined QUERY REQUEST to trigger device-side logical "
     "block defragmentation; reduces read-tail latency on aged devices; "
     "Linux sysfs: /sys/class/block/sda/device/hid_enable, hid_progress",
     "base"),
    ("UFS-4.1-WBBR",          "storage-feature",    "JEDEC",
     "UFS 4.1 WriteBooster Buffer Resize (WBBR) — host can request runtime "
     "resize of SLC write-buffer region to match workload phase (e.g., shrink "
     "during idle to reclaim MLC capacity; enlarge during sustained write "
     "phase); previously fixed at provisioning; Linux sysfs: "
     "write_booster_buffer_size",
     "base"),
    ("UFS-4.1-WBPF",          "storage-feature",    "JEDEC",
     "UFS 4.1 WriteBooster Partial Flush (WBPF) — host can flush a subset of "
     "the WB buffer to MLC without full stall; replaces the all-or-nothing "
     "flush semantics of UFS 4.0 WriteBooster; reduces write-latency spikes "
     "during camera burst capture and 4K video record",
     "base"),
    ("UFS-4.1-PermBootLU",    "storage-feature",    "JEDEC",
     "UFS 4.1 Permanent Bootable Logical Unit — bConfigDescrLock combined with "
     "bBootLunEn=0xFF permanently locks a LU as bootable; cannot be unset even "
     "with vendor commands; hardens automotive / IoT device secure-boot chain "
     "against malicious re-partitioning",
     "base"),
    ("UFS-4.1-RPMB-Auth",     "storage-feature",    "JEDEC",
     "UFS 4.1 RPMB Authentication extension — vendor-specific commands now "
     "require RPMB-authenticated payload before device accepts them; protects "
     "against firmware-replace and defrag-abuse attacks; Linux driver must "
     "provide HMAC-SHA256 over RPMB key (stored in HLOS keyring)",
     "base"),
    ("linux-ufs-4-1",         "driver",             "linux",
     "Linux UFS 4.1 host controller prep (drivers/ufs/core/) — adds HID "
     "sysfs attributes, WBBR/WBPF ioctls, RPMB-authenticated query support; "
     "merged in fragments across kernel 6.14–6.18; full ratification pending "
     "broader UFS 4.1 device availability in 2026",
     "base"),
]

# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------

_UFS41_REGISTERS = [
    ("UFSHCI-41-VER",     "0x008", "RO", "0x00000410", "UFS-4.1-HCI",
     "UFSHCI v4.1 Version Register — reads 0x00000410 for UFSHCI 4.1 "
     "(major=4, minor=1); Linux driver reads this during probe to dispatch "
     "v4.0 vs v4.1 feature paths",
     "base"),
    ("UFSHCI-41-HID-CTL",  "0x3C0", "RW", "0x00000000", "UFS-4.1-HCI",
     "UFSHCI v4.1 HID Control Register — bit[0]: HID enable; bit[1]: HID "
     "trigger; bits[15:8]: defrag-target LBA range selector; written by "
     "Linux hid_enable sysfs handler",
     "base"),
    ("UFSHCI-41-WB-CFG",   "0x3C8", "RW", "0x00000000", "UFS-4.1-HCI",
     "UFSHCI v4.1 WriteBooster Config Register — bits[15:0]: requested WB "
     "buffer size in MB (WBBR); bit[16]: WBPF partial-flush request; "
     "bits[23:17]: WBPF flush-target LU; Linux write_booster_buffer_size "
     "sysfs handler writes this",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_UFS41_FAILURES = [
    ("FM-UFS41-HID-Timeout",
     "HID (Host-Initiated Defragmentation) request times out; sysfs hid_progress frozen at <100%",
     "Device-side defrag stalled on bad-block remap; check vendor log page "
     "for media health; HID should not be issued on devices already in "
     "critical wear state; abort via hid_enable=0 and run fsck; consider "
     "device replacement if HID fails repeatedly on same LBA range",
     "storage",
     "JEDEC JESD220G §14 HID; Linux drivers/ufs/core/ufshcd.c hid_* paths",
     "base"),
    ("FM-UFS41-WBBR-NotSupported",
     "sysfs write_booster_buffer_size returns EINVAL; dmesg: 'UFS: WBBR not advertised by device'",
     "Device reports UFS 4.1 capability in bUFSVersion but does not "
     "advertise bWriteBoosterBufferResize=1 in descriptor; vendor firmware "
     "missing optional WBBR support; fallback to static WB size; pressure "
     "vendor for firmware update or accept UFS 4.0 semantics",
     "storage",
     "JEDEC JESD220G §13 WriteBooster 2.0; UFS descriptor bWriteBoosterFeatureSupport",
     "base"),
    ("FM-UFS41-RPMB-Auth-Fail",
     "Vendor query command rejected: 'UFS: RPMB authentication failure, result=0x0007'",
     "RPMB key mismatch between HLOS keyring and UFS device-provisioned "
     "key; caused by mismatched manufacturing provisioning vs HLOS keyblob "
     "restore after factory reset; re-provision RPMB key via vendor tool or "
     "unlock pathway (device-specific, may require fuse-burn)",
     "storage",
     "JEDEC JESD220G §15 RPMB Auth; Linux drivers/mmc/core/mmc_ops.c (RPMB)",
     "base"),
    ("FM-UFS41-PermBootLU-Stuck",
     "Cannot unlock bootable LU after user-initiated re-partition attempt; bConfigDescrLock stays 0xFF",
     "UFS 4.1 Permanent Bootable LU is BY DESIGN unable to be unlocked; "
     "bConfigDescrLock=0xFF is a one-way transition; for field-returns, "
     "the device must be physically replaced — software workaround is "
     "impossible; audit factory provisioning flow to avoid premature lock",
     "storage",
     "JEDEC JESD220G §6.4.5 bConfigDescrLock; vendor provisioning guide",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    for name, ctype, vendor, desc, ns in _UFS41_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, addr, access, reset, component, desc, ns in _UFS41_REGISTERS:
        if upsert_node(conn, "Register", {
            "name": name, "address": addr, "access_type": access,
            "reset_value": reset, "component": component,
            "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _UFS41_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # UFS 4.1 stack topology
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-4.1-HCI", dst_name="UFS-4.1-UniPro-v2")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-4.1-UniPro-v2", dst_name="UFS-4.1-M-PHY-v5")

    # Features hang off the HCI
    for feat in ("UFS-4.1-HID", "UFS-4.1-WBBR", "UFS-4.1-WBPF",
                 "UFS-4.1-PermBootLU", "UFS-4.1-RPMB-Auth"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=feat, dst_name="UFS-4.1-HCI")

    # Linux driver → HCI
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-ufs-4-1", dst_name="UFS-4.1-HCI")

    # Generational link — UFS 4.0 → UFS 4.1
    create_rel(conn, "SHARED_WITH", "Component", "Component",
               src_name="UFS-4.1-HCI", dst_name="UFS-4.0-HCI")
    create_rel(conn, "SHARED_WITH", "Component", "Component",
               src_name="UFS-4.1-M-PHY-v5", dst_name="UFS-4.0-M-PHY-Gen4")

    # Reuse existing UFS power/clock domains from linux-lpddr5x-ufs4.py
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="UFS-VCC-2.5V", dst_name="UFS-4.1-HCI")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="UFS-VCCQ2-1.8V", dst_name="UFS-4.1-M-PHY-v5")
    create_rel(conn, "CLOCKS", "ClockSource", "Component",
               src_name="clk-ufs-hs-g5", dst_name="UFS-4.1-M-PHY-v5")
    create_rel(conn, "CLOCKS", "ClockSource", "Component",
               src_name="clk-ufs-ref-26m", dst_name="UFS-4.1-HCI")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "ClockSource",
               src_name="UFS-4.1-HCI", dst_name="clk-ufs-ref-26m")

    # Failure modes → root components
    for fm_name, comp_name in [
        ("FM-UFS41-HID-Timeout",        "UFS-4.1-HID"),
        ("FM-UFS41-WBBR-NotSupported",  "UFS-4.1-WBBR"),
        ("FM-UFS41-RPMB-Auth-Fail",     "UFS-4.1-RPMB-Auth"),
        ("FM-UFS41-PermBootLU-Stuck",   "UFS-4.1-PermBootLU"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    create_rel(conn, "AFFECTS_IF_REMOVED", "PowerDomain", "Component",
               src_name="UFS-VCC-2.5V", dst_name="UFS-4.1-HCI")

    print(f"[jedec-ufs4-1] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
