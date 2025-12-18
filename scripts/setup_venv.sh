#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

log() { echo "[setup_venv] $*" >&2; }
warn() { echo "[setup_venv][WARN] $*" >&2; }
die() { echo "[setup_venv][ERROR] $*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

usage() {
  cat <<'EOF'
Usage: scripts/setup_venv.sh [--python /path/to/python] [--python-index N] [--list-pythons]

Creates/uses .venv, ensures uv is available, installs system deps (best-effort),
then runs `uv sync`.

Python selection:
  --python PATH       Use this python to create .venv (must be >= 3.10)
  --python-index N    Choose from auto-discovered candidates by index (see --list-pythons)
  --list-pythons      Print discovered Python candidates and exit

Non-interactive:
  If multiple candidates exist and no selection is provided, the script will
  prompt when running in a TTY; otherwise it will choose the highest version.
EOF
}

python_major_minor() {
  # Prints like: 3.12
  "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null
}

version_ge() {
  # Compare two dot versions using sort -V, return 0 if $1 >= $2
  [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

detect_os_like() {
  # Outputs a normalized family: rhel | debian | unknown
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    local like="${ID_LIKE:-}"
    local id="${ID:-}"
    if echo " $id $like " | grep -Eq ' (rhel|fedora|centos|anolis|alinux) '; then
      echo "rhel"
      return
    fi
    if echo " $id $like " | grep -Eq ' (debian|ubuntu) '; then
      echo "debian"
      return
    fi
  fi
  echo "unknown"
}

install_system_deps_rhel() {
  if ! have_cmd sudo; then
    warn "sudo not found; skipping system dependency installation"
    return
  fi
  if ! sudo -n true >/dev/null 2>&1; then
    warn "sudo requires a password; skipping system dependency installation (run as root or configure passwordless sudo)"
    return
  fi

local dnf_cmd="dnf"
if ! have_cmd dnf && have_cmd yum; then
  dnf_cmd="yum"
fi
have_cmd "$dnf_cmd" || { warn "dnf/yum not found; skipping system dependency installation"; return; }

log "Installing system deps for building pyicu (ICU + pkg-config + toolchain) via $dnf_cmd"

# Some environments have broken optional repos (e.g., local CUDA repo path, nvidia repo SSL issues).
local disablerepos=(
  "cuda-rhel8-12-8-local"
  "nvidia-container-toolkit"
  "nvidia-container-toolkit-experimental"
)

local disable_args=()
for r in "${disablerepos[@]}"; do
  disable_args+=( "--disablerepo=$r" )
done

sudo -n "$dnf_cmd" -y "${disable_args[@]}" install \
  libicu-devel \
  pkgconf-pkg-config \
  gcc gcc-c++ make \
  || die "Failed to install system deps. You may need to fix/disable broken yum repos."
}

install_system_deps_debian() {
  if ! have_cmd sudo; then
    warn "sudo not found; skipping system dependency installation"
    return
  fi
  if ! sudo -n true >/dev/null 2>&1; then
    warn "sudo requires a password; skipping system dependency installation (run as root or configure passwordless sudo)"
    return
  fi
  have_cmd apt-get || { warn "apt-get not found; skipping system dependency installation"; return; }

log "Installing system deps for building pyicu (ICU + pkg-config + toolchain) via apt-get"
sudo -n apt-get update -y
sudo -n apt-get install -y \
  libicu-dev \
  pkg-config \
  build-essential \
  || die "Failed to install system deps via apt-get"
}

discover_python_candidates() {
  # Outputs lines: "<index>\t<version>\t<label>\t<path>"
  local idx=0

  add_candidate() {
    local label="$1"
    local path="$2"
    [ -n "$path" ] || return
    [ -x "$path" ] || return
    local v
    v="$(python_major_minor "$path" || true)"
    [ -n "$v" ] || return
    version_ge "$v" "3.10" || return
    printf "%s\t%s\t%s\t%s\n" "$idx" "$v" "$label" "$path"
    idx=$((idx + 1))
  }

  # 1) Explicit env var
  if [ -n "${PYTHON:-}" ] && [ -x "${PYTHON:-}" ]; then
    add_candidate "env:PYTHON" "$PYTHON"
  fi

  # 2) Current shell python (if any)
  if have_cmd python; then
    add_candidate "PATH:python" "$(command -v python)"
  fi
  if have_cmd python3; then
    add_candidate "PATH:python3" "$(command -v python3)"
  fi
  if have_cmd python3.12; then add_candidate "PATH:python3.12" "$(command -v python3.12)"; fi
  if have_cmd python3.11; then add_candidate "PATH:python3.11" "$(command -v python3.11)"; fi
  if have_cmd python3.10; then add_candidate "PATH:python3.10" "$(command -v python3.10)"; fi

  # 3) Current conda env
  if [ -n "${CONDA_PREFIX:-}" ] && [ -x "${CONDA_PREFIX}/bin/python" ]; then
    add_candidate "conda:active($(basename "$CONDA_PREFIX"))" "${CONDA_PREFIX}/bin/python"
  fi

  # 4) Conda envs (best-effort discovery)
  local conda_base=""
  if have_cmd conda; then
    conda_base="$(conda info --base 2>/dev/null || true)"
  fi

  local p
  for p in \
    "$HOME/.conda/envs"/*/bin/python \
    "$HOME/miniconda3/envs"/*/bin/python \
    "$HOME/anaconda3/envs"/*/bin/python \
    "/opt/conda/envs"/*/bin/python \
    ${conda_base:+$conda_base/envs/*/bin/python}
  do
    [ -x "$p" ] || continue
    add_candidate "conda:env($(basename "$(dirname "$(dirname "$p")")"))" "$p"
  done
}

print_python_candidates() {
  local lines
  lines="$(discover_python_candidates || true)"
  if [ -z "$lines" ]; then
    echo "No Python >= 3.10 candidates found."
    return 1
  fi
  echo "Discovered Python candidates (>=3.10):"
  echo "IDX  VERSION  LABEL                 PATH"
  echo "$lines" | awk -F'\t' '{printf "%-4s %-7s %-20s %s\n", $1, $2, $3, $4}'
}

select_python() {
  local requested_python="${1:-}"
  local requested_index="${2:-}"

  if [ -n "$requested_python" ]; then
    if [ ! -x "$requested_python" ]; then
      die "--python '$requested_python' is not executable"
    fi
    local v
    v="$(python_major_minor "$requested_python" || true)"
    [ -n "$v" ] || die "--python '$requested_python' is not a valid python"
    version_ge "$v" "3.10" || die "--python '$requested_python' is too old ($v), need >= 3.10"
    echo "$requested_python"
    return
  fi

  local lines
  lines="$(discover_python_candidates || true)"
  if [ -z "$lines" ]; then
    die "No usable Python (>=3.10) found. Use --python /path/to/python3.12 (e.g., conda env python) and retry."
  fi

  if [ -n "$requested_index" ]; then
    local chosen
    chosen="$(echo "$lines" | awk -F'\t' -v idx="$requested_index" '$1==idx{print $4; exit}')"
    [ -n "$chosen" ] || die "--python-index '$requested_index' not found. Run with --list-pythons."
    echo "$chosen"
    return
  fi

  # Interactive choose if TTY and more than 1 candidate
  local count
  count="$(echo "$lines" | wc -l | tr -d ' ')"
  if [ "$count" -gt 1 ] && [ -t 0 ] && [ -t 1 ]; then
    print_python_candidates >/dev/stderr
    echo -n "Select Python index (blank = choose highest version): " >/dev/stderr
    local ans=""
    read -r ans || true
    if [ -n "$ans" ]; then
      local chosen
      chosen="$(echo "$lines" | awk -F'\t' -v idx="$ans" '$1==idx{print $4; exit}')"
      [ -n "$chosen" ] || die "Invalid selection: $ans"
      echo "$chosen"
      return
    fi
  fi

  # Default: choose highest version (tie-breaker: first encountered)
  echo "$lines" | sort -t $'\t' -k2,2V | tail -n 1 | awk -F'\t' '{print $4}'
}

ensure_uv() {
  # Prefer project venv uv if present, else PATH uv, else install via pip.
  if [ -x "$PROJECT_ROOT/.venv/bin/uv" ]; then
    echo "$PROJECT_ROOT/.venv/bin/uv"
    return
  fi
  if have_cmd uv; then
    command -v uv
    return
  fi

  local venv_python="$PROJECT_ROOT/.venv/bin/python"
  if [ ! -x "$venv_python" ]; then
    echo "[setup_venv][ERROR] Expected venv python at $venv_python. (.venv should have been created before ensure_uv)" >&2
    return 1
  fi

  local pip_log="$PROJECT_ROOT/.venv/uv_pip_install.log"
  : >"$pip_log" || true

  # Log helpful context for debugging index/mirror issues.
  log "uv not found; installing via pip into project venv: pip install -U --force-reinstall uv"
  log "uv pip install log: $pip_log"
  log "Venv python: $venv_python ($("$venv_python" -c 'import sys; print(sys.version)' 2>/dev/null || echo "unknown"))"
  log "Venv pip: $("$venv_python" -m pip --version 2>/dev/null || echo "pip-missing")"
  if [ -n "${PIP_INDEX_URL:-}" ]; then
    # Mask potential credentials (user:pass@) in the URL for safety.
    local masked="${PIP_INDEX_URL}"
    masked="$(echo "$masked" | sed -E 's#(https?://)[^/@:]+(:[^/@]+)?@#\1***:***@#')"
    log "PIP_INDEX_URL is set (masked): $masked"
  else
    log "PIP_INDEX_URL is not set (pip will use its default/configured index)"
  fi
  if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
    warn "pip not available in venv; attempting ensurepip"
    "$venv_python" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi

  # Emit full pip output for visibility and keep a copy on disk.
  # -v provides detailed download/index logs.
  if ! "$venv_python" -m pip install -v -U --force-reinstall uv 2>&1 | tee -a "$pip_log"; then
    echo "[setup_venv][ERROR] Failed to install 'uv' via pip." >&2
    echo "[setup_venv][ERROR] Your pip index/mirror may not provide the 'uv' package." >&2
    echo "[setup_venv][ERROR] See pip log: $pip_log" >&2
    echo "[setup_venv][ERROR] Fix by configuring pip, e.g. set PIP_INDEX_URL / PIP_EXTRA_INDEX_URL (or pip config set global.index-url ...), then re-run this script." >&2
    return 1
  fi

  if [ ! -x "$PROJECT_ROOT/.venv/bin/uv" ]; then
    echo "[setup_venv][ERROR] pip succeeded but $PROJECT_ROOT/.venv/bin/uv is missing. Check your venv scripts/bin path." >&2
    echo "[setup_venv][ERROR] See pip log: $pip_log" >&2
    return 1
  fi
  echo "$PROJECT_ROOT/.venv/bin/uv"
}

main() {
  local arg_python=""
  local arg_python_index=""
  local arg_list_pythons="0"

  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --python)
        shift || true
        arg_python="${1:-}"
        [ -n "$arg_python" ] || die "--python requires a path"
        ;;
      --python-index)
        shift || true
        arg_python_index="${1:-}"
        [ -n "$arg_python_index" ] || die "--python-index requires a number"
        ;;
      --list-pythons)
        arg_list_pythons="1"
        ;;
      *)
        die "Unknown argument: $1 (use --help)"
        ;;
    esac
    shift || true
  done

  if [ "$arg_list_pythons" = "1" ]; then
    print_python_candidates
    exit 0
  fi

  local os_like
  os_like="$(detect_os_like)"

  case "$os_like" in
    rhel) install_system_deps_rhel ;;
    debian) install_system_deps_debian ;;
    *) warn "Unknown distro; skipping system dependency installation. If pyicu fails, install ICU dev libs + pkg-config manually." ;;
  esac

  if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    log "Venv exists: $PROJECT_ROOT/.venv"
  else
    local py
    py="$(select_python "$arg_python" "$arg_python_index")"
    log "Using Python: $py ($(python_major_minor "$py"))"
    log "Creating venv: $PROJECT_ROOT/.venv"
    "$py" -m venv "$PROJECT_ROOT/.venv"
  fi

  local uv_bin
  if ! uv_bin="$(ensure_uv)"; then
    exit 1
  fi
  log "Using uv: $uv_bin"
  "$uv_bin" --version

  # Avoid hardlink warnings/slowdowns when cache & venv are on different filesystems.
  export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

  # Workaround for pyicu 2.15.3 C++ compilation issue (missing <memory> include)
  # IMPORTANT: Only set CXXFLAGS (not CPPFLAGS) to avoid breaking C packages (e.g., datrie).
  export CXXFLAGS="${CXXFLAGS:-"-include memory"}"

  log "Running: uv sync"
  "$uv_bin" sync

  log "Done."
}

main "$@"


