import pandas as pd
import os
import re

def load_bom_data(bom_file_path):
    return pd.read_excel(bom_file_path)

def load_component_library(lib_file_path):
    return pd.read_excel(lib_file_path)

def parse_resistor_value(value_str):
    original_value = str(value_str).strip()
    
    precision = 5
    if '1%' in original_value or 'F' in original_value:
        precision = 1
    elif '5%' in original_value or 'J' in original_value:
        precision = 5
    
    value_str_clean = re.sub(r'[15]%|[FJ]|/\d+W?|/\d+MHZ|\s*MHZ', '', original_value).strip()
    
    match = re.match(r'^([\d.]+)\s*MR$', value_str_clean)
    if match:
        return float(match.group(1)) * 1000000, precision
    
    match = re.match(r'^([\d.]+)\s*mR$', value_str_clean, re.IGNORECASE)
    if match:
        return float(match.group(1)) / 1000, precision
    
    match = re.match(r'^([\d.]+)\s*m', value_str_clean)
    if match:
        return float(match.group(1)) / 1000, precision
    
    match = re.match(r'^([\d.]+)\s*M', value_str_clean)
    if match:
        return float(match.group(1)) * 1000000, precision
    
    match = re.match(r'^([\d.]+)\s*K', value_str_clean)
    if match:
        return float(match.group(1)) * 1000, precision
    
    match = re.match(r'^([\d.]+)\s*R(?:/|$|\s|_)', value_str_clean)
    if match:
        return float(match.group(1)), precision
    
    match = re.match(r'^([\d.]+)\s*OHM', value_str_clean)
    if match:
        return float(match.group(1)), precision
    
    match = re.match(r'^([\d.]+)\s*Ω?$', value_str_clean)
    if match:
        return float(match.group(1)), precision
    
    return None, precision

def parse_power(value_str):
    power_match = re.search(r'/(\d+\.?\d*)W', str(value_str).upper())
    if power_match:
        power_val = float(power_match.group(1))
        power_fractions = {
            0.0625: '1/16W',
            0.125: '1/8W',
            0.25: '1/4W',
            0.5: '1/2W',
            1.0: '1W',
            2.0: '2W'
        }
        return power_fractions.get(power_val, f'{power_val}W')
    return None

def parse_capacitor_value(value_str):
    value_str = str(value_str).strip().upper()
    
    match = re.match(r'^([\d.]+)\s*([PFNU]F?)\s*(?:[/_-]?(\d+V))?$', value_str)
    if match:
        num = float(match.group(1))
        unit = match.group(2)
        voltage = match.group(3)
        
        if unit == 'PF' or unit == 'P':
            value_pf = num
        elif unit == 'NF' or unit == 'N':
            value_pf = num * 1000
        elif unit == 'UF' or unit == 'U' or unit == 'μF' or unit == 'ΜF':
            value_pf = num * 1000000
        else:
            value_pf = num
        
        voltage_val = int(voltage[:-1]) if voltage else None
        return value_pf, voltage_val
    
    return None, None

def extract_resistance_value(spec):
    spec_str = str(spec)
    spec_upper = spec_str.upper()
    
    k_match = re.search(r'(?:^|，|,)([\d.]+)\s*KΩ', spec_upper)
    if k_match:
        return float(k_match.group(1)) * 1000
    
    m_match_upper = re.search(r'(?:^|，|,)([\d.]+)\s*MΩ', spec_upper)
    if m_match_upper:
        m_match_lower = re.search(r'(?:^|，|,)([\d.]+)\s*mΩ', spec_str)
        if not m_match_lower:
            return float(m_match_upper.group(1)) * 1000000
    
    ohm_matches = re.findall(r'(?:^|，|,)([\d.]+)\s*Ω', spec_upper)
    if ohm_matches:
        return float(ohm_matches[0])
    
    m_ohm_match = re.search(r'(?:^|，|,)([\d.]+)\s*mΩ', spec_str)
    if m_ohm_match:
        return float(m_ohm_match.group(1)) / 1000
    
    return None

def extract_capacitance_value(spec):
    spec_upper = spec.upper()
    
    match = re.search(r'(?:^|，|,)([\d.]+)\s*([PFNU]F?)', spec_upper)
    if match:
        num = float(match.group(1))
        unit = match.group(2)
        
        if unit == 'PF' or unit == 'P':
            return num
        elif unit == 'NF' or unit == 'N':
            return num * 1000
        elif unit == 'UF' or unit == 'U':
            return num * 1000000
    return None

def extract_voltage_from_spec(spec):
    spec_upper = spec.upper()
    match = re.search(r'(?:^|，|,)(\d+)V(?:,|$|\s)', spec_upper)
    if match:
        return int(match.group(1))
    return None

def validate_resistor_match(found_component, value_str):
    if found_component is None:
        return False
    
    target_value, _ = parse_resistor_value(value_str)
    if target_value is None:
        return True
    
    spec = str(found_component['*(物料)规格型号'])
    lib_value = extract_resistance_value(spec)
    
    if lib_value is None:
        return True
    
    return abs(lib_value - target_value) < 1e-10

def find_component_by_part_no(lib, part_no):
    results = lib[lib['(物料)编码'] == part_no]
    if not results.empty:
        return results.iloc[0]
    return None

def find_component_by_value_footprint(lib, value, footprint, reference=None):
    if pd.isna(value) or pd.isna(footprint):
        return None
    
    value_str = str(value).strip()
    footprint_str = str(footprint).strip().upper()
    ref_str = str(reference).strip().upper() if pd.notna(reference) else ''
    
    if 'NC' in value_str.upper():
        return None
    
    lib_filtered = lib[lib['*(物料)规格型号'].notna()]
    
    if value_str.upper().startswith('RTL') or value_str.upper().startswith('STM') or value_str.upper().startswith('ATMEGA') or value_str.upper().startswith('ESP') or value_str.upper().startswith('GD32') or value_str.upper().startswith('NXP') or value_str.upper().startswith('TI') or value_str.upper().startswith('MICROCHIP') or value_str.upper().startswith('CA-'):
        return find_ic(lib_filtered, value_str, footprint_str)
    elif footprint_str.startswith('X4-') or '_X4_' in footprint_str or footprint_str.endswith('_X4') or 'XTAL' in footprint_str or 'OSC' in footprint_str:
        return find_crystal(lib_filtered, value_str, footprint_str)
    elif ref_str.startswith('FB') or 'FB' in footprint_str.upper():
        return find_bead(lib_filtered, value_str, footprint_str)
    elif footprint_str.startswith('R') or 'RES' in footprint_str or 'OHM' in value_str.upper() or ('K' in value_str and 'F' in value_str) or 'R/' in value_str or (re.match(r'^\d{4}R$', footprint_str) is not None) or ('M/' in value_str and 'F' in value_str) or (footprint_str.endswith('R') and footprint_str[:-1].isdigit()):
        return find_resistor(lib_filtered, value_str, footprint_str)
    elif footprint_str.startswith('C') or 'CAP' in footprint_str or ('F' in value_str.upper() and not ('K' in value_str and 'F' in value_str) and not 'R/' in value_str and not 'M/' in value_str and not value_str.upper().startswith('RTL') and not value_str.upper().startswith('STM') and not ref_str.startswith('FB') and not (('_' in value_str or '-' in value_str) and not re.search(r'\d+[Vv]$', value_str))):
        return find_capacitor(lib_filtered, value_str, footprint_str)
    elif 'MHZ' in value_str.upper():
        return find_bead(lib_filtered, value_str, footprint_str)
    else:
        return find_generic(lib_filtered, value_str, footprint_str)

def find_ic(lib, value_str, footprint_str):
    value_upper = value_str.upper()
    candidates = []
    for _, row in lib.iterrows():
        spec = str(row['*(物料)规格型号']).upper()
        name = str(row['*(物料)名称']).upper()
        
        if value_upper in spec or value_upper in name or spec in value_upper or name in value_upper:
            candidates.append(row)
    
    if candidates:
        for row in candidates:
            spec = str(row['*(物料)规格型号'])
            if value_str in spec:
                return row
        return candidates[0]
    return None

def find_resistor(lib, value_str, footprint_str):
    target_value, target_precision = parse_resistor_value(value_str)
    if target_value is None:
        return None
    
    target_package = None
    pkg_match = re.search(r'R(\d{4})', footprint_str)
    if not pkg_match:
        pkg_match = re.search(r'(\d{4})R', footprint_str)
    if pkg_match:
        target_package = pkg_match.group(1)
    
    candidates = []
    for _, row in lib.iterrows():
        spec = str(row['*(物料)规格型号'])
        name = str(row['*(物料)名称']).upper()
        
        if 'RES' not in name and '电阻' not in str(row['*(物料)名称']):
            continue
        
        lib_value = extract_resistance_value(spec)
        if lib_value is None:
            continue
        
        lib_precision = 1 if '±1%' in spec else 5
        
        has_correct_package = False
        if target_package and target_package in spec:
            has_correct_package = True
        
        if abs(lib_value - target_value) < 1e-10:
            candidates.append((has_correct_package, lib_precision, row))
    
    if candidates:
        if target_package:
            package_matched = [c for c in candidates if c[0]]
            if package_matched:
                package_matched.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
                return package_matched[0][2]
            else:
                return None
        else:
            candidates.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
            return candidates[0][2]
    return None

def find_capacitor(lib, value_str, footprint_str):
    target_value_pf, target_voltage = parse_capacitor_value(value_str)
    if target_value_pf is None:
        return None
    
    target_package = None
    pkg_match = re.search(r'C?(\d{4})C?', footprint_str)
    if pkg_match:
        target_package = pkg_match.group(1)
    
    candidates = []
    for _, row in lib.iterrows():
        spec = str(row['*(物料)规格型号']).upper()
        name = str(row['*(物料)名称']).upper()
        
        if not ('CAP' in name or '电容' in str(row['*(物料)名称']) or 'X7R' in spec or 'X5R' in spec or 'C0G' in spec or 'NP0' in spec):
            continue
        
        lib_value = extract_capacitance_value(spec)
        if lib_value is None:
            continue
        
        lib_voltage = extract_voltage_from_spec(spec)
        
        has_correct_package = False
        if target_package and target_package in spec:
            has_correct_package = True
        
        if abs(lib_value - target_value_pf) < 1e-10:
            if target_voltage is None or (lib_voltage is not None and lib_voltage >= target_voltage):
                candidates.append((has_correct_package, lib_voltage, row))
    
    if candidates:
        if target_package:
            package_matched = [c for c in candidates if c[0]]
            if package_matched:
                package_matched.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
                return package_matched[0][2]
            else:
                return None
        else:
            candidates.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
            return candidates[0][2]
    return None

def find_bead(lib, value_str, footprint_str):
    target_value, _ = parse_resistor_value(value_str)
    
    target_package = None
    pkg_match = re.search(r'(\d{4})', footprint_str)
    if pkg_match:
        target_package = pkg_match.group(1)
    
    candidates = []
    for _, row in lib.iterrows():
        spec = str(row['*(物料)规格型号'])
        name = str(row['*(物料)名称']).upper()
        
        if '磁珠' not in str(row['*(物料)名称']) and 'BEAD' not in name and 'FERRITE' not in name:
            continue
        
        lib_value = extract_resistance_value(spec)
        if lib_value is None:
            continue
        
        has_correct_package = False
        if target_package and target_package in spec:
            has_correct_package = True
        
        if target_value is not None and abs(lib_value - target_value) < 1e-10:
            candidates.append((has_correct_package, row))
    
    if candidates:
        if target_package:
            package_matched = [c for c in candidates if c[0]]
            if package_matched:
                return package_matched[0][1]
            else:
                return None
        else:
            return candidates[0][1]
    return None

def remove_special_chars(s):
    return re.sub(r'[_-]', '', s)

def find_generic(lib, value_str, footprint_str):
    value_upper = value_str.upper()
    footprint_upper = footprint_str.upper() if footprint_str else ''
    
    value_clean = remove_special_chars(value_upper)
    
    footprint_key = None
    if 'XT30PW' in footprint_upper or 'PWPW' in footprint_upper:
        footprint_key = 'XT30PW'
    elif 'XT30PB' in footprint_upper or 'PBPB' in footprint_upper:
        footprint_key = 'XT30PB'
    elif 'XT30' in footprint_upper:
        footprint_key = 'XT30'
    elif 'XT60' in footprint_upper:
        footprint_key = 'XT60'
    
    candidates = []
    for _, row in lib.iterrows():
        spec = str(row['*(物料)规格型号']).upper()
        name = str(row['*(物料)名称']).upper()
        spec_clean = remove_special_chars(spec)
        
        score = 0
        if value_upper in spec or value_clean in spec_clean:
            score += 2
        if value_upper in name:
            score += 1
        if footprint_upper in spec or footprint_upper in name:
            score += 1
        
        if footprint_key and footprint_key in spec:
            score += 3
        
        if score > 0:
            candidates.append((score, row))
    
    if candidates:
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]
    return None

def find_crystal(lib, value_str, footprint_str, return_all=False):
    value_upper = value_str.upper()
    candidates = []
    
    pkg_match = re.search(r'(\d{4})', footprint_str)
    target_package = pkg_match.group(1) if pkg_match else None
    
    target_freq = None
    freq_match = re.search(r'(\d+)\s*MHZ', value_upper)
    if freq_match:
        target_freq = freq_match.group(1)
    
    for _, row in lib.iterrows():
        spec = str(row['*(物料)规格型号']).upper()
        name = str(row['*(物料)名称']).upper()
        
        if '晶振' not in str(row['*(物料)名称']) and 'XTAL' not in name and 'OSC' not in name and 'CRYSTAL' not in name:
            continue
        
        has_correct_package = False
        if target_package and target_package in spec:
            has_correct_package = True
        
        if target_freq:
            spec_freq_match = re.search(r'(\d+)\s*MHZ', spec)
            if spec_freq_match and spec_freq_match.group(1) == target_freq:
                package_score = 2 if has_correct_package else 0
                candidates.append((package_score, row))
        elif value_upper in spec:
            package_score = 2 if has_correct_package else 0
            candidates.append((package_score, row))
    
    if candidates:
        candidates.sort(key=lambda x: -x[0])
        if return_all:
            return [c[1] for c in candidates]
        return candidates[0][1]
    return None if not return_all else []

def merge_by_part_no(df):
    merged = {}
    
    for _, row in df.iterrows():
        part_no = row['Part NO.']
        if pd.isna(part_no) or part_no == '':
            key = f"UNKNOWN_{row.name}"
        else:
            key = part_no
        
        if key not in merged:
            merged[key] = {
                'Item': row['Item'],
                'Part NO.': part_no,
                'Part Name': row['Part Name'],
                '规格型号': row['规格型号'],
                'Quantity': 0,
                'Reference': [],
                'PCB Footprint': row['PCB Footprint'],
                'Value': row['Value']
            }
        
        merged[key]['Quantity'] += row['Quantity']
        merged[key]['Reference'].append(str(row['Reference']))
    
    result = []
    for key, data in merged.items():
        result.append({
            'Item': data['Item'],
            'Part NO.': data['Part NO.'],
            'Part Name': data['Part Name'],
            '规格型号': data['规格型号'],
            'Quantity': data['Quantity'],
            'Reference': ','.join(data['Reference']),
            'PCB Footprint': data['PCB Footprint'],
            'Value': data['Value']
        })
    
    return pd.DataFrame(result)

def process_bom(bom_file, lib_file, output_dir, merge_same_part_no=True):
    bom = load_bom_data(bom_file)
    lib = load_component_library(lib_file)
    
    columns = bom.columns.tolist()
    
    if 'Item' in columns and 'Part NO.' in columns and 'Part Name' in columns:
        item_col = 'Item'
        part_no_col = 'Part NO.'
        part_name_col = 'Part Name'
        quantity_col = 'Quantity'
        reference_col = 'Reference'
        footprint_col = 'PCB Footprint'
        value_col = 'Value'
    elif '序号' in columns and '编码' in columns and '名称' in columns:
        item_col = '序号'
        part_no_col = '编码'
        part_name_col = '名称'
        quantity_col = '数量'
        reference_col = '位号'
        footprint_col = '封装'
        value_col = '规格'
    else:
        raise ValueError("不支持的BOM列格式")
    
    processed_data = []
    
    for _, row in bom.iterrows():
        item = row[item_col]
        part_no = row[part_no_col]
        part_name = row[part_name_col]
        quantity = row[quantity_col]
        reference = row[reference_col]
        footprint = row[footprint_col]
        value = row[value_col]
        
        if pd.notna(reference) and str(reference).strip().upper().startswith('TP'):
            continue
        
        if pd.notna(value) and 'NC' in str(value).upper():
            continue
        
        found_components = []
        part_no_is_valid = pd.notna(part_no) and str(part_no).strip() != '' and str(part_no).strip() != '/'
        
        if part_no_is_valid:
            found_component = find_component_by_part_no(lib, part_no)
            
            if found_component is not None and pd.notna(value):
                value_str = str(value).strip()
                if (footprint and str(footprint).strip().upper().startswith('R')) or 'OHM' in value_str.upper() or ('K' in value_str and 'F' in value_str) or 'R/' in value_str:
                    if not validate_resistor_match(found_component, value_str):
                        found_component = None
            
            if found_component is not None:
                found_components = [found_component]
        
        if not found_components:
            found_component = find_component_by_value_footprint(lib, value, footprint, reference)
            if found_component is not None:
                found_components = [found_component]
        
        if not found_components:
            new_part_no = part_no if part_no_is_valid else ''
            part_name_valid = pd.notna(part_name) and str(part_name).strip() != '/' and str(part_name).strip() != ''
            is_component_model = str(part_name).strip().startswith('GRM') or str(part_name).strip().startswith('E.') if pd.notna(part_name) else False
            
            if part_no_is_valid and not part_name_valid:
                new_part_name = '未找到匹配'
            elif part_name_valid and not is_component_model:
                new_part_name = part_name
            else:
                new_part_name = '未找到匹配'
            
            processed_data.append({
                'Item': item,
                'Part NO.': new_part_no,
                'Part Name': new_part_name,
                '规格型号': '',
                'Quantity': quantity,
                'Reference': reference,
                'PCB Footprint': footprint,
                'Value': value
            })
        else:
            for found_component in found_components:
                processed_data.append({
                    'Item': item,
                    'Part NO.': found_component['(物料)编码'],
                    'Part Name': found_component['*(物料)名称'],
                    '规格型号': found_component['*(物料)规格型号'],
                    'Quantity': quantity,
                    'Reference': reference,
                    'PCB Footprint': footprint,
                    'Value': value
                })
    
    result_df = pd.DataFrame(processed_data)
    
    if merge_same_part_no:
        result_df = merge_by_part_no(result_df)
    
    base_name = os.path.basename(bom_file).replace('.xlsx', '_processed.xlsx')
    output_path = os.path.join(output_dir, base_name)
    result_df.to_excel(output_path, index=False)
    
    print(f"处理完成！输出文件: {output_path}")
    print(f"处理记录数: {len(result_df)}")
    
    return result_df

if __name__ == '__main__':
    import glob
    import sys
    import os
    
    # 默认配置
    BOM_FILES = glob.glob(os.path.join('03_order', '*.xlsx'))
    LIB_FILE = sorted(glob.glob(os.path.join('02_BOMfromSystem', '*.xlsx')), reverse=True)
    OUTPUT_DIR = '04_output'
    
    # CLI参数支持
    if len(sys.argv) > 1:
        BOM_FILES = sys.argv[1:]
    
    if not LIB_FILE:
        print("错误: 未找到元件库文件，请将元件库放入 02_BOMfromSystem/ 目录")
        sys.exit(1)
    LIB_FILE = LIB_FILE[0]
    
    print(f"=== 批量处理BOM文件 ===")
    print(f"元件库: {LIB_FILE}")
    for bom_file in BOM_FILES:
        print(f"\n处理: {bom_file}")
        try:
            process_bom(bom_file, LIB_FILE, OUTPUT_DIR)
        except Exception as e:
            print(f"处理失败: {e}")
    print("\n=== 处理完成 ===")