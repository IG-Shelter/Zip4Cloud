#encoding=utf-8
#!/usr/bin/env python3
"""
分卷压缩脚本 - 保持目录结构，单独压缩每个文件
"""

import os
import sys
import subprocess
import hashlib
import argparse
from pathlib import Path
import shutil

class AdvancedVolumeCompressor:
    def __init__(self):
        self.checksum_data = {}  # 存储所有校验信息
        
    def log_info(self, message):
        """信息级别日志"""
        print(f"[INFO] {message}")

    def log_debug(self, message):
        """调试级别日志"""
        print(f"[DEBUG] {message}")
    
    def log_error(self, message):
        """错误级别日志"""
        print(f"[ERROR] {message}", file=sys.stderr)
    
    def log_warning(self, message):
        """警告级别日志"""
        print(f"[WARNING] {message}")
    
    def parse_arguments(self):
        """解析命令行参数"""
        parser = argparse.ArgumentParser(
            description='高级分卷压缩工具 - 单独压缩每个文件',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
使用示例:
  # 基本分卷压缩，保持目录结构
  python compressor.py /path/to/source --volume-size 100M
  
  # 排除特定文件类型并生成MD5
  python compressor.py /path/to/source -v 500M -e ".tmp,.log" --generate-md5
  
  # 控制遍历深度
  python compressor.py /path/to/source -v 1G --max-depth 2
  
  # 启用压缩校验和设置压缩级别
  python compressor.py /path/to/source -v 100M --test --compression-level 5
  
  # 最高压缩级别
  python compressor.py /path/to/source -v 100M --compression-level 9
            '''
        )
        
        parser.add_argument('source', help='源文件或目录路径')
        parser.add_argument('-v', '--volume-size', required=True, 
                          help='分卷大小 (例如: 100M, 1G, 500K)')
        parser.add_argument('-e', '--exclude-extensions', default='',
                          help='要排除的文件扩展名，逗号分隔 (例如: ".tmp,.log,.bak")')
        parser.add_argument('-m', '--generate-md5', action='store_true',
                          help='生成MD5校验文件')
        parser.add_argument('-d', '--max-depth', type=int, default=-1,
                          help='最大遍历深度 (-1表示无限制)')
        parser.add_argument('-o', '--output', default=None,
                          help='输出目录 (默认: 源目录同级)')
        parser.add_argument('-t','--test',action='store_true',
                          help='启用压缩校验，测试每个压缩包的完整性')
        parser.add_argument('-l', '--compression-level', type=int, choices=range(0, 10), default=1,
                          help='压缩级别 (0-9, 0=不压缩, 1=最快, 5=标准, 9=最高压缩, 默认: 5)')
        parser.add_argument('--7z-path', default='7z', dest='seven_zip_path',
                          help='7z可执行文件路径 (默认: 使用系统PATH中的7z)')
        
        return parser.parse_args()
    
    def validate_7z(self, seven_zip_path):
        """验证7z是否可用"""
        try:
            result = subprocess.run(
                [seven_zip_path], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            return result.returncode == 0 or result.returncode == 7
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            self.log_error(f"无法找到或执行7z: {seven_zip_path}")
            return False
    
    def find_volume_files(self, base_path):
        """
        查找分卷压缩的所有卷文件
        
        返回:
            list: 按顺序排列的分卷文件路径列表
        """
        base_path = Path(base_path)
        parent_dir = base_path.parent
        
        # 查找所有可能的分卷文件
        volume_files = []
        
        # 查找基础文件名开头的所有文件
        pattern = f"{base_path.name}.*"
        for file_path in parent_dir.glob(pattern):
            # 检查是否是分卷文件（以数字结尾）
            suffix = file_path.suffix
            if suffix and suffix[1:].isdigit() and len(suffix) >= 4:  # 至少3位数字加一个点
                try:
                    volume_num = int(suffix[1:])
                    volume_files.append((volume_num, file_path))
                except ValueError:
                    continue
        
        # 按卷号排序
        volume_files.sort()
        return [file_path for _, file_path in volume_files]
    
    def verify_compressed_archive(self, archive_path, seven_zip_path):
        """
        使用7z测试压缩包的完整性
        
        返回:
            bool: 压缩包是否完整可用
        """
        try:
            self.log_debug(f"正在验证压缩包完整性: {archive_path}")
            
            # 使用7z测试命令验证压缩包完整性
            cmd = [
                seven_zip_path, 't', 
                '-y',  # 假设对所有提示回答是
                str(archive_path)
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5分钟超时
                check=True
            )
            
            if result.returncode == 0:
                self.log_debug(f"✓ 压缩包验证成功: {archive_path}")
                return True
            else:
                self.log_error(f"✗ 压缩包验证失败: {archive_path}")
                if result.stderr:
                    self.log_error(f"7z错误输出: {result.stderr}")
                return False
                
        except subprocess.CalledProcessError as e:
            self.log_error(f"✗ 压缩包验证异常 {archive_path}: {e}")
            if e.stderr:
                self.log_error(f"7z错误输出: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            self.log_error(f"✗ 压缩包验证超时: {archive_path}")
            return False
        except Exception as e:
            self.log_error(f"✗ 压缩包验证未知错误 {archive_path}: {e}")
            return False
    
    def verify_volume_archive(self, base_archive_path, seven_zip_path):
        """
        验证分卷压缩的完整性
        
        对于分卷压缩，我们需要找到第一个分卷文件(.001)进行验证
        """
        # 查找所有分卷文件
        volume_files = self.find_volume_files(base_archive_path)
        
        if not volume_files:
            self.log_warning(f"未找到分卷文件: {base_archive_path}")
            return False
        
        self.log_info(f"找到 {len(volume_files)} 个分卷文件")
        
        # 使用第一个分卷进行测试（7z会自动识别后续分卷）
        first_volume = volume_files[0]
        self.log_debug(f"使用第一个分卷进行验证: {first_volume}")
        
        return self.verify_compressed_archive(first_volume, seven_zip_path)
    
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
    
    def should_exclude(self, file_path, exclude_extensions):
        """检查文件是否应该被排除"""
        if not exclude_extensions:
            return False
        
        file_ext = Path(file_path).suffix.lower()
        exclude_list = [ext.lower().strip() for ext in exclude_extensions.split(',') if ext.strip()]
        
        return file_ext in exclude_list
    
    def scan_and_organize_files(self, source_path, max_depth, exclude_extensions):
        """
        扫描文件并根据深度策略组织
        返回:
          - shallow_files_to_compress: 需要压缩的浅层文件
          - shallow_files_to_copy: 需要复制的浅层文件（被排除的文件）
          - deep_folders: 深层文件夹列表 (整体压缩)
        """

        shallow_files_to_compress = []  # 需要压缩的浅层文件
        shallow_files_to_copy = []      # 需要复制的浅层文件（被排除的文件）
        deep_folders = []               # 深层文件夹 - 整体压缩
        
        if source_path.is_file():
            # 单个文件
            if self.should_exclude(source_path, exclude_extensions):
                shallow_files_to_copy.append({
                    'path': source_path,
                    'relative_path': source_path.name
                })
            else:
                shallow_files_to_compress.append({
                    'path': source_path,
                    'relative_path': source_path.name
                })
            return shallow_files_to_compress, shallow_files_to_copy, deep_folders
        
        # 遍历目录
        for root, dirs, files in os.walk(source_path):
            # 计算当前深度
            current_depth = 0
            rel_path = Path(root).relative_to(source_path)
            if rel_path != Path('.'):
                current_depth = len(rel_path.parts)
            
            # 检查是否超过最大深度
            if max_depth != -1 and current_depth >= max_depth:
                # 超过最大深度，将整个文件夹作为一个整体
                folder_path = Path(root)
                if folder_path not in deep_folders:
                    deep_folders.append(folder_path)
                # 跳过这个文件夹的进一步遍历
                dirs.clear()
                continue
            
            # 处理当前目录的文件
            for file in files:
                file_path = Path(root) / file
                # 计算相对于源目录的路径
                relative_path = file_path.relative_to(source_path)
                
                if self.should_exclude(file_path, exclude_extensions):
                    # 被排除的文件，需要复制
                    shallow_files_to_copy.append({
                        'path': file_path,
                        'relative_path': relative_path
                    })
                else:
                    # 需要压缩的文件
                    shallow_files_to_compress.append({
                        'path': file_path,
                        'relative_path': relative_path
                    })
        
        return shallow_files_to_compress, shallow_files_to_copy, deep_folders
    
    def copy_excluded_files(self, files_to_copy, output_path):
        """复制被排除的文件到输出目录"""
        if not files_to_copy:
            return
        
        self.log_info(f"正在复制 {len(files_to_copy)} 个被排除的文件...")
        
        for i, file_info in enumerate(files_to_copy, 1):
            file_path = file_info['path']
            relative_path = file_info['relative_path']
            
            # 创建输出子目录以保持结构
            output_subdir = output_path / relative_path.parent
            output_subdir.mkdir(parents=True, exist_ok=True)
            target_path = output_subdir / file_path.name
            
            try:
                shutil.copy2(file_path, target_path)
                self.log_info(f"复制文件: {relative_path}")
            except Exception as e:
                self.log_error(f"复制文件失败 {file_path}: {e}")
        
        self.log_info(f"已复制 {len(files_to_copy)} 个被排除的文件")
    
    def compress_item(self, item_info, source_path, output_path, volume_size, seven_zip_path, compression_level=1, is_folder=False, test=False):
        """
        压缩单个文件或文件夹
        修复：使用7z的路径控制选项，确保压缩包内不包含路径
        """
        if is_folder:
            item_path = item_info
            relative_path = item_path.relative_to(source_path)
            output_file_name = f"{item_path.name}.zip"
        else:
            item_path = item_info['path']
            relative_path = item_info['relative_path']
            output_file_name = f"{item_path.stem}.zip"
        
        # 创建输出子目录以保持结构
        output_subdir = output_path / relative_path.parent
        output_subdir.mkdir(parents=True, exist_ok=True)
        
        # 修复变量重用问题 - 使用不同的变量名
        output_archive_path = output_subdir / output_file_name
        
        item_type = "文件夹" if is_folder else "文件"
        self.log_info(f"压缩{item_type}: {item_path} -> {output_archive_path} (压缩级别: {compression_level})")
        
        try:
            # 使用7z的路径控制选项，不切换工作目录
            cmd = [
                seven_zip_path, 'a',
                '-tzip',
                '-v' + volume_size,
                '-y',
                f'-mx={compression_level}',  # 使用指定的压缩级别
                '-r',
                '-aoa',
                str(output_archive_path),
                str(item_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.log_info(f"压缩完成: {output_archive_path}")
            
            # 如果启用验证，检查压缩包完整性
            if test:
                # 检查是否是分卷压缩
                volume_files = self.find_volume_files(output_archive_path)
                if volume_files:
                    # 分卷压缩，验证第一个分卷
                    self.log_info(f"检测到分卷压缩，共 {len(volume_files)} 个分卷")
                    test_success = self.verify_volume_archive(output_archive_path, seven_zip_path)
                else:
                    # 单文件压缩，直接验证
                    self.log_info("检测到单文件压缩")
                    test_success = self.verify_compressed_archive(output_archive_path, seven_zip_path)
                
                if not test_success:
                    self.log_error(f"压缩包验证失败: {output_archive_path}")
                    return False
            
            return True
        except subprocess.CalledProcessError as e:
            self.log_error(f"压缩失败 {item_path}: {e}")
            if e.stderr:
                self.log_error(f"7z错误输出: {e.stderr}")
            return False
    
    def calculate_files_md5(self, files_or_folders, source_path, prefix="SOURCE"):
        """
        计算文件或文件夹内所有文件的MD5
        files_or_folders: 可以是文件信息列表或文件夹路径列表
        """
        # 先统计总文件数
        total_files = 0
        file_list = []
        
        for item in files_or_folders:
            if isinstance(item, dict):  # 文件信息
                total_files += 1
                file_list.append(item)
            else:  # 文件夹路径
                folder = item
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        total_files += 1
                        file_path = Path(root) / file
                        relative_path = file_path.relative_to(source_path)
                        file_list.append({
                            'path': file_path,
                            'relative_path': relative_path
                        })
        
        if total_files == 0:
            return 0
            
        self.log_info(f"开始计算 {total_files} 个文件的MD5...")
        
        count = 0
        for i, item in enumerate(file_list, 1):
            if isinstance(item, dict):  # 文件信息
                file_path = item['path']
                relative_path = item['relative_path']
                md5 = self.calculate_file_md5(file_path)
                if md5:
                    self.checksum_data[f"{prefix}:{relative_path}"] = md5
                    count += 1
                else:
                    self.log_warning(f"无法计算{prefix}文件MD5: {file_path}")
        
        return count
    
    def find_and_calculate_md5(self, directory, prefix="TARGET"):
        """查找目录中的所有文件并计算MD5"""
        all_files = []
        
        # 遍历目录中的所有文件
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = Path(root) / file
                all_files.append(file_path)
        
        total_files = len(all_files)
        self.log_info(f"找到 {total_files} 个文件用于MD5计算")
        
        if total_files == 0:
            return 0
            
        count = 0
        for i, file_path in enumerate(all_files, 1):
            # 计算相对于目录的路径
            relative_path = file_path.relative_to(directory)
            
            # 计算MD5
            md5 = self.calculate_file_md5(file_path)
            if md5:
                self.checksum_data[f"{prefix}:{relative_path}"] = md5
                count += 1
            else:
                self.log_warning(f"无法计算{prefix}文件MD5: {file_path}")
        
        return count
    
    def generate_global_checksum_file(self, output_path):
        """生成全局MD5校验文件"""
        if not self.checksum_data:
            self.log_warning("没有MD5数据可写入")
            return
        
        import time
        
        checksum_file = output_path / "compression_checksums.md5"
        try:
            # 准备要写入的内容
            content = []
            content.append("# 压缩过程MD5校验文件")
            content.append(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            content.append("")
            
            # 写入源文件MD5
            content.append("# 源文件MD5校验值")
            source_entries = {k: v for k, v in self.checksum_data.items() if k.startswith('SOURCE:')}
            for key, md5 in sorted(source_entries.items()):
                filename = key.replace('SOURCE:', '')
                content.append(f"{md5} *{filename}")
            
            content.append("")
            content.append("# 目标文件MD5校验值")
            target_entries = {k: v for k, v in self.checksum_data.items() if k.startswith('TARGET:')}
            for key, md5 in sorted(target_entries.items()):
                filename = key.replace('TARGET:', '')
                content.append(f"{md5} *{filename}")
            
            # 写入文件
            with open(checksum_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
            
            self.log_info(f"全局MD5校验文件已生成: {checksum_file}")
            self.log_info(f"包含 {len(source_entries)} 个源文件和 {len(target_entries)} 个目标文件的校验信息")
            
        except Exception as e:
            self.log_error(f"生成全局MD5文件失败: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """主运行函数"""
        args = self.parse_arguments()

        source_path = Path(args.source).absolute()
        
        # 验证参数
        if not os.path.exists(source_path):
            self.log_error(f"源路径不存在: {source_path}")
            sys.exit(1)
        
        # 使用正确的参数名
        seven_zip_path = getattr(args, 'seven_zip_path', '7z')
        
        if not self.validate_7z(seven_zip_path):
            self.log_error("7z不可用，请确保已安装7-zip并添加到PATH")
            sys.exit(1)
        
        # 扫描文件
        self.log_info("正在扫描文件...")
        shallow_files_to_compress, shallow_files_to_copy, deep_folders = self.scan_and_organize_files(
            source_path, 
            args.max_depth, 
            args.exclude_extensions
        )
        
        self.log_info(f"找到 {len(shallow_files_to_compress)} 个需要压缩的浅层文件，{len(shallow_files_to_copy)} 个需要复制的浅层文件，{len(deep_folders)} 个深层文件夹")
        
        # 创建输出目录
        if args.output:
            output_path = Path(args.output).absolute()
        else:
            # 默认输出目录：源目录同级，添加_compressed后缀
            if source_path.is_file():
                output_path = source_path.parent / f"{source_path.stem}_compressed"
            else:
                output_path = source_path.parent / f"{source_path.name}_compressed"
        
        output_path.mkdir(parents=True, exist_ok=True)
        self.log_info(f"输出目录: {output_path}")
        
        # 复制被排除的文件
        self.copy_excluded_files(shallow_files_to_copy, output_path)
        
        success_count = 0

        total_count = len(shallow_files_to_compress) + len(deep_folders)

        # 压缩深层文件夹
        self.log_info("开始压缩深层文件夹...")
        for i, folder in enumerate(deep_folders, 1):
            self.log_info(f"处理深层文件夹: {folder}")
            if self.compress_item(folder, source_path, output_path, args.volume_size, 
                                seven_zip_path, args.compression_level, is_folder=True, test=args.test):
                success_count += 1
        
        # 压缩浅层文件
        self.log_info("开始压缩浅层文件...")
        for i, file_info in enumerate(shallow_files_to_compress, 1):
            self.log_info(f"处理文件: {file_info['path']}")
            if self.compress_item(file_info, source_path, output_path, args.volume_size,
                                seven_zip_path, args.compression_level, is_folder=False, test=args.test):
                success_count += 1

        # 计算源文件MD5
        if args.generate_md5:
            self.log_info("正在计算源文件MD5...")
            source_count = 0
            source_count += self.calculate_files_md5(shallow_files_to_compress, source_path, "SOURCE")
            source_count += self.calculate_files_md5(shallow_files_to_copy, source_path, "SOURCE")
            source_count += self.calculate_files_md5(deep_folders, source_path, "SOURCE")
            self.log_info(f"已计算 {source_count} 个源文件的MD5")
        
        # 计算输出目录中所有文件的MD5
        if args.generate_md5:
            target_count = self.find_and_calculate_md5(output_path, "TARGET")
            self.log_info(f"已计算 {target_count} 个目标文件的MD5")
            self.generate_global_checksum_file(output_path)
        
        # 总结
        self.log_info(f"压缩完成: {success_count}/{total_count} 个任务成功")
        
        if success_count == total_count:
            self.log_info("所有压缩任务均成功完成")
            if args.test:
                self.log_info("所有压缩包均已通过完整性验证")
            self.log_info(f"压缩级别: {args.compression_level}")
            self.log_info(f"输出目录: {output_path}")
        else:
            self.log_warning("部分压缩任务失败")
            sys.exit(1)

def main():
    """主函数"""
    compressor = AdvancedVolumeCompressor()
    try:
        compressor.run()
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
