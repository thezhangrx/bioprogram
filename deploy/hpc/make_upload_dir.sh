#!/usr/bin/env bash
# 生成 upload/ —— 只含"HPC 上训练/预测真正需要"的数据与程序。
#
# 与 build_upload.sh 的区别：
#   build_upload.sh  把整个仓库打 tar（含 results/models/.git），体积巨大；
#   make_upload_dir.sh 只挑必要子树，产出可直接 scp/rsync 的 upload/ 目录。
#
# 用法:
#   bash deploy/hpc/make_upload_dir.sh [输出目录]      # 默认 ./upload
#
# 包内容:
#   core/ workflows/ deploy/{hpc,environment}/   训练与预测的全部代码路径
#   data/processed/<数据集>/                     已处理特征（DeepCRISPR/Hiranniramol/Labuhn）
#   data/raw/<数据集>/                           原始数据（可重跑特征工程）
#   data/metadata/  data/candidate/              特征配置 / 候选待测表
#   docs/                                        HPC 与外部数据集说明
#   README_UPLOAD.md                             在超算上怎么跑（先读这个）
#
# 不含: app/ tests/ analysis/ results/ models/ .git .venv workspace/ __pycache__
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/upload}"

if [ -e "$OUT" ]; then
  echo "[make_upload_dir] 清空已存在的 $OUT"
  rm -rf "$OUT"
fi

echo "[make_upload_dir] 源仓库 : $ROOT"
echo "[make_upload_dir] 输出   : $OUT"

mkdir -p "$OUT"

copy_tree() {
  # 复制子树，顺带剔除 pycache / pyc / 隐藏噪音
  local rel="$1"
  if [ ! -e "$ROOT/$rel" ]; then
    echo "  [skip] 缺失: $rel"
    return
  fi
  mkdir -p "$OUT/$(dirname "$rel")"
  rsync -a \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
        --exclude='.DS_Store' --exclude='*.ipynb_checkpoints' \
        "$ROOT/$rel" "$OUT/$(dirname "$rel")/"
  echo "  [ok]   $rel"
}

echo "[1/3] 代码"
for rel in core workflows deploy/hpc deploy/environment; do
  copy_tree "$rel"
done

echo "[2/3] 数据"
for rel in data/processed/DeepCRISPR data/processed/Hiranniramol data/processed/Labuhn \
           data/raw/DeepCRISPR data/raw/Hiranniramol data/raw/Labuhn \
           data/metadata data/candidate; do
  copy_tree "$rel"
done

echo "[3/3] 文档"
mkdir -p "$OUT/docs/reproducibility" "$OUT/docs/audit"
for f in docs/reproducibility/EXTERNAL_DATASETS.md \
         docs/reproducibility/HPC_EXPERIMENT_PROTOCOL.md \
         docs/reproducibility/HPC_ENVIRONMENT.md \
         docs/audit/HPC_ENVIRONMENT_FIT.md \
         docs/audit/HPC_ENV_COMPATIBILITY_REPORT.md \
         docs/audit/HPC_RERUN_PREFLIGHT.md; do
  if [ -f "$ROOT/$f" ]; then
    cp -a "$ROOT/$f" "$OUT/$f"
    echo "  [ok]   $f"
  else
    echo "  [skip] 缺失: $f"
  fi
done

# 包内 README（与仓库 README 不同：只讲超算上怎么跑）
cp -a "$ROOT/deploy/hpc/README_UPLOAD_TEMPLATE.md" "$OUT/README_UPLOAD.md"

# 包指纹，便于确认远端解压的是同一份
( cd "$OUT" && find . -type f -not -name MANIFEST.md5 -print0 \
    | sort -z | xargs -0 md5sum > MANIFEST.md5 )
echo "  [ok]   MANIFEST.md5 ($(wc -l < "$OUT/MANIFEST.md5") 个文件)"

echo
echo "[make_upload_dir] 完成: $OUT"
du -sh "$OUT"
echo "上传示例:  rsync -avP $OUT/ <user>@<hpc>:~/Submit/"
echo "远端校验:  md5sum -c MANIFEST.md5"
echo "远端自检:  python deploy/hpc/preflight_hpc_rerun.py --package . --data-set DeepCRISPR --batch-name <名>"
