# ============================================================
# 代码行数统计:按文件类型汇总,排除依赖/构建/缓存目录
# 用法:python count_lines.py
# ============================================================
import os
from pathlib import Path

ROOT = Path(__file__).parent
SKIP_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', 'data', '.idea', '.vscode', 'memory'}
SKIP_FILES = {'count_lines.py'}  # 统计脚本自身不计入
EXT_LABELS = {
    '.py': 'Python',
    '.vue': 'Vue',
    '.ts': 'TypeScript',
    '.js': 'JavaScript',
    '.css': 'CSS',
    '.html': 'HTML',
    '.json': 'JSON',
}


def count_file(p: Path) -> int:
    with open(p, encoding='utf-8', errors='ignore') as f:
        return sum(1 for _ in f)


stats: dict[str, int] = {}
total = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        if fn in SKIP_FILES:
            continue
        p = Path(dirpath) / fn
        ext = p.suffix.lower()
        if ext not in EXT_LABELS:
            continue
        n = count_file(p)
        stats[ext] = stats.get(ext, 0) + n
        total += n

print(f'代码统计: {ROOT}')
print('-' * 40)
for ext in sorted(stats, key=lambda e: -stats[e]):
    print(f'  {EXT_LABELS[ext]:<14} {stats[ext]:>7,} 行')
print('-' * 40)
print(f'  {"总计":<14} {total:>7,} 行')
