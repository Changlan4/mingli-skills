#!/usr/bin/env bash
# 命理排盘工具包装器：自动挑选带 lunar-python 的 Python 解释器。
#
# 三个入口：
#   run.sh liuyao --yao "7 8 9 6 7 8" --datetime "2025-11-01 10:30" --question "..."
#   run.sh parse  盘面.txt          # 解析用户粘来的、别的软件排好的盘
#   run.sh judge  --yao ... / --chart x.json / --parsed 盘面.txt --text
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"

CANDIDATES=(
  "${LIUYAO_PY:-}"
  "${PYTHON:-}"
  "python3"
  "python"
  "py"
)

PY=""
for cand in "${CANDIDATES[@]}"; do
  [ -z "$cand" ] && continue
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c "import lunar_python" >/dev/null 2>&1; then
      PY="$cand"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "错误：未找到带 lunar-python 的 Python 解释器。" >&2
  echo "请先安装依赖：  pip install lunar-python" >&2
  exit 1
fi

case "${1:-}" in
  test|tests)
    shift
    exec "$PY" "$HERE/tests/test_all.py" "$@"
    ;;
  parse)
    shift
    exec "$PY" "$HERE/parse_chart.py" "$@"
    ;;
  judge)
    shift
    exec "$PY" "$HERE/judge.py" "$@"
    ;;
  paipan|liuyao)
    # 两种写法都收：老习惯写 paipan，等价的 liuyao 是正式子命令
    shift
    exec "$PY" "$HERE/paipan.py" liuyao "$@"
    ;;
  *)
    exec "$PY" "$HERE/paipan.py" "$@"
    ;;
esac
