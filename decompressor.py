#encoding=utf-8
#!/usr/bin/env python3
"""
分卷压缩解压脚本 - 支持MD5校验和进度显示
"""

import os
import sys
import subprocess
import hashlib
import argparse
from pathlib import Path
import shutil

class SimpleVolumeDecompressor:
    def __init__(self):
        self.source_md5_map = {}
        self.target_md5_map = {}
    
    def log_info(self, message):
        """信息级别日志"""
        print(f"[INFO] {message}")
    
    def log_error(self, message):
        """错误级别日志"""
        print(f"[ERROR] {message}", file=sys.stderr)
    
    def log_debug(self, message):
        """调试级别日志"""
        print(f"[DEBUG] {message}")
    
    def parse_arguments(self):
        """解析命令行参数"""
        parser = argparse.ArgumentParser(description='分卷压缩解压工具')
        parser.add_argument('source', help='压缩文件目录路径')
        parser.add_argument('-o', '--output', required=True, help='解压输出目录路径')
        parser.add_argument('--7z-path', default='7z', dest='seven_zip_path', help='7z可执行文件路径')
        parser.add_argument('-m','--verify-md5', action='store_true', help='使用MD5校验文件进行解压校验')
        parser.add_argument('-f','--md5-file', default=None, help='MD5校验文件路径')
        return parser.parse_args()
    
    def validate_7z(self, seven_zip_path):
        """验证7z是否可用"""
        try:
            subprocess.run([seven_zip_path], capture_output=True, timeout=5)
            return True
        except:
            self.log_error(f"无法执行7z: {seven_zip_path}")
            return False
    
    def find_md5_file(self, source_dir):
        """在源目录中查找MD5校验文件"""
        md5_files = list(Path(source_dir).glob("**/compression_checksums.md5"))
        if md5_files:
            return md5_files[0]
        
        root_md5 = Path(source_dir) / "compression_checksums.md5"
        if root_md5.exists():
            return root_md5
        
        return None
    
    def parse_md5_file(self, md5_file_path):
        """解析MD5校验文件"""
        try:
            with open(md5_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.source_md5_map = {}
            self.target_md5_map = {}
            current_section = None
            
            for line in content.split('\n'):
                line = line.strip()
                
                if not line or line.startswith('#'):
                    if "源文件MD5校验值" in line:
                        current_section = "SOURCE"
                    elif "目标文件MD5校验值" in line:
                        current_section = "TARGET"
                    continue
                
                if current_section and '*' in line:
                    parts = line.split(' *', 1)
                    if len(parts) == 2:
                        md5_hash, filename = parts
                        if current_section == "SOURCE":
                            self.source_md5_map[filename] = md5_hash
                        elif current_section == "TARGET":
                            self.target_md5_map[filename] = md5_hash
            
            self.log_info(f"已解析MD5文件: {len(self.source_md5_map)} 个源文件, {len(self.target_md5_map)} 个目标文件")
            return True
            
        except Exception as e:
            self.log_error(f"解析MD5文件失败: {e}")
            return False
    
    def calculate_file_md5(self, file_path):
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.log_error(f"计算MD5失败 {file_path}: {e}")
            return None
    
    def verify_file_md5(self, file_path, expected_md5, relative_path):
        """验证文件的MD5"""
        actual_md5 = self.calculate_file_md5(file_path)
        if actual_md5 is None:
            self.log_error(f"无法计算文件MD5: {relative_path}")
            return False
        
        if actual_md5 == expected_md5:
            self.log_debug(f"MD5验证通过: {relative_path}")
            return True
        else:
            self.log_error(f"MD5验证失败: {relative_path}")
            self.log_error(f"  期望: {expected_md5}")
            self.log_error(f"  实际: {actual_md5}")
            return False
    
    def is_volume_file(self, file_path):
        """检查是否是分卷压缩文件"""
        # 分卷文件的后缀应该是3位数字，如 .001, .002 等
        if len(file_path.suffix) == 4 and file_path.suffix[1:].isdigit():
            return True
        return False
    
    def is_zip_file(self, file_path):
        """检查是否是ZIP文件"""
        return file_path.suffix.lower() == '.zip'
    
    def find_volume_files(self, base_path):
        """查找分卷压缩的所有卷文件"""
        base_path = Path(base_path)
        parent_dir = base_path.parent
        
        volume_files = []
        pattern = f"{base_path.name}.*"
        
        for file_path in parent_dir.glob(pattern):
            # 使用新的判断方法
            if self.is_volume_file(file_path):
                try:
                    volume_num = int(file_path.suffix[1:])
                    volume_files.append((volume_num, file_path))
                except ValueError:
                    continue
        
        volume_files.sort()
        return [file_path for _, file_path in volume_files]
    
    def get_original_filename(self, archive_path):
        """获取压缩文件对应的原始文件名"""
        # 从压缩文件名推断原始文件名
        # 例如: "file.zip" -> "file", "file.zip.001" -> "file"
        if self.is_volume_file(archive_path):
            # 分卷文件，去掉.001等后缀
            return archive_path.stem
        elif self.is_zip_file(archive_path):
            # ZIP文件，去掉.zip后缀
            return archive_path.stem
        else:
            return archive_path.name
    
    def extract_archive(self, archive_path, output_path, seven_zip_path):
        """解压单个压缩包到指定目录"""
        try:
            # 检查是否是分卷压缩
            if self.is_volume_file(archive_path):
                volume_files = self.find_volume_files(archive_path.parent / archive_path.stem)
                if volume_files:
                    # 使用第一个分卷进行解压
                    first_volume = volume_files[0]
                    self.log_info(f"解压分卷压缩: {first_volume.name} (共{len(volume_files)}个分卷)")
                    
                    # 创建输出目录
                    output_path.mkdir(parents=True, exist_ok=True)
                    
                    # 使用7z解压第一个分卷
                    cmd = [seven_zip_path, 'x', '-y', '-o' + str(output_path), str(first_volume)]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    
                    self.log_info(f"解压完成: {first_volume.name}")
                    return True
                else:
                    self.log_error(f"未找到分卷文件: {archive_path}")
                    return False
            else:
                # 普通ZIP文件
                self.log_info(f"解压: {archive_path.name}")
                
                # 创建输出目录
                output_path.mkdir(parents=True, exist_ok=True)
                
                # 使用7z解压
                cmd = [seven_zip_path, 'x', '-y', '-o' + str(output_path), str(archive_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                self.log_info(f"解压完成: {archive_path.name}")
                return True
            
        except subprocess.CalledProcessError as e:
            self.log_error(f"解压失败 {archive_path}: {e}")
            if e.stderr:
                self.log_error(f"7z错误输出: {e.stderr}")
            return False
        except Exception as e:
            self.log_error(f"解压异常 {archive_path}: {e}")
            return False
    
    def count_items(self, source_dir):
        """统计需要处理的文件总数"""
        count = 0
        source_path = Path(source_dir)
        
        for item in source_path.rglob('*'):
            if item.is_file():
                count += 1
        
        return count
    
    def process_directory(self, source_dir, output_path, seven_zip_path, verify_md5=False):
        """处理目录中的所有文件"""
        source_path = Path(source_dir)
        
        # 用于跟踪已经处理过的分卷文件，避免重复处理
        processed_volumes = set()
        
        for item in source_path.rglob('*'):
            if item.is_file():
                relative_path = item.relative_to(source_path)
                
                # 检查是否是压缩文件
                if self.is_zip_file(item) or self.is_volume_file(item):
                    # 对于分卷文件，只处理第一个分卷，避免重复
                    if self.is_volume_file(item):
                        base_name = self.get_original_filename(item)
                        if base_name in processed_volumes:
                            continue  # 已经处理过这个分卷集
                        processed_volumes.add(base_name)
                    
                    # 获取原始文件名
                    original_name = self.get_original_filename(item)
                    
                    # 确定解压目录 - 直接解压到原始文件应该存在的位置
                    extract_dir = output_path / relative_path.parent
                    
                    # 解压文件
                    if self.extract_archive(item, extract_dir, seven_zip_path) and verify_md5:
                        # 验证解压后的文件
                        extracted_file = extract_dir / original_name
                        if extracted_file.exists():
                            relative_extracted_path = extracted_file.relative_to(output_path)
                            if str(relative_extracted_path) in self.source_md5_map:
                                expected_md5 = self.source_md5_map[str(relative_extracted_path)]
                                self.verify_file_md5(extracted_file, expected_md5, str(relative_extracted_path))
                else:
                    # 普通文件，直接复制
                    target_path = output_path / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target_path)
                    
                    # 如果启用MD5校验，验证复制的文件
                    if verify_md5 and str(relative_path) in self.target_md5_map:
                        expected_md5 = self.target_md5_map[str(relative_path)]
                        self.verify_file_md5(target_path, expected_md5, str(relative_path))
    
    def run(self):
        """主运行函数"""
        args = self.parse_arguments()

        source_path = Path(args.source).absolute()
        
        if not os.path.exists(source_path):
            self.log_error(f"源路径不存在: {source_path}")
            sys.exit(1)

        # 验证7z
        if not self.validate_7z(args.seven_zip_path):
            self.log_error("7z不可用")
            sys.exit(1)

        # 创建输出目录
        output_path = Path(args.output).absolute()
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 处理MD5校验
        if args.verify_md5:
            if args.md5_file:
                md5_file_path = Path(args.md5_file).absolute()
            else:
                md5_file_path = self.find_md5_file(source_path)
            
            if not md5_file_path or not md5_file_path.exists():
                self.log_error("未找到MD5校验文件，请使用 --md5-file 指定路径")
                sys.exit(1)
            
            if not self.parse_md5_file(md5_file_path):
                self.log_error("MD5文件解析失败")
                sys.exit(1)
        
        self.log_info(f"开始解压: {source_path} -> {output_path}")
        
        # 处理目录
        self.process_directory(source_path, output_path, args.seven_zip_path, args.verify_md5)
        
        self.log_info("解压完成")
        if args.verify_md5:
            self.log_info("MD5校验已完成")

def main():
    """主函数"""
    decompressor = SimpleVolumeDecompressor()
    try:
        decompressor.run()
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"程序执行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
