# 分卷压缩脚本 Zip4Cloud - Volume Compression Script Zip4Cloud

## 中文版 README

### 概述
这是一个分卷压缩工具，能够保持目录结构并单独压缩每个文件以便于云端备份。支持多种压缩选项、完整性验证和MD5校验功能。

### 主要功能
- **智能分卷压缩**: 自动按指定大小分割压缩文件
- **目录结构保持**: 压缩后保持原始目录结构
- **深度控制**: 可设置最大遍历深度，超出深度的文件夹整体压缩
- **文件过滤**: 支持排除特定扩展名的文件
- **完整性验证**: 使用7z测试压缩包完整性
- **MD5校验**: 生成源文件和压缩文件的MD5校验信息
- **压缩级别控制**: 支持0-9级压缩级别调节

### 系统要求
- Python 3.6+
- 7-zip 命令行工具

### 安装依赖
```bash
# 需要安装7-zip
# Windows: 从官网下载安装
# Linux: sudo apt-get install p7zip-full
# macOS: brew install p7zip
```

### 使用方法
```bash
# 基本分卷压缩
python compressor.py /path/to/source --volume-size 100M

# 排除特定文件类型并生成MD5
python compressor.py /path/to/source -v 500M -e ".tmp,.log" --generate-md5

# 控制遍历深度
python compressor.py /path/to/source -v 1G --max-depth 2

# 启用压缩校验和设置压缩级别
python compressor.py /path/to/source -v 100M --test --compression-level 5

# 最高压缩级别
python compressor.py /path/to/source -v 100M --compression-level 9
```

### 参数说明
- `source`: 源文件或目录路径（必需）
- `-v, --volume-size`: 分卷大小（如100M, 1G, 500K）（必需）
- `-e, --exclude-extensions`: 排除的文件扩展名，逗号分隔
- `-m, --generate-md5`: 生成MD5校验文件
- `-d, --max-depth`: 最大遍历深度（-1表示无限制）
- `-o, --output`: 输出目录（默认：源目录同级）
- `-t, --test`: 启用压缩校验，测试每个压缩包的完整性
- `-l, --compression-level`: 压缩级别（0-9，默认：1）
- `--7z-path`: 7z可执行文件路径

### 压缩策略
- **浅层文件**: 在最大深度范围内的文件单独压缩
- **深层文件夹**: 超出最大深度的文件夹整体压缩
- **排除文件**: 被排除扩展名的文件直接复制到输出目录

### 输出结构
```
输出目录/
├── 子目录1/
│   ├── 文件1.zip
│   ├── 文件2.zip.001
│   ├── 文件2.zip.002
│   └── ...
├── 子目录2/
│   └── 深层文件夹.zip
├── 排除文件.txt (直接复制)
└── compression_checksums.md5 (MD5校验文件)
```

---

## English Version README

### Overview
An volume compression tool that maintains directory structure and compresses each file individually for cloud backup convenience. Supports multiple compression options, integrity verification, and MD5 checksum functionality.

### Key Features
- **Smart Volume Compression**: Automatically splits compressed files by specified size
- **Directory Structure Preservation**: Maintains original directory structure after compression
- **Depth Control**: Configurable maximum traversal depth, folders beyond depth are compressed as whole
- **File Filtering**: Support for excluding specific file extensions
- **Integrity Verification**: Uses 7z to test compressed archive integrity
- **MD5 Checksum**: Generates MD5 checksum information for source and compressed files
- **Compression Level Control**: Supports 0-9 compression levels

### System Requirements
- Python 3.6+
- 7-zip command line tool

### Installation Dependencies
```bash
# 7-zip required
# Windows: Download from official website
# Linux: sudo apt-get install p7zip-full
# macOS: brew install p7zip
```

### Usage
```bash
# Basic volume compression
python compressor.py /path/to/source --volume-size 100M

# Exclude specific file types and generate MD5
python compressor.py /path/to/source -v 500M -e ".tmp,.log" --generate-md5

# Control traversal depth
python compressor.py /path/to/source -v 1G --max-depth 2

# Enable compression verification and set compression level
python compressor.py /path/to/source -v 100M --test --compression-level 5

# Maximum compression level
python compressor.py /path/to/source -v 100M --compression-level 9
```

### Parameter Description
- `source`: Source file or directory path (required)
- `-v, --volume-size`: Volume size (e.g., 100M, 1G, 500K) (required)
- `-e, --exclude-extensions`: Excluded file extensions, comma separated
- `-m, --generate-md5`: Generate MD5 checksum file
- `-d, --max-depth`: Maximum traversal depth (-1 for unlimited)
- `-o, --output`: Output directory (default: same level as source directory)
- `-t, --test`: Enable compression verification, test integrity of each archive
- `-l, --compression-level`: Compression level (0-9, default: 1)
- `--7z-path`: Path to 7z executable

### Compression Strategy
- **Shallow Files**: Files within maximum depth range are compressed individually
- **Deep Folders**: Folders beyond maximum depth are compressed as whole
- **Excluded Files**: Files with excluded extensions are copied directly to output directory

### Output Structure
```
output_directory/
├── subdirectory1/
│   ├── file1.zip
│   ├── file2.zip.001
│   ├── file2.zip.002
│   └── ...
├── subdirectory2/
│   └── deep_folder.zip
├── excluded_file.txt (direct copy)
└── compression_checksums.md5 (MD5 checksum file)
```

### Notes
- The script automatically handles both single files and directory structures
- Compression progress and results are logged with detailed information
- MD5 checksums help verify data integrity before and after compression
- Volume splitting is automatic based on the specified size limit
