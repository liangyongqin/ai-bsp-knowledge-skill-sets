#!/usr/bin/env python3
"""
Generate eval cases 341-380 expanding coverage of the latest seed scripts:
  - LPDDR5X / UFS 4.0 (linux-lpddr5x-ufs4.py)        - power-thermal + multimedia + boot-debug
  - CoreSight ETF/ETR/STM/CTI (arm-coresight-full.py) - boot-debug + interrupt-virt
  - Cross-domain Blackboard scenarios stitching the above with prior seed coverage

Distribution:
  341-350: LPDDR5X / UFS 4.0 (10 cases)  - power-thermal-expert + multimedia-camera-expert
  351-360: CoreSight trace subsystem (10 cases) - boot-debug-expert + interrupt-virtualization-expert
  361-370: Cross-domain Blackboard mentor scenarios (10 cases) - bsp-knowledge-mentor
  371-380: Edge cases / negative tests / boundary conditions (10 cases) - mixed skills

Run from repo root:
  python3 scripts/gen_eval_cases_341_380.py
"""
import json
import os

CASES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "evals", "cases")

CASES = [

    # -- LPDDR5X / UFS 4.0 cases (341-350) --

    {
        "id": "case_341",
        "skill": "power-thermal-expert",
        "input": (
            "Our flagship phone uses LPDDR5X-8533 (JEDEC JESD79-5B). Idle power is "
            "200mW higher than the LPDDR5-6400 reference design we previously shipped. "
            "Battery life regressed by 8% on the always-on dashboard test.\n\n"
            "PMIC rail telemetry:\n"
            "  VDD2H (1.05V): +35mA average vs reference\n"
            "  VDDQ (0.5V): +20mA average vs reference\n"
            "  Self-refresh entries per second: 1200 (vs 4500 on reference)\n\n"
            "Why is LPDDR5X showing higher idle current despite supporting deeper "
            "background-gate-self-throttle (BSST) modes? What kernel knobs in "
            "drivers/memory/ control LPDDR5X power state transitions, and what "
            "hardware mechanism reduces self-refresh entry frequency at HS-G5?"
        ),
        "expected_topics": [
            "LPDDR5X", "JESD79-5B", "BSST", "bank-subset-shutdown",
            "VDD2H", "VDDQ", "self-refresh", "TCSR", "DSM",
            "deep-sleep-mode", "self-refresh-residency", "devfreq"
        ],
        "min_score": 4,
        "tags": ["power-thermal-expert", "lpddr5x", "self-refresh", "memory-power", "battery-regression"]
    },

    {
        "id": "case_342",
        "skill": "power-thermal-expert",
        "input": (
            "LPDDR5X-7500 thermal runaway during sustained 4K60 video capture. After "
            "5 minutes the DRAM die temperature reaches 95C and the controller drops "
            "from HS-G5 to LPDDR5-6400 mode. Frame drops follow.\n\n"
            "Thermal log:\n"
            "  [00:00] dram_temp=72C, gear=HS-G5\n"
            "  [04:30] dram_temp=88C, gear=HS-G5, refresh_rate=2x\n"
            "  [05:01] dram_temp=95C, gear demoted to LPDDR5-6400\n"
            "  [05:01] camera_pipeline: dropped frames=12 in 1s\n\n"
            "What thermal feedback path does the LPDDR5X controller use to demote "
            "speed gears? What is the MR (Mode Register) used to signal die "
            "temperature, and how does temperature-compensated self-refresh (TCSR) "
            "interact with thermal demotion?"
        ),
        "expected_topics": [
            "LPDDR5X", "thermal-demotion", "MR4", "TCSR",
            "refresh-rate-doubling", "die-temperature", "HS-G5",
            "speed-gear-demotion", "camera-frame-drop", "thermal-zone"
        ],
        "min_score": 4,
        "tags": ["power-thermal-expert", "lpddr5x", "thermal-demotion", "dram-thermal", "speed-gear"]
    },

    {
        "id": "case_343",
        "skill": "multimedia-camera-expert",
        "input": (
            "UFS 4.0 (HS-G5) storage subsystem stalls during 8K60 RAW recording. The "
            "UFS host controller (UFSHCI v4.0) reports queue full, and the camera "
            "pipeline drops to RAW10 from RAW12.\n\n"
            "iostat -x 1:\n"
            "  /dev/sda  rkB/s=0  wkB/s=2300000  await=85ms  %util=100\n"
            "  ufs_qdepth: max=32, in_flight=32 sustained\n"
            "  ufs_temp: 78C (host), 82C (device)\n"
            "  HPB hits: 12% (cold cache, recording pattern)\n\n"
            "Why is the UFS 4.0 sustained write throughput collapsing despite HS-G5 "
            "advertising 23 Gbps per lane? What is the role of WriteBooster in UFS 4.0, "
            "and how does HPB (Host Performance Booster) factor into sequential write "
            "performance? What thermal interaction exists between the M-PHY Gen4 PHY "
            "and the NAND die?"
        ),
        "expected_topics": [
            "UFS-4.0", "UFSHCI-v4.0", "HS-G5", "M-PHY-Gen4",
            "WriteBooster", "HPB", "ufs-thermal", "queue-depth",
            "8K-recording", "JESD220F", "host-queue-depth"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "ufs-4.0", "writebooster", "8k-recording", "storage-stall"]
    },

    {
        "id": "case_344",
        "skill": "multimedia-camera-expert",
        "input": (
            "UFS 4.0 latency outliers during burst camera capture. Frame deadline is "
            "16.6ms (60fps) but every ~2 minutes a single write takes 220ms, causing "
            "missed frames.\n\n"
            "blktrace excerpt:\n"
            "  [120.012] write 4MB queued\n"
            "  [120.013] WB enabled (write booster)\n"
            "  [120.234] write 4MB completed (221ms!)\n"
            "  [120.235] dmesg: ufs: turbo write buffer flush triggered\n\n"
            "What internal UFS 4.0 device state transition causes a 200+ms outlier? "
            "How does the WriteBooster turbo buffer flush interact with foreground I/O? "
            "What `ufs-bsg` knob can clamp WB buffer size to bound worst-case latency?"
        ),
        "expected_topics": [
            "UFS-4.0", "WriteBooster", "WB-flush", "turbo-write-buffer",
            "latency-outlier", "ufs-bsg", "background-ops",
            "frame-deadline", "burst-capture", "WB-shared-buffer"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "ufs-4.0", "writebooster-flush", "latency-outlier", "burst-capture"]
    },

    {
        "id": "case_345",
        "skill": "boot-debug-expert",
        "input": (
            "Cold boot fails intermittently with LPDDR5X-7500. The bootloader reports "
            "DRAM training success but kernel panics 200ms into boot with random "
            "memory corruption.\n\n"
            "Bootloader log:\n"
            "  [pmic] VDD2H ramp to 1.05V: OK (sequence step 4/6)\n"
            "  [pmic] VDDQ ramp to 0.5V: OK (sequence step 5/6)\n"
            "  [dram] LPDDR5X DQS training: PASS (margin=18%)\n"
            "  [dram] CA training: PASS (margin=22%)\n"
            "  [dram] ZQ calibration done\n"
            "  [boot] kernel handoff at 145ms\n"
            "Kernel:\n"
            "  [200ms] BUG: KASAN out-of-bounds at random addresses\n\n"
            "The training margins look healthy. What in the LPDDR5X power-up sequence "
            "could complete training successfully but still cause random corruption "
            "shortly after? Consider VDD2H/VDDQ ordering, ZQ calibration timing, and "
            "RDQS strobe stability requirements at 7500 Mbps."
        ),
        "expected_topics": [
            "LPDDR5X", "VDD2H", "VDDQ", "power-sequencing",
            "DQS-training", "RDQS", "ZQ-calibration", "memory-corruption",
            "KASAN", "DRAM-training", "boot-failure"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "lpddr5x", "power-sequencing", "dram-training", "memory-corruption"]
    },

    {
        "id": "case_346",
        "skill": "boot-debug-expert",
        "input": (
            "UFS 4.0 device fails to enumerate during cold boot on 1 in 50 units. "
            "Failure mode: M-PHY Gen4 link initialization succeeds at HS-G3 but fails "
            "to negotiate HS-G5 boost.\n\n"
            "Bootloader UFS log:\n"
            "  [ufs] UIC link startup: OK\n"
            "  [ufs] HS-G3 negotiation: OK\n"
            "  [ufs] HS-G5 boost request sent\n"
            "  [ufs] DME_GET PA_PWRMODE timeout (200ms)\n"
            "  [ufs] fallback to HS-G3, performance mode degraded\n\n"
            "What in the M-PHY Gen4 link training would cause HS-G5 boost negotiation "
            "to fail intermittently? What role does RX squelch detection and CLK lane "
            "termination play in HS-G5 negotiation? Which UFSHCI v4.0 register exposes "
            "the PA_PWRMODE state machine?"
        ),
        "expected_topics": [
            "UFS-4.0", "M-PHY-Gen4", "HS-G5", "DME_GET",
            "PA_PWRMODE", "UIC-link-startup", "RX-squelch",
            "boost-mode", "boot-enumeration", "UFSHCI-v4.0"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "ufs-4.0", "m-phy-gen4", "hs-g5-boost", "cold-boot-failure"]
    },

    {
        "id": "case_347",
        "skill": "power-thermal-expert",
        "input": (
            "We need to validate that LPDDR5X DSM (Deep Sleep Mode) is actually being "
            "entered during system suspend-to-RAM. Currently suspend power is 50mW "
            "above target.\n\n"
            "What kernel sysfs path exposes LPDDR5X DSM residency counters? What "
            "PMIC rail measurement confirms the controller VDD has dropped to "
            "retention level? Walk through the verification sequence: \n"
            "  1. Enter S2R\n"
            "  2. Confirm DSM entry on each channel\n"
            "  3. Measure leakage on VDD2H and VDDQ\n"
            "  4. Verify wakeup latency stays under 500us\n"
            "Which Linux subsystem owns the DSM transition (devfreq, drivers/memory, "
            "or arm-smccc PSCI call)?"
        ),
        "expected_topics": [
            "LPDDR5X", "DSM", "deep-sleep-mode", "S2R",
            "VDD2H", "VDDQ", "self-refresh-residency",
            "wakeup-latency", "PSCI", "suspend-to-ram"
        ],
        "min_score": 4,
        "tags": ["power-thermal-expert", "lpddr5x", "deep-sleep-mode", "s2r-verification", "leakage-measurement"]
    },

    {
        "id": "case_348",
        "skill": "multimedia-camera-expert",
        "input": (
            "UFS 4.0 ZNS (Zoned Namespace) is enabled to extend NAND endurance during "
            "video recording. F2FS is configured for the streaming zone but we see "
            "Zone Append failures every few hours.\n\n"
            "F2FS log:\n"
            "  ufs_zone_append: zone 0x42 write_pointer=0x100000\n"
            "  ufs_zone_append: write 0x10000 bytes failed (-EIO)\n"
            "  ufs: device reports zone state TRANSITIONING\n"
            "  f2fs: GC bypass attempted, fallback to copy GC\n\n"
            "Why does a zone in TRANSITIONING state reject Zone Append? What is the "
            "F2FS interaction model with UFS 4.0 ZNS, and how does explicit zone "
            "RESET differ from implicit zone management? Should we configure a "
            "different segment size in F2FS to align with the UFS zone capacity?"
        ),
        "expected_topics": [
            "UFS-4.0", "ZNS", "Zone-Append", "F2FS",
            "zone-state", "TRANSITIONING", "implicit-zone-mgmt",
            "F2FS-GC", "segment-size", "zone-capacity", "JESD220F"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "ufs-4.0-zns", "f2fs", "zone-append", "video-recording"]
    },

    {
        "id": "case_349",
        "skill": "power-thermal-expert",
        "input": (
            "During graphics-heavy gameplay we measured LPDDR5X bandwidth at 51.2 GB/s "
            "(theoretical peak for HS-G5). The thermal envelope can only sustain "
            "32 GB/s without ambient cooling. We need a runtime cap that pegs LPDDR5X "
            "to a lower speed gear when the SoC die temperature exceeds 65C.\n\n"
            "Where does the Linux memory devfreq governor sit in the LPDDR5X clock "
            "tree? Can we dynamically demote the LPDDR5X data rate from HS-G5 (8533) "
            "to HS-G4 (7500) without re-training? What is the latency impact of an "
            "in-flight gear demotion vs a full re-train?"
        ),
        "expected_topics": [
            "LPDDR5X", "devfreq", "memory-bandwidth", "speed-gear",
            "thermal-envelope", "HS-G5", "HS-G4",
            "in-flight-demotion", "re-training-latency", "clock-tree"
        ],
        "min_score": 4,
        "tags": ["power-thermal-expert", "lpddr5x", "devfreq", "thermal-cap", "speed-gear-demotion"]
    },

    {
        "id": "case_350",
        "skill": "boot-debug-expert",
        "input": (
            "UFS 4.0 host controller reports SCSI sense data 'Logical Unit Not Ready, "
            "Cause Not Reportable' during cold boot, intermittently 1 in 200 boots. "
            "Other boots work fine.\n\n"
            "What in the UFS 4.0 boot sequence after VCC ramp could leave the device "
            "in 'not ready' state? Walk through: VCC ramp -> reset deassert -> "
            "boot LU initialization -> link startup -> Active mode. Where could a "
            "marginal timing violation cause intermittent enumeration failure?"
        ),
        "expected_topics": [
            "UFS-4.0", "VCC-ramp", "reset-deassert", "boot-LU",
            "link-startup", "active-mode", "logical-unit-not-ready",
            "JESD220F", "cold-boot", "enumeration-failure"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "ufs-4.0", "boot-lu", "intermittent-enum", "vcc-ramp"]
    },

    # -- CoreSight trace subsystem cases (351-360) --

    {
        "id": "case_351",
        "skill": "boot-debug-expert",
        "input": (
            "We are debugging an intermittent kernel hang during heavy I/O. We want "
            "to capture an instruction trace of the last few hundred microseconds "
            "before the hang using CoreSight ETM4 + ETF + ETR. The ETF has 64KB; "
            "the ETR is configured to write to a 16MB DRAM buffer.\n\n"
            "Walk through the configuration sequence: \n"
            "  1. CTI cross-trigger to halt all CPUs simultaneously\n"
            "  2. Stop ETM trace generation\n"
            "  3. Drain the ETF\n"
            "  4. Decode the ETR DRAM buffer using perf script\n"
            "Which Linux Documentation/trace/coresight/ files describe the sysfs "
            "configuration interface, and what is the role of TRBE in modern ARMv9 "
            "cores when capturing self-hosted trace?"
        ),
        "expected_topics": [
            "CoreSight", "ETM4", "ETF", "ETR", "CTI",
            "TRBE", "perf-script", "self-hosted-trace",
            "cross-trigger", "DRAM-buffer", "instruction-trace"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "etm-etf-etr", "trace-capture", "kernel-hang-debug"]
    },

    {
        "id": "case_352",
        "skill": "boot-debug-expert",
        "input": (
            "ETM4 trace generation hangs the CPU at activation time. dmesg shows:\n"
            "  coresight: TRCPRGCTLR write timeout\n"
            "  coresight etm0: failed to enable ETM\n\n"
            "ROM table walk shows ETM4 at the expected base address. What ADIv6 "
            "Q-Channel handshake is required before the ETM can be programmed? "
            "Which power domain and clock must be active for ETM4 register access? "
            "How does this relate to the CoreSight SoC-600 ATB (AMBA Trace Bus) "
            "fabric clock gating?"
        ),
        "expected_topics": [
            "CoreSight", "ETM4", "ADIv6", "Q-Channel",
            "TRCPRGCTLR", "ATB-clock", "ROM-table",
            "power-domain", "trace-fabric", "SoC-600"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "etm-activation", "adiv6", "trace-fabric-clock"]
    },

    {
        "id": "case_353",
        "skill": "boot-debug-expert",
        "input": (
            "We need software-level event correlation with hardware ETM trace. "
            "How do we use CoreSight STM (System Trace Macrocell) channels to log "
            "kernel scheduler decisions alongside ETM instruction trace?\n\n"
            "What MIPI STP (System Trace Protocol) records map to STM channels, and "
            "how does the Linux drivers/hwtracing/stm/ subsystem expose stimulus "
            "ports to user-space via /dev/stm0? How does the kernel correlate STM "
            "and ETM timestamps into a unified trace view?"
        ),
        "expected_topics": [
            "CoreSight", "STM", "MIPI-STP", "stimulus-port",
            "stm-policy", "scheduler-trace", "trace-correlation",
            "ETM4", "perf-trace", "/dev/stm0"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "stm", "stp-protocol", "trace-correlation"]
    },

    {
        "id": "case_354",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "When a watchdog NMI fires we need to halt all 8 CPU cores simultaneously "
            "and dump per-CPU ETM trace. We use CTI (Cross Trigger Interface) to "
            "broadcast halt across the cluster.\n\n"
            "What is the relationship between the per-CPU CTI, the cluster-level "
            "CTM (Cross Trigger Matrix), and external debug halt requests? How are "
            "trigger channels (input vs output) configured in CTICONTROL, "
            "CTITRIGINEN, CTITRIGOUTEN registers? What sequence enables 'halt on "
            "NMI' across all PEs in a Linux production kernel?"
        ),
        "expected_topics": [
            "CoreSight", "CTI", "CTM", "cross-trigger",
            "CTICONTROL", "CTITRIGINEN", "CTITRIGOUTEN",
            "halt-on-nmi", "external-debug", "cluster-halt", "NMI"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "coresight", "cti-ctm", "cluster-halt", "nmi-debug"]
    },

    {
        "id": "case_355",
        "skill": "boot-debug-expert",
        "input": (
            "ETR is configured to route trace into a 32MB DRAM region but we observe "
            "trace overrun (TMC_STS.Full) within 200ms of enabling. The same workload "
            "fits in the 64KB ETF without overflow.\n\n"
            "How does AXI bandwidth between the ATB-AXI bridge and DRAM limit "
            "sustainable trace bandwidth? What ETR scatter-gather (SG) mode allows "
            "non-contiguous DRAM regions, and how does its use of DMA SMMU "
            "translation tables interact with normal device DMA traffic? When does "
            "Catch-Up mode in TMC_CTL help vs hurt overflow conditions?"
        ),
        "expected_topics": [
            "CoreSight", "ETR", "TMC", "AXI-bandwidth",
            "scatter-gather", "TMC_STS", "Catch-Up-mode",
            "trace-overrun", "SMMU-translation", "ATB-AXI-bridge"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "etr-overrun", "axi-bandwidth", "scatter-gather"]
    },

    {
        "id": "case_356",
        "skill": "boot-debug-expert",
        "input": (
            "We are bringing up a new SoC and the CoreSight ROM table walk fails — "
            "the kernel cannot enumerate any debug components. The DAP (Debug Access "
            "Port) responds to SWD/JTAG queries but the ROM table base register at "
            "0x800000 returns 0xDEADBEEF.\n\n"
            "Walk through CoreSight ROM table debug: \n"
            "  1. Verify DAP idcode and version (ADIv5 vs ADIv6)\n"
            "  2. Confirm CoreSight power and clock domains are ungated\n"
            "  3. Check authentication signals (DBGEN, NIDEN, SPIDEN, SPNIDEN)\n"
            "  4. Verify the ROM table base in the integration manual matches\n"
            "What is the difference between an 'authenticated' debug session and "
            "self-hosted (Linux-driven) trace, and how do the authentication signals "
            "differ for each mode?"
        ),
        "expected_topics": [
            "CoreSight", "ROM-table", "DAP", "ADIv5", "ADIv6",
            "DBGEN", "NIDEN", "SPIDEN", "authentication-signals",
            "debug-power-domain", "self-hosted-trace"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "rom-table", "dap-debug", "authentication-signals"]
    },

    {
        "id": "case_357",
        "skill": "boot-debug-expert",
        "input": (
            "We added an off-chip trace probe via TPIU (Trace Port Interface Unit) "
            "but trace data is corrupted. Trace probe captures bytes but the decoder "
            "fails to align frames.\n\n"
            "TPIU configuration:\n"
            "  TPIU_CSPSR = 0x10  (16-bit data port width)\n"
            "  TPIU_SPPR = 0x00   (parallel mode)\n"
            "  Trace probe sample rate: 200MHz\n"
            "  ATB clock from SoC: 600MHz\n\n"
            "Why does the probe sample rate mismatch with the ATB clock cause frame "
            "misalignment? What is the role of the formatter (FFCR) in interleaving "
            "ETM/STM/ITM trace, and how does enabling FFCR.EnFCont help vs hurt "
            "frame alignment?"
        ),
        "expected_topics": [
            "CoreSight", "TPIU", "TPIU_CSPSR", "TPIU_SPPR",
            "ATB-clock", "FFCR", "trace-formatter",
            "frame-alignment", "off-chip-trace", "interleaving"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "tpiu", "off-chip-trace", "formatter-frame"]
    },

    {
        "id": "case_358",
        "skill": "boot-debug-expert",
        "input": (
            "ETE (Embedded Trace Extension, ARMv9) trace into TRBE (Trace Buffer "
            "Extension) is producing trace records but they are not decodable by "
            "OpenCSD. Errors:\n"
            "  decoder: stream sync lost at offset 0x100\n"
            "  decoder: I_SYNC packet missing\n\n"
            "ETE configuration:\n"
            "  TRCPRGCTLR.EN = 1\n"
            "  TRCSYNCPR = 0x0B  (sync every 4KB)\n"
            "  TRCCONFIGR.TS = 1 (timestamps enabled)\n\n"
            "What is the sync period interaction between TRCSYNCPR and TRBE? Is the "
            "OpenCSD decoder version compatible with ETE? How does ETE differ from "
            "ETM4 in terms of sync packet generation, and what perf script invocation "
            "decodes ETE trace records produced via TRBE?"
        ),
        "expected_topics": [
            "CoreSight", "ETE", "TRBE", "OpenCSD",
            "TRCSYNCPR", "I_SYNC", "ARMv9-trace",
            "perf-script", "sync-period", "ETM4-vs-ETE"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "ete-trbe", "opencsd-decode", "armv9-trace"]
    },

    {
        "id": "case_359",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "We need to capture a virtualized guest's instruction trace from the "
            "host using CoreSight ETE + TRBE. The host runs Linux 6.10 with KVM, "
            "and the guest runs an unmodified RTOS.\n\n"
            "What is the host-side ETE configuration to filter trace to a specific "
            "vCPU thread? How does ETE.EXLEVEL_NS_S (exception level filter) interact "
            "with EL1/EL2 boundaries? Does TRBE need EL2 access mode for cross-VM "
            "trace, and what is the role of HCR_EL2.TID4 trap configuration?"
        ),
        "expected_topics": [
            "CoreSight", "ETE", "TRBE", "KVM",
            "EXLEVEL_NS_S", "EL2", "HCR_EL2", "vCPU-trace",
            "exception-level-filter", "guest-trace"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "coresight", "ete-kvm", "trbe-el2", "guest-trace"]
    },

    {
        "id": "case_360",
        "skill": "boot-debug-expert",
        "input": (
            "Production kernel must support 'always-on' last-trace capture for field "
            "crash analysis. Constraints: ETR overhead < 1% CPU, no impact on perf "
            "tools, trace ring buffer must survive a kernel panic.\n\n"
            "Design a CoreSight always-on trace pipeline:\n"
            "  1. ETM4 with sparse instruction filtering (TRCSSCCRn)\n"
            "  2. ETR scatter-gather to a reserved DMA pool\n"
            "  3. pstore integration so trace is preserved across reboot\n"
            "  4. Recovery path: read trace from /sys/fs/pstore on next boot\n"
            "What kernel command-line options enable this, and what is the upstream "
            "status (Linux 6.x) of pstore-coresight integration?"
        ),
        "expected_topics": [
            "CoreSight", "ETM4", "ETR", "TRCSSCCRn",
            "pstore", "always-on-trace", "scatter-gather",
            "DMA-pool", "kernel-panic", "field-crash"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "coresight", "always-on-trace", "pstore", "production-tracing"]
    },

    # -- Cross-domain Blackboard mentor scenarios (361-370) --

    {
        "id": "case_361",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "We are debugging a flagship phone that reboots when the user records "
            "8K60 RAW video for >3 minutes. The reboot is silent — no kernel panic "
            "in /proc/last_kmsg, no dmesg trail. Three subsystems are involved: "
            "LPDDR5X-8533 (peak bandwidth), UFS 4.0 HS-G5 (sustained writes), and "
            "the camera ISP pipeline (8K RAW capture).\n\n"
            "Initial telemetry:\n"
            "  PMIC: VDD2H droop to 0.95V (target 1.05V) at minute 2:30\n"
            "  UFS: WriteBooster turbo flush at minute 2:45 (220ms stall)\n"
            "  Camera: V4L2 buffer queue empty at minute 2:46\n"
            "  Last sample: thermal_zone0=98C\n\n"
            "Apply the Blackboard pattern. Which domain experts should activate? "
            "What hypothesis ordering makes physical sense given the telemetry? "
            "How would you use CoreSight ETR with pstore to capture the next "
            "occurrence's instruction trace across the silent reboot?"
        ),
        "expected_topics": [
            "Blackboard", "LPDDR5X", "UFS-4.0", "8K-recording",
            "VDD2H-droop", "WriteBooster", "thermal", "silent-reboot",
            "pstore", "CoreSight", "cross-domain", "PMIC-transient"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "blackboard", "8k-reboot", "lpddr5x-ufs", "cross-domain"]
    },

    {
        "id": "case_362",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "An algorithm engineer reports: 'Inference latency on the on-device LLM "
            "spikes from 80ms to 350ms intermittently. Memory bandwidth profiling "
            "shows we are not bound on bandwidth. NPU utilization stays at 95%.'\n\n"
            "How do you translate this complaint into a BSP investigation? Walk "
            "through your Socratic guidance: \n"
            "  1. What hypotheses span across the BSP / algorithm boundary?\n"
            "  2. Which Blackboard agents should engage (power-thermal? interrupt-virt?)?\n"
            "  3. How do you re-frame 'inference latency spike' in terms of LPDDR5X "
            "self-refresh exits, NPU IRQ coalescing, or SCP firmware preemption?"
        ),
        "expected_topics": [
            "Blackboard", "Socratic", "algorithm-engineer",
            "inference-latency", "LPDDR5X", "self-refresh-exit",
            "NPU-IRQ", "SCP-preemption", "cross-department",
            "terminology-translation", "BSP-translation"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "socratic", "algo-translation", "inference-latency", "cross-department"]
    },

    {
        "id": "case_363",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Cross-domain failure: 'Kernel panic at boot, only on units with the "
            "new UFS 4.0 SKU. The same firmware on UFS 3.1 boards boots fine.'\n\n"
            "Console capture (over UART):\n"
            "  [0.012] DRAM init: LPDDR5X-7500 OK\n"
            "  [0.045] PSCI: CPU1 brought up\n"
            "  [0.080] coresight: ROM table walk failed\n"
            "  [0.100] BUG: kernel NULL pointer dereference\n"
            "  [0.100] PC is at coresight_etm_init+0x44\n\n"
            "Why might enabling UFS 4.0 cause CoreSight init to fail? Hint: think "
            "about device-tree clock and power-domain references. Which Blackboard "
            "experts (boot-debug, interrupt-virtualization, hardware-spec) should "
            "examine which artifacts? Lead the engineer through Socratic discovery."
        ),
        "expected_topics": [
            "Blackboard", "UFS-4.0", "CoreSight", "device-tree",
            "clock-domain", "power-domain", "ROM-table",
            "kernel-panic", "Socratic", "cross-domain",
            "boot-debug", "hardware-spec"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "blackboard", "ufs-coresight", "boot-panic", "dt-clock"]
    },

    {
        "id": "case_364",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Management asks: 'Our smart glasses competitor advertises 8h continuous "
            "video recording with 2x our battery capacity. We get 4h on equivalent "
            "hardware. What's the physics gap?'\n\n"
            "Translate this into a BSP investigation tree without exposing register "
            "addresses. What top-level BSP factors limit continuous-recording battery "
            "life on a 1W power budget? How do LPDDR5X DSM residency, UFS 4.0 "
            "WriteBooster discipline, ISP-DMA bypass paths, and CoreSight always-on "
            "trace overhead each factor in? Frame your answer in business terms "
            "first, then surface the BSP investigation steps."
        ),
        "expected_topics": [
            "business-impact", "battery-life", "1W-budget",
            "LPDDR5X-DSM", "UFS-WriteBooster", "ISP-DMA",
            "CoreSight-overhead", "cross-department",
            "smart-glasses", "continuous-recording"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "business-translation", "battery-analysis", "smart-glasses", "continuous-recording"]
    },

    {
        "id": "case_365",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "A new BSP engineer (1 week experience) asks: 'The system hangs when I "
            "enable CoreSight ETM trace. Should I just disable trace?'\n\n"
            "Apply ITS Socratic teaching at the application/driver boundary. The "
            "engineer is at the driver-engineer level (mentions kernel ETM driver). "
            "Do not give the answer. Lead them through:\n"
            "  1. Symptom restatement (what exactly hangs?)\n"
            "  2. Resource state probe (what does dmesg say?)\n"
            "  3. Hypothesis (what does ETM need to operate?)\n"
            "  4. Tool verification (which sysfs files reveal CoreSight power state?)\n"
            "Avoid giving the answer (clock/power domain ungated). Build the "
            "engineer's diagnostic thinking."
        ),
        "expected_topics": [
            "Socratic", "ITS", "driver-engineer-level",
            "CoreSight", "ETM", "clock-domain", "power-domain",
            "sysfs-probe", "diagnostic-thinking", "no-direct-answer"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "socratic", "its-teaching", "junior-engineer", "coresight-debug"]
    },

    {
        "id": "case_366",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Diagnose a complex device-tree issue spanning UFS 4.0, LPDDR5X, and "
            "CoreSight: 'After upgrading from kernel 6.6 to 6.12, the bootloader "
            "successfully passes DT to the kernel, but the kernel logs cascading "
            "probe failures: ufshcd-pltfrm probe defer, lpddr5x-mc probe defer, "
            "coresight-etm probe failure. Reverting to 6.6 works.'\n\n"
            "Use the Blackboard pattern. What kernel 6.7-6.12 device-tree binding "
            "changes could cascade into these three subsystems? Which agents "
            "(boot-debug, multimedia-camera, hardware-spec) should engage? How would "
            "you instrument 'probe defer chain' debugging across subsystems?"
        ),
        "expected_topics": [
            "Blackboard", "device-tree", "kernel-6.12",
            "UFS-4.0", "LPDDR5X", "CoreSight",
            "probe-defer", "ufshcd-pltfrm", "binding-change",
            "cross-domain", "subsystem-cascade"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "blackboard", "kernel-upgrade", "probe-defer", "dt-cascade"]
    },

    {
        "id": "case_367",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Real-world cross-team incident: \n"
            "  - QA team: 'video preview shows tearing every 30 seconds'\n"
            "  - GPU team: 'frame deadline met, no overdraw issues'\n"
            "  - BSP team: 'thermal not throttling, PMIC stable'\n"
            "  - Camera team: 'V4L2 stats show no buffer underrun'\n\n"
            "Each team's measurement is correct in isolation, but tearing is "
            "reproducible. Apply the Blackboard pattern. What single root cause "
            "could simultaneously appear invisible to all four teams? Hint: think "
            "about LPDDR5X self-refresh exit latency synchronization across the "
            "ISP-GPU-Display data path. How do you frame the convergence step?"
        ),
        "expected_topics": [
            "Blackboard", "video-tearing", "LPDDR5X",
            "self-refresh-exit", "ISP-GPU-Display",
            "convergence", "cross-team", "DMA-synchronization",
            "memory-bus-contention", "frame-pacing"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "blackboard", "video-tearing", "cross-team", "memory-contention"]
    },

    {
        "id": "case_368",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Senior engineer pushback: 'CoreSight trace is overhead I don't want in "
            "production. Just give me ftrace.'\n\n"
            "Use ITS to validate the engineer's expertise (don't talk down) but "
            "build the case for a hybrid: ftrace for software-level events, "
            "always-on CoreSight ETM for last-N-cycles instruction trace at panic. "
            "How do you frame the trade-off in driver-engineer language without "
            "being preachy? What concrete kernel configuration delivers both, and "
            "what production overhead measurements should the engineer collect to "
            "validate the hybrid approach?"
        ),
        "expected_topics": [
            "ITS", "senior-engineer", "ftrace", "CoreSight",
            "ETM4", "always-on-trace", "hybrid-tracing",
            "production-overhead", "panic-trace", "driver-language",
            "trade-off-framing"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "its-teaching", "senior-engineer", "ftrace-vs-coresight", "hybrid-tracing"]
    },

    {
        "id": "case_369",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Coordination scenario: 'Our team is integrating a new camera sensor "
            "(CSI-2 v4.2 with EVS). Before we cut a tape-out, we want a Blackboard "
            "review across BSP domains.'\n\n"
            "Schedule the multi-agent review: \n"
            "  1. multimedia-camera-expert: V4L2/MIPI binding readiness\n"
            "  2. power-thermal-expert: LPDDR5X bandwidth headroom for EVS streaming\n"
            "  3. interrupt-virtualization-expert: GIC-700 SPI assignment for sensor IRQs\n"
            "  4. boot-debug-expert: device-tree review and CoreSight trace plan\n"
            "What is the synthesis output format? How does the mentor weight "
            "conflicting recommendations (e.g., camera asks for 8533 Mbps DRAM, "
            "power says cap at 7500 for thermal)?"
        ),
        "expected_topics": [
            "Blackboard", "multi-agent-review", "tape-out",
            "MIPI-CSI-2", "EVS", "LPDDR5X", "GIC-700",
            "device-tree", "CoreSight",
            "synthesis", "conflict-resolution", "cross-domain"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "blackboard", "tape-out-review", "multi-agent", "design-review"]
    },

    {
        "id": "case_370",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Field issue post-mortem: 0.3% of devices in production show 'random "
            "reboot under heavy network load'. Field returns show no consistent "
            "hardware fault. Three teams have proposed root causes:\n"
            "  - Kernel team: TCP softirq starvation\n"
            "  - BSP team: PMIC transient under WiFi-6 burst load\n"
            "  - Driver team: WiFi MAC IRQ storm\n\n"
            "Each is plausible. Apply the Blackboard convergence step. How do you "
            "design a coordinated diagnostic capture (CoreSight ETM trace + irqbalance "
            "stats + PMIC telemetry) that arbitrates between the three hypotheses? "
            "What is the success criterion for each test, and what synthesis output "
            "would route the fix correctly?"
        ),
        "expected_topics": [
            "Blackboard", "field-issue", "post-mortem",
            "TCP-softirq", "PMIC-transient", "WiFi-IRQ-storm",
            "CoreSight", "irqbalance", "convergence",
            "arbitration", "diagnostic-capture", "cross-team"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "blackboard", "field-postmortem", "convergence", "diagnostic-capture"]
    },

    # -- Edge cases / negative tests / boundary conditions (371-380) --

    {
        "id": "case_371",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Test: a manager asks 'What are the values of GICD_INMIR0 register on "
            "our SoC, and how do we configure SPI 32 for NMI delivery?'\n\n"
            "The mentor MUST refuse to give register addresses to a non-engineering "
            "audience and translate the request into business language: 'Why does "
            "watchdog hang detection matter for shipping reliability?'\n\n"
            "Demonstrate the prohibition rule and the cross-department translation "
            "from low-level register configuration to business outcome (uptime, "
            "field-return rate, brand reputation)."
        ),
        "expected_topics": [
            "prohibition", "no-register-cross-department",
            "business-translation", "watchdog", "uptime",
            "field-return", "brand-reputation", "ITS",
            "level-mismatch", "GICD_INMIR0"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "negative-test", "prohibition-rule", "register-redaction", "cross-department"]
    },

    {
        "id": "case_372",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Test: an engineer asks 'How do we force-shutdown VDD_LPDDR5X to save "
            "power during S2R?'\n\n"
            "The mentor MUST refuse without verifying the full power sequence (DRAM "
            "must be in Self-Refresh before VDD2H is lowered, not removed). "
            "Demonstrate the prohibition rule against suggesting power-domain "
            "shutdown without verifying the supply sequence."
        ),
        "expected_topics": [
            "prohibition", "power-domain-shutdown",
            "supply-sequence", "DRAM-self-refresh",
            "VDD2H-retention", "S2R", "data-loss-risk",
            "verification-required", "LPDDR5X"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "negative-test", "prohibition-rule", "power-shutdown", "supply-sequence"]
    },

    {
        "id": "case_373",
        "skill": "power-thermal-expert",
        "input": (
            "Boundary test: LPDDR5X-8533 minimum self-refresh entry latency. The "
            "JEDEC spec requires tCKESR (CKE-low setup before SRE) of 5ns at 8533. "
            "Our board measures tCKESR_actual=4.8ns under high temperature.\n\n"
            "Is 4.8ns within the spec margin? What is the consequence of marginal "
            "tCKESR violation: data corruption, missed self-refresh entry, or both? "
            "Which DDR PHY register exposes the actual measured timing for this "
            "parameter, and what is the recommended margin to add for thermal "
            "compensation?"
        ),
        "expected_topics": [
            "LPDDR5X", "tCKESR", "self-refresh-entry",
            "JEDEC-spec", "thermal-compensation",
            "PHY-register", "marginal-timing", "data-corruption",
            "JESD79-5B", "boundary-condition"
        ],
        "min_score": 4,
        "tags": ["power-thermal-expert", "boundary-test", "lpddr5x-timing", "tckesr", "marginal-spec"]
    },

    {
        "id": "case_374",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "Edge case: GICv4.2 vNMI delivery to a vPE that is NOT currently "
            "scheduled. The host has the vPE in 'unscheduled' state in the ITS "
            "VPENDBASER register.\n\n"
            "Per the GICv4.2 architecture spec: \n"
            "  - Pending bit is set in vPE's pending table\n"
            "  - When vPE is later scheduled (VMOVP), vNMI fires\n"
            "  - Latency between physical NMI source and vNMI delivery = "
            "    schedule latency (potentially milliseconds)\n\n"
            "Is this acceptable for a hard-real-time vNMI watchdog? What pinning "
            "strategy (vCPU-to-pCPU affinity) eliminates schedule latency? When "
            "should the system fall back to direct NMI delivery to the host (vs vNMI)?"
        ),
        "expected_topics": [
            "GICv4.2", "vNMI", "vPE", "ITS",
            "VPENDBASER", "VMOVP", "schedule-latency",
            "real-time", "vCPU-pinning", "fallback-NMI",
            "boundary-condition"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "boundary-test", "gicv4.2-vnmi", "vpe-unscheduled", "real-time"]
    },

    {
        "id": "case_375",
        "skill": "multimedia-camera-expert",
        "input": (
            "Edge case: UFS 4.0 with a single LU (Logical Unit) versus the typical "
            "4-LU partition layout (boot/main/RPMB/well-known). On a single-LU "
            "device, can we achieve the JEDEC theoretical 23 Gbps per lane HS-G5 "
            "throughput, or is multi-LU partitioning required for queue parallelism?\n\n"
            "What is the host-side queue depth limit per LU vs total host queue "
            "depth in UFSHCI v4.0? How does the multi-circular queue (MCQ) feature "
            "interact with single-LU configurations?"
        ),
        "expected_topics": [
            "UFS-4.0", "Logical-Unit", "single-LU",
            "queue-depth", "MCQ", "multi-circular-queue",
            "HS-G5", "JEDEC", "JESD220F", "UFSHCI-v4.0",
            "boundary-condition"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "boundary-test", "ufs-4.0", "single-lu", "mcq"]
    },

    {
        "id": "case_376",
        "skill": "boot-debug-expert",
        "input": (
            "Edge case: CoreSight ETR is configured but the system has only 1MB of "
            "DRAM available for trace (extreme low-memory device). The recommended "
            "ETR buffer is 16-32MB.\n\n"
            "Is ETR usable with 1MB? What is the worst-case trace overrun behavior? "
            "Should we fall back to ETF-only configuration (64KB on-chip), and what "
            "trace-capture-window length does that limit us to under typical CPU "
            "instruction rate?\n\n"
            "Walk through the math: at 2GHz CPU, ~3 IPC, 1 byte per instruction "
            "encoded ETM4 trace, what trace-window does 64KB ETF buffer?"
        ),
        "expected_topics": [
            "CoreSight", "ETR", "ETF", "low-memory",
            "trace-overrun", "ETF-only", "trace-window",
            "instruction-rate", "IPC", "boundary-condition"
        ],
        "min_score": 4,
        "tags": ["boot-debug-expert", "boundary-test", "coresight", "low-memory-trace", "etf-only"]
    },

    {
        "id": "case_377",
        "skill": "gpu-rendering-expert",
        "input": (
            "Edge case: GPU rendering at 120fps with LPDDR5X-8533 — sustained memory "
            "bandwidth measured at 65 GB/s (close to theoretical peak of 68.3 GB/s). "
            "Frame pacing jitters by +/- 2ms.\n\n"
            "Is this jitter caused by GPU shader stalls, or by LPDDR5X self-refresh "
            "exits during inter-frame gaps? How do you isolate GPU-side vs DRAM-side "
            "jitter using Perfetto + memory bus probes? What sysfs knob tunes the "
            "self-refresh entry threshold to avoid entering self-refresh during "
            "120fps gaps (if the gap is shorter than self-refresh entry latency)?"
        ),
        "expected_topics": [
            "GPU-rendering", "LPDDR5X", "self-refresh",
            "frame-pacing", "120fps", "Perfetto",
            "memory-jitter", "self-refresh-entry-threshold",
            "inter-frame-gap", "shader-stall"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "boundary-test", "120fps-pacing", "lpddr5x-jitter", "self-refresh"]
    },

    {
        "id": "case_378",
        "skill": "hardware-spec-extractor",
        "input": (
            "Edge case: a vendor TRM provides UFS 4.0 controller registers as a "
            "non-standard XML format (not Accellera IP-XACT 2022). The XML uses "
            "different field names (offset vs address, bit_range vs bit_field). "
            "How does the spec extractor handle non-standard XML?\n\n"
            "Walk through the validation pipeline: \n"
            "  1. Detect XML schema (IP-XACT 2014 vs 2022 vs custom)\n"
            "  2. Apply field-name mapping (custom -> canonical)\n"
            "  3. Validate against the Kuzu Register schema\n"
            "  4. Report any fields that cannot be mapped\n"
            "What is the recommended workflow when 30% of register fields cannot "
            "be auto-mapped — manual annotation, template extension, or refusal?"
        ),
        "expected_topics": [
            "IP-XACT", "Accellera", "non-standard-XML",
            "field-mapping", "schema-detection",
            "validation", "Kuzu-Register-schema",
            "manual-annotation", "boundary-condition", "extractor"
        ],
        "min_score": 4,
        "tags": ["hardware-spec-extractor", "boundary-test", "non-standard-xml", "field-mapping", "validation"]
    },

    {
        "id": "case_379",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "Negative test: a junior driver engineer proposes 'increase GIC ITS "
            "ITT (Interrupt Translation Table) size to 1GB to support more MSIs'. "
            "The current ITT is 16MB and the system has 8GB DRAM total.\n\n"
            "Why is 1GB an unreasonable ITT size, even with abundant DRAM? What is "
            "the ITT entry size (per LPI), and what is the upper bound on number of "
            "LPIs in GICv3/v4 architecture? How would you Socratically guide the "
            "engineer to size ITT correctly based on platform LPI count?"
        ),
        "expected_topics": [
            "GIC-ITS", "ITT", "Interrupt-Translation-Table",
            "LPI", "ITT-entry-size", "GICv3", "GICv4",
            "Socratic", "negative-test", "platform-sizing"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "negative-test", "its-itt-sizing", "lpi-count", "socratic"]
    },

    {
        "id": "case_380",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Cross-domain end-to-end exercise: a new BSP team member is given this "
            "incomplete bug report: \n"
            "  'Phone gets warm. Performance feels sluggish. Sometimes camera "
            "doesn't open. We think it's the kernel.'\n\n"
            "Apply the full mentor workflow: \n"
            "  1. Symptom restatement (what 'warm' means measurably)\n"
            "  2. Resource probe (what telemetry to capture)\n"
            "  3. Hypothesis fan-out (which Blackboard agents to engage)\n"
            "  4. Convergence (how to narrow from 'kernel issue' to specific subsystem)\n"
            "  5. Cross-department output (what to tell PM / QA in business terms)\n\n"
            "Demonstrate the full ITS+Blackboard+terminology-translation flow on "
            "this vague-but-realistic bug report. Do not solve the bug — teach the "
            "engineer the diagnostic process."
        ),
        "expected_topics": [
            "ITS", "Blackboard", "Socratic",
            "symptom-restatement", "resource-probe",
            "hypothesis-fanout", "convergence",
            "business-translation", "diagnostic-process",
            "thermal", "performance", "camera-open",
            "cross-domain", "end-to-end"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "end-to-end", "full-workflow", "vague-bug-report", "teaching"]
    },
]


def main():
    os.makedirs(CASES_DIR, exist_ok=True)
    written = 0
    for case in CASES:
        case_id = case["id"]
        path = os.path.join(CASES_DIR, f"{case_id}.json")
        with open(path, "w") as f:
            json.dump(case, f, indent=2)
            f.write("\n")
        written += 1
    print(f"Written {written} eval cases to {CASES_DIR}")
    print(f"Case range: case_341 - case_380")


if __name__ == "__main__":
    main()
