"""
ISP Pipeline Query — GraphRAG template for multimedia data path tracing.

Traces the sensor → ISP → DMA-BUF → GPU/NPU pipeline using
STREAMS_TO and DMA_TO relationships in the knowledge graph.

Covers:
  - MIPI CSI-2 sensor input
  - ISP processing stages
  - DMA-BUF zero-copy buffer handoff
  - GPU/NPU downstream consumption
  - Bandwidth requirements
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
_BASE_DB = os.path.join(_HERE, "..", "base", "bsp_base.db")

sys.path.insert(0, _SCHEMA_DIR)


def _open_db(db_path: str):
    import kuzu
    db_path = os.path.abspath(db_path)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return db, conn


def _result_to_list(result) -> list:
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    return rows


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_isp_pipeline(
    sensor_name: str = None,
    db_path: str = None,
) -> list[dict]:
    """Trace the ISP multimedia pipeline from sensor to GPU/NPU.

    Walks STREAMS_TO and DMA_TO relationships starting from the sensor
    (or MIPI-CSI2-RX if sensor_name is None) through the ISP to
    DMA-BUF then GPU/NPU.

    Parameters
    ----------
    sensor_name:
        Optional name of the sensor component to start from.  If None,
        uses ``"MIPI-CSI2-RX"`` as the default CSI entry point.
    db_path:
        Path to Kuzu DB directory.

    Returns
    -------
    list[dict]
        Each entry has: ``pipeline_stages``, ``dma_buf_config``,
        ``bandwidth_requirement``.
    """
    if db_path is None:
        db_path = _BASE_DB
    if sensor_name is None:
        sensor_name = "MIPI-CSI2-RX"

    t0 = time.perf_counter()
    _, conn = _open_db(db_path)

    results: list[dict] = []

    # Step 1 — verify sensor / entry node exists
    sensor_info: dict = {}
    try:
        q = conn.execute(
            "MATCH (c:Component {name: $name}) "
            "RETURN c.name, c.type, c.description",
            {"name": sensor_name},
        )
        rows = _result_to_list(q)
        if rows:
            sensor_info = {"name": rows[0][0], "type": rows[0][1], "description": rows[0][2]}
        else:
            sensor_info = {"name": sensor_name, "type": "unknown", "description": "Not found in graph"}
    except Exception as e:
        sensor_info = {"error": str(e)}

    # Step 2 — STREAMS_TO chain from sensor through ISP
    stream_chain: list[dict] = []
    total_bandwidth = 0.0
    try:
        q = conn.execute(
            "MATCH (src:Component {name: $name})-[r:STREAMS_TO*1..4]->(dst:Component) "
            "RETURN src.name, dst.name, dst.type",
            {"name": sensor_name},
        )
        for row in _result_to_list(q):
            stream_chain.append({
                "from": row[0],
                "to": row[1],
                "dst_type": row[2],
                "relationship": "STREAMS_TO",
            })
    except Exception as e:
        stream_chain.append({"error": str(e)})

    # Step 3 — STREAMS_TO bandwidth on direct hops
    bandwidth_list: list[dict] = []
    try:
        q = conn.execute(
            "MATCH (src:Component)-[r:STREAMS_TO]->(dst:Component) "
            "WHERE src.type IN ['multimedia', 'isp_power_domain'] "
            "   OR dst.name = 'DDR-Controller' "
            "   OR src.name = $sensor "
            "RETURN src.name, dst.name, r.bandwidth_mbps, r.description",
            {"sensor": sensor_name},
        )
        for row in _result_to_list(q):
            bw = row[2] or 0.0
            total_bandwidth += bw
            bandwidth_list.append({
                "from": row[0],
                "to": row[1],
                "bandwidth_mbps": bw,
                "description": row[3],
            })
    except Exception as e:
        bandwidth_list.append({"error": str(e)})

    # Step 4 — DMA_TO chain from ISP/NPU
    dma_chain: list[dict] = []
    for node_name in ["ISP-AXI-Master", "ISP-Controller", "NPU-AXI-Master"]:
        try:
            q = conn.execute(
                "MATCH (src:Component {name: $name})-[r:DMA_TO]->(dst:Component) "
                "RETURN src.name, dst.name, r.channel, r.description",
                {"name": node_name},
            )
            for row in _result_to_list(q):
                dma_chain.append({
                    "from": row[0],
                    "to": row[1],
                    "channel": row[2],
                    "description": row[3],
                    "relationship": "DMA_TO",
                })
        except Exception:
            pass

    # Step 5 — DMA-BUF config
    dma_buf_config: dict = {}
    try:
        q = conn.execute(
            "MATCH (c:Component {name: 'DMA-BUF'}) "
            "RETURN c.name, c.type, c.description, c.version",
        )
        rows = _result_to_list(q)
        if rows:
            dma_buf_config = {
                "name": rows[0][0],
                "type": rows[0][1],
                "description": rows[0][2],
                "version": rows[0][3],
                "heaps": ["CMA", "system", "system-uncached"],
                "zero_copy": True,
            }
    except Exception as e:
        dma_buf_config = {"error": str(e)}

    # Step 6 — downstream GPU/NPU consumers
    consumers: list[dict] = []
    for dst_node in ["GPU-AXI-Master", "GPU-Controller", "NPU-AXI-Master"]:
        try:
            q = conn.execute(
                "MATCH (c:Component {name: $name}) "
                "RETURN c.name, c.type, c.description",
                {"name": dst_node},
            )
            rows = _result_to_list(q)
            if rows:
                consumers.append({
                    "name": rows[0][0],
                    "type": rows[0][1],
                    "description": rows[0][2],
                })
        except Exception:
            pass

    pipeline_stages = []
    if sensor_info:
        pipeline_stages.append({"stage": "sensor_input", "component": sensor_info})
    if stream_chain:
        pipeline_stages.append({"stage": "streaming", "chain": stream_chain})
    if dma_chain:
        pipeline_stages.append({"stage": "dma_transfer", "chain": dma_chain})
    if consumers:
        pipeline_stages.append({"stage": "consumers", "components": consumers})

    results.append({
        "sensor": sensor_info,
        "pipeline_stages": pipeline_stages,
        "dma_buf_config": dma_buf_config,
        "bandwidth_requirement": {
            "total_mbps": round(total_bandwidth, 2),
            "per_link": bandwidth_list,
        },
        "query_ms": round((time.perf_counter() - t0) * 1000, 2),
    })

    return results


def query_multimedia_components(db_path: str = None) -> list[dict]:
    """Return all multimedia-type components in the graph.

    Parameters
    ----------
    db_path:
        Optional Kuzu DB path override.

    Returns
    -------
    list[dict]
    """
    if db_path is None:
        db_path = _BASE_DB

    _, conn = _open_db(db_path)
    results = []
    try:
        q = conn.execute(
            "MATCH (c:Component) "
            "WHERE c.type IN ['multimedia', 'isp', 'gpu', 'camera', 'video_encoder'] "
            "   OR c.name CONTAINS 'ISP' OR c.name CONTAINS 'CSI' "
            "   OR c.name CONTAINS 'GPU' OR c.name CONTAINS 'NPU' "
            "RETURN c.name, c.type, c.description "
            "ORDER BY c.type, c.name"
        )
        for row in _result_to_list(q):
            results.append({
                "name": row[0],
                "type": row[1],
                "description": row[2],
            })
    except Exception as e:
        results.append({"error": str(e)})
    return results


if __name__ == "__main__":
    print("=== ISP pipeline from MIPI-CSI2-RX ===")
    for r in query_isp_pipeline():
        print(f"  sensor    : {r['sensor']}")
        print(f"  bandwidth : {r['bandwidth_requirement']['total_mbps']} Mbps total")
        print(f"  dma_buf   : {r['dma_buf_config'].get('name')} zero_copy={r['dma_buf_config'].get('zero_copy')}")
        for stage in r["pipeline_stages"]:
            print(f"  stage[{stage['stage']}]: {stage}")
        print(f"  query_ms  : {r['query_ms']}")

    print("\n=== Multimedia components ===")
    for c in query_multimedia_components():
        print(f"  {c['name']:30s} [{c['type']}]")
