#!/usr/bin/env bash
set -euo pipefail

INFER_BIN="${INFER_BIN:-/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer}"
ROOT="$(cd "$(dirname "$0")" && pwd)"

run_case() {
  local name="$1"
  local source="$2"
  shift 2
  local out="${ROOT}/${name}/sympas-out-ci"

  (cd "${ROOT}/${name}" && \
    "${INFER_BIN}" --sympas --results-dir "${out}" capture -- clang -c "${source}" >/dev/null && \
    "${INFER_BIN}" --sympas --results-dir "${out}" analyze >/dev/null && \
    "${INFER_BIN}" --sympas --results-dir "${out}" report > report.txt)

  for needle in "$@"; do
    grep -Fq "${needle}" "${ROOT}/${name}/report.txt"
  done
  echo "PASS ${name}"
}

run_case intraprocedural data_dependency.c "frontier={ x }" "line 3, column 5" "line 4, column 5"
run_case intraprocedural field_dependency.c "frontier={ x, box }" "line 6" "line 7"
run_case intraprocedural array_dependency.c "frontier={ arr," "value," "index }" "line 2" "line 3"
run_case intraprocedural global_dependency.c "frontier={ x }" "line 4" "line 5"
run_case intraprocedural pointer_dependency.c "frontier={ ptr, value }" "line 2" "line 3"
run_case intraprocedural heap_field_dependency.c "frontier={ x }" "line 8" "line 9" "line 10" "line 12"
run_case control_dependency conditional_return.c "frontier={ x }" "line 2, column 9" "line 3, column 9"
run_case control_dependency nested_conditions.c "frontier={ x, y }" "line 2" "line 3" "line 4"
run_case control_dependency loop_return.c "frontier={ x }" "line 2" "line 3" "line 7"
run_case control_dependency unrelated_branch.c "frontier={ x, flag }" "line 2" "line 3" "line 4" "line 5"
run_case interprocedural call_summary.c "frontier={ a }" "line 6, column 15" "line 7, column 5"
