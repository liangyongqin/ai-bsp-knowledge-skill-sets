"""
AMBA AXI4 Bus Topology — seed knowledge ingestion.

Ingests open-source documented knowledge about the ARM AMBA AXI4 bus
specification and related interconnect concepts into the BSP knowledge graph.

Reference: ARM AMBA AXI4 spec (ARM IHI0022), AMBA AHB (ARM IHI0033),
           AMBA APB (ARM IHI0024), Linux DMA-BUF kernel docs
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _HERE)

import kuzu
import schema as _schema
from _ingest_helpers import upsert_node, create_rel

DEFAULT_DB_PATH = os.path.join(_HERE, "bsp_base.db")

_COMPONENTS = [
    ("AXI4-Interconnect", "bus_protocol", "ARM AMBA AXI4 high-performance bus protocol with 5-channel structure", "base", "ARM", "AMBA4"),
    ("AXI4-Master-Port", "bus_port", "AXI4 master port: initiates read/write transactions", "base", "ARM", "AMBA4"),
    ("AXI4-Slave-Port", "bus_port", "AXI4 slave port: responds to transactions from masters", "base", "ARM", "AMBA4"),
    ("AXI4-AW-Channel", "axi_channel", "AXI4 Write Address channel (AW): carries address and burst attributes", "base", "ARM", "AMBA4"),
    ("AXI4-W-Channel", "axi_channel", "AXI4 Write Data channel (W): carries write data and strobes", "base", "ARM", "AMBA4"),
    ("AXI4-B-Channel", "axi_channel", "AXI4 Write Response channel (B): carries write completion status", "base", "ARM", "AMBA4"),
    ("AXI4-AR-Channel", "axi_channel", "AXI4 Read Address channel (AR): carries read address and burst attributes", "base", "ARM", "AMBA4"),
    ("AXI4-R-Channel", "axi_channel", "AXI4 Read Data channel (R): carries read data and response", "base", "ARM", "AMBA4"),
    ("AXI4-Lite", "bus_protocol", "AXI4-Lite: simplified single-beat AXI4 for low-bandwidth register access", "base", "ARM", "AMBA4"),
    ("AXI4-Stream", "bus_protocol", "AXI4-Stream: unidirectional streaming bus for data-path applications (no address phase)", "base", "ARM", "AMBA4"),
    ("AXI-ACE", "bus_protocol", "AXI4 with ACE extensions: full cache coherency with snoop channels (AR IHI0022)", "base", "ARM", "AMBA4"),
    ("AXI-ACE-Lite", "bus_protocol", "AXI4 ACE-Lite: I/O coherent masters without snoop acceptance", "base", "ARM", "AMBA4"),
    ("CCI-550", "bus_component", "ARM CCI-550 Cache Coherent Interconnect, supports ACE/ACE-Lite ports", "base", "ARM", "r1p0"),
    ("CMN-650", "bus_component", "ARM CMN-650 Coherent Mesh Network, high-bandwidth SoC interconnect", "base", "ARM", "r0p0"),
    ("AXI-Crossbar", "interconnect", "AXI4 crossbar switch: NxM full-mesh connectivity between masters and slaves", "base", "generic", ""),
    ("SoC-NoC", "interconnect", "System-on-Chip Network-on-Chip: packet-based AXI4 transport fabric", "base", "generic", ""),
    ("AXI-Arbiter", "bus_component", "AXI4 bus arbiter: round-robin or priority-based access scheduling", "base", "generic", ""),
    ("AXI-Width-Converter", "bus_component", "AXI4 data width converter: 32-64-128-256-bit path bridging", "base", "generic", ""),
    ("AXI-Clock-Bridge", "bus_component", "AXI4 asynchronous clock domain crossing bridge (CDC)", "base", "generic", ""),
    ("AHB-Bus", "bus_protocol", "ARM AMBA AHB: pipelined bus for medium-bandwidth peripheral access (IHI0033)", "base", "ARM", "AMBA3"),
    ("AHB-to-AXI4-Bridge", "bus_bridge", "Bridge converting AHB master transactions to AXI4 slave transactions", "base", "generic", ""),
    ("AXI4-to-AHB-Bridge", "bus_bridge", "Bridge converting AXI4 master transactions to AHB slave transactions", "base", "generic", ""),
    ("APB-Bus", "bus_protocol", "ARM AMBA APB: low-power peripheral bus for low-bandwidth register access (IHI0024)", "base", "ARM", "AMBA4"),
    ("APB-to-AXI4-Bridge", "bus_bridge", "Bridge converting APB master transactions to AXI4 slave transactions", "base", "generic", ""),
    ("AXI4-to-APB-Bridge", "bus_bridge", "Bridge converting AXI4 master to APB peripheral registers", "base", "generic", ""),
    ("DMA-BUF", "linux_kernel_subsystem", "Linux DMA-BUF: zero-copy buffer sharing between drivers via file descriptors", "base", "Linux", "5.15+"),
    ("DMA-BUF-Heap", "linux_kernel_subsystem", "Linux DMA-BUF heaps: CMA, system, system-uncached allocators", "base", "Linux", "5.10+"),
    ("ION-Allocator", "linux_kernel_subsystem", "Android ION memory allocator (legacy), superseded by DMA-BUF heaps", "base", "Android", ""),
    ("CPU-Cluster-AXI-Master", "bus_master", "CPU cluster ACE master port on CCI/CMN for cache coherent access", "base", "generic", ""),
    ("GPU-AXI-Master", "bus_master", "GPU ACE-Lite master for coherent memory access to framebuffers", "base", "generic", ""),
    ("ISP-AXI-Master", "bus_master", "ISP AXI4 master for DMA-BUF zero-copy frame data to DDR", "base", "generic", ""),
    ("NPU-AXI-Master", "bus_master", "NPU AXI4 master for weight/activation tensor DMA", "base", "generic", ""),
    ("DMA-AXI-Master", "bus_master", "System DMA controller AXI4 master", "base", "generic", ""),
    ("DDR-Controller", "memory_controller", "DDR memory controller AXI4 slave, LPDDR4/LPDDR5", "base", "generic", ""),
    ("SRAM-AXI-Slave", "memory", "On-chip SRAM AXI4 slave, low-latency local scratch", "base", "generic", ""),
    ("Peripheral-Bus-AXI-Slave", "bus_bridge", "AXI4 to APB bridge slave for low-bandwidth peripherals", "base", "generic", ""),
    ("SMMU-v3-AXI-Slave", "iommu", "ARM SMMUv3 AXI4 slave interface for stream translation", "base", "ARM", "r3p0"),
    ("AXI-QoS-Controller", "qos", "AXI4 QoS controller: assigns ARQOS/AWQOS values per master", "base", "generic", ""),
    ("AXI-Bandwidth-Limiter", "qos", "AXI4 bandwidth limiter: throttles individual master bandwidth", "base", "generic", ""),
    ("AXI4-Barrier", "bus_component", "AXI4 memory barrier concept: DMB/DSB mapped to AXI4 ordering model", "base", "ARM", ""),
    ("AXI4-AxPROT", "bus_component", "AXI4 AxPROT attribute: encodes privilege, security, and data/instruction type", "base", "ARM", "AMBA4"),
]

_STREAMS_TO = [
    ("ISP-AXI-Master", "DDR-Controller", 4096.0, "ISP writes 4K DMA-BUF frames to DDR via AXI4 master"),
    ("GPU-AXI-Master", "DDR-Controller", 8192.0, "GPU reads/writes framebuffers to DDR via ACE-Lite"),
    ("NPU-AXI-Master", "DDR-Controller", 16384.0, "NPU streams tensor data to/from DDR at peak bandwidth"),
    ("DMA-AXI-Master", "DDR-Controller", 1024.0, "System DMA streams peripheral data to DDR"),
    ("CPU-Cluster-AXI-Master", "CCI-550", 3200.0, "CPU cluster ACE port to CCI-550 cache coherent interconnect"),
]

_ROUTES_TO = [
    ("CPU-Cluster-AXI-Master", "CCI-550", "CPU cluster connects to CCI-550 ACE master port"),
    ("GPU-AXI-Master", "CCI-550", "GPU ACE-Lite port connects to CCI-550"),
    ("CCI-550", "AXI-Crossbar", "CCI-550 connects downstream to main AXI crossbar"),
    ("AXI-Crossbar", "DDR-Controller", "AXI crossbar routes memory transactions to DDR controller"),
    ("AXI-Crossbar", "Peripheral-Bus-AXI-Slave", "AXI crossbar routes peripheral accesses to APB bridge"),
    ("AXI-Crossbar", "SMMU-v3-AXI-Slave", "AXI crossbar routes IOMMU-mapped transactions through SMMUv3"),
    ("ISP-AXI-Master", "AXI-Crossbar", "ISP DMA master connects to main AXI crossbar"),
    ("NPU-AXI-Master", "AXI-Crossbar", "NPU tensor DMA master connects to main AXI crossbar"),
    ("DMA-AXI-Master", "AXI-Crossbar", "System DMA master connects to main AXI crossbar"),
    ("AHB-to-AXI4-Bridge", "AXI-Crossbar", "AHB bridge promotes legacy AHB masters to AXI4 fabric"),
    ("AXI4-to-APB-Bridge", "APB-Bus", "AXI4 to APB bridge drives low-bandwidth peripheral registers"),
]

_DMA_TO = [
    ("ISP-AXI-Master", "DDR-Controller", "dma-ch0", "ISP DMA channel 0 writes frame to DDR"),
    ("DMA-AXI-Master", "SRAM-AXI-Slave", "dma-ch1", "DMA channel 1 copies data to on-chip SRAM"),
    ("NPU-AXI-Master", "DDR-Controller", "dma-ch2", "NPU DMA channel 2 loads weight tensors from DDR"),
]


def ingest(db_path: str = None) -> int:
    """Ingest AMBA AXI4 bus topology knowledge into the Kuzu database."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = os.path.abspath(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    inserted = 0
    for name, ctype, desc, ns, vendor, version in _COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "description": desc,
            "namespace": ns, "vendor": vendor, "version": version,
        }):
            inserted += 1

    for src, dst, bw, desc in _STREAMS_TO:
        create_rel(conn, "STREAMS_TO", "Component", "Component", src, dst,
                   {"bandwidth_mbps": bw, "description": desc})

    for src, dst, desc in _ROUTES_TO:
        create_rel(conn, "ROUTES_TO", "Component", "Component", src, dst, {"description": desc})

    for src, dst, ch, desc in _DMA_TO:
        create_rel(conn, "DMA_TO", "Component", "Component", src, dst,
                   {"channel": ch, "description": desc})

    print(f"[arm-amba-axi] Inserted {inserted} Component nodes.")
    return inserted


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db-path", default=None)
    args = p.parse_args()
    ingest(args.db_path)
