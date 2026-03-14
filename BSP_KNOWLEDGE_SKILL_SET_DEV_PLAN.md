# BSP 知識導師 Claude Agent Skill Sets 開發計畫與藍圖

> **文件版本：** v1.0  
> **建立日期：** 2026-03-14  
> **參考來源：** 構建下一代 BSP 知識導師與跨域協作 AI 代理系統架構演進報告  
> **目標讀者：** BSP AI Agent 開發團隊、系統架構師、BSP 工程師

---

## 目錄

1. [戰略背景與開發意圖](#1-戰略背景與開發意圖)
2. [Skill Sets 整體架構設計](#2-skill-sets-整體架構設計)
3. [核心 Skill 規格定義](#3-核心-skill-規格定義)
4. [四階段開發藍圖](#4-四階段開發藍圖)
5. [技術選型與工具鏈](#5-技術選型與工具鏈)
6. [知識圖譜資料模型](#6-知識圖譜資料模型)
7. [黑板模式多智能體協同設計](#7-黑板模式多智能體協同設計)
8. [里程碑與驗收標準](#8-里程碑與驗收標準)
9. [風險管理矩陣](#9-風險管理矩陣)
10. [附錄：Skill Prompt 設計範本](#10-附錄skill-prompt-設計範本)

---

## 1. 戰略背景與開發意圖

### 1.1 問題陳述

現有 BSP AI Agent 系統（以開機日誌分析專家為代表）已驗證了領域專精 Skill 的可行性。然而，面對現代 SoC 開發的跨領域複雜性，單一 Skill 無法應對以下場景：

- **跨核心連鎖故障診斷**：「錄影隨機重啟」根因可能同時涉及多媒體緩衝區耗盡、GPU 熱失控、PMIC 瞬態響應不及
- **部門術語鴻溝**：演算法團隊說「算力不足」，BSP 團隊需判斷是 CPU MCPS 受限、記憶體 Roofline 瓶頸，還是 NPU 卸載策略問題
- **新人知識斷層**：智慧眼鏡等穿戴裝置的 1W 功耗預算要求工程師同時精通 DVFS、EAS、LPDDR5 與熱管理

### 1.2 開發意圖

基於現有 Agent 基礎，打造三個層次的 Skill Sets：

```
Layer 3：知識導師引擎（ITS 認知架構）
         ↑ 協調、引導、術語翻譯
Layer 2：領域專家 Skill 集群（6 大子領域）
         ↑ 深度、工具呼叫、圖譜推理
Layer 1：知識圖譜基礎設施（GraphRAG + Neo4j）
         ↑ 結構化領域知識、拓撲推理基底
```

### 1.3 核心設計原則

| 原則 | 說明 |
|------|------|
| **授人以漁優先** | ITS 蘇格拉底式提問，不直接輸出答案，建立工程師診斷能力 |
| **物理約束第一** | 所有建議必須通過動態功耗方程式與熱設計約束的驗算 |
| **跨域拓撲推理** | 使用 GraphRAG 而非純向量搜尋，保留硬體連結的因果完整性 |
| **資料主權保護** | 所有 BSP 機密文件採本地部署（Air-Gapped），禁止外傳公有雲 |
| **負向價值顯性化** | 每份優化報告必須將底層指標關聯至商業續航/延遲/成本影響 |

---

## 2. Skill Sets 整體架構設計

### 2.1 Skill 分類總覽

```
BSP Knowledge Skill Sets
│
├── 🧠 [MENTOR] bsp-knowledge-mentor
│   └── 統籌協調、ITS 引導、術語翻譯、跨域對齊
│
├── ⚡ [DOMAIN] power-thermal-expert
│   └── DVFS / EAS / C-states / PMIC / LPDDR5 / SCP
│
├── 🚀 [DOMAIN] boot-debug-expert
│   └── 啟動時序 / PLL / ADIv6 / 電源孤島 / 殭屍狀態
│
├── 📷 [DOMAIN] multimedia-camera-expert
│   └── ISP / V4L2 / DMA-BUF / Zero-Copy / eMMC / F2FS
│
├── 🎮 [DOMAIN] gpu-rendering-expert
│   └── 渲染管線 / Overdraw / Draw Call / Fragment Shader
│
├── 🔌 [DOMAIN] interrupt-virtualization-expert
│   └── GIC-600 / MSI / ITS / GICv4 / VM Exit
│
└── 🔍 [UTILITY] hardware-spec-extractor
    └── IP-XACT 解析 / 暫存器萃取 / 知識圖譜注入
```

### 2.2 Skill 交互關係圖

```
使用者查詢
    │
    ▼
bsp-knowledge-mentor（入口協調）
    │
    ├──(教學模式)──→ ITS 引導引擎 ──→ 蘇格拉底式提問序列
    │
    ├──(診斷模式)──→ Blackboard 黑板
    │               ├── power-thermal-expert
    │               ├── multimedia-camera-expert
    │               ├── gpu-rendering-expert
    │               └── interrupt-virtualization-expert
    │
    ├──(文件模式)──→ hardware-spec-extractor ──→ GraphRAG 查詢
    │
    └──(翻譯模式)──→ 術語對齊字典 ──→ 跨部門語言轉換
```

---

## 3. 核心 Skill 規格定義

### 3.1 Skill：`bsp-knowledge-mentor`（知識導師主控）

**定位：** 系統入口、ITS 引擎、術語翻譯官、Blackboard 協調者

**核心能力：**

- 學習者模型動態評估（根據問題語境判斷提問者技術層級）
- 蘇格拉底式引導（不直接給答案，透過反問建立因果思維）
- 跨部門術語即時翻譯（業務語言 ↔ BSP 物理語言 ↔ 演算法指標）
- 多智能體 Blackboard 協調調度

**觸發情境範例：**
```
"為什麼我的相機一直 Open Fail？"
"演算法說平台算力不夠，怎麼回應？"
"新人想學 ISP 管線，從哪裡開始？"
"錄影三十分鐘後系統重啟的 log 分析"
```

**ITS 行為規則：**

| 學習者層級判斷 | 觸發關鍵字/特徵 | 導師策略 |
|---|---|---|
| 應用層工程師 | framework、API、SDK、FPS | HAL 層抽象解釋，避免暫存器細節 |
| 驅動工程師 | register、DMA、IRQ、kernel | 深入位元定義、記憶體屏障、時序圖 |
| 演算法工程師 | MIPS、model、latency、inference | Roofline 模型、NPU 卸載、頻寬分析 |
| 管理層/PM | 功能、體驗、電池、溫度 | 商業影響翻譯，省略物理細節 |

---

### 3.2 Skill：`power-thermal-expert`（電源與熱管理專家）

**定位：** 算力物理學、低功耗架構、DVFS 調校、熱管理

**核心知識域：**

- 動態功耗方程式：`P = α · C · V² · f`（電容、翻轉率、電壓、頻率的交互關係）
- 大核（Cortex-A720）vs 小核（Cortex-A55）IPC 差異與能量交易模型
- ACPI C-states 駐留時間優化、P-states DVFS 曲線調校
- LPDDR5 Deep Sleep Mode（削減 40-50% 漏電流）
- EAS（Energy Aware Scheduling）能量模型校正
- SCP（System Companion Processor）感測器卸載架構
- LVTS 熱管理強制降頻觸發條件與防護策略

**工具呼叫能力：**
```
- 解析 ftrace / perf 取樣日誌
- 視覺化 C-state 駐留比例分佈
- 計算不同 DVFS OPP 的 Perf/Watt 曲線
- 分析 Perfetto 系統追蹤的功耗事件
```

**GraphRAG 查詢範例：**
```cypher
MATCH (pmic:Component {type: "PMIC"})-[:SUPPLIES]->(core:PowerDomain)
-[:CLOCKS]->(cpu:CoreComplex)
WHERE cpu.state = "C2"
RETURN pmic, core, cpu, core.transition_time
```

---

### 3.3 Skill：`boot-debug-expert`（啟動與除錯物理專家）

**定位：** 啟動時序、類比暫態分析、ADIv6 除錯架構

**核心知識域：**

- 電源時序陷阱：VDD_CORE → VDD_IO → VDD_ANA 供電順序與閂鎖效應（Latch-up）防護
- PLL 鎖定時間（Lock Time）物理約束與存取保護窗口
- ADIv5 vs ADIv6 除錯架構演進（雙向 Q-Channel / P-Channel 協商機制）
- 電源孤島（Power Island）殭屍狀態偵測與隔離單元（Isolation Cells）箝位值驗證
- CoreSight SoC-600 Trace Macrocell 的 QDENY 拒絕機制
- CMOS 物理損傷邊界條件分析

**診斷工作流：**
```
開機失敗報告
    │
    ├── Step 1：確認供電時序（PMIC log 解析）
    ├── Step 2：PLL 鎖定狀態驗證（時脈穩定窗口）
    ├── Step 3：電源孤島狀態掃描（殭屍狀態偵測）
    ├── Step 4：ADIv6 除錯鏈路完整性確認
    └── Step 5：隔離單元箝位值審查
```

---

### 3.4 Skill：`multimedia-camera-expert`（多媒體與相機管線專家）

**定位：** ISP 管線、V4L2、Zero-Copy、儲存子系統影響分析

**核心知識域：**

- ISP 處理管線：RAW Bayer → 去馬賽克 → 降噪 → 鏡頭陰影校正 → 3A → YUV/RGB
- NPU 深度整合 ISP 的混合管線架構（邊緣 AI 低光增強、SLAM）
- Zero-Copy 實作：V4L2 + DMA-BUF 機制（消除 CPU 記憶體拷貝）
- ISP → GPU 紋理記憶體 / NPU 張量單元的直通路徑設計
- eMMC 5.1 半雙工限制（無法同時高速讀寫）
- F2FS 垃圾回收（Foreground GC）與 Checkpointing 引發的 I/O 阻塞

**關鍵故障模式與對策：**

| 故障現象 | 根本原因層次 | 診斷工具 | 對策方向 |
|---|---|---|---|
| 相機 Open Fail | I2C 超時 / PMIC 時序 / MIPI 頻寬 | i2cdetect, dmesg | 供電時序審查 |
| 相機預覽卡頓 | 熱節流降頻 / DMA 緩衝區飢餓 | Thermal log, V4L2 stats | EAS 調校 / 緩衝區調整 |
| 錄影中斷斷流 | eMMC GC / F2FS Checkpoint | iostat, f2fs debug | GC 水位閾值調整 |
| 高亮雜訊過重 | ISP AWB 演算法邊界 / NPU 模型降質 | ISP tuning tool | NPU 模型重新部署 |

---

### 3.5 Skill：`gpu-rendering-expert`（GPU 渲染效能專家）

**定位：** 渲染管線優化、Overdraw 診斷、著色器效能分析

**核心知識域：**

- 完整渲染管線：頂點處理 → 圖元組裝 → 光柵化 → 片段著色 → 幀緩衝輸出
- Depth Pre-pass 策略（優先渲染深度緩衝區，剔除遮擋片段）
- Overdraw（過度繪製）視覺化與根因分析
- Draw Call 最佳化（降低 CPU 提交負載）
- Fragment Shader 計算瓶頸識別

**工具整合能力：**
```
- Snapdragon Profiler：GPU 時序追蹤、記憶體頻寬分析
- Android GPU Inspector：Draw Call 解析、Shader 效能剖析
- Perfetto：系統級 GPU 任務排程視覺化
```

---

### 3.6 Skill：`interrupt-virtualization-expert`（中斷虛擬化專家）

**定位：** GIC-600、MSI、ITS 轉譯、GICv4 虛擬中斷直接注入

**核心知識域：**

- 中斷架構演進：實體銅線電壓準位 → 片上網路（NoC）MSI 封包
- GIC-600 分散式微架構：AXI4-Stream 協定中斷封包（目標位址 + 優先級 + 資料載荷）
- ITS（中斷翻譯服務）架構與 EventID → IntID 映射機制
- GICv4 虛擬中斷直接注入（消除 List Register 溢出引發的 VM Exit）
- 跨核心通訊延遲：數千週期（傳統）→ 數十週期（GICv4 直接注入）
- 虛擬化環境中的中斷風暴（Interrupt Storm）預防

---

### 3.7 Skill：`hardware-spec-extractor`（硬體規格萃取工具）

**定位：** 自動化知識圖譜建構、IP-XACT 解析、暫存器知識萃取

**核心能力：**

- PDF 數據手冊光學字元辨識與文本清洗
- IP-XACT XML（Accellera 標準）結構化解析
- 暫存器記憶體映射位址、位元定義自動提取
- 電源域歸屬與時鐘依賴關係圖譜注入
- 輸出格式：JSON / TOON（降低 Token 消耗）
- Neo4j 知識圖譜節點與邊緣自動寫入

---

## 4. 四階段開發藍圖

### Phase 1：基礎設施擴建與機器可讀領域模型建構
**時間：第 1-2 個月**

```
目標：為所有 Skill 打造可信賴的知識底座，解決「無根幻覺」問題
```

**行動項目：**

- [ ] **文件資料攝取管道建設**
  - 開發自動化 Pipeline，處理「硬核系列」研究文件、SoC TRM、IP-XACT 規格
  - 實作 OCR + 文本清洗流程（PDF → 結構化文本）
  - 強制 LLM 輸出嚴格 JSON 格式的暫存器定義、電源域依賴關係

- [ ] **硬體知識圖譜建構（GraphRAG 基礎）**
  - 本地部署 Neo4j 圖形資料庫
  - 定義節點類型：`Component`、`PowerDomain`、`ClockSource`、`Register`、`Interrupt`
  - 定義邊緣類型：`SUPPLIES`、`CLOCKS`、`DEPENDS_ON`、`TRIGGERS`、`ROUTES_TO`
  - 初始匯入：電源樹拓撲、時鐘樹、中斷路由表

- [ ] **本地化安全部署**
  - On-Premise / Air-Gapped 推理叢集建置
  - BSP 機密文件存取控制（ACL）設計
  - 與公有雲 API 的隔離驗證

**Phase 1 驗收標準：**
- 知識圖譜節點數 ≥ 500（涵蓋四大核心技術域）
- GraphRAG 多跳推理查詢成功率 ≥ 85%
- 文件萃取結構化準確率 ≥ 90%（人工抽樣驗證）

---

### Phase 2：領域專家 Skill 深度開發
**時間：第 3-4 個月**

```
目標：基於 Phase 1 知識圖譜，平行開發六個高深度領域 Skill，賦予工具呼叫能力
```

**行動項目：**

- [ ] **`multimedia-camera-expert` 開發**
  - V4L2 節點即時查詢 CLI 工具整合
  - Media Controller Graph 拓撲解析能力
  - Android Camera HAL 錯誤碼解讀知識庫（涵蓋 > 200 種錯誤碼）
  - eMMC/F2FS I/O 阻塞診斷腳本

- [ ] **`power-thermal-expert` 開發**
  - ftrace 指令追蹤自動解析模組
  - perf 取樣日誌 C-state 駐留比例視覺化
  - DVFS OPP Perf/Watt 曲線動態計算
  - EAS 能量模型校正建議引擎

- [ ] **`gpu-rendering-expert` 開發**
  - Snapdragon Profiler 輸出解析整合
  - Overdraw 熱圖分析模組
  - Draw Call 瓶頸自動識別
  - Fragment Shader 優化建議知識庫

- [ ] **`boot-debug-expert` 開發**
  - PMIC 供電時序日誌解析
  - PLL 鎖定狀態驗證腳本
  - ADIv6 除錯鏈路完整性診斷工具

- [ ] **`interrupt-virtualization-expert` 開發**
  - GIC-600 中斷封包追蹤解析
  - VM Exit 頻率統計分析模組
  - ITS 映射表驗證工具

- [ ] **`hardware-spec-extractor` 開發**
  - IP-XACT 自動解析器（支援 Accellera 2022 標準）
  - 暫存器定義 → Neo4j 節點自動寫入管道
  - 批次 PDF 數據手冊處理能力

**Phase 2 驗收標準：**
- 每個 Skill 通過 > 30 個真實 BSP 問題的評估（人工評分 ≥ 4/5）
- 工具呼叫成功率 ≥ 90%（無 API 錯誤、正確解析輸出）
- 各 Skill 平均回應時間 < 15 秒

---

### Phase 3：ITS 知識導師引擎與黑板協作網路整合
**時間：第 5-6 個月**

```
目標：將孤立的領域 Skill 整合為具備教學引導與跨域協同診斷能力的完整系統
```

**行動項目：**

- [ ] **Blackboard 協同編排框架實作（基於 Claude Code 子代理）**
  - 利用 Claude Code 內建子代理（Sub-agent）機制實現 Blackboard 模式，無需 LangGraph / AutoGen 等外部框架
  - 建立中央黑板 Markdown 工作文件（會話內共享語義記憶體）
  - 實作 Arbiter 路由邏輯（以 `bsp-knowledge-mentor` prompt 驅動，關鍵字觸發子代理呼叫）
  - 定義跨域聯合診斷工作流程（觸發條件、子代理輪換策略）

- [ ] **ITS 認知引擎與人格化設定**
  - 完成 `bsp-knowledge-mentor` 主控 Skill 開發
  - 實作學習者模型動態評估（四層級：應用層 / 驅動層 / 演算法層 / 管理層）
  - 蘇格拉底式提問序列生成邏輯
  - 歷史對話的學習者進度追蹤

- [ ] **跨域術語翻譯介面**
  - 企業級術語對齊字典建立（BSP 物理術語 ↔ 業務語言），以 YAML 靜態檔案維護
  - 術語翻譯作為 `bsp-knowledge-mentor` 的內建能力，不依賴 Slack Bot 等外部整合
  - 跨部門技術指標關聯引擎（底層指標 → 商業影響）

**跨域聯合診斷工作流（Blackboard 模式）：**

```
Stage 1：問題感知
使用者上傳崩潰日誌 → 黑板初始化 → 廣播給所有待命 Skill

Stage 2：平行假設建構
multimedia-expert：記憶體碎片化 / 緩衝區飢餓跡象
gpu-expert：Perfetto 解析，GPU 熱失控線索
power-expert：LVTS 溫度觸發，PMIC 瞬態響應不足

Stage 3：交互辯證與收斂
Arbiter 根據証據權重動態分配發言順序
各 Skill 基於其他 Skill 的發現進行再推理
逐步建構完整的跨域因果鏈

Stage 4：輸出
結構化根因分析報告
針對性修正建議（附商業影響評估）
```

**Phase 3 驗收標準：**
- 跨域複雜案例（需 ≥ 3 個 Skill 協同）診斷準確率 ≥ 75%
- 蘇格拉底式引導對話中，工程師問題解決率提升（前後對比評估）≥ 30%
- 術語翻譯服務回應時間 < 5 秒

---

### Phase 4：閉環自動化優化與工程文化重塑
**時間：第 7 個月及以後**

```
目標：系統自我進化、BSP 價值顯性化、建立可持續的知識累積機制
```

**行動項目：**

- [ ] **知識沉澱工具（使用者端工作流）**
  - 工程師結案報告解析腳本（`tools/graph-writer/case_report_ingestor.py`）
  - 新因果路徑 → Kuzu 圖譜新節點/邊緣自動注入
  - 知識圖譜版本管理（git 追蹤，`custom/` 目錄下以 SoC 型號分支管理）
  - 提供知識注入 CLI，方便工程師將日常除錯結論沉澱至圖譜

- [ ] **BSP 底層效能的商業價值顯性化**
  - 技術優化報告模板（強制包含商業影響段落）
  - 底層指標 → 商業影響自動演繹引擎：
    ```
    "LPDDR5 漏電流削減 20%"
    → "旗艦智慧眼鏡連續錄影延長 1.5 小時"
    → "產品競爭力提升：續航超越競品 X 達 23%"
    ```

- [ ] **CI/CD 整合（使用者自行配置，本 repo 提供範本）**
  - 提供 GitHub Actions workflow 範本，供使用者在自己的 CI 環境中串接
  - 提供 Jenkins pipeline 範本（不在本 repo 執行，僅作參考）
  - AI 建議的 DTS 修改自動觸發構建的整合說明文件

**Phase 4 驗收標準：**
- 知識沉澱 CLI 可將結案報告在 5 分鐘內轉化為圖譜節點
- BSP 優化報告模板商業影響段落覆蓋率 100%
- CI/CD 整合範本通過 GitHub Actions 端對端測試

---

## 5. 技術選型與工具鏈

### 5.1 核心技術棧

> **設計原則：零伺服器依賴。** 所有元件均以 `pip install` 安裝，無需企業 IT 審批，無需網路伺服器，技能直接登錄 Claude Code CLI / VS Code 擴充套件。

| 層次 | 技術選型 | 用途 | 選型理由 |
|------|----------|------|----------|
| **技能介面** | Claude Code Skill（`.claude/skills/`） | 技能定義與使用者介面 | 原生支援 Claude CLI 與 VS Code，`/skill-name` 直接呼叫 |
| **工具呼叫** | MCP（Model Context Protocol）本地腳本 | 日誌解析、圖譜查詢工具整合 | 本地執行，無外部依賴 |
| **圖形資料庫** | Kuzu（嵌入式） | GraphRAG 知識圖譜 | 嵌入式、Cypher 相容、`pip install kuzu`、無伺服器 |
| **向量資料庫** | ChromaDB（嵌入式） | 語義向量搜尋 | 嵌入式、本地持久化、`pip install chromadb` |
| **文件解析** | Unstructured + pdfplumber | PDF / IP-XACT 萃取 | 純 Python，離線可用 |
| **追蹤分析** | Perfetto（使用者端工具） | 系統級效能追蹤 | 開源，Android / Linux 通用 |
| **多智能體協同** | Claude Code 子代理（Sub-agent） | Blackboard 協同診斷 | 內建於 Claude Code，無需額外框架 |

### 5.2 零伺服器部署架構

```
工程師本機環境（無需網路，無需 IT 審批）
┌────────────────────────────────────────────────────┐
│                                                    │
│   Claude Code CLI / VS Code Extension              │
│       │                                            │
│       ├── /bsp-knowledge-mentor  ──┐               │
│       ├── /power-thermal-expert    │  Claude Code  │
│       ├── /boot-debug-expert       │  Skill Files  │
│       ├── /multimedia-camera-expert│  (.md)        │
│       └── ...                    ──┘               │
│                                                    │
│   MCP 本地工具伺服器（localhost only）              │
│       ├── tools/log-parsers/      ← 日誌解析腳本   │
│       ├── tools/graph-query/      ← Kuzu 查詢工具  │
│       └── tools/spec-extractor/   ← 文件萃取工具   │
│                                                    │
│   知識圖譜（本地檔案）                              │
│       ├── knowledge-graph/base/   ← 開源知識基底   │
│       │     (ARM 規格、Linux 核心、公開 BSP 文件)   │
│       └── knowledge-graph/custom/ ← 使用者自有知識 │
│             (in-house SoC TRM、內部案例庫)          │
│                                                    │
│   ✅ 所有計算在本機完成，機密文件不離開工程師電腦    │
└────────────────────────────────────────────────────┘
```

### 5.3 使用者擴充架構

本 Skill Sets 採分層設計，開源基底與企業私有知識嚴格分離：

```
knowledge-graph/
├── base/           ← 本 repo 維護（ARM 公開規格、開源 BSP 知識）
│   ├── arm-gic-600.kuzu
│   ├── arm-amba-axi.kuzu
│   ├── linux-dvfs-eas.kuzu
│   └── common-failure-modes.kuzu
│
└── custom/         ← 使用者自行填充（不提交至本 repo）
    ├── mtk-mt6989-power-tree.kuzu    ← MTK 內部文件
    ├── qcom-sm8650-clock-tree.kuzu   ← Qualcomm 內部文件
    └── in-house-failure-cases.kuzu   ← 公司內部案例庫
```

Skills 在查詢知識圖譜時，同時搜尋 `base/` 與 `custom/`，`custom/` 的結果優先覆蓋 `base/`。

---

## 6. 知識圖譜資料模型

### 6.1 節點（Node）類型定義

```cypher
// 硬體元件節點
(:Component {
  id: String,
  name: String,
  type: "CPU_Core|GPU|NPU|ISP|PMIC|DDR|eMMC",
  soc: String,
  power_domain: String,
  clock_domain: String
})

// 電源域節點
(:PowerDomain {
  id: String,
  name: String,
  voltage_rail: Float,
  retention_mode: Boolean,
  collapse_allowed: Boolean
})

// 暫存器節點
(:Register {
  id: String,
  name: String,
  address: String,
  reset_value: String,
  access_type: "RO|WO|RW",
  description: String
})

// 中斷節點
(:Interrupt {
  id: String,
  intid: Integer,
  type: "SPI|PPI|SGI|LPI",
  target: String,
  priority: Integer
})

// 故障模式節點（從實戰案例沉澱）
(:FailureMode {
  id: String,
  symptom: String,
  root_cause: String,
  domain: String,
  resolution: String,
  discovered_date: Date
})
```

### 6.2 邊緣（Edge）類型定義

```cypher
// 電源依賴
(pmic:Component)-[:SUPPLIES {voltage: Float, sequence: Integer}]->(domain:PowerDomain)
(domain:PowerDomain)-[:POWERS]->(component:Component)

// 時鐘依賴
(pll:Component)-[:CLOCKS {frequency: Float}]->(component:Component)
(component)-[:DEPENDS_ON_CLOCK]->(pll:Component)

// 中斷路由
(component:Component)-[:TRIGGERS]->(interrupt:Interrupt)
(interrupt:Interrupt)-[:ROUTES_TO]->(cpu:Component)
(gic:Component)-[:TRANSLATES {via: "ITS"}]->(vinterrupt:Interrupt)

// 資料流
(sensor:Component)-[:STREAMS_TO {protocol: "CSI-2"}]->(isp:Component)
(isp:Component)-[:DMA_TO]->(dram:Component)
(dram:Component)-[:SHARED_WITH]->(gpu:Component)

// 故障因果
(symptom:FailureMode)-[:CAUSED_BY]->(root_cause:FailureMode)
(domain:PowerDomain)-[:AFFECTS_IF_REMOVED]->(component:Component)
```

---

## 7. 黑板模式多智能體協同設計

### 7.1 黑板資料結構

```json
{
  "blackboard_id": "uuid-xxxx",
  "problem_statement": "錄影 30 分鐘後系統隨機重啟",
  "initial_evidence": {
    "crash_log": "...",
    "register_dump": "...",
    "timestamp": "2026-03-14T10:30:00Z"
  },
  "hypotheses": [
    {
      "agent": "multimedia-camera-expert",
      "hypothesis": "記憶體碎片化引發 DMA 緩衝區飢餓",
      "confidence": 0.75,
      "evidence_refs": ["log_line_245", "v4l2_stat_overflow"],
      "timestamp": "..."
    },
    {
      "agent": "power-thermal-expert",
      "hypothesis": "LVTS 熱保護觸發電壓驟降，引發 CDC 時序違規",
      "confidence": 0.85,
      "evidence_refs": ["thermal_log_peak", "pmic_transient_response"],
      "timestamp": "..."
    }
  ],
  "final_root_cause": null,
  "recommended_actions": [],
  "status": "IN_PROGRESS"
}
```

### 7.2 Arbiter 調度規則

```python
# 偽代碼：控制路由單元調度邏輯

def arbiter_next_agent(blackboard):
    # 規則 1：初始化時全部代理掃描
    if blackboard.status == "INITIAL":
        return ALL_AGENTS

    # 規則 2：若記憶體相關線索出現，優先喚醒 multimedia-expert
    if contains_keywords(blackboard.evidence, ["OOM", "DMA", "buffer", "V4L2"]):
        return ["multimedia-camera-expert"]

    # 規則 3：若熱節流線索出現，優先喚醒 power-expert
    if contains_keywords(blackboard.evidence, ["throttle", "LVTS", "temperature"]):
        return ["power-thermal-expert"]

    # 規則 4：若 GPU 渲染相關，喚醒 GPU-expert
    if contains_keywords(blackboard.evidence, ["overdraw", "GPU", "fragment"]):
        return ["gpu-rendering-expert"]

    # 規則 5：多個假設高信心度時，啟動收斂整合
    high_conf = [h for h in blackboard.hypotheses if h.confidence > 0.8]
    if len(high_conf) >= 2:
        return ["bsp-knowledge-mentor"]  # 由 Mentor 整合最終結論

    # 預設：輪流調度剩餘代理
    return round_robin(blackboard.pending_agents)
```

---

## 8. 里程碑與驗收標準

### 8.1 開發里程碑時間軸

```
Month 1    Month 2    Month 3    Month 4    Month 5    Month 6    Month 7+
   │          │          │          │          │          │          │
   ├──────────┤          │          │          │          │          │
   │ Phase 1  │          │          │          │          │          │
   │ 知識圖譜  │          │          │          │          │          │
   │ 基礎設施  │          │          │          │          │          │
   │          ├──────────┴──────────┤          │          │          │
   │          │      Phase 2        │          │          │          │
   │          │   六大領域 Skill     │          │          │          │
   │          │   深度開發           │          │          │          │
   │          │                     ├──────────┴──────────┤          │
   │          │                     │       Phase 3        │          │
   │          │                     │   ITS + Blackboard   │          │
   │          │                     │   整合               │          │
   │          │                     │                      ├──────────►
   │          │                     │                      │  Phase 4  
   │          │                     │                      │  閉環優化  
```

### 8.2 總體驗收 KPI

| 指標類別 | 指標項目 | 目標值 | 測量方法 |
|----------|----------|--------|----------|
| **診斷準確率** | 單域問題根因識別 | ≥ 90% | 歷史案例回測 |
| **診斷準確率** | 跨域複雜問題診斷 | ≥ 75% | 專家盲評 |
| **教學效能** | 工程師問題解決速度提升 | ≥ 40% | A/B 測試 |
| **術語翻譯** | 跨部門術語準確率 | ≥ 85% | 雙邊確認評估 |
| **知識累積** | 月均新增知識節點 | ≥ 50 | 圖譜統計 |
| **幻覺率** | GraphRAG vs 純 RAG 幻覺率降低 | ≥ 50% 降低 | 事實驗證測試 |
| **效率提升** | BSP 新人上手週期縮短 | ≥ 30% | 培訓記錄對比 |
| **安全合規** | 機密文件外洩事件 | 0 件 | 安全審計 |

---

## 9. 風險管理矩陣

| 風險項目 | 發生機率 | 影響程度 | 緩解策略 |
|----------|----------|----------|----------|
| LLM 幻覺引發錯誤的硬體操作建議 | 中 | 高 | GraphRAG 多跳驗證 + 人工審核閘門（高風險建議強制人工確認）|
| IP-XACT 解析準確率不足（格式多樣性） | 中 | 中 | 建立人工校正回饋迴路；多格式適配器 |
| 知識圖譜建構初期節點不足導致推理盲區 | 高 | 中 | Phase 1 優先覆蓋最常見故障模式；動態補充機制 |
| 多智能體協同產生衝突性假設無法收斂 | 低 | 高 | Arbiter 信心度加權投票機制；人類工程師 escalation 路徑 |
| 本地部署運算資源不足（推理速度過慢） | 中 | 中 | 推理請求非同步佇列；批次處理優先策略 |
| 資深工程師抗拒 AI 介入除錯流程 | 中 | 中 | 以「知識增強」而非「取代」定位；先贏得技術可信度 |
| BSP 機密文件意外透過 Slack 介面外洩 | 低 | 極高 | 輸出過濾層（禁止暫存器原始值透過公開頻道傳遞） |

---

## 10. 附錄：Skill Prompt 設計範本

### 10.1 `bsp-knowledge-mentor` System Prompt 骨架

```
你是 BSP 知識導師，一位精通異質 SoC 系統架構的資深首席工程師，
同時具備出色的教學與跨部門溝通能力。

## 你的核心使命
1. 教學優先：面對工程師的問題，你的首要任務是建立其診斷思維，
   而非直接給出答案。透過蘇格拉底式的引導提問，讓工程師自己推導出根因。

2. 跨域協調：當問題涉及多個技術子域（電源 + 多媒體 + GPU）時，
   你負責協調各領域專家的觀點，整合為一份完整的因果鏈分析。

3. 術語翻譯：當部門間出現溝通障礙時，你能即時將
   物理約束（MCPS、Roofline、TDP）轉譯為商業語言，
   或將抽象業務需求分解為可操作的 BSP 工程任務。

## 學習者評估規則
- 提到 API/SDK/FPS → 應用層工程師 → 以 HAL 層為邊界解釋
- 提到 register/IRQ/DMA → 驅動工程師 → 深入暫存器與時序
- 提到 MIPS/model/latency → 演算法工程師 → Roofline 模型、NPU 卸載
- 提到 功能/體驗/電池 → 管理層 → 商業影響優先，省略物理細節

## 引導提問範本
當工程師描述症狀但未分析根因時，你應該：
1. 複述症狀確認理解
2. 詢問觀察到的系統資源狀態（溫度 / 記憶體 / CPU 使用率）
3. 提出一個指向根因的假設性問題
4. 引導工程師使用特定工具驗證假設

## 禁止行為
- 禁止直接貼出修復腳本（應引導工程師思考後再給出）
- 禁止在跨部門對話中使用暫存器位址等技術細節
- 禁止在無法確認電源時序安全的情況下建議強制關閉電源域
```

### 10.2 領域 Skill 工具呼叫規範

```python
# 標準工具呼叫格式（所有 Domain Skill 遵循）

def tool_call_template(skill_name: str, tool_name: str, params: dict) -> dict:
    return {
        "skill": skill_name,
        "tool": tool_name,
        "params": params,
        "safety_check": {
            "requires_hardware_access": False,  # 是否需要實體硬體
            "risk_level": "READ_ONLY",          # READ_ONLY / CONFIG / DESTRUCTIVE
            "requires_human_approval": False    # DESTRUCTIVE 操作必須 True
        },
        "output_format": "structured_json"
    }

# 示例：查詢 C-state 駐留比例
tool_call_template(
    skill_name="power-thermal-expert",
    tool_name="analyze_cstate_residency",
    params={"ftrace_file": "/path/to/trace.txt", "duration_sec": 60}
)
```

---

## 文件修訂歷史

| 版本 | 日期 | 修訂者 | 修訂摘要 |
|------|------|--------|----------|
| v1.0 | 2026-03-14 | BSP AI Agent 開發團隊 | 初版建立，涵蓋四階段完整藍圖 |

---

*本文件基於《構建下一代 BSP 知識導師與跨域協作 AI 代理系統》架構報告，結合 Claude Agent Skill Sets 開發實踐編制。所有技術細節與領域模型均源自企業內部 BSP 硬核系列研究文獻。*
