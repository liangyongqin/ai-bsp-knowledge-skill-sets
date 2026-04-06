"""
ARM TrustZone & Trusted Firmware-A (TF-A) seed — open-source knowledge ingestion.

Adds security/boot chain components: TrustZone, TF-A boot stages, secure
monitor, OP-TEE, and ARM CCA (Confidential Compute Architecture).

Sources:
  - ARM TrustZone Technology overview (ARM 100690)
  - ARM Trusted Firmware-A documentation (trustedfirmware.org)
  - ARM Confidential Compute Architecture (CCA) spec DEN0096
  - ARM PSCI specification DEN0022D
  - ARM SMCCC (SMC Calling Convention) DEN0028
  - OP-TEE documentation (optee.readthedocs.io)
  - Linux Documentation/arm64/booting.rst

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
# Components — TrustZone hardware
# ---------------------------------------------------------------------------

_TRUSTZONE_HW = [
    ("TrustZone-TZASC",       "security",   "ARM",
     "TrustZone Address Space Controller (TZASC) — partitions DRAM into secure and non-secure "
     "regions; configurable per memory region; protects secure firmware and OP-TEE memory from "
     "normal world access",
     "base"),
    ("TrustZone-TZPC",        "security",   "ARM",
     "TrustZone Protection Controller (TZPC) — configures peripheral security attributes, "
     "marks peripherals as secure or non-secure; accessed from secure world only",
     "base"),
    ("TrustZone-GIC-Security","security",   "ARM",
     "GIC Security extensions — interrupt groups: Group 0 (secure FIQ), Group 1S (secure IRQ), "
     "Group 1NS (non-secure IRQ); configured via GICD_IGROUPRn and GICD_IGRPMODRn",
     "base"),
    ("ARM-SAU",               "security",   "ARM",
     "Security Attribution Unit (SAU) — Cortex-M TrustZone; marks memory regions as "
     "Secure/Non-Secure/Non-Secure Callable; up to 8 regions on Cortex-M33/M55",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — TF-A boot stages
# ---------------------------------------------------------------------------

_TFA_STAGES = [
    ("TFA-BL1",               "firmware",   "ARM",
     "Trusted Firmware-A BL1 (AP Trusted ROM) — first-stage boot, "
     "runs from on-chip ROM, initialises minimum hardware (UART, clocks), "
     "verifies and loads BL2; root of trust for secure boot chain",
     "base"),
    ("TFA-BL2",               "firmware",   "ARM",
     "TF-A BL2 (Trusted Boot Firmware) — second-stage secure boot, "
     "initialises DRAM (DDR training), loads BL31/BL32/BL33; "
     "implements Trusted Board Boot (TBB) with certificate chain verification",
     "base"),
    ("TFA-BL31",              "firmware",   "ARM",
     "TF-A BL31 (EL3 Runtime Firmware / Secure Monitor) — runs at EL3, "
     "handles SMC calls (PSCI, SCMI, vendor-specific), manages secure/normal world switching, "
     "exception vector table at VBAR_EL3; persistent throughout OS lifetime",
     "base"),
    ("TFA-BL32",              "firmware",   "ARM",
     "TF-A BL32 (Secure-EL1 Payload) — typically OP-TEE or other TEE OS; "
     "runs in secure world at S-EL1; loaded by BL2, initialised by BL31",
     "base"),
    ("TFA-BL33",              "firmware",   "ARM",
     "TF-A BL33 (Non-secure Firmware) — typically U-Boot or UEFI, "
     "first non-secure world code; loaded by BL2 after secure world is up; "
     "transitions to EL2 (hypervisor) or EL1 (kernel)",
     "base"),
    ("TFA-FIP",               "firmware",   "ARM",
     "Firmware Image Package (FIP) — binary container format for TF-A images, "
     "packs BL2/BL31/BL32/BL33 + certificates into single flashable image; "
     "parsed by BL1/BL2 during boot",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — SMCCC and runtime services
# ---------------------------------------------------------------------------

_SMCCC = [
    ("ARM-SMCCC",             "firmware",   "ARM",
     "ARM SMC Calling Convention (SMCCC) DEN0028 — ABI for SMC/HVC calls between "
     "exception levels; defines function ID encoding, register usage (X0–X7), "
     "and standard service ranges (PSCI, SCMI, vendor SiP)",
     "base"),
    ("TFA-PSCI-Service",      "firmware",   "ARM",
     "TF-A PSCI runtime service — BL31 implementation of PSCI DEN0022D; "
     "handles CPU_ON, CPU_OFF, CPU_SUSPEND, SYSTEM_SUSPEND, SYSTEM_RESET SMC calls; "
     "coordinates with SoC-specific power controller driver",
     "base"),
    ("TFA-SiP-Service",       "firmware",   "ARM",
     "TF-A SiP (Silicon Provider) service — vendor-specific SMC handler in BL31, "
     "implements SoC-specific operations: DRAM frequency scaling, efuse read, "
     "secure register access; function IDs in SiP range 0xC2000000+",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — OP-TEE
# ---------------------------------------------------------------------------

_OPTEE = [
    ("OP-TEE-Core",           "firmware",   "Linaro",
     "OP-TEE OS core — open-source TEE (Trusted Execution Environment) at S-EL1; "
     "manages Trusted Applications (TAs), secure memory, crypto drivers; "
     "GlobalPlatform TEE Internal Core API compliant",
     "base"),
    ("OP-TEE-Driver",         "driver",     "linux",
     "Linux OP-TEE driver (drivers/tee/optee/) — normal world TEE client, "
     "communicates with OP-TEE via SMC; implements TEE subsystem for userspace "
     "(/dev/tee0); supports shared memory, RPC, and dynamic TA loading",
     "base"),
    ("linux-tee-subsystem",   "framework",  "linux",
     "Linux TEE subsystem (drivers/tee/) — generic framework for TEE access, "
     "provides /dev/teeN and /dev/teepriv0; backends: OP-TEE, AMD-TEE, tstee (test); "
     "used by DRM key provisioning, secure storage, crypto offload",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — ARM CCA (Confidential Compute Architecture)
# ---------------------------------------------------------------------------

_CCA = [
    ("ARM-CCA",               "security",   "ARM",
     "ARM Confidential Compute Architecture (CCA) — framework for confidential computing, "
     "introduces Realm world (fourth security state); hardware isolation of workloads from "
     "hypervisor and host OS; requires RME (Realm Management Extension)",
     "base"),
    ("ARM-RMM",               "firmware",   "ARM",
     "Realm Management Monitor (RMM) — firmware at R-EL2, manages Realm VMs; "
     "provides attestation, memory encryption oversight, and realm lifecycle management; "
     "loaded by TF-A BL31; standardised by ARM DEN0096",
     "base"),
    ("ARM-GPT",               "security",   "ARM",
     "Granule Protection Table (GPT) — hardware-enforced physical address space partitioning, "
     "tags each 4KB granule as Root/Realm/Secure/Non-secure; managed by EL3 firmware; "
     "enforced by MMU and interconnect",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Secure boot chain
# ---------------------------------------------------------------------------

_SECURE_BOOT = [
    ("OTP-Fuse-Controller",   "security",   "generic",
     "OTP (One-Time Programmable) Fuse Controller — stores root-of-trust public key hash, "
     "secure boot enable bit, device lifecycle state; irreversible once blown; "
     "read by BL1 to verify BL2 image signature",
     "base"),
    ("Secure-Boot-Certificate","security",  "ARM",
     "TF-A Trusted Board Boot certificate chain — X.509v3 certificates for each boot stage, "
     "root key (ROT) → trusted key → content certificates; "
     "verified by mbedTLS/OpenSSL in BL1/BL2",
     "base"),
    ("Anti-Rollback-Counter", "security",   "generic",
     "Anti-rollback counter (ARC) — monotonic counter in OTP/RPMB, prevents rollback to "
     "vulnerable firmware versions; BL2 checks image NV counter against stored value",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Linux secure boot integration
# ---------------------------------------------------------------------------

_LINUX_SECURE = [
    ("linux-efi-stub",        "firmware",   "linux",
     "Linux EFI stub — kernel built-in UEFI boot path, handles EFI memory map, "
     "ACPI/DT discovery, initrd loading from EFI; used when BL33 is UEFI",
     "base"),
    ("linux-kexec-secure",    "framework",  "linux",
     "Linux kexec with secure boot — signature verification of kexec kernel image, "
     "prevents loading unsigned kernels; integrates with IMA/EVM and lockdown LSM",
     "base"),
    ("linux-dm-verity",       "framework",  "linux",
     "dm-verity — device mapper target for block-level integrity verification, "
     "Merkle tree hash of filesystem blocks; used by Android Verified Boot (AVB) "
     "to protect system/vendor partitions; root hash signed by OEM key",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_SECURE_INTERRUPTS = [
    ("IRQ-Secure-Timer",     "PPI", 29, "level-high", "base"),
    ("IRQ-Non-Secure-Timer", "PPI", 30, "level-high", "base"),
    ("IRQ-Secure-SGI-0",    "SGI",  8, "edge-rising", "base"),
    ("IRQ-Secure-SGI-1",    "SGI",  9, "edge-rising", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_SECURE_FAILURES = [
    ("FM-TFA-BL2-Auth-Fail",
     "Boot halts at BL2: CERT_NOT_VERIFIED; device stuck in recovery mode",
     "BL2 image certificate does not match ROT key hash in OTP fuses; "
     "key rotation not committed to fuses before image update; "
     "recover by re-signing image with correct key or using recovery mode",
     "boot",
     "ARM TF-A documentation: Trusted Board Boot",
     "base"),
    ("FM-OPTEE-Shared-Mem-Fail",
     "TEE client call returns TEEC_ERROR_OUT_OF_MEMORY; secure operation fails",
     "OP-TEE shared memory pool exhausted; too many concurrent TA sessions or "
     "shared memory not freed after use; check shm pool size in OP-TEE config",
     "security",
     "OP-TEE documentation: Shared Memory",
     "base"),
    ("FM-SMC-Undefined-ID",
     "SMC returns UNKNOWN_SMC (-1); service not registered in BL31",
     "SMC function ID not in any registered service range; "
     "vendor SiP service not compiled into TF-A build; "
     "check TF-A plat/ directory for SoC-specific SiP handler",
     "boot",
     "ARM SMCCC DEN0028",
     "base"),
    ("FM-Anti-Rollback-Block",
     "Firmware downgrade blocked: NV counter too low; device refuses to boot old FW",
     "Anti-rollback counter in OTP/RPMB higher than image NV counter; "
     "cannot downgrade firmware without hardware modification; "
     "this is by design to prevent security rollback attacks",
     "boot",
     "ARM TF-A documentation: Anti-Rollback Protection",
     "base"),
    ("FM-TZASC-Violation",
     "Bus error or data abort accessing secure memory from normal world; kernel crash",
     "Application or driver accessing physical address range protected by TZASC; "
     "memory region marked secure-only; check TZASC region configuration in TF-A platform code",
     "security",
     "ARM TrustZone TZASC-400 TRM",
     "base"),
    ("FM-Realm-Creation-Fail",
     "KVM: failed to create realm VM; RMM returns error; CCA workload cannot start",
     "RMM not loaded or GPT not configured for realm granules; "
     "check TF-A CCA support is enabled and RMM image included in FIP",
     "virtualization",
     "ARM CCA specification DEN0096",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _TRUSTZONE_HW + _TFA_STAGES + _SMCCC +
        _OPTEE + _CCA + _SECURE_BOOT + _LINUX_SECURE
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _SECURE_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _SECURE_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Boot chain: BL1 → BL2 → BL31/BL32/BL33
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL1", dst_name="TFA-BL2")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL2", dst_name="TFA-BL31")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL2", dst_name="TFA-BL32")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL2", dst_name="TFA-BL33")

    # FIP contains all images
    for bl in ("TFA-BL2", "TFA-BL31", "TFA-BL32", "TFA-BL33"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="TFA-FIP", dst_name=bl)

    # BL31 provides PSCI and SiP services
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL31", dst_name="TFA-PSCI-Service")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL31", dst_name="TFA-SiP-Service")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL31", dst_name="ARM-SMCCC")

    # PSCI service → existing arm-psci node
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-PSCI-Service", dst_name="arm-psci")

    # BL32 = OP-TEE
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL32", dst_name="OP-TEE-Core")

    # Linux OP-TEE driver → TEE subsystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="OP-TEE-Driver", dst_name="linux-tee-subsystem")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="OP-TEE-Driver", dst_name="OP-TEE-Core")

    # TZASC protects secure memory
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TrustZone-TZASC", dst_name="DDR-Controller")

    # GIC security → GIC-600
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TrustZone-GIC-Security", dst_name="GIC-600")

    # CCA: RMM loaded by BL31, uses GPT
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="TFA-BL31", dst_name="ARM-RMM")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-CCA", dst_name="ARM-RMM")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-CCA", dst_name="ARM-GPT")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-CCA", dst_name="ARMv9-RME")

    # Secure boot: OTP → BL1 verification
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="OTP-Fuse-Controller", dst_name="TFA-BL1")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Secure-Boot-Certificate", dst_name="TFA-BL2")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Anti-Rollback-Counter", dst_name="TFA-BL2")

    # dm-verity → filesystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-dm-verity", dst_name="eMMC-Controller")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-TFA-BL2-Auth-Fail",      "TFA-BL2"),
        ("FM-OPTEE-Shared-Mem-Fail",   "OP-TEE-Core"),
        ("FM-SMC-Undefined-ID",        "TFA-BL31"),
        ("FM-Anti-Rollback-Block",     "Anti-Rollback-Counter"),
        ("FM-TZASC-Violation",         "TrustZone-TZASC"),
        ("FM-Realm-Creation-Fail",     "ARM-RMM"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-trustzone-tfa] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
