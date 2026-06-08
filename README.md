# erp-bom-processor

PCB BOM处理与比对工具。将原理图导出的基础BOM与元件库自动匹配，生成格式化的ERP BOM文件，并支持多BOM差异比对分析。

## 安装

```bash
npm install -g erp-bom-processor
```

**要求**:
- Node.js >= 14.0.0
- Python 3.7+ (需安装 pandas, openpyxl)
  ```bash
  pip install pandas openpyxl
  ```

## 快速开始

### 1. 准备目录结构

```bash
mkdir my-bom-project
cd my-bom-project
mkdir 02_BOMfromSystem 03_order 04_output
```

### 2. 放置文件

- **元件库** → `02_BOMfromSystem/`（系统导出的最新电子料库 .xlsx）
- **待处理BOM** → `03_order/`（原理图导出的 BOM 文件）

### 3. 处理 BOM

```bash
# 批量处理 03_order/ 下所有 BOM 文件
erp-bom process

# 处理单个文件
erp-bom process my_bom.xlsx
```

处理后输出到 `04_output/`，文件带 `_processed` 后缀。

### 4. 比对 BOM

```bash
# 自动比对 04_output/ 下所有已处理文件
erp-bom diff

# 指定文件比对
erp-bom diff BOM_A_processed.xlsx BOM_B_processed.xlsx
```

生成 `04_output/BOM差异清单.xlsx`，包含4个Sheet页。

## 功能特性

### BOM 处理

- **料号索引**: 有料号的通过料号从元件库提取最新描述
- **值+封装匹配**: 无料号的通过Value+Footprint自动匹配，提取料号和描述
- **智能精度匹配**: 电阻优先1%精度，电容无满足耐压时匹配更高耐压
- **封装严格验证**: BOM指定封装时，只能匹配库中相同封装的元件
- **自动合并**: 相同料号自动合并到同一行，位号用逗号拼接
- **跳过规则**: TP测试点、NC不连接自动跳过
- **多语言兼容**: 支持中英文列名格式

支持的元件类型:
| 类型 | 匹配方式 |
|------|-----------|
| IC/芯片 | 型号直接/包含匹配 |
| 电阻 | 值+精度+封装严格匹配 |
| 电容 | 容值+耐压+封装严格匹配 |
| 磁珠 | 阻抗值+封装严格匹配 |
| 晶振 | 频率精确匹配+封装 |
| 连接器等通用元件 | 模糊匹配+评分机制 |

### BOM 比对

- 以Part NO.为主键，识别BOM间的差异
- 输出格式化差异清单（汇总统计/独有物料/共有差异/未匹配物料）
- 差异项彩色标记（独有按BOM分色、差异黄色、未匹配红色）

## BOM 列格式

支持以下列名（中英文均可）:
| 英文 | 中文 |
|------|------|
| Item | 序号 |
| Part NO. | 编码 |
| Part Name | 名称 |
| Quantity | 数量 |
| Reference | 位号 |
| PCB Footprint | 封装 |
| Value | 规格 |

## 目录结构

```
项目根目录/
├── 01_Template/          # BOM模板参考文件(可选)
├── 02_BOMfromSystem/     # 元件库文件
├── 03_order/             # 待处理的BOM文件
├── 04_output/            # 处理输出目录
│   ├── *_processed.xlsx  # 处理后的格式化BOM
│   └── BOM差异清单.xlsx   # 差异比对报告
```

## License

MIT