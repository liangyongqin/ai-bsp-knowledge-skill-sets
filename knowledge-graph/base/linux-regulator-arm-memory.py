"""
Linux Regulator Framework + ARM Memory Subsystem — seed knowledge.

Sources:
  - Linux Documentation/power/regulator/ (regulator consumer/provider APIs)
  - Linux Documentation/power/regulator/overview.rst
  - Linux Documentation/power/regulator/machine.rst
  - Linux drivers/regulator/ (regmap-based PMIC drivers)
  - ARM Architecture Reference Manual for A-profile (DDI 0487)
    §D5 — The AArch64 Virtual Memory System Architecture
    §D8 — AArch64 System Register Descriptions (SCTLR_EL1, TCR_EL1, MAIR_EL1, TTBR0/1_EL1)
  - ARM Cortex-A55/A76/A78 TRMs — cache geometry, TLB structure
  - Linux Documentation/admin-guide/mm/ (memory management overview)
  - Linux Documentation/core-api/cachetlb.rst (cache/TLB flush APIs)
  - Linux Documentation/vm/page_owner.rst, Documentation/mm/hugetlbpage.rst

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
# Linux Regulator Framework — PowerDomain nodes
# ---------------------------------------------------------------------------

_POWER_DOMAINS = [
    # (name, type, description, voltage_mv, current_ma)
    ("VDD_CPU_BIG", "core-rail", "Big CPU cluster core voltage rail (regulator framework)", 900.0, 8000.0),
    ("VDD_CPU_LITTLE", "core-rail", "Little CPU cluster core voltage rail", 750.0, 4000.0),
    ("VDD_GPU", "core-rail", "GPU core voltage rail managed by regulator framework", 800.0, 6000.0),
    ("VDD_INT", "core-rail", "Internal logic voltage rail (bus fabric, NoC)", 750.0, 3000.0),
    ("VDD_MIF", "core-rail", "Memory interface voltage rail (DRAM PHY, controller)", 700.0, 2000.0),
    ("VDD_CAM", "peripheral-rail", "Camera subsystem power domain (ISP, CSI-2 PHY)", 850.0, 2500.0),
    ("VDD_DISP", "peripheral-rail", "Display subsystem power domain (DSI PHY, DPU)", 850.0, 2000.0),
    ("VDD_NPU", "core-rail", "NPU/AI accelerator voltage rail", 800.0, 5000.0),
    ("VDD_MODEM", "peripheral-rail", "Modem subsystem power domain", 900.0, 3000.0),
    ("VDD_IO_1V8", "io-rail", "1.8V I/O voltage rail (LPDDR interface, GPIO)", 1800.0, 1000.0),
    ("VDD_IO_3V3", "io-rail", "3.3V I/O voltage rail (SD card, legacy peripherals)", 3300.0, 500.0),
]

# ---------------------------------------------------------------------------
# Linux Regulator Framework — Component nodes
# ---------------------------------------------------------------------------

_REGULATOR_COMPONENTS = [
    # (name, type, description, vendor, version)
    ("Linux-Regulator-Framework", "subsystem", "Linux kernel voltage/current regulator framework (drivers/regulator/core.c)", "linux-kernel", "6.x"),
    ("Regulator-Consumer-API", "framework", "regulator_get/put/enable/disable/set_voltage consumer API", "linux-kernel", "6.x"),
    ("Regulator-Provider-API", "framework", "regulator_register/unregister/regulator_desc provider API for PMIC drivers", "linux-kernel", "6.x"),
    ("PMIC-I2C-Driver", "driver", "Generic PMIC I2C/SPI regmap-based regulator driver pattern", "linux-kernel", "6.x"),
    ("Regulator-Coupler", "framework", "Voltage coupling constraints between dependent regulators", "linux-kernel", "6.x"),
    ("DCDC-Converter", "component", "DC-DC buck/boost converter — high-efficiency switching regulator for core rails", "generic", ""),
    ("LDO-Regulator", "component", "Low-dropout linear regulator — low-noise for analog/RF/PLL supply", "generic", ""),
    ("Voltage-Scaling-Governor", "driver", "Regulator framework voltage scaling tied to CPUFreq/devfreq OPP tables", "linux-kernel", "6.x"),
    ("Power-Sequencer", "component", "PMIC power sequencing engine — controls rail enable/disable ordering", "generic", ""),
    ("OVP-UVP-Monitor", "component", "Over-voltage and under-voltage protection monitor in PMIC", "generic", ""),
]

# ---------------------------------------------------------------------------
# ARM Memory Subsystem — Component nodes
# ---------------------------------------------------------------------------

_MEMORY_COMPONENTS = [
    ("ARM-MMU", "subsystem", "ARM Memory Management Unit — virtual-to-physical address translation (AArch64 VMSA)", "ARM", "ARMv8/v9"),
    ("TLB-L1-Instruction", "cache", "Level-1 instruction TLB (micro-TLB), typically 48-64 entries fully-associative", "ARM", "ARMv8/v9"),
    ("TLB-L1-Data", "cache", "Level-1 data TLB (micro-TLB), typically 48-64 entries fully-associative", "ARM", "ARMv8/v9"),
    ("TLB-L2-Unified", "cache", "Level-2 unified main TLB, 1024-2048 entries, 4-way set-associative", "ARM", "ARMv8/v9"),
    ("Page-Table-Walker", "component", "Hardware page table walker — traverses 4-level page tables (4KB/16KB/64KB granules)", "ARM", "ARMv8/v9"),
    ("L1-ICache", "cache", "Level-1 instruction cache, 32-64KB, 4-way set-associative, VIPT", "ARM", "ARMv8/v9"),
    ("L1-DCache", "cache", "Level-1 data cache, 32-64KB, 4-way set-associative, PIPT, write-back", "ARM", "ARMv8/v9"),
    ("L2-Unified-Cache", "cache", "Level-2 unified cache, 128KB-1MB per core, inclusive or non-inclusive", "ARM", "ARMv8/v9"),
    ("L3-System-Cache", "cache", "Level-3 system-level cache in DSU (DynamIQ Shared Unit), 1-16MB shared", "ARM", "ARMv8/v9"),
    ("SCU-Snoop-Control-Unit", "component", "Snoop Control Unit / ACE interface in DSU for cache coherency", "ARM", "ARMv8/v9"),
    ("Hardware-Prefetcher", "component", "ARM hardware prefetch engine — stream, stride, and next-line prefetchers", "ARM", "ARMv8/v9"),
    ("MESI-Coherency-Protocol", "protocol", "MOESI/MESI cache coherency protocol implemented via CHI/ACE interconnect", "ARM", "ARMv8/v9"),
    ("Linux-MM-Subsystem", "subsystem", "Linux memory management subsystem — page allocator, slab, vmalloc, mmap", "linux-kernel", "6.x"),
    ("Linux-CMA-Allocator", "subsystem", "Contiguous Memory Allocator — reserves DMA-capable contiguous regions", "linux-kernel", "6.x"),
    ("Linux-ION-DMA-Heap", "subsystem", "DMA-BUF heap allocator (replaced ION in 5.6+) — dma_buf_fd for multimedia/GPU", "linux-kernel", "6.x"),
    ("Linux-KASAN", "debug-tool", "Kernel Address Sanitizer — runtime memory error detector for BSP debug", "linux-kernel", "6.x"),
]

# ---------------------------------------------------------------------------
# ARM Memory Subsystem — Register nodes (key system registers)
# ---------------------------------------------------------------------------

_MEMORY_REGISTERS = [
    # (name, address, size_bits, access_type, reset_value, description, component)
    ("SCTLR_EL1", "S3_0_C1_C0_0", 64, "RW", "0x0000000030D00800", "System Control Register EL1 — MMU enable, cache enable, alignment check, WXN", "ARM-MMU"),
    ("TCR_EL1", "S3_0_C2_C0_2", 64, "RW", "0x0", "Translation Control Register EL1 — granule size, address space size, shareability", "ARM-MMU"),
    ("TTBR0_EL1", "S3_0_C2_C0_0", 64, "RW", "0x0", "Translation Table Base Register 0 — user-space page table base address", "ARM-MMU"),
    ("TTBR1_EL1", "S3_0_C2_C0_1", 64, "RW", "0x0", "Translation Table Base Register 1 — kernel-space page table base address", "ARM-MMU"),
    ("MAIR_EL1", "S3_0_C10_C2_0", 64, "RW", "0x0", "Memory Attribute Indirection Register — defines 8 memory types (Device/Normal/Cacheable)", "ARM-MMU"),
    ("FAR_EL1", "S3_0_C6_C0_0", 64, "RO", "0x0", "Fault Address Register EL1 — faulting virtual address on data/instruction abort", "ARM-MMU"),
    ("ESR_EL1", "S3_0_C5_C2_0", 64, "RO", "0x0", "Exception Syndrome Register EL1 — exception class, ISS for abort type decode", "ARM-MMU"),
    ("PAR_EL1", "S3_0_C7_C4_0", 64, "RW", "0x0", "Physical Address Register — result of AT (address translation) instruction", "ARM-MMU"),
    ("CONTEXTIDR_EL1", "S3_0_C13_C0_1", 64, "RW", "0x0", "Context ID Register EL1 — ASID for TLB tagging, process identification", "ARM-MMU"),
    ("CLIDR_EL1", "S3_1_C0_C0_1", 64, "RO", "IMPL_DEF", "Cache Level ID Register — number of cache levels, cache type per level", "L1-DCache"),
    ("CCSIDR_EL1", "S3_1_C0_C0_0", 64, "RO", "IMPL_DEF", "Current Cache Size ID Register — line size, associativity, number of sets", "L1-DCache"),
    ("CSSELR_EL1", "S3_2_C0_C0_0", 64, "RW", "0x0", "Cache Size Selection Register — select which cache level CCSIDR_EL1 reports", "L1-DCache"),
]

# ---------------------------------------------------------------------------
# FailureMode nodes — regulator + memory subsystem failures
# ---------------------------------------------------------------------------

_FAILURE_MODES = [
    # (name, symptom, root_cause, affected_domain, source, severity)
    ("PMIC-Under-Voltage-Lockout", "System reset or brown-out during high-load transient",
     "PMIC output drops below UVLO threshold due to insufficient decoupling or PCB trace impedance",
     "power-thermal", "Linux Documentation/power/regulator/, PMIC vendor datasheets", "critical"),

    ("Regulator-Enable-Timeout", "Peripheral fails to probe, regulator_enable returns -ETIMEDOUT",
     "PMIC I2C communication failure or power sequencing constraint violated",
     "boot-debug", "Linux drivers/regulator/core.c regulator_enable() flow", "high"),

    ("Voltage-Scaling-Glitch", "CPU instruction corruption or hang after DVFS transition",
     "Regulator ramp rate too slow for CPUFreq governor request; voltage not settled before frequency change",
     "power-thermal", "Linux Documentation/power/regulator/consumer.rst, OPP framework", "critical"),

    ("Rail-Coupling-Violation", "Analog PLL unlock or clock jitter after voltage change",
     "Coupled regulator constraints violated — VDD_CPU changed without maintaining VDD_INT >= VDD_CPU - 100mV",
     "power-thermal", "Linux drivers/regulator/coupling.c", "high"),

    ("TLB-Shootdown-Storm", "Soft lockup or RCU stall on multi-core system during heavy mmap/munmap",
     "Excessive TLB invalidation IPIs from frequent address space changes; tlb_flush_all triggered too often",
     "interrupt-virt", "Linux Documentation/core-api/cachetlb.rst, arch/arm64/mm/tlb.c", "medium"),

    ("Cache-Thrashing-L2", "Unexplained performance degradation in memory-intensive workload",
     "Working set exceeds L2 cache capacity causing continuous eviction/reload cycles; perf shows high L2 refill rate",
     "gpu-rendering", "ARM Cortex-A76/A78 TRM cache architecture sections, perf stat L2D_CACHE_REFILL", "medium"),

    ("CMA-Allocation-Failure", "Camera or GPU buffer allocation fails with -ENOMEM despite free memory",
     "CMA region fragmented by pinned pages; no contiguous block available for DMA-BUF allocation",
     "multimedia", "Linux Documentation/admin-guide/mm/cma.rst, drivers/dma-buf/", "high"),

    ("Page-Table-Walk-Stall", "High memory access latency spikes in latency-sensitive RT workload",
     "Concurrent page table walks saturate the PTW hardware; occurs with many concurrent processes and large VA ranges",
     "power-thermal", "ARM Architecture Reference Manual DDI 0487 §D5, perf stat DTLB_WALK", "medium"),

    ("Kernel-OOM-DMA-Heap", "Process killed by OOM despite dma-buf accounting not visible in /proc/meminfo",
     "DMA-BUF heap allocations not tracked by kernel memory accounting; hidden memory usage in camera/GPU buffers",
     "multimedia", "Linux Documentation/driver-api/dma-buf.rst, /sys/kernel/dmabuf/buffers/", "high"),

    ("KASAN-Use-After-Free", "Kernel panic with KASAN report pointing to slab cache object",
     "BSP driver accesses freed structure after put; common in deferred probe paths and async probe",
     "boot-debug", "Linux Documentation/dev-tools/kasan.rst", "critical"),
]

# ---------------------------------------------------------------------------
# Ingest function
# ---------------------------------------------------------------------------

def ingest(db_path: str | None = None) -> int:
    """Insert Linux regulator framework + ARM memory subsystem nodes.

    Returns the number of new nodes inserted.
    """
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    count = 0

    # PowerDomain nodes
    for name, ptype, desc, voltage_mv, current_ma in _POWER_DOMAINS:
        if upsert_node(conn, "PowerDomain", {
            "name": name, "type": ptype, "description": desc,
            "namespace": "base", "voltage_mv": voltage_mv, "current_ma": current_ma,
        }):
            count += 1

    # Regulator Component nodes
    for name, ctype, desc, vendor, version in _REGULATOR_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "description": desc,
            "namespace": "base", "vendor": vendor, "version": version,
        }):
            count += 1

    # ARM Memory Component nodes
    for name, ctype, desc, vendor, version in _MEMORY_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "description": desc,
            "namespace": "base", "vendor": vendor, "version": version,
        }):
            count += 1

    # Register nodes
    for name, addr, size_bits, access, reset, desc, component in _MEMORY_REGISTERS:
        if upsert_node(conn, "Register", {
            "name": name, "address": addr, "size_bits": size_bits,
            "access_type": access, "reset_value": reset,
            "description": desc, "namespace": "base", "component": component,
        }):
            count += 1

    # FailureMode nodes
    for name, symptom, root_cause, domain, source, severity in _FAILURE_MODES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": domain, "source": source,
            "namespace": "base", "severity": severity,
        }):
            count += 1

    # -----------------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------------

    # PowerDomain POWERS Component relationships
    _pd_powers = [
        ("VDD_CPU_BIG", "Cortex-A76", "Big core cluster supply"),
        ("VDD_CPU_BIG", "Cortex-A78", "Big core cluster supply"),
        ("VDD_CPU_LITTLE", "Cortex-A55", "Little core cluster supply"),
        ("VDD_GPU", "GPU-Core", "GPU core voltage supply"),
        ("VDD_INT", "NoC-Interconnect", "Bus fabric voltage supply"),
        ("VDD_MIF", "LPDDR5-Controller", "DRAM interface voltage supply"),
        ("VDD_CAM", "ISP-Pipeline", "Camera ISP power supply"),
        ("VDD_DISP", "MIPI-DSI-Host", "Display PHY power supply"),
        ("VDD_NPU", "NPU-Accelerator", "NPU voltage supply"),
        ("VDD_IO_1V8", "LPDDR5-PHY", "DRAM PHY I/O voltage"),
    ]
    for src, dst, desc in _pd_powers:
        create_rel(conn, "POWERS", "PowerDomain", "Component", src, dst, {"description": desc})

    # Component ROUTES_TO relationships (regulator framework)
    _regulator_routes = [
        ("Linux-Regulator-Framework", "Regulator-Consumer-API", "Consumer-side API"),
        ("Linux-Regulator-Framework", "Regulator-Provider-API", "Provider-side API"),
        ("PMIC-I2C-Driver", "Linux-Regulator-Framework", "PMIC registers regulators"),
        ("Regulator-Consumer-API", "DCDC-Converter", "Consumer requests voltage from DCDC"),
        ("Regulator-Consumer-API", "LDO-Regulator", "Consumer requests voltage from LDO"),
        ("Voltage-Scaling-Governor", "Linux-Regulator-Framework", "Governor triggers voltage change via regulator API"),
        ("Power-Sequencer", "DCDC-Converter", "Sequencer controls DCDC enable order"),
        ("Power-Sequencer", "LDO-Regulator", "Sequencer controls LDO enable order"),
        ("OVP-UVP-Monitor", "DCDC-Converter", "Monitors DCDC output voltage"),
        ("Regulator-Coupler", "Linux-Regulator-Framework", "Coupling constraints registered with framework"),
    ]
    for src, dst, desc in _regulator_routes:
        create_rel(conn, "ROUTES_TO", "Component", "Component", src, dst, {"description": desc})

    # Component ROUTES_TO relationships (memory subsystem)
    _memory_routes = [
        ("ARM-MMU", "TLB-L1-Instruction", "MMU checks iTLB first"),
        ("ARM-MMU", "TLB-L1-Data", "MMU checks dTLB first"),
        ("TLB-L1-Instruction", "TLB-L2-Unified", "iTLB miss → L2 TLB lookup"),
        ("TLB-L1-Data", "TLB-L2-Unified", "dTLB miss → L2 TLB lookup"),
        ("TLB-L2-Unified", "Page-Table-Walker", "L2 TLB miss → hardware page table walk"),
        ("Page-Table-Walker", "L1-DCache", "PTW reads page table entries from L1 data cache"),
        ("L1-ICache", "L2-Unified-Cache", "L1 I$ miss → L2 lookup"),
        ("L1-DCache", "L2-Unified-Cache", "L1 D$ miss → L2 lookup"),
        ("L2-Unified-Cache", "L3-System-Cache", "L2 miss → L3 (DSU) lookup"),
        ("L3-System-Cache", "SCU-Snoop-Control-Unit", "L3 miss → snoop other cores via SCU"),
        ("SCU-Snoop-Control-Unit", "MESI-Coherency-Protocol", "SCU implements coherency protocol"),
        ("Hardware-Prefetcher", "L2-Unified-Cache", "Prefetcher fills L2 from L3/DRAM"),
        ("Linux-MM-Subsystem", "ARM-MMU", "Linux MM programs page tables consumed by MMU"),
        ("Linux-CMA-Allocator", "Linux-MM-Subsystem", "CMA reserves contiguous regions from page allocator"),
        ("Linux-ION-DMA-Heap", "Linux-CMA-Allocator", "DMA-BUF heap uses CMA for contiguous allocations"),
        ("Linux-KASAN", "Linux-MM-Subsystem", "KASAN instruments memory allocator for error detection"),
    ]
    for src, dst, desc in _memory_routes:
        create_rel(conn, "ROUTES_TO", "Component", "Component", src, dst, {"description": desc})

    # CAUSED_BY relationships for FailureModes
    _failure_causes = [
        ("PMIC-Under-Voltage-Lockout", "DCDC-Converter"),
        ("PMIC-Under-Voltage-Lockout", "OVP-UVP-Monitor"),
        ("Regulator-Enable-Timeout", "PMIC-I2C-Driver"),
        ("Regulator-Enable-Timeout", "Power-Sequencer"),
        ("Voltage-Scaling-Glitch", "Voltage-Scaling-Governor"),
        ("Voltage-Scaling-Glitch", "DCDC-Converter"),
        ("Rail-Coupling-Violation", "Regulator-Coupler"),
        ("TLB-Shootdown-Storm", "TLB-L1-Data"),
        ("TLB-Shootdown-Storm", "ARM-MMU"),
        ("Cache-Thrashing-L2", "L2-Unified-Cache"),
        ("CMA-Allocation-Failure", "Linux-CMA-Allocator"),
        ("CMA-Allocation-Failure", "Linux-ION-DMA-Heap"),
        ("Page-Table-Walk-Stall", "Page-Table-Walker"),
        ("Page-Table-Walk-Stall", "TLB-L2-Unified"),
        ("Kernel-OOM-DMA-Heap", "Linux-ION-DMA-Heap"),
        ("Kernel-OOM-DMA-Heap", "Linux-MM-Subsystem"),
        ("KASAN-Use-After-Free", "Linux-KASAN"),
    ]
    for fm_name, comp_name in _failure_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component", fm_name, comp_name)

    print(f"  [linux-regulator-arm-memory] Inserted {count} new nodes")
    return count


if __name__ == "__main__":
    inserted = ingest()
    print(f"Total inserted: {inserted}")
