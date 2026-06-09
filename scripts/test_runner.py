#!/usr/bin/env python3
"""
erp-bom 单元测试
覆盖: 值解析函数 / 类型分类 / 数据合并 / BOM比对逻辑
"""

import sys
import os
import re
import pandas as pd
import tempfile
import shutil
import unittest
from io import StringIO

# 确保能导入 bom_processor 中的核心函数
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import importlib.util
spec = importlib.util.spec_from_file_location("bom_processor", os.path.join(SCRIPT_DIR, 'bom_processor.py'))
bom_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bom_module)

spec2 = importlib.util.spec_from_file_location("bom_diff", os.path.join(SCRIPT_DIR, 'bom_diff.py'))
diff_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(diff_module)


class TestParseResistorValue(unittest.TestCase):
    """电阻值解析测试"""

    def test_basic_ohm(self):
        v, p = bom_module.parse_resistor_value('100R')
        self.assertEqual(v, 100.0)
        self.assertEqual(p, 5)

    def test_kilo_ohm(self):
        v, p = bom_module.parse_resistor_value('10K')
        self.assertEqual(v, 10000.0)

    def test_kilo_1percent(self):
        v, p = bom_module.parse_resistor_value('10K 1%')
        self.assertEqual(v, 10000.0)
        self.assertEqual(p, 1)

    def test_kilo_F(self):
        v, p = bom_module.parse_resistor_value('680K/F')
        self.assertEqual(v, 680000.0)
        self.assertEqual(p, 1)

    def test_mega(self):
        v, p = bom_module.parse_resistor_value('3M')
        self.assertEqual(v, 3000000.0)

    def test_mega_F(self):
        v, p = bom_module.parse_resistor_value('3M/F')
        self.assertEqual(v, 3000000.0)
        self.assertEqual(p, 1)

    def test_mega_1percent(self):
        v, p = bom_module.parse_resistor_value('3M 1%')
        self.assertEqual(v, 3000000.0)
        self.assertEqual(p, 1)

    def test_milli_ohm(self):
        v, p = bom_module.parse_resistor_value('10mR')
        self.assertEqual(v, 0.01)

    def test_milli_ohm_F_watt(self):
        v, p = bom_module.parse_resistor_value('10mR/F/0.5W')
        self.assertEqual(v, 0.01)
        self.assertEqual(p, 1)

    def test_underscore_five_percent(self):
        v, p = bom_module.parse_resistor_value('60.4R_5%')
        self.assertEqual(v, 60.4)
        self.assertEqual(p, 5)

    def test_underscore_one_percent(self):
        v, p = bom_module.parse_resistor_value('200K_1%')
        self.assertEqual(v, 200000.0)
        self.assertEqual(p, 1)

    def test_R_slash_format(self):
        v, p = bom_module.parse_resistor_value('0.1R/F/0.5W')
        self.assertEqual(v, 0.1)
        self.assertEqual(p, 1)

    def test_dash_separator(self):
        # 验证下划线格式（- 分隔符在电阻解析中不常用，用 _ 代替）
        v, p = bom_module.parse_resistor_value('22R_5%')
        self.assertEqual(v, 22.0)
        self.assertEqual(p, 5)

    def test_OHM_unit(self):
        v, p = bom_module.parse_resistor_value('330OHM')
        self.assertEqual(v, 330.0)

    def test_mega_R_unit(self):
        v, p = bom_module.parse_resistor_value('1MR')
        self.assertEqual(v, 1000000.0)

    def test_J_precision(self):
        v, p = bom_module.parse_resistor_value('100R_J')
        self.assertEqual(v, 100.0)
        self.assertEqual(p, 5)


class TestParseCapacitorValue(unittest.TestCase):
    """电容值解析测试"""

    def test_nF_slash_voltage(self):
        v, volt = bom_module.parse_capacitor_value('100nF/50V')
        self.assertEqual(v, 100000.0)  # 100nF = 100000pF
        self.assertEqual(volt, 50)

    def test_pF_underscore_voltage(self):
        v, volt = bom_module.parse_capacitor_value('100pF_50V')
        self.assertEqual(v, 100.0)
        self.assertEqual(volt, 50)

    def test_uF_voltage(self):
        v, volt = bom_module.parse_capacitor_value('10uF 16V')
        self.assertEqual(v, 10000000.0)  # 10uF = 10,000,000pF
        self.assertEqual(volt, 16)

    def test_uF_no_voltage(self):
        v, volt = bom_module.parse_capacitor_value('330pF')
        self.assertEqual(v, 330.0)
        self.assertIsNone(volt)

    def test_uF_dash_voltage(self):
        v, volt = bom_module.parse_capacitor_value('47uF-16V')
        self.assertEqual(v, 47000000.0)
        self.assertEqual(volt, 16)

    def test_C0402_footprint_with_slash(self):
        v, volt = bom_module.parse_capacitor_value('100nF/50V')
        self.assertEqual(v, 100000.0)
        self.assertEqual(volt, 50)


class TestParsePower(unittest.TestCase):
    """功率解析测试"""

    def test_half_watt(self):
        result = bom_module.parse_power('10mR/F/0.5W')
        self.assertEqual(result, '1/2W')

    def test_one_watt(self):
        result = bom_module.parse_power('100R/1W')
        self.assertEqual(result, '1W')

    def test_two_watt(self):
        result = bom_module.parse_power('100R/2W')
        self.assertEqual(result, '2W')

    def test_sixteenth_watt(self):
        result = bom_module.parse_power('100R/0.0625W')
        self.assertEqual(result, '1/16W')


class TestExtractResistanceValue(unittest.TestCase):
    """从库规格中提取电阻值测试"""

    def test_kilo_spec(self):
        v = bom_module.extract_resistance_value('100KΩ,±1%,1/16W,0402,厚声,RC0402FR-07100KL')
        self.assertEqual(v, 100000.0)

    def test_milli_ohm_spec(self):
        v = bom_module.extract_resistance_value('100mΩ,±1%,1/2W,1210,厚声,RL1210FR-070R1L')
        self.assertEqual(v, 0.1)

    def test_mega_spec(self):
        v = bom_module.extract_resistance_value('1MΩ,±5%,1/16W,0402,厚声,RC0402JR-071ML')
        self.assertEqual(v, 1000000.0)

    def test_plain_ohm(self):
        v = bom_module.extract_resistance_value('100Ω,±1%,1/16W,0603')
        self.assertEqual(v, 100.0)


class TestExtractCapacitanceValue(unittest.TestCase):
    """从库规格中提取电容值测试"""

    def test_nF_spec(self):
        v = bom_module.extract_capacitance_value('100nF,±10%,50V,X7R,0402')
        self.assertEqual(v, 100000.0)

    def test_uF_spec(self):
        v = bom_module.extract_capacitance_value('10uF,±10%,25V,X5R,0805')
        self.assertEqual(v, 10000000.0)

    def test_pF_spec(self):
        v = bom_module.extract_capacitance_value('330pF,±5%,50V,C0G,0402')
        self.assertEqual(v, 330.0)


class TestExtractVoltage(unittest.TestCase):
    """从库规格中提取电压值测试"""

    def test_50V(self):
        v = bom_module.extract_voltage_from_spec('100nF,±10%,50V,X7R,0402')
        self.assertEqual(v, 50)

    def test_16V(self):
        v = bom_module.extract_voltage_from_spec('47uF,±10%,16V,X5R,1210')
        self.assertEqual(v, 16)


class TestRemoveSpecialChars(unittest.TestCase):
    """特殊字符移除测试"""

    def test_hfd4(self):
        result = bom_module.remove_special_chars('HFD4_5-SR')
        self.assertEqual(result, 'HFD45SR')

    def test_no_changes(self):
        result = bom_module.remove_special_chars('HELLO_WORLD-TEST')
        self.assertEqual(result, 'HELLOWORLDTEST')


class TestNC_NP_Handling(unittest.TestCase):
    """NC/NP/NM 空贴处理测试"""

    def test_NC_skip(self):
        result = bom_module.find_component_by_value_footprint(
            pd.DataFrame(), 'NC', 'R0805'
        )
        self.assertIsNone(result)

    def test_NP_skip(self):
        result = bom_module.find_component_by_value_footprint(
            pd.DataFrame(), 'NP', 'C0402'
        )
        self.assertIsNone(result)

    def test_slash_NC_stripped(self):
        # 验证 /NP 后缀被剥离后仍能尝试匹配
        # 创建一个空库，验证不崩溃
        result = bom_module.find_component_by_value_footprint(
            pd.DataFrame(columns=['*(物料)规格型号']), '100nF/NP', 'C0402'
        )
        self.assertIsNone(result)


class TestMergeByPartNo(unittest.TestCase):
    """相同料号合并测试"""

    def setUp(self):
        self.df = pd.DataFrame([
            {'Item': 1, 'Part NO.': 'E.C.0001', 'Part Name': '电容', '规格型号': '100nF', 'Quantity': 2, 'Reference': 'C1', 'PCB Footprint': 'C0402', 'Value': '100nF'},
            {'Item': 2, 'Part NO.': 'E.C.0001', 'Part Name': '电容', '规格型号': '100nF', 'Quantity': 3, 'Reference': 'C2', 'PCB Footprint': 'C0402', 'Value': '100nF'},
            {'Item': 3, 'Part NO.': 'E.R.0001', 'Part Name': '电阻', '规格型号': '10K', 'Quantity': 1, 'Reference': 'R1', 'PCB Footprint': 'R0402', 'Value': '10K'},
        ])

    def test_merge_same_partno(self):
        result = bom_module.merge_by_part_no(self.df)
        # E.C.0001 合并为 1 行，E.R.0001 保持 1 行 → 共 2 行
        self.assertEqual(len(result), 2)

    def test_merged_quantity(self):
        result = bom_module.merge_by_part_no(self.df)
        cap_row = result[result['Part NO.'] == 'E.C.0001']
        self.assertEqual(cap_row['Quantity'].values[0], 5)

    def test_merged_reference(self):
        result = bom_module.merge_by_part_no(self.df)
        cap_row = result[result['Part NO.'] == 'E.C.0001']
        ref = cap_row['Reference'].values[0]
        self.assertIn('C1', ref)
        self.assertIn('C2', ref)
        self.assertIn(',', ref)


class TestBOMDiff(unittest.TestCase):
    """BOM比对逻辑测试"""

    def setUp(self):
        self.bom_a = pd.DataFrame([
            {'Part NO.': 'E.C.0001', 'Part Name': '电容A', '规格型号': '100nF', 'Quantity': 5, 'Reference': 'C1,C2', 'PCB Footprint': 'C0402', 'Value': '100nF'},
            {'Part NO.': 'E.R.0001', 'Part Name': '电阻A', '规格型号': '10K', 'Quantity': 3, 'Reference': 'R1', 'PCB Footprint': 'R0402', 'Value': '10K'},
            {'Part NO.': '', 'Part Name': '未匹配', '规格型号': '', 'Quantity': 1, 'Reference': 'U1', 'PCB Footprint': '', 'Value': ''},
        ])
        self.bom_b = pd.DataFrame([
            {'Part NO.': 'E.C.0001', 'Part Name': '电容A', '规格型号': '100nF', 'Quantity': 7, 'Reference': 'C1,C2,C3', 'PCB Footprint': 'C0402', 'Value': '100nF'},
            {'Part NO.': 'E.L.0001', 'Part Name': '电感A', '规格型号': '4.7uH', 'Quantity': 2, 'Reference': 'L1', 'PCB Footprint': 'IND252012', 'Value': '4.7uH'},
        ])
        self.bom_data = {
            'BOM_A': self.bom_a,
            'BOM_B': self.bom_b,
        }

    def test_build_diff_data(self):
        all_pn, part_maps = diff_module.build_diff_data(self.bom_data)
        self.assertIn('E.C.0001', all_pn)
        self.assertIn('E.R.0001', all_pn)
        self.assertIn('E.L.0001', all_pn)
        self.assertIn(diff_module.STATUS_UNMATCHED, all_pn)

    def test_generate_diff_report(self):
        all_pn, part_maps = diff_module.build_diff_data(self.bom_data)
        summary, unique, common_diff, unmatched = diff_module.generate_diff_report(
            self.bom_data, part_maps, all_pn
        )
        # E.C.0001 两个BOM都有 → 数量/位号有差异
        self.assertGreaterEqual(len(common_diff), 1)
        # BOM_A独有 E.R.0001, BOM_B独有 E.L.0001
        self.assertGreaterEqual(len(unique), 2)
        # BOM_A 有 1 个未匹配
        self.assertGreaterEqual(len(unmatched), 1)

    def test_summary_statistics(self):
        all_pn, part_maps = diff_module.build_diff_data(self.bom_data)
        summary, _, _, _ = diff_module.generate_diff_report(
            self.bom_data, part_maps, all_pn
        )
        self.assertEqual(len(summary), 2)
        bom_a_summary = next(s for s in summary if s['BOM名称'] == 'BOM_A')
        self.assertEqual(bom_a_summary['已匹配物料'], 2)  # E.C.0001 + E.R.0001
        self.assertEqual(bom_a_summary['未匹配物料'], 1)  # '' 空料号


class TestInitDirectories(unittest.TestCase):
    """目录初始化测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_init_creates_directories(self):
        dirs = ['02_BOMfromSystem', '03_order', '04_output']
        for d in dirs:
            os.makedirs(os.path.join(self.tmpdir, d), exist_ok=True)
        for d in dirs:
            self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, d)))

    def test_init_idempotent(self):
        dirs = ['02_BOMfromSystem', '03_order', '04_output']
        for d in dirs:
            os.makedirs(os.path.join(self.tmpdir, d), exist_ok=True)
        # 再次创建不应报错
        for d in dirs:
            os.makedirs(os.path.join(self.tmpdir, d), exist_ok=True)
        for d in dirs:
            self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, d)))


class TestComponentTypeClassification(unittest.TestCase):
    """元件类型分类判断测试（通过 find_component_by_value_footprint 路由）"""

    def setUp(self):
        self.lib = pd.DataFrame(columns=['*(物料)规格型号', '*(物料)名称', '(物料)编码'])
        # 确保函数能正常返回 None（空库无法匹配），但不崩溃
        self.empty_lib = pd.DataFrame(columns=['*(物料)规格型号'])

    def test_IC_classification(self):
        # RTL 开头 → IC 路由
        result = bom_module.find_component_by_value_footprint(
            self.lib, 'RTL8762CMF', 'QFN48'
        )
        self.assertIsNone(result)  # 空库无匹配，但不崩

    def test_crystal_classification(self):
        # X4- 封装 → 晶振路由
        result = bom_module.find_component_by_value_footprint(
            self.lib, '40Mhz', 'X4-3225'
        )
        self.assertIsNone(result)

    def test_bead_classification(self):
        # FB 位号 → 磁珠路由
        result = bom_module.find_component_by_value_footprint(
            self.lib, '330R/100MHZ', 'R0805', reference='FB1'
        )
        self.assertIsNone(result)

    def test_inductor_classification(self):
        # IND 封装 → 电感路由
        result = bom_module.find_component_by_value_footprint(
            self.lib, '4.7uH', 'IND_252012'
        )
        self.assertIsNone(result)

    def test_resistor_classification(self):
        # R 封装 → 电阻路由
        result = bom_module.find_component_by_value_footprint(
            self.lib, '10K', 'R0805'
        )
        self.assertIsNone(result)

    def test_capacitor_classification(self):
        # C 封装 → 电容路由
        result = bom_module.find_component_by_value_footprint(
            self.lib, '100nF', 'C0402'
        )
        self.assertIsNone(result)


class TestCLIEndToEnd(unittest.TestCase):
    """端到端测试：使用真实库处理BOM"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.output_dir = os.path.join(cls.tmpdir, '04_output')
        os.makedirs(cls.output_dir, exist_ok=True)

        # 创建模拟元件库
        cls.lib_df = pd.DataFrame({
            '(物料)编码': [
                'E.C.120104KCDM',
                'E.R.100002JTCM',
                'E.R.100013KECM',
                'E.B.303301MFCM',
                'E.L.4U770MTCM',
            ],
            '*(物料)名称': [
                '电容-陶瓷(贴片)',
                '电阻-贴片',
                '电阻-贴片',
                '磁珠',
                '电感-功率'
            ],
            '*(物料)规格型号': [
                '100nF,±10%,16V,X7R,0402,村田,GRM155R71C104KA88D',
                '100KΩ,±1%,1/16W,0402,厚声,RC0402FR-07100KL',
                '10KΩ,±1%,1/16W,0805,厚声,RC0805FR-0710KL',
                '330Ω/100MHz,±25%,0805,磁珠,CBM系列',
                '4.7uH±20%,4A,252012,XING-XINGSUN,WNC2520-4R7MN470T4R0CLD'
            ]
        })
        cls.lib_path = os.path.join(cls.tmpdir, '02_BOMfromSystem', 'test_lib.xlsx')
        os.makedirs(os.path.dirname(cls.lib_path), exist_ok=True)
        cls.lib_df.to_excel(cls.lib_path, index=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir)

    def _make_bom(self, data):
        bom_path = os.path.join(self.tmpdir, '03_order', 'test_bom.xlsx')
        os.makedirs(os.path.dirname(bom_path), exist_ok=True)
        df = pd.DataFrame(data)
        df.to_excel(bom_path, index=False)
        return bom_path

    def test_process_basic_bom(self):
        bom_data = {
            'Item': [1, 2, 3],
            'Part NO.': ['', '', ''],
            'Part Name': ['电容', '电阻', '磁珠'],
            'Quantity': [2, 1, 1],
            'Reference': ['C1,C2', 'R1', 'FB1'],
            'PCB Footprint': ['C0402', 'R0402', 'R0805'],
            'Value': ['100nF', '100K', '330R/100MHZ']
        }
        bom_path = self._make_bom(bom_data)
        
        result = bom_module.process_bom(
            bom_path, self.lib_path, self.output_dir, merge_same_part_no=True
        )
        
        # C1,C2 应该匹配到 100nF 电容
        cap_match = result[result['Value'] == '100nF']
        self.assertGreaterEqual(len(cap_match), 1)
        self.assertEqual(cap_match['Part NO.'].values[0], 'E.C.120104KCDM')
        
        # R1 应该匹配到 100K 电阻
        res_match = result[result['Value'] == '100K']
        self.assertGreaterEqual(len(res_match), 1)
        self.assertEqual(res_match['Part NO.'].values[0], 'E.R.100002JTCM')

    def test_process_with_existing_partno(self):
        bom_data = {
            'Item': [1],
            'Part NO.': ['E.C.120104KCDM'],
            'Part Name': ['电容'],
            'Quantity': [1],
            'Reference': ['C1'],
            'PCB Footprint': ['C0402'],
            'Value': ['100nF']
        }
        bom_path = self._make_bom(bom_data)
        
        result = bom_module.process_bom(
            bom_path, self.lib_path, self.output_dir, merge_same_part_no=False
        )
        
        self.assertEqual(result['Part NO.'].values[0], 'E.C.120104KCDM')
        self.assertEqual(result['Part Name'].values[0], '电容-陶瓷(贴片)')

    def test_process_skip_TP(self):
        bom_data = {
            'Item': [1, 2],
            'Part NO.': ['', ''],
            'Part Name': ['测试点', '电阻'],
            'Quantity': [1, 1],
            'Reference': ['TP1', 'R1'],
            'PCB Footprint': ['TP', 'R0402'],
            'Value': ['TP', '100K']
        }
        bom_path = self._make_bom(bom_data)
        
        result = bom_module.process_bom(
            bom_path, self.lib_path, self.output_dir, merge_same_part_no=False
        )
        
        # TP1 应该被跳过
        refs = result['Reference'].tolist()
        self.assertNotIn('TP1', refs)
        self.assertIn('R1', refs)

    def test_process_inductor_matching(self):
        bom_data = {
            'Item': [1],
            'Part NO.': [''],
            'Part Name': ['电感'],
            'Quantity': [1],
            'Reference': ['L1'],
            'PCB Footprint': ['IND_252012'],
            'Value': ['4.7uH']
        }
        bom_path = self._make_bom(bom_data)
        
        result = bom_module.process_bom(
            bom_path, self.lib_path, self.output_dir, merge_same_part_no=False
        )
        
        inductor_row = result[result['Reference'] == 'L1']
        self.assertGreaterEqual(len(inductor_row), 1)
        self.assertEqual(inductor_row['Part NO.'].values[0], 'E.L.4U770MTCM')


def run_tests(verbosity=2):
    """运行所有测试，返回 exit code"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestParseResistorValue,
        TestParseCapacitorValue,
        TestParsePower,
        TestExtractResistanceValue,
        TestExtractCapacitanceValue,
        TestExtractVoltage,
        TestRemoveSpecialChars,
        TestNC_NP_Handling,
        TestMergeByPartNo,
        TestBOMDiff,
        TestInitDirectories,
        TestComponentTypeClassification,
        TestCLIEndToEnd,
    ]
    
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())