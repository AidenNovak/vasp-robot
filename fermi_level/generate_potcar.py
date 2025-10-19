#!/usr/bin/env python3
"""
POTCAR生成器 - 解决POTCAR缺失问题
根据子代理专家建议，创建健壮的POTCAR生成逻辑
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

class POTCARGenerator:
    """VASP POTCAR文件生成器，包含完整的错误处理和验证"""

    def __init__(self):
        self.elements: Dict[str, str] = {}
        self.potcar_paths: List[str] = [
            "/public/apps/vasp/6.3.2/potentials/pbe",
            "/public/apps/vasp/6.3.2/potentials",
            "/opt/vasp/potentials/pbe",
            "/opt/vasp/potentials"
        ]

    def find_potcar_directory(self) -> Optional[str]:
        """自动查找VASP赝势目录"""
        for path in self.potcar_paths:
            if os.path.exists(path):
                print(f"✓ 找到VASP赝势目录: {path}")
                return path
        return None

    def discover_potentials(self, potcar_dir: str) -> Dict[str, str]:
        """发现可用的POTCAR文件"""
        potentials = {}
        for element in ["Si", "C", "H"]:
            element_files = []
            for root, dirs, files in os.walk(potcar_dir):
                for file in files:
                    if element in file.upper() and "POTCAR" in file.upper():
                        element_files.append(os.path.join(root, file))

            if element_files:
                # 选择最合适的POTCAR文件
                potentials[element] = self.select_best_potcar(element_files, element)
                print(f"✓ {element} POTCAR: {potentials[element]}")
            else:
                print(f"✗ 未找到{element}的POTCAR文件")

        return potentials

    def select_best_potcar(self, files: List[str], element: str) -> str:
        """选择最佳的POTCAR文件"""
        # 优先级：PBE > PAW > 最新版本 > 推荐版本
        priority_keywords = ["PBE", "PAW", "PV", "SV"]

        scored_files = []
        for file in files:
            score = 0
            filename = os.path.basename(file).upper()

            for i, keyword in enumerate(priority_keywords):
                if keyword in filename:
                    score += (len(priority_keywords) - i) * 10

            # 优先选择较新的文件
            try:
                mtime = os.path.getmtime(file)
                score += mtime / 1e10  # 将时间戳转换为小数分数
            except:
                pass

            scored_files.append((score, file))

        # 返回得分最高的文件
        scored_files.sort(reverse=True)
        return scored_files[0][1]

    def generate_potcar(self, elements: List[str], output_file: str = "POTCAR") -> bool:
        """生成POTCAR文件"""
        print(f"🔧 开始生成POTCAR文件，包含元素: {', '.join(elements)}")

        # 1. 查找赝势目录
        potcar_dir = self.find_potcar_directory()
        if not potcar_dir:
            print("❌ 未找到VASP赝势目录")
            return False

        # 2. 发现可用的POTCAR文件
        potentials = self.discover_potentials(potcar_dir)

        # 3. 验证所有元素都有对应的POTCAR
        missing_elements = [elem for elem in elements if elem not in potentials]
        if missing_elements:
            print(f"❌ 缺少元素的POTCAR: {', '.join(missing_elements)}")
            return False

        # 4. 生成POTCAR文件
        try:
            with open(output_file, 'w') as outfile:
                for element in elements:
                    potcar_file = potentials[element]
                    print(f"  📝 添加 {element} POTCAR: {potcar_file}")

                    with open(potcar_file, 'r') as infile:
                        content = infile.read()

                    # 验证POTCAR文件格式
                    if not self.validate_potcar_content(content, element):
                        print(f"❌ {element} POTCAR文件格式无效")
                        return False

                    outfile.write(content)
                    outfile.write("\n")  # 添加分隔符

            print(f"✅ POTCAR文件生成成功: {output_file}")

            # 5. 验证生成的POTCAR文件
            if self.validate_generated_potcar(output_file, elements):
                print("✅ POTCAR文件验证通过")
                return True
            else:
                print("❌ POTCAR文件验证失败")
                return False

        except Exception as e:
            print(f"❌ 生成POTCAR文件时出错: {str(e)}")
            return False

    def validate_potcar_content(self, content: str, element: str) -> bool:
        """验证POTCAR文件内容的正确性"""
        # 检查关键标识符
        required_keywords = [
            "PAW_PBE",
            element.upper(),
            "TITEL",
            "End of Dataset"
        ]

        content_upper = content.upper()
        for keyword in required_keywords:
            if keyword not in content_upper:
                print(f"❌ POTCAR文件缺少关键字: {keyword}")
                return False

        return True

    def validate_generated_potcar(self, filename: str, elements: List[str]) -> bool:
        """验证生成的POTCAR文件"""
        try:
            with open(filename, 'r') as f:
                content = f.read()

            # 检查文件大小
            if len(content) < 1000:  # POTCAR文件应该很大
                print("❌ POTCAR文件太小，可能生成不完整")
                return False

            # 检查元素数量
            element_count = content.count("PAW_PBE")
            if element_count != len(elements):
                print(f"❌ POTCAR元素数量不匹配，期望{len(elements)}，实际{element_count}")
                return False

            # 检查每个元素是否存在
            for element in elements:
                if element.upper() not in content.upper():
                    print(f"❌ POTCAR中未找到元素: {element}")
                    return False

            return True

        except Exception as e:
            print(f"❌ 验证POTCAR文件时出错: {str(e)}")
            return False

def main():
    """主函数 - 支持命令行调用"""
    import argparse

    parser = argparse.ArgumentParser(description="生成VASP POTCAR文件")
    parser.add_argument("--elements", nargs="+", default=["Si", "C"],
                       help="元素列表，默认: Si C")
    parser.add_argument("--output", default="POTCAR",
                       help="输出文件名，默认: POTCAR")

    args = parser.parse_args()

    generator = POTCARGenerator()
    success = generator.generate_potcar(args.elements, args.output)

    if success:
        print("🎉 POTCAR生成完成！")
        sys.exit(0)
    else:
        print("💥 POTCAR生成失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()