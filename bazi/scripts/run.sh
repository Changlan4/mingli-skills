#!/usr/bin/env bash
# 八字技能统一入口：自动挑一个装了 lunar-python 的 python 来跑。
#
#   bash run.sh pan  --date "1990-06-15 10:00" --gender male --city 上海
#   bash run.sh check 盘面.txt --birth "1990-06-15 10:00" --city 上海
#   bash run.sh test
#
# 之所以要挑解释器：本机可能有多个 python，只有某些装了 lunar-python 与 sxtwl。
# 可用环境变量 BAZI_PY / PYTHON 指定解释器。

set -u
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pick_py() {
  local cands=()
  [ -n "${BAZI_PY:-}" ] && cands+=("$BAZI_PY")
  [ -n "${PYTHON:-}" ] && cands+=("$PYTHON")
  cands+=(
    "$(command -v python3 2>/dev/null || true)"
    "$(command -v python 2>/dev/null || true)"
    "$(command -v py 2>/dev/null || true)"
  )
  for p in "${cands[@]}"; do
    [ -x "$p" ] || continue
    if "$p" -c "import lunar_python, sxtwl" >/dev/null 2>&1; then
      echo "$p"; return 0
    fi
  done
  return 1
}

PY="$(pick_py)" || {
  echo "找不到装了 lunar-python / sxtwl 的 python。" >&2
  echo "请先：pip install lunar-python sxtwl" >&2
  exit 1
}

cmd="${1:-}"; shift || true
case "$cmd" in
  pan|paipan|排盘)
    exec "$PY" "$SKILL_DIR/scripts/paipan.py" "$@"
    ;;
  check|parse|对账|校验)
    exec "$PY" "$SKILL_DIR/scripts/parse_chart.py" "$@"
    ;;
  test|tests|测试)
    exec "$PY" "$SKILL_DIR/scripts/tests/test_all.py"
    ;;
  build-book)
    exec "$PY" "$SKILL_DIR/scripts/build_book.py" "$@"
    ;;
  build-index)
    exec "$PY" "$SKILL_DIR/scripts/build_index.py" "$@"
    ;;
  *)
    grep '^#' "${BASH_SOURCE[0]}" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
    echo
    echo "可用子命令：pan | check | test | build-book | build-index"
    exit 2
    ;;
esac
