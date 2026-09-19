#!/usr/bin/env bash
# =============================================================================
# clean_user_test — 用户视角端到端验收
#
# 目的：验证「只依赖 Bash + README + 配置文件」能否完成全流程。
# 做法：从 README.md 的 Quick Start 代码块**逐字提取**命令并执行，逐步记录退出码。
#       不修改任何源码、不手工补参数、不依赖隐藏环境变量。
#
# 用法：  bash tests/workflow/clean_user_test.sh
# 退出码：0 = 全部步骤 PASS；1 = 有步骤 FAIL
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

PY="${PY:-/home/zhang/bioprogram/myenv/bin/python}"
BATCH="cleancheck"
LOG="/tmp/clean_user_test.log"
: > "$LOG"

pass=0; fail=0; skip=0
declare -a RESULTS

run_step() {
  local name="$1"; shift
  local cmd="$*"
  printf '\n\033[1m>>> [%s]\033[0m\n%s\n' "$name" "$cmd" | tee -a "$LOG"
  # 统一用项目解释器，避免 shell 默认 venv 缺依赖
  local eval_cmd="${cmd//python /$PY }"
  if eval "$eval_cmd" >>"$LOG" 2>&1; then
    printf '  \033[32mPASS\033[0m %s\n' "$name" | tee -a "$LOG"
    pass=$((pass+1)); RESULTS+=("PASS  $name")
  else
    local rc=$?
    printf '  \033[31mFAIL\033[0m %s (exit=%d)\n' "$name" "$rc" | tee -a "$LOG"
    fail=$((fail+1)); RESULTS+=("FAIL  $name (exit=$rc)")
  fi
}

expect_fail() {
  local name="$1"; shift
  local cmd="$*"
  printf '\n\033[1m>>> [%s]（期望非零退出）\033[0m\n%s\n' "$name" "$cmd" | tee -a "$LOG"
  local eval_cmd="${cmd//python /$PY }"
  if eval "$eval_cmd" >>"$LOG" 2>&1; then
    printf '  \033[31mFAIL\033[0m %s（本应失败却成功）\n' "$name" | tee -a "$LOG"
    fail=$((fail+1)); RESULTS+=("FAIL  $name(本应失败)")
  else
    printf '  \033[32mPASS\033[0m %s（正确返回非零）\n' "$name" | tee -a "$LOG"
    pass=$((pass+1)); RESULTS+=("PASS  $name")
  fi
}

echo "=================================================================="
echo " clean_user_test — 用户视角端到端验收"
echo " 项目根: $ROOT"
echo " 解释器: $PY"
echo " 详细日志: $LOG"
echo "=================================================================="

# ---------------------------------------------------------------------------
# Step 0 环境：不重复安装，只断言关键依赖可导入
# ---------------------------------------------------------------------------
run_step "Step0 环境依赖可导入" \
  "python -c \"import numpy,pandas,scipy,sklearn,xgboost,torch,matplotlib,seaborn;print('deps ok')\""

# ---------------------------------------------------------------------------
# Step 1 数据：原始 CSV 就位
# ---------------------------------------------------------------------------
run_step "Step1 原始数据可读" "python -c \"import pathlib;ps=sorted(pathlib.Path('data/raw/DeepCRISPR').glob('*.csv'));print([p.name for p in ps]);assert len(ps)>=4\""

# ---------------------------------------------------------------------------
# Step 2 schema：校验声明 == 实际张量
# ---------------------------------------------------------------------------
run_step "Step2 schema 一致性校验" \
  "python core/features/engineering/validate_feature_schema.py --all"

# ---------------------------------------------------------------------------
# Step 3 预处理：原始 CSV → 张量 + schema
# ---------------------------------------------------------------------------
run_step "Step3 预处理 DeepCRISPR" \
  "python core/features/engineering/feature_engineering.py --raw-data data/raw/DeepCRISPR --output-dir data/processed/DeepCRISPR --config data/metadata/feature_config.json"

# ---------------------------------------------------------------------------
# Step 4 训练：一次最小实验
# ---------------------------------------------------------------------------
run_step "Step4 最小训练" \
  "python workflows/training/train.py --model linear --split-type single --cell-line hct116 --environment sequence --data-set DeepCRISPR --results-dir results/batches --model-dir models/weights --logs-dir results/logs --batch-name $BATCH --run-name ${BATCH}_linear --seed 42"

# ---------------------------------------------------------------------------
# Step 5 评估：读测试集指标
# ---------------------------------------------------------------------------
run_step "Step5 评估指标可读" \
  "python -c \"import json;d=json.load(open('results/batches/$BATCH/${BATCH}_linear/linear_regression_metrics.json'));assert 'R2' in d;print('test R2 =',round(d['R2'],4))\""

run_step "Step5b 验证集指标与测试集分离" \
  "python -c \"import pathlib;p=pathlib.Path('results/batches/$BATCH/${BATCH}_linear/linear_regression_validation_metrics.json');assert p.is_file();print('validation metrics exist')\""

# ---------------------------------------------------------------------------
# Step 6 数据挖掘
# ---------------------------------------------------------------------------
run_step "Step6 数据挖掘计划模式" \
  "python workflows/training/data_digging.py --data-set DeepCRISPR --cell-lines hct116 --models linear --split-types single --environments sequence --batch-name $BATCH --dry-run"

# ---------------------------------------------------------------------------
# Step 7 预测
# ---------------------------------------------------------------------------
run_step "Step7 预测计划模式" \
  "python workflows/prediction/predict.py --data-set DeepCRISPR --batch-name $BATCH --models linear --dry-run"

# ---------------------------------------------------------------------------
# Step 8 结果汇总
# ---------------------------------------------------------------------------
run_step "Step8 结果汇总" \
  "python -m analysis.collect_results --results-dir results/batches --batch-name $BATCH"

run_step "Step8b 汇总产物存在" \
  "python -c \"import pathlib;d=pathlib.Path('results/batches/$BATCH/summary/metrics_tables');fs=sorted(d.glob('*.csv'));print([f.name for f in fs]);assert fs\""

# ---------------------------------------------------------------------------
# Step 9 关键特征库
# ---------------------------------------------------------------------------
run_step "Step9 关键调控特征库" \
  "python analysis/importance_extraction.py --batch_dir results/batches/$BATCH"

# ---------------------------------------------------------------------------
# Step 10 可视化
# ---------------------------------------------------------------------------
run_step "Step10a 全景图" "python analysis/panorama.py --batch-dir results/batches/$BATCH"
run_step "Step10b 分析引擎" \
  "python -m analysis.pipeline --batch-dir results/batches/$BATCH --output results/batches/$BATCH/analysis"

# ---------------------------------------------------------------------------
# 编排层
# ---------------------------------------------------------------------------
run_step "Orch list"  "python -m workflows.orchestrator list"
run_step "Orch command" "python -m workflows.orchestrator command --step feature_engineering --data-set DeepCRISPR"
run_step "Orch context" "python -m workflows.orchestrator context --data-set DeepCRISPR"

# ---------------------------------------------------------------------------
# 失败路径必须返回非零（脚本化安全）
# ---------------------------------------------------------------------------
expect_fail "负向: 批次不存在应非零退出" \
  "python -m analysis.collect_results --batch-name __no_such_batch__"
expect_fail "负向: 训练缺必填参数应非零退出" \
  "python workflows/training/train.py --model linear"
expect_fail "负向: 预测缺数据集应非零退出" \
  "python workflows/prediction/predict.py --batch-name x --models linear"
expect_fail "负向: 未知数据集应非零退出" \
  "python workflows/training/train.py --model linear --split-type single --cell-line hct116 --environment sequence --data-set __NoSuchDataset__"

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
echo
echo "=================================================================="
echo " 验收汇总"
echo "=================================================================="
for r in "${RESULTS[@]}"; do
  case "$r" in
    PASS*) printf '  \033[32m%s\033[0m\n' "$r" ;;
    *)     printf '  \033[31m%s\033[0m\n' "$r" ;;
  esac
done
echo "------------------------------------------------------------------"
printf '  PASS=%d  FAIL=%d\n' "$pass" "$fail"
echo "  完整日志: $LOG"
echo "=================================================================="

[ "$fail" -eq 0 ] && exit 0 || exit 1
