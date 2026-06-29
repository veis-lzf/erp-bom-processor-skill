#!/usr/bin/env python3
"""OrCAD EXP 文件处理器 — 3 种功能：
  1. EXP → BOM：提取 Part Reference/Value/DESCRIPTION/Part NO./Part Name/PCB Footprint，合并相同物料
  2. Library → EXP：用元件库更新 EXP 中的 DESCRIPTION/Part NO./Part Name
  3. BOM + Library → EXP：用 BOM+库 更新 EXP，生成新 EXP 文件
"""
import sys, os, re, csv, glob
import pandas as pd
import importlib.util

# 导入 bom_processor 库加载函数
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bom_processor", os.path.join(SCRIPT_DIR, 'bom_processor.py'))
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)

# ─── EXP 文件读写 ───
EXP_HEADER_LINES = 2
COL_IDX = {
    'Part Reference': 2,   # 位号
    'Value': 3,            # 值
    'DESCRIPTION': 7,      # 描述字段1（OrCAD property）
    'Description': 9,      # 描述字段2
    'PCB Footprint': 30,   # PCB 封装
    'Part NO': 33,         # 料号
    'Part Name': 34,       # 零件名 ← 规格型号
    'Part Type': 36,       # 元件类型 ← 名称
    'DNP': 8,              # 不焊接标记
}


def read_exp(path):
    """读取 EXP 文件，返回 (design_line, header_line, rows)"""
    with open(path, 'r', encoding='gbk', errors='replace') as f:
        lines = f.readlines()
    design = lines[0].rstrip('\n')
    header = lines[1].rstrip('\n')
    rows = []
    for line in lines[2:]:
        line = line.rstrip('\n').rstrip('\r')
        if line.startswith('"PARTINST:'):
            rows.append(line)
    return design, header, rows


def parse_exp_row(line):
    """解析一行 EXP 为字段列表（直接按 \"\t\" 分割，不用 csv.reader 避免破坏内部引号）"""
    # EXP 格式：每个字段用双引号包裹，字段间用 tab 分隔
    # 直接用 "\t 分割即可，去掉首尾引号
    fields = line.split('\t')
    # 去掉每个字段的首尾引号
    fields = [f[1:-1] if (f.startswith('"') and f.endswith('"')) else f for f in fields]
    return fields


def rebuild_exp_row(fields):
    """将字段列表重建为 EXP 行"""
    return '\t'.join(f'"{f}"' for f in fields)


def write_exp(path, design, header, rows):
    """写 EXP 文件（GBK 编码，兼容 OrCAD）"""
    with open(path, 'w', encoding='gbk', newline='\r\n') as f:
        f.write(design + '\n')
        f.write(header + '\n')
        for r in rows:
            f.write(r + '\n')


def load_lib():
    """加载最新元件库"""
    lib_files = sorted(glob.glob(os.path.join('02_BOMfromSystem', '*.xlsx')), reverse=True)
    if not lib_files:
        raise FileNotFoundError('未找到元件库')
    return bm.load_component_library(lib_files[0])


# ─── 功能 1: EXP → BOM ───
def exp_to_bom(exp_path, output_path=None):
    """从 EXP 提取 BOM，相同物料合并"""
    design, header, rows = read_exp(exp_path)
    
    items = []
    for line in rows:
        fields = parse_exp_row(line)
        ref = fields[COL_IDX['Part Reference']]
        value = fields[COL_IDX['Value']]
        desc = fields[COL_IDX['Description']] or fields[COL_IDX['DESCRIPTION']]
        part_no = fields[COL_IDX['Part NO']]
        part_name = fields[COL_IDX['Part Name']]
        footprint = fields[COL_IDX['PCB Footprint']]
        dnp = fields[COL_IDX['DNP']]
        
        # 跳过 TP 测试点
        if ref.upper().startswith('TP'):
            continue
        
        items.append({
            'Part Reference': ref,
            'Value': value,
            'DESCRIPTION': desc,
            'Part NO.': part_no if part_no and part_no != '<null>' else '',
            'Part Name': part_name if part_name and part_name != '<null>' else '',
            'PCB Footprint': footprint,
            'DNP': dnp if dnp and dnp != '<null>' else '',
        })
    
    df = pd.DataFrame(items)
    
    # 合并相同物料：按 Part NO. > Value+Footprint 分组
    merged = {}
    for _, row in df.iterrows():
        pn = row['Part NO.']
        if pd.notna(pn) and pn and pn not in ('Needless_Part_Number', '<null>'):
            key = pn
        else:
            key = f"{row['Value']}|{row['PCB Footprint']}"
        
        if key not in merged:
            merged[key] = {
                'Part NO.': pn if pn not in ('Needless_Part_Number', '<null>') else '',
                'Part Name': row['Part Name'],
                'Value': row['Value'],
                'DESCRIPTION': row['DESCRIPTION'],
                'PCB Footprint': row['PCB Footprint'],
                'References': [],
                'Quantity': 0,
            }
        merged[key]['Quantity'] += 1
        merged[key]['References'].append(row['Part Reference'])
    
    result = []
    for i, (key, data) in enumerate(merged.items(), 1):
        result.append({
            'Item': i,
            'Part NO.': data['Part NO.'],
            'Part Name': data['Part Name'],
            'Value': data['Value'],
            'DESCRIPTION': data['DESCRIPTION'],
            'PCB Footprint': data['PCB Footprint'],
            'Quantity': data['Quantity'],
            'Reference': ','.join(data['References']),
        })
    
    out_df = pd.DataFrame(result)
    if output_path is None:
        base = os.path.splitext(os.path.basename(exp_path))[0]
        output_path = os.path.join('04_output', f'{base}_BOM_from_EXP.xlsx')
    out_df.to_excel(output_path, index=False)
    print(f'[EXP→BOM] 输出: {output_path}')
    print(f'  器件总数: {len(items)}, 合并后: {len(out_df)} 行')
    return out_df


# ─── 功能 3: Library → EXP 更新 ───
def library_update_exp(exp_path, output_path=None):
    """用元件库更新 EXP 中的 DESCRIPTION/Part NO./Part Name"""
    design, header, rows = read_exp(exp_path)
    lib = load_lib()
    print(f'[Library→EXP] 元件库: {os.path.basename(list(glob.glob("02_BOMfromSystem/*.xlsx"))[0])}')
    
    updated = 0
    no_match = 0
    skipped_tp = 0
    no_match_list = []
    new_rows = []
    
    for line in rows:
        fields = parse_exp_row(line)
        ref = fields[COL_IDX['Part Reference']]
        part_no = fields[COL_IDX['Part NO']]
        
        # 跳过 TP 测试点
        if ref.upper().startswith('TP'):
            skipped_tp += 1
            new_rows.append(rebuild_exp_row(fields))
            continue
        
        # 尝试用料号查库
        found = None
        if part_no and part_no not in ('<null>', 'Needless_Part_Number', '0', ''):
            found = bm.find_component_by_part_no(lib, part_no)
        
        # 如果料号找不到，用 value+footprint 查
        if found is None:
            value = fields[COL_IDX['Value']]
            footprint = fields[COL_IDX['PCB Footprint']]
            if value and footprint:
                found = bm.find_component_by_value_footprint(lib, value, footprint, ref)
        
        if found is not None:
            fields[COL_IDX['Part NO']] = str(found['(物料)编码'])
            fields[COL_IDX['Part Name']] = str(found['*(物料)规格型号'])
            fields[COL_IDX['Part Type']] = str(found['*(物料)名称'])
            fields[COL_IDX['DESCRIPTION']] = str(found['*(物料)规格型号'])
            fields[COL_IDX['Description']] = str(found['*(物料)规格型号'])
            updated += 1
        else:
            no_match += 1
            no_match_list.append({
                'Reference': ref,
                'Value': fields[COL_IDX['Value']],
                'PCB Footprint': fields[COL_IDX['PCB Footprint']],
                'Part NO': part_no,
            })
        
        new_rows.append(rebuild_exp_row(fields))
    
    if output_path is None:
        base, ext = os.path.splitext(os.path.basename(exp_path))
        output_path = os.path.join('04_output', f'{base}_updated{ext}')
    
    write_exp(output_path, design, header, new_rows)
    print(f'  输出: {output_path}')
    print(f'  更新: {updated}, 未匹配: {no_match}, 跳过TP: {skipped_tp}')
    
    if no_match_list:
        # 生成详细未匹配清单（不合并，保留所有 Reference）
        um_df = pd.DataFrame(no_match_list)
        um_df = um_df.rename(columns={
            'Reference': '位号', 'Value': '属性值',
            'PCB Footprint': '封装', 'Part NO': '原料号'
        })
        um_df.insert(0, '序号', range(1, len(um_df)+1))
        
        base_nm = os.path.splitext(os.path.basename(exp_path))[0]
        um_path = os.path.join('04_output', f'{base_nm}_未匹配物料清单.xlsx')
        um_df.to_excel(um_path, index=False)
        print(f'\n  未匹配清单: {um_path} ({len(um_df)} 项)')
        
        # 控制台摘要
        seen = set()
        unique_um = []
        for item in no_match_list:
            k = f"{item['Value']}|{item['PCB Footprint']}"
            if k not in seen:
                seen.add(k)
                unique_um.append(item)
        print(f'  去重后: {len(unique_um)} 种')
        for item in unique_um[:20]:
            print(f'    {item["Reference"]} | {item["Value"]} | {item["PCB Footprint"]} | PN={item["Part NO"]}')
        if len(unique_um) > 20:
            print(f'    ... 还有 {len(unique_um)-20} 种')
    
    return output_path


# ─── 功能 2: BOM + Library → EXP 更新 ───
def bom_update_exp(bom_path, exp_path, output_path=None):
    """用 BOM 文件和元件库的信息更新 EXP"""
    # 读取 BOM
    bom = pd.read_excel(bom_path)
    lib = load_lib()
    print(f'[BOM+Lib→EXP] BOM: {os.path.basename(bom_path)}')
    print(f'  元件库: {os.path.basename(list(glob.glob("02_BOMfromSystem/*.xlsx"))[0])}')
    
    # 建立 BOM 查找：Reference → Part NO / Part Name / 规格
    bom_refs = {}
    ref_col = 'Reference' if 'Reference' in bom.columns else '位号'
    pn_col = 'Part NO.' if 'Part NO.' in bom.columns else '编码'
    name_col = 'Part Name' if 'Part Name' in bom.columns else '名称'
    
    if '规格型号' in bom.columns:
        spec_col = '规格型号'
    elif '*(物料)规格型号' in bom.columns:
        spec_col = '*(物料)规格型号'
    else:
        spec_col = None
    
    for _, row in bom.iterrows():
        refs = str(row[ref_col]).split(',')
        pn = row.get(pn_col, '')
        name = row.get(name_col, '')
        spec = row.get(spec_col, '') if spec_col else ''
        for r in refs:
            r = r.strip()
            if r:
                bom_refs[r] = (pn, name, spec)
    
    # 读取 EXP
    design, header, rows = read_exp(exp_path)
    
    updated_bom = 0
    updated_lib = 0
    no_match = 0
    skipped_tp = 0
    new_rows = []
    
    for line in rows:
        fields = parse_exp_row(line)
        ref = fields[COL_IDX['Part Reference']]
        cur_pn = fields[COL_IDX['Part NO']]
        
        # 跳过 TP 测试点
        if ref.upper().startswith('TP'):
            skipped_tp += 1
            new_rows.append(rebuild_exp_row(fields))
            continue
        
        updated = False
        
        # 优先用 BOM 的数据刷新 EXP
        if ref in bom_refs:
            bom_pn, bom_name, bom_spec = bom_refs[ref]
            if bom_pn and bom_pn not in ('<null>', 'Needless_Part_Number', '0', '', 'nan'):
                fields[COL_IDX['Part NO']] = str(bom_pn)
                if bom_spec:
                    fields[COL_IDX['Part Name']] = str(bom_spec)
                    fields[COL_IDX['DESCRIPTION']] = str(bom_spec)
                    fields[COL_IDX['Description']] = str(bom_spec)
                if bom_name and bom_name not in ('<null>', 'nan', ''):
                    fields[COL_IDX['Part Type']] = str(bom_name)
                updated = True
                updated_bom += 1
        
        # 再用库更新（即使 BOM 已有料号，也去库取最新描述和类型）
        new_pn = fields[COL_IDX['Part NO']]
        if new_pn and new_pn not in ('<null>', 'Needless_Part_Number', '0', ''):
            found = bm.find_component_by_part_no(lib, new_pn)
            if found is not None:
                fields[COL_IDX['Part Name']] = str(found['*(物料)规格型号'])
                fields[COL_IDX['Part Type']] = str(found['*(物料)名称'])
                fields[COL_IDX['DESCRIPTION']] = str(found['*(物料)规格型号'])
                fields[COL_IDX['Description']] = str(found['*(物料)规格型号'])
                updated_lib += 1
                updated = True
        
        if not updated:
            no_match += 1
        
        new_rows.append(rebuild_exp_row(fields))
    
    if output_path is None:
        base, ext = os.path.splitext(os.path.basename(exp_path))
        output_path = os.path.join('04_output', f'{base}_fromBOM{ext}')
    
    write_exp(output_path, design, header, new_rows)
    print(f'  输出: {output_path}')
    print(f'  BOM更新: {updated_bom}, 库描述更新: {updated_lib}, 未匹配: {no_match}, 跳过TP: {skipped_tp}')
    return output_path


# ─── CLI ───
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("""
EXP 文件处理器

用法:
  python exp_processor.py to-bom <exp文件>              # EXP → BOM 提取
  python exp_processor.py lib-update <exp文件>          # 用库更新 EXP 描述
  
  python exp_processor.py bom-update <bom文件> <exp文件> # BOM+库 → 更新 EXP
""")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'to-bom':
        exp_to_bom(sys.argv[2])
    elif cmd == 'lib-update':
        library_update_exp(sys.argv[2])
    elif cmd == 'bom-update':
        if len(sys.argv) < 4:
            print('用法: python exp_processor.py bom-update <bom文件> <exp文件>')
            sys.exit(1)
        bom_update_exp(sys.argv[2], sys.argv[3])
    else:
        print(f'未知命令: {cmd}')
        sys.exit(1)
