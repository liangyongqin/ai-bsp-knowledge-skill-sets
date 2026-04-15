#!/usr/bin/env python3
"""
Generate eval cases 301–340 targeting newer knowledge graph domains:
  - GIC NMI / GICv4.2 vNMI (interrupt-virtualization-expert)
  - Panthor DRM / Mali CSF (gpu-rendering-expert)
  - MIPI CSI-2 v4.0/v4.2 features (multimedia-camera-expert)
  - Cross-domain mentor scenarios using the above domains

Run from repo root:
  python3 scripts/gen_eval_cases_301_340.py
"""
import json
import os

CASES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "evals", "cases")

CASES = [

    # ── GIC NMI v4.2 cases (301–310) ─────────────────────────────────────────

    {
        "id": "case_301",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "Our hardware watchdog NMI is not being delivered on a GICv3.3 system. "
            "The watchdog is configured to fire a non-maskable interrupt when the CPU "
            "lockup is detected, but the NMI handler is never called during a simulated "
            "CPU hang.\n\n"
            "dmesg (before hang):\n"
            "  [  0.500] GICv3: Using GICv3.3 NMI support (FEAT_GICv3_NMI detected)\n"
            "  [  0.501] watchdog: nmi_watchdog_setup: marking SPI 32 as NMI via GICD_INMIR0\n"
            "  [  0.502] GICv3-NMI: SPI 32 configured as non-maskable in GICD_INMIR0\n"
            "  ... (system hangs, no crash dump, no NMI handler invocation)\n\n"
            "ID_AA64PFR1_EL1 readout:\n"
            "  NMI field = 0b0000  (FEAT_NMI NOT implemented on this PE)\n\n"
            "The kernel shows GICv3.3 detected at the GIC level, but the PE itself does "
            "not implement FEAT_NMI. How do we diagnose and resolve this NMI delivery "
            "failure? What is the relationship between GICv3.3 FEAT_GICv3_NMI and the "
            "PE-level FEAT_NMI?"
        ),
        "expected_topics": [
            "GICv3.3", "FEAT_NMI", "FEAT_GICv3_NMI", "GICD_INMIR",
            "NMI-masked", "ID_AA64PFR1_EL1", "watchdog", "pseudo-NMI",
            "ALLINT", "ICC_PMR_EL1"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "gic-nmi", "gicv3.3", "feat-nmi", "watchdog", "nmi-delivery"]
    },

    {
        "id": "case_302",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "We are running a real-time VM with a hardware watchdog. The VM uses "
            "GICv4.2 vNMI to deliver non-maskable virtual interrupts directly without "
            "trap-and-emulate. The guest watchdog timer fires but the virtual NMI is "
            "never delivered inside the guest.\n\n"
            "Host dmesg:\n"
            "  [  0.100] GICv4.2 detected, vNMI support enabled\n"
            "  [  0.200] kvm: vgic-v4: ITS VMAPP for vPE 0 configured (vNMI=0)\n"
            "  [  0.201] kvm: vgic: GICv4.2 vNMI delivery bit NOT set for vPE 0\n\n"
            "Guest dmesg:\n"
            "  (no NMI received, guest watchdog timeout, soft lockup)\n\n"
            "KVM config:\n"
            "  CONFIG_KVM_ARM_VGIC_V4=y\n"
            "  GIC hardware: GICv4.2 confirmed via GICD_TYPER2.nASSGIcap\n\n"
            "The ITS VMAPP command was issued but the vNMI delivery bit was not set. "
            "What is the correct sequence to enable vNMI delivery for a vPE via the "
            "ITS VMAPP/VMOVP command interface?"
        ),
        "expected_topics": [
            "GICv4.2", "vNMI", "ITS", "VMAPP", "VMOVP", "vPE",
            "KVM", "GICv4.2-vNMI-Not-Injected", "VINMI",
            "virtual-NMI", "trap-and-emulate"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "gicv4.2", "vnmi", "its-vmapp", "kvm-vgic", "real-time-vm"]
    },

    {
        "id": "case_303",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "We are using Linux pseudo-NMI on an arm64 system with GIC-600 (pre-GICv3.3). "
            "The 'perf record' command shows missing PMU overflow samples intermittently. "
            "We also see spurious 'unexpected NMI' messages in dmesg during heavy CPU load.\n\n"
            "dmesg:\n"
            "  [  45.100] perf: arm_pmu: PMU overflow NMI handler invoked\n"
            "  [  45.101] NMI: Unexpected NMI from unknown source, ignored\n"
            "  [  45.102] perf: arm_pmu: missed overflow sample, counter=0x80000000\n\n"
            "Kernel: 5.15 LTS (before architectural NMI support)\n"
            "ICC_PMR_EL1 usage: pseudo-NMI via priority masking\n\n"
            "The pseudo-NMI implementation uses ICC_PMR_EL1 to create a superpriority "
            "window. What race condition in the interrupt exit path can cause PMR to "
            "mask a pending pseudo-NMI, and what is the architectural fix available "
            "on GICv3.3+ hardware?"
        ),
        "expected_topics": [
            "pseudo-NMI", "ICC_PMR_EL1", "GIC-600", "PMU-overflow",
            "pseudo-NMI-PMR-race", "ALLINT", "GICv3.3", "perf",
            "arm64-nmi", "interrupt-exit"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "pseudo-nmi", "pmr-race", "icc-pmr", "perf-pmu", "gic-600"]
    },

    {
        "id": "case_304",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "How do I configure a specific SPI as non-maskable on a GICv3.3 system? "
            "I have SPI 45 (watchdog timer) that should fire even when the CPU is in "
            "a critical section with interrupts disabled. I need to understand the "
            "GICD_INMIR register layout and the required CPU-side configuration "
            "(PSTATE.ALLINT) to correctly enable architectural NMI on arm64."
        ),
        "expected_topics": [
            "GICD_INMIR", "GICR_INMIR", "GICv3.3", "NMI", "SPI",
            "ALLINT", "PSTATE", "ICC_PMR_EL1", "FEAT_NMI",
            "non-maskable-interrupt", "watchdog-configuration"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "gicd-inmir", "nmi-configuration", "gicv3.3", "pstate-allint"]
    },

    {
        "id": "case_305",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "We are bringing up a new SoC that claims GICv3.3 support. Before enabling "
            "architectural NMI in the kernel, I need to verify both the GIC hardware and "
            "the CPU cores support the feature. What registers and ID fields should I "
            "check to confirm end-to-end NMI support, and what is the fallback path "
            "if the CPU does not implement FEAT_NMI?"
        ),
        "expected_topics": [
            "FEAT_NMI", "ID_AA64PFR1_EL1", "GICv3.3", "FEAT_GICv3_NMI",
            "pseudo-NMI", "GIC-capabilities", "cpu-id-registers",
            "GICD_TYPER", "NMI-bringup"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "nmi-bringup", "feat-nmi", "id-registers", "gicv3.3-capability"]
    },

    {
        "id": "case_306",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "Explain the NMI superpriority mechanism in GICv3.3. How does a non-maskable "
            "interrupt bypass the ICC_PMR_EL1 priority mask? What are the PSTATE.ALLINT "
            "and MSR ALLINT operations, and when does the kernel set or clear ALLINT "
            "during NMI handler entry and exit? Provide the interrupt delivery flow "
            "for a GICv3.3 NMI from hardware assertion to kernel handler invocation."
        ),
        "expected_topics": [
            "NMI-superpriority", "ICC_PMR_EL1", "ALLINT", "PSTATE",
            "GICv3.3", "NMI-delivery-flow", "interrupt-masking",
            "FEAT_NMI", "priority-bypass", "handler-entry"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "nmi-superpriority", "allint", "nmi-delivery-flow", "gicv3.3"]
    },

    {
        "id": "case_307",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "We are planning to migrate from Linux pseudo-NMI to architectural NMI "
            "on a GICv3.3 platform. Our current pseudo-NMI is used for perf PMU "
            "sampling and the hardware watchdog. What are the key differences between "
            "pseudo-NMI and architectural GICv3.3 NMI in terms of kernel configuration, "
            "GICD_INMIR setup, and PSTATE.ALLINT handling? What regressions should "
            "we test for during the migration?"
        ),
        "expected_topics": [
            "pseudo-NMI", "GICv3.3", "FEAT_NMI", "GICD_INMIR",
            "ICC_PMR_EL1", "ALLINT", "PMU", "watchdog",
            "migration", "arm64-nmi-config"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "nmi-migration", "pseudo-nmi-to-architectural", "gicv3.3"]
    },

    {
        "id": "case_308",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "We need to enable KVM GICv4.2 vNMI support for a real-time automotive VM. "
            "The goal is to deliver virtual watchdog NMIs directly to the guest without "
            "VM exits. What kernel configuration options are required? How does the "
            "ITS VMAPP command differ when setting up a vNMI-capable vPE versus a "
            "standard GICv4.1 vPE? What is the VINMI signaling path?"
        ),
        "expected_topics": [
            "GICv4.2", "vNMI", "VINMI", "ITS", "VMAPP", "KVM",
            "CONFIG_KVM_ARM_VGIC_V4", "vPE", "VM-exit-reduction",
            "GICv4.1", "automotive-vm"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "kvm-gicv4.2", "vnmi-config", "its-vmapp-vnmi", "automotive"]
    },

    {
        "id": "case_309",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "Production system crash: the CPU lockup watchdog fired but no crash dump "
            "was captured. The system rebooted cleanly, which suggests the NMI handler "
            "ran but kdump did not trigger. The platform uses GICv3.3 architectural NMI "
            "for the watchdog.\n\n"
            "dmesg (recovered from pstore):\n"
            "  [3600.001] watchdog: BUG: soft lockup - CPU#2 stuck for 23s!\n"
            "  [3600.002] GICv3-NMI: NMI delivered to CPU#2 (SPI 32)\n"
            "  [3600.003] nmi_handler: watchdog invoked, kdump_crash_setup not called\n\n"
            "kdump is configured with crash_kexec_on_nmi=0 (default). How should we "
            "configure the kernel to ensure kdump captures a vmcore when the NMI "
            "watchdog fires?"
        ),
        "expected_topics": [
            "GICv3.3", "NMI", "watchdog", "kdump", "crash_kexec_on_nmi",
            "soft-lockup", "pstore", "vmcore",
            "nmi-handler", "crash-dump-configuration"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "nmi-kdump", "watchdog-crash-dump", "gicv3.3", "crash-kexec-on-nmi"]
    },

    {
        "id": "case_310",
        "skill": "interrupt-virtualization-expert",
        "input": (
            "I am evaluating a safety-critical RTOS design on Cortex-R82 with GICv3.2 "
            "(AArch64-R profile). We need deterministic interrupt latency below 1 "
            "microsecond for a hard real-time control loop. How does GICv3.2's support "
            "for the AArch64-R profile differ from the standard Cortex-A GICv3.x "
            "interrupt path? What GIC features support deterministic delivery for "
            "Cortex-R class CPUs?"
        ),
        "expected_topics": [
            "GICv3.2", "AArch64-R", "Cortex-R82", "GICv3.2-AArch64-R",
            "real-time", "deterministic-interrupt", "interrupt-latency",
            "GIC-600", "safety-critical"
        ],
        "min_score": 4,
        "tags": ["interrupt-virtualization-expert", "gicv3.2-aarch64-r", "cortex-r82", "real-time-interrupt", "safety-critical"]
    },

    # ── Panthor DRM / Mali CSF cases (311–320) ────────────────────────────────

    {
        "id": "case_311",
        "skill": "gpu-rendering-expert",
        "input": (
            "Our Mali-G710 GPU (Panthor driver, Linux 6.10) is crashing applications "
            "with EGL_CONTEXT_LOST. The kernel logs show CSF firmware timeout.\n\n"
            "dmesg:\n"
            "  [  60.100] panthor: CSF firmware timeout, group 2 (prio=HIGH)\n"
            "  [  60.101] panthor: Initiating GPU hang recovery\n"
            "  [  60.102] panthor: firmware version: 29.0.2 (expected >=29.0.0)\n"
            "  [  60.103] panthor: GPU MCU: clock gated during active queue processing\n"
            "  [  60.200] GPU hang recovery complete, context lost\n\n"
            "The firmware version matches the minimum requirement. The log shows "
            "'clock gated during active queue processing'. What causes the CSF MCU "
            "clock to gate while GPU queues are active, and how do we prevent this?"
        ),
        "expected_topics": [
            "panthor-drm-driver", "mali-csf-firmware", "CSF-firmware-timeout",
            "panthor-csf-fw-timeout", "GPU-MCU", "clock-gating",
            "hang-recovery", "EGL_CONTEXT_LOST", "mali-g710", "queue-group"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panthor", "csf-firmware-timeout", "gpu-mcu-clock", "mali-g710", "hang-recovery"]
    },

    {
        "id": "case_312",
        "skill": "gpu-rendering-expert",
        "input": (
            "On our Mali-G610 (Panthor driver) system, UI compositing (high priority) "
            "stutters during heavy background compute (low priority). Perfetto shows "
            "the compositing GPU queue waiting behind compute queue workloads.\n\n"
            "Perfetto trace (GPU track):\n"
            "  t=0ms:    compute_queue (prio=MEDIUM): job_A dispatch\n"
            "  t=4ms:    composite_queue (prio=HIGH): blocked waiting for CSF slot\n"
            "  t=12ms:   compute_queue job_A complete\n"
            "  t=12.1ms: composite_queue: frame delivered (12ms stall!)\n\n"
            "drm_sched entity priorities:\n"
            "  composite_entity: priority=DRM_SCHED_PRIORITY_HIGH\n"
            "  compute_entity: priority=DRM_SCHED_PRIORITY_NORMAL\n\n"
            "But both entities are in the same CSF queue group (group_0). "
            "What is the panthor-queue-priority-inversion failure mode and how "
            "do CSF queue groups need to be configured to prevent it?"
        ),
        "expected_topics": [
            "mali-csf-queue-group", "panthor-queue-priority-inversion",
            "drm-sched-framework", "mali-g610", "priority",
            "compositing", "queue-group-priority", "CSF", "preemption"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panthor", "queue-priority-inversion", "csf-queue-group", "mali-g610", "compositing"]
    },

    {
        "id": "case_313",
        "skill": "gpu-rendering-expert",
        "input": (
            "Explain the fundamental difference between Mali Job Manager (JM) scheduling "
            "used in Panfrost and the Command Stream Frontend (CSF) scheduling used in "
            "Panthor. Which Mali GPU generations use JM vs CSF? What does firmware-assisted "
            "scheduling in CSF provide that JM lacks? When should a BSP engineer choose "
            "Panthor vs Panfrost for a new SoC platform?"
        ),
        "expected_topics": [
            "panthor-drm-driver", "panfrost-mt8188", "mali-csf-firmware",
            "CSF", "JM", "job-manager", "firmware-scheduling",
            "mali-g710", "mali-g610", "bifrost", "valhall",
            "drm-sched-framework"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panthor-vs-panfrost", "csf-vs-jm", "firmware-scheduling", "mali-architecture"]
    },

    {
        "id": "case_314",
        "skill": "gpu-rendering-expert",
        "input": (
            "Our Mali-G710 GPU crashed with a GPU MMU fault. The kernel captured a "
            "devcoredump at /sys/class/devcoredump/devcd0. How do I analyze a Panthor "
            "devcoredump? What key fields should I look for in the dump to identify "
            "whether the fault was caused by a buffer overflow, use-after-free, or "
            "incorrect GPU VA mapping?"
        ),
        "expected_topics": [
            "gpu-devcoredump", "panthor-drm-driver", "GPU-MMU",
            "GPU-MMU-fault", "devcoredump", "mali-g710",
            "VA-fault", "buffer-overflow", "debug-analysis"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panthor", "gpu-devcoredump", "mmu-fault", "mali-g710", "gpu-debug"]
    },

    {
        "id": "case_315",
        "skill": "gpu-rendering-expert",
        "input": (
            "Our MediaTek MT8188 SoC uses a Mali-G57 MC3 GPU. We are selecting a "
            "kernel GPU driver. dmesg shows Panfrost is loaded:\n"
            "  [  2.100] panfrost: MT8188 Mali-G57 MC3 (Bifrost G7x)\n"
            "  [  2.101] panfrost: using drm_sched for job scheduling\n\n"
            "We need OpenGL ES 3.2 and Vulkan 1.1 for our Android-based product. "
            "Is Panfrost the right driver for MT8188? What is the Mesa userspace "
            "driver pairing? Is Panthor applicable to this hardware, or is Panthor "
            "only for CSF-based GPUs?"
        ),
        "expected_topics": [
            "panfrost-mt8188", "mali-g57", "Bifrost", "panthor-drm-driver",
            "CSF", "JM", "mesa", "opengl-es", "vulkan",
            "drm-sched-framework", "mt8188"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panfrost-mt8188", "mali-g57", "mt8188", "driver-selection", "mesa-vulkan"]
    },

    {
        "id": "case_316",
        "skill": "gpu-rendering-expert",
        "input": (
            "Our product has three GPU workloads: UI compositing (latency-sensitive), "
            "ML inference (throughput-sensitive), and video decode (background). We "
            "are using a Mali-G710 with Panthor driver. How should we configure the "
            "Mali CSF Queue Groups to give each workload the right QoS treatment? "
            "How many queue groups should we create, and how do group priorities "
            "map to CSF firmware scheduling decisions?"
        ),
        "expected_topics": [
            "mali-csf-queue-group", "mali-csf-firmware", "panthor-drm-driver",
            "queue-priority", "QoS", "CSF-scheduling",
            "mali-g710", "compositing", "ML-inference",
            "group-priority", "drm_sched_entity"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "mali-csf-queue-group", "panthor-qos", "mali-g710", "workload-scheduling"]
    },

    {
        "id": "case_317",
        "skill": "gpu-rendering-expert",
        "input": (
            "MT8188 Mali-G57 MC3 GPU is not reaching its rated 850 MHz peak frequency. "
            "Panfrost reports OPP set failures:\n\n"
            "dmesg:\n"
            "  [  5.200] panfrost: GPU OPP table has 3 entries\n"
            "  [  5.201] panfrost: OPP 850MHz: Failed to set, regulator VGPU at 850mV "
                        "(required 900mV)\n"
            "  [  5.202] panfrost: clamping to max achievable OPP: 700MHz\n\n"
            "device-tree GPU OPP table shows 850MHz@850mV but the regulator can only "
            "deliver up to 850mV. This is the panfrost-mt8188-opp-mismatch failure mode. "
            "How do we diagnose whether this is a DT error or a hardware limitation, "
            "and what is the proper fix?"
        ),
        "expected_topics": [
            "panfrost-mt8188", "panfrost-mt8188-opp-mismatch", "OPP",
            "regulator", "VGPU", "mali-g57", "mt8188",
            "device-tree", "OPP-table", "gpu-frequency"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panfrost-mt8188", "opp-mismatch", "gpu-regulator", "mt8188", "device-tree"]
    },

    {
        "id": "case_318",
        "skill": "gpu-rendering-expert",
        "input": (
            "We have a Mali-G610 on RK3588 with Panthor driver (Linux 6.10+) and Mesa. "
            "We want to run Vulkan workloads. The Panthor driver claims to support "
            "Vulkan via Mesa's Panfrost/Panthor Vulkan backend. What is the Mesa "
            "driver stack for Panthor-based Vulkan? How does the open-source Vulkan "
            "path differ from the proprietary Mali DDK path, and what Vulkan extensions "
            "are typically missing in the open-source implementation?"
        ),
        "expected_topics": [
            "mali-g610", "panthor-drm-driver", "Vulkan", "mesa",
            "RK3588", "open-source-vulkan", "mali-ddk",
            "CSF", "vulkan-extensions", "conformance"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "mali-g610", "panthor-vulkan", "mesa-vulkan", "rk3588", "open-source-gpu"]
    },

    {
        "id": "case_319",
        "skill": "gpu-rendering-expert",
        "input": (
            "After a kernel upgrade from 6.10 to 6.12, our Mali-G710 Panthor driver "
            "fails to load the CSF firmware:\n\n"
            "dmesg:\n"
            "  [  2.100] panthor: Loading CSF firmware: mali_csffw.bin\n"
            "  [  2.101] panthor: Firmware version: 28.0.4 (minimum required: 29.0.0)\n"
            "  [  2.102] panthor: ERROR: Firmware version too old, driver requires >=29.0.0\n"
            "  [  2.103] panthor: GPU unavailable\n\n"
            "The firmware binary is the same one that worked with kernel 6.10. Why "
            "did the minimum firmware version requirement change? Where is the firmware "
            "stored and how do we update it for Panthor-based systems?"
        ),
        "expected_topics": [
            "mali-csf-firmware", "panthor-drm-driver", "firmware-version",
            "panthor-csf-fw-timeout", "firmware-binary", "CSF-MCU",
            "mali-g710", "firmware-update", "kernel-upgrade"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panthor", "csf-firmware-version", "firmware-upgrade", "mali-g710", "kernel-upgrade"]
    },

    {
        "id": "case_320",
        "skill": "gpu-rendering-expert",
        "input": (
            "A GPU devcoredump was captured after a Panthor crash. The dump includes "
            "the following key entries:\n\n"
            "  GPU MMU fault: AS=2, FAULT_ADDR=0x7f3a000, TYPE=READ\n"
            "  FAULT_STATUS=0x92 (PERMISSION_FAULT, OUTER_FAULT)\n"
            "  Active CSF queue group: group_id=3, prio=HIGH, state=RUNNABLE\n"
            "  Last dispatched job: job_id=1452, ring_buffer_offset=0x3c80\n"
            "  Firmware state: MCU_STATUS=0x01 (ACTIVE)\n\n"
            "How do I interpret the FAULT_STATUS=0x92 PERMISSION_FAULT for an OUTER fault? "
            "What does OUTER_FAULT mean in Mali GPU MMU terminology? How do I trace "
            "the faulty buffer mapping from the fault address back to the GPU VA "
            "allocation in the application?"
        ),
        "expected_topics": [
            "gpu-devcoredump", "GPU-MMU", "MMU-fault", "PERMISSION_FAULT",
            "OUTER_FAULT", "panthor-drm-driver", "GPU-VA",
            "fault-status", "AS", "address-space", "mali-csf-firmware"
        ],
        "min_score": 4,
        "tags": ["gpu-rendering-expert", "panthor", "gpu-mmu-fault", "devcoredump-analysis", "permission-fault", "outer-fault"]
    },

    # ── MIPI CSI-2 v4.0/v4.2 cases (321–330) ─────────────────────────────────

    {
        "id": "case_321",
        "skill": "multimedia-camera-expert",
        "input": (
            "Our 50MP sensor is configured with MIPI CSI-2 v4.0 SROI to transmit only "
            "a 12MP region of interest to the ISP. After enabling SROI, the ISP produces "
            "corrupted output.\n\n"
            "dmesg:\n"
            "  [  10.100] csi2_rx: SROI Phase 1 active, crop 4032x3024 from 8192x6144\n"
            "  [  10.101] csi2_rx: SROI frame geometry received: 4035x3024\n"
            "  [  10.102] isp_fe: ERROR: input crop mismatch (expected 4032x3024, "
                        "got 4035x3024)\n"
            "  [  10.103] isp_fe: frame corrupted, pixel alignment error\n\n"
            "The sensor SROI is configured for a 4032x3024 ROI but the ISP sees "
            "4035x3024. What alignment requirement does MIPI CSI-2 SROI impose on "
            "ROI coordinates, and how should the SROI crop be adjusted?"
        ),
        "expected_topics": [
            "MIPI-CSI2-SROI", "SROI-crop-mismatch", "ISP-pipeline",
            "pixel-alignment", "ROI", "MIPI-CSI2-SROI-Crop-Mismatch",
            "CSI-2", "crop-geometry", "V4L2", "alignment-requirement"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-sroi", "sroi-crop-mismatch", "isp-alignment", "csi2-v4"]
    },

    {
        "id": "case_322",
        "skill": "multimedia-camera-expert",
        "input": (
            "We enabled MIPI CSI-2 v4.0 Multi-Pixel Compression (MPC) on our sensor "
            "to reduce DDR bandwidth. With MPC enabled, raw captures show visible "
            "artifacts — horizontal color banding every 16 lines and magenta fringing "
            "on high-contrast edges.\n\n"
            "dmesg:\n"
            "  [  20.100] csi2_rx: MPC mode enabled, compression ratio=2:1\n"
            "  [  20.101] isp_mpc_decoder: MPC frame received, mode=LOSSLESS\n"
            "  [  20.102] isp_mpc_decoder: WARNING: block boundary artifact detected "
                        "at line 16, 32, 48\n\n"
            "The sensor transmits with MPC 2:1 compression. The ISP MPC decoder "
            "reports block boundary artifacts at 16-line intervals. What causes MPC "
            "decode artifacts, and is this a sensor-side or ISP-side configuration "
            "issue? What is MIPI-CSI2-MPC-Decode-Fail?"
        ),
        "expected_topics": [
            "MIPI-CSI2-MPC", "MIPI-CSI2-MPC-Decode-Fail", "MPC-compression",
            "ISP-pipeline", "artifact", "compression-ratio",
            "CSI-2", "bandwidth-reduction", "MPC-decoder",
            "sensor-ISP-mismatch"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-mpc", "mpc-decode-fail", "compression-artifact", "csi2-v4"]
    },

    {
        "id": "case_323",
        "skill": "multimedia-camera-expert",
        "input": (
            "We integrated a MIPI CSI-2 v4.2 Event-Based Vision Sensor (EVS) for our "
            "autonomous robot platform. During fast scene motion (high contrast transitions "
            "across many pixels simultaneously), the event stream drops events.\n\n"
            "dmesg:\n"
            "  [  5.100] mipi-csi2: ESP virtual channel 2 overflow, event_count=48000/ms\n"
            "  [  5.101] csi2_rx: VC2 FIFO overrun, dropped 1200 events\n"
            "  [  5.102] evs_driver: event gap detected at t=5.100s\n\n"
            "The sensor is a Prophesee Metavision at 1MP resolution. The CSI-2 link "
            "is D-PHY 4-lane at 2.5Gbps/lane. The event burst rate during the scene "
            "transition is estimated at 48,000 events/ms. What causes MIPI-CSI2-ESP-"
            "Event-Drop, and how should we configure the CSI-2 virtual channel "
            "allocation to handle event bursts?"
        ),
        "expected_topics": [
            "MIPI-CSI2-ESP", "EVS-sensor", "MIPI-CSI2-ESP-Event-Drop",
            "event-based-vision", "D-PHY", "virtual-channel",
            "FIFO-overrun", "bandwidth", "event-burst", "dynamic-vision"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-esp", "evs-sensor", "event-drop", "csi2-v4.2", "neuromorphic"]
    },

    {
        "id": "case_324",
        "skill": "multimedia-camera-expert",
        "input": (
            "After enabling MIPI D-PHY v2.1 Error Correction Mode (ECM) on our "
            "automotive camera module (CSI-2 v4.2), we see a flood of ECC correction "
            "events that was not present before ECM was enabled.\n\n"
            "dmesg:\n"
            "  [  0.500] mipi-csi2: D-PHY ECM enabled on lanes 0-3\n"
            "  [  1.000] mipi-csi2: ECM ECC correction count: 1450 in last 500ms\n"
            "  [  1.001] mipi-csi2: ECM ECC threshold exceeded, link degraded\n"
            "  [  1.002] mipi-csi2: CSI-2 link reset triggered\n\n"
            "The SoC CSI-2 RX was manufactured in 2022 (pre-CSI-2 v4.2). What causes "
            "MIPI-DPHY-ECM-CRC-Storm on an older SoC receiver, and what is the "
            "correct approach when the receiver does not support CSI-2 v4.2 ECM?"
        ),
        "expected_topics": [
            "MIPI-DPHY-ECM", "MIPI-DPHY-ECM-CRC-Storm", "ECM",
            "D-PHY", "ECC", "CSI-2-v4.2", "link-degradation",
            "automotive-camera", "receiver-compatibility", "FEC"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-dphy-ecm", "ecm-crc-storm", "csi2-v4.2", "automotive", "d-phy-ecc"]
    },

    {
        "id": "case_325",
        "skill": "multimedia-camera-expert",
        "input": (
            "We are designing a camera subsystem for a wearable AR device. Power "
            "budget is critical. The main sensor is 50MP (8192x6144) at 30fps. "
            "We want to use MIPI CSI-2 v4.0 features to minimize DDR bandwidth "
            "and MIPI link power. Explain how SROI, MPC, and LRTE can work "
            "together to reduce the effective data rate from the sensor to the ISP. "
            "What is the theoretical maximum bandwidth reduction achievable by "
            "combining all three features?"
        ),
        "expected_topics": [
            "MIPI-CSI2-SROI", "MIPI-CSI2-MPC", "MIPI-CSI2-LRTE",
            "bandwidth-reduction", "CSI-2-v4.0", "ISP-pipeline",
            "power-budget", "wearable", "MIPI-bandwidth",
            "compound-savings"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-bandwidth", "sroi-mpc-lrte", "csi2-v4-features", "power-optimization"]
    },

    {
        "id": "case_326",
        "skill": "multimedia-camera-expert",
        "input": (
            "We need to implement a always-on camera presence detection feature that "
            "wakes the main SoC from deep sleep when a person is detected. The sensor "
            "supports MIPI CSI-2 v4.0 Always-On Sentinel Conduit. Currently, the "
            "full CSI-2 link is kept active for presence detection, consuming 80mW. "
            "Explain how the Sentinel Conduit enables low-power wake without full "
            "link activation, and what kernel/driver changes are needed to implement "
            "the Sentinel wake path."
        ),
        "expected_topics": [
            "MIPI-CSI2-Sentinel", "MIPI-CSI2-RX", "always-on",
            "low-power-wake", "presence-detection", "CSI-2-v4.0",
            "wake-trigger", "deep-sleep", "power-reduction",
            "sentinel-conduit"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-sentinel", "always-on-camera", "low-power-wake", "csi2-v4"]
    },

    {
        "id": "case_327",
        "skill": "multimedia-camera-expert",
        "input": (
            "Our augmented reality pipeline requires camera frame latency below 5ms "
            "from sensor capture to ISP output for motion-to-photon requirements. "
            "Currently achieving 8ms. We are using MIPI CSI-2 v4.0. The ISP pipeline "
            "processes 4K at 60fps. How does MIPI CSI-2 v4.0 LRTE (Latency Reduction "
            "and Transport Efficiency) reduce the capture-to-ISP latency, and what "
            "other pipeline stages should we optimize to reach the 5ms target?"
        ),
        "expected_topics": [
            "MIPI-CSI2-LRTE", "ISP-pipeline", "latency",
            "CSI-2-v4.0", "motion-to-photon", "packet-scheduling",
            "pipeline-latency", "AR", "frame-latency",
            "interleaving"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-lrte", "latency-reduction", "ar-pipeline", "motion-to-photon"]
    },

    {
        "id": "case_328",
        "skill": "multimedia-camera-expert",
        "input": (
            "We are integrating a Sony IMX636 event-based vision sensor (EVS) using "
            "MIPI CSI-2 v4.2 ESP protocol alongside our frame-based RGB camera "
            "on the same CSI-2 controller with virtual channel multiplexing. "
            "The EVS delivers asynchronous events at up to 100M events/sec. "
            "How do we design the V4L2 driver architecture to handle the EVS event "
            "stream? What are the differences between V4L2 capture for frame-based "
            "cameras vs event-based sensors? How do we handle the asynchronous "
            "event delivery model in Linux?"
        ),
        "expected_topics": [
            "EVS-sensor", "MIPI-CSI2-ESP", "V4L2", "virtual-channel",
            "asynchronous-events", "event-based-vision", "CSI-2-v4.2",
            "IMX636", "V4L2-driver", "neuromorphic-sensor"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "evs-sensor-integration", "mipi-csi2-esp", "v4l2-evs", "csi2-v4.2"]
    },

    {
        "id": "case_329",
        "skill": "multimedia-camera-expert",
        "input": (
            "Our ML-based security camera needs to run two algorithms simultaneously: "
            "full-frame face detection at 2fps (for enrollment) and SROI-cropped "
            "facial landmark tracking at 30fps (for authentication). The 50MP sensor "
            "supports MIPI CSI-2 v4.0 SROI Phase 2 (ESROI) with companion VDSP. "
            "How does SROI Phase 2 ESROI differ from Phase 1, and how can we configure "
            "it to deliver both full-frame at low rate and cropped ROI at high rate "
            "simultaneously over the same CSI-2 link?"
        ),
        "expected_topics": [
            "MIPI-CSI2-SROI", "ESROI", "ISROI", "SROI-Phase2",
            "VDSP", "CSI-2-v4.0", "dual-stream", "facial-landmark",
            "ISP-pipeline", "ROI-multiplexing"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "mipi-csi2-sroi-phase2", "esroi", "dual-stream", "csi2-v4", "ai-camera"]
    },

    {
        "id": "case_330",
        "skill": "multimedia-camera-expert",
        "input": (
            "Our hardware team is asking us to choose between a sensor that supports "
            "MIPI CSI-2 v4.0 and one that supports v4.2 for our next product. The "
            "key use cases are: (1) AI-driven ROI tracking, (2) HDR video at 4K/120fps, "
            "(3) always-on presence detection. Give a concise comparison of what v4.0 "
            "adds over v3.x and what v4.2 adds over v4.0, focusing on the features "
            "relevant to these three use cases."
        ),
        "expected_topics": [
            "MIPI-CSI2-SROI", "MIPI-CSI2-MPC", "MIPI-CSI2-Sentinel",
            "MIPI-CSI2-LRTE", "MIPI-CSI2-ESP", "MIPI-DPHY-ECM",
            "CSI-2-v4.0", "CSI-2-v4.2", "EVS", "feature-comparison"
        ],
        "min_score": 4,
        "tags": ["multimedia-camera-expert", "csi2-v4-comparison", "csi2-feature-selection", "v4.0-vs-v4.2"]
    },

    # ── Cross-domain mentor cases (331–340) ───────────────────────────────────

    {
        "id": "case_331",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "System-level intermittent hang requiring reboot. The hardware watchdog "
            "is configured with GICv3.3 NMI but the crash dump is missing intermittently. "
            "Simultaneously, thermal sensors show the SoC approaching 90C before hangs. "
            "The dmesg shows thermal throttling events 2 seconds before each hang.\n\n"
            "dmesg:\n"
            "  [120.100] thermal_zone0: temp=89500 (passive trip)\n"
            "  [120.101] thermal_cooling: all clusters capped to OPP1\n"
            "  [120.200] GICv3-NMI: watchdog SPI 32 configured\n"
            "  [121.900] GICv3-NMI: NMI delivered to CPU#0\n"
            "  [121.901] watchdog: hardware watchdog timeout, kdump triggered\n"
            "  [121.902] kdump: capture failed (memory controller in self-refresh)\n\n"
            "The memory controller enters self-refresh during thermal throttling, "
            "which prevents kdump from capturing the crash. How do we architect "
            "a solution that handles both the thermal runaway and the NMI/kdump "
            "interaction?"
        ),
        "expected_topics": [
            "GICv3.3", "NMI", "watchdog", "kdump", "thermal-throttling",
            "DVFS", "memory-self-refresh", "LPDDR5", "crash-dump",
            "thermal-zone", "cross-domain"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "nmi-thermal", "kdump-thermal", "thermal-throttle", "lpddr5"]
    },

    {
        "id": "case_332",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Our Mali-G710 using Panthor driver is crashing with CSF firmware timeout "
            "during sustained GPU compute workloads. The crashes correlate with thermal "
            "throttling events. The GPU power domain is on the same thermal zone as "
            "the CPU cluster.\n\n"
            "dmesg:\n"
            "  [  90.100] thermal_zone1: temp=87000 (passive trip_point_1)\n"
            "  [  90.101] thermal_cooling: gpu_clk capped 900MHz -> 450MHz\n"
            "  [  90.102] panthor: CSF firmware MCU clock gated\n"
            "  [  90.103] panthor: CSF firmware timeout, group 1\n"
            "  [  90.104] panthor: GPU hang recovery initiated\n\n"
            "The thermal framework capped the GPU clock via devfreq, but the MCU "
            "inside the GPU was not notified of the frequency change before the "
            "cap took effect. How does the Panthor/CSF thermal interaction need to "
            "be implemented correctly?"
        ),
        "expected_topics": [
            "panthor-drm-driver", "mali-csf-firmware", "thermal-throttling",
            "GPU-MCU", "devfreq", "panthor-csf-fw-timeout",
            "thermal-zone", "gpu-frequency-cap", "clock-gating",
            "cross-domain", "power-thermal"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "panthor-thermal", "csf-thermal", "gpu-thermal", "devfreq"]
    },

    {
        "id": "case_333",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Camera pipeline performance degradation under load: ISP → GPU super-resolution "
            "pipeline drops from 30fps to 12fps under sustained operation. The camera uses "
            "MIPI CSI-2 v4.0 SROI to crop a 4K ROI from a 50MP sensor. The GPU processes "
            "the ISP output via DMA-BUF for AI super-resolution.\n\n"
            "System observations:\n"
            "  - MIPI bandwidth utilization: 42% savings from SROI\n"
            "  - ISP processing: 4K@30fps (within spec)\n"
            "  - GPU compute: exceeds 16ms budget per frame at 4x upscale\n"
            "  - DMA-BUF import latency: 2.3ms (abnormally high)\n"
            "  - thermal_zone0: 83C sustained (near passive trip)\n\n"
            "This spans three domains: MIPI/camera, GPU, and thermal. Use the Blackboard "
            "pattern to diagnose the root cause of the fps drop."
        ),
        "expected_topics": [
            "MIPI-CSI2-SROI", "ISP-pipeline", "GPU", "DMA-BUF",
            "thermal", "Blackboard", "super-resolution", "devfreq",
            "panthor-drm-driver", "cross-domain", "frame-drop"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "blackboard", "sroi-gpu-thermal", "dma-buf", "super-resolution"]
    },

    {
        "id": "case_334",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Boot hang investigation: new SoC platform hangs at the 'Starting kernel ...' "
            "stage intermittently (1 in 10 boots). When it hangs, the hardware watchdog "
            "(configured as GICv3.3 NMI) fires after 30 seconds but no crash dump is "
            "captured. The platform has ADIv6 CoreSight debug.\n\n"
            "uart log:\n"
            "  [    0.000] Booting Linux on physical CPU 0x0000000000 [0x412fd000]\n"
            "  [    0.100] GIC: Using GICv3.3 with 512 IRQs\n"
            "  [    0.101] GICv3-NMI: FEAT_NMI enabled, SPI 32 = watchdog NMI\n"
            "  [    0.200] CPU1: Booting secondary processor\n"
            "  (hang — no further output for 30s, then NMI fires, system reboots)\n\n"
            "How should we use the cross-domain diagnostic approach to investigate "
            "the intermittent boot hang? What is the role of NMI in boot hang diagnosis, "
            "and how does CoreSight ADIv6 help capture state when the hang occurs?"
        ),
        "expected_topics": [
            "boot-debug-expert", "GICv3.3", "NMI", "CoreSight",
            "ADIv6", "watchdog", "secondary-CPU-boot", "PSCI",
            "boot-hang", "cross-domain"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "boot-debug", "nmi-boot-hang", "coresight-adiv6", "secondary-cpu"]
    },

    {
        "id": "case_335",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "I'm a product manager for a smart security camera product. Our engineering "
            "team says we need to add 'MIPI CSI-2 v4.2 ESP event sensor support' for "
            "our next generation. I need to understand what this means for our product "
            "roadmap. The engineers mentioned 'neuromorphic sensors', 'microsecond "
            "temporal resolution', and 'asynchronous event streams'. What does this "
            "actually mean for our camera product's user-facing features and competitive "
            "positioning?"
        ),
        "expected_topics": [
            "MIPI-CSI2-ESP", "EVS-sensor", "terminology-translation",
            "learner-level", "management", "business-impact",
            "event-based-vision", "competitive-advantage",
            "always-on", "power-efficiency"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "learner-level-detection", "management-level", "terminology-translation", "esp-business-impact"]
    },

    {
        "id": "case_336",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "The algorithm team is proposing to use an event-based vision sensor (EVS) "
            "for their object tracking algorithm. They claim 'zero motion blur' and "
            "'microsecond latency'. The BSP team says this will 'require MIPI CSI-2 "
            "ESP virtual channel allocation and custom V4L2 event buffer management'. "
            "Translate between these two perspectives: what does the algorithm team's "
            "request mean in BSP terms, and what do the BSP constraints mean in "
            "algorithm performance terms?"
        ),
        "expected_topics": [
            "MIPI-CSI2-ESP", "EVS-sensor", "V4L2", "virtual-channel",
            "terminology-translation", "algorithm-team", "motion-blur",
            "event-latency", "asynchronous-events", "bandwidth"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "terminology-translation", "evs-algorithm-bsp", "cross-team-communication", "v4l2-evs"]
    },

    {
        "id": "case_337",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "I need to fix a GICv4.2 vNMI issue in our VM. Can you give me the exact "
            "ITS VMAPP command sequence I need to write to GITS_CBASER to enable "
            "vNMI delivery for our vPE? Just give me the register write sequence, "
            "I'm in a hurry."
        ),
        "expected_topics": [
            "Socratic-questioning", "ITS", "VMAPP", "GICv4.2",
            "vNMI", "diagnostic-process", "symptom-confirmation",
            "register-safety", "prohibited-behavior"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "negative-test", "socratic-questioning", "no-direct-fix", "gicv4.2-vnmi"]
    },

    {
        "id": "case_338",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Power island interaction with GPU: after entering system suspend (STR), "
            "the Mali-G710 GPU fails to resume. The Panthor driver reports firmware "
            "not loaded after resume.\n\n"
            "dmesg:\n"
            "  [1800.100] Suspending...\n"
            "  [1800.101] panthor: GPU power domain OFF (suspend)\n"
            "  [1800.200] Suspend complete\n"
            "  ... (resume) ...\n"
            "  [3600.100] Resuming...\n"
            "  [3600.101] panthor: GPU power domain ON (resume)\n"
            "  [3600.102] panthor: ERROR: CSF firmware not loaded after power cycle\n"
            "  [3600.103] panthor: GPU unavailable\n\n"
            "The GPU power domain was collapsed during suspend and the firmware needs "
            "to be reloaded. This spans power management and GPU subsystems. What is "
            "the correct Panthor/CSF suspend-resume sequence?"
        ),
        "expected_topics": [
            "panthor-drm-driver", "mali-csf-firmware", "STR", "suspend-resume",
            "power-domain", "GPU-power", "PSCI", "firmware-reload",
            "power-island", "cross-domain"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "panthor-suspend-resume", "gpu-power-domain", "str", "power-island"]
    },

    {
        "id": "case_339",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "We are designing an always-on AI security camera. Requirements:\n"
            "  1. Always-on presence detection using EVS (event-based sensor, MIPI CSI-2 v4.2 ESP)\n"
            "  2. Wake-on-detection: EVS Sentinel triggers full SoC wake for detailed analysis\n"
            "  3. After wake: NMI watchdog protection during heavy ISP+GPU processing\n"
            "  4. Power budget: <5mW in always-on mode, <2W in active mode\n\n"
            "This spans three technical domains: MIPI camera (EVS + Sentinel), "
            "interrupt architecture (NMI watchdog), and power management (wake path + "
            "power island). How would you coordinate the design review across these "
            "three BSP domains using the Blackboard pattern? Which domain experts "
            "should contribute and in what order?"
        ),
        "expected_topics": [
            "MIPI-CSI2-ESP", "MIPI-CSI2-Sentinel", "EVS-sensor",
            "GICv3.3", "NMI", "Blackboard", "power-domain",
            "wake-path", "PSCI", "cross-domain", "always-on"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "blackboard", "evs-sentinel-nmi-power", "always-on-design", "multi-domain"]
    },

    {
        "id": "case_340",
        "skill": "bsp-knowledge-mentor",
        "input": (
            "Complex VM scenario: We run a VM with GPU passthrough (Mali-G710 with "
            "Panthor VFIO passthrough) and a real-time control vPE using GICv4.2 "
            "vNMI for watchdog. During GPU-intensive ML inference in the VM, the "
            "real-time control vPE's watchdog vNMI is intermittently delayed by "
            "more than 100 microseconds — violating our real-time requirement.\n\n"
            "System topology:\n"
            "  Host: Linux 6.12, KVM, GICv4.2 vNMI enabled\n"
            "  VM1: ML inference (Mali-G710 passthrough, Panthor in guest)\n"
            "  VM2: Real-time control (GICv4.2 vNMI watchdog, 100μs deadline)\n\n"
            "The vNMI latency spikes correlate with GPU SMMU TLB shootdown events. "
            "This is a three-way interaction between GICv4.2 vNMI, GPU SMMU, and "
            "KVM vCPU scheduling. Use the Blackboard pattern to diagnose the "
            "vNMI latency jitter."
        ),
        "expected_topics": [
            "GICv4.2", "vNMI", "SMMU", "KVM", "GPU-passthrough",
            "panthor-drm-driver", "Blackboard", "TLB-shootdown",
            "real-time", "vNMI-latency", "cross-domain",
            "VFIO", "vCPU-scheduling"
        ],
        "min_score": 4,
        "tags": ["bsp-knowledge-mentor", "cross-domain", "blackboard", "gicv4.2-vnmi-gpu", "smmu-tlb", "kvm-real-time", "vfio"]
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
    print(f"Case range: case_301 – case_340")


if __name__ == "__main__":
    main()
