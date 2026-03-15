#!/usr/bin/env bash
# tui-input installer — detects agents and registers shell aliases
set -euo pipefail

GUARD_BEGIN="# >>> tui-input aliases >>>"
GUARD_END="# <<< tui-input aliases <<<"
KNOWN_AGENTS=(claude codex gemini aider goose)

# --- Helpers ----------------------------------------------------------------

info()  { printf "\033[1;34m[tui-input]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m[tui-input]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[tui-input]\033[0m %s\n" "$*"; }
error() { printf "\033[1;31m[tui-input]\033[0m %s\n" "$*" >&2; }

die() { error "$@"; exit 1; }

# --- Prerequisite checks ----------------------------------------------------

check_python() {
    local py=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            py="$cmd"
            break
        fi
    done
    [[ -n "$py" ]] || die "Python 3.10+ is required but not found."

    local ver
    ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local major minor
    major=${ver%%.*}
    minor=${ver##*.}
    if (( major < 3 || (major == 3 && minor < 10) )); then
        die "Python >= 3.10 required (found $ver)."
    fi
    info "Found Python $ver ($py)"
}

check_tmux() {
    command -v tmux &>/dev/null || die "tmux is required but not found. Install it first."
    info "Found tmux $(tmux -V | awk '{print $2}')"
}

# --- Install package ---------------------------------------------------------

install_package() {
    if command -v uv &>/dev/null; then
        info "Installing tui-input via uv..."
        uv tool install tui-input
    elif command -v pipx &>/dev/null; then
        info "Installing tui-input via pipx..."
        pipx install tui-input
    elif command -v pip &>/dev/null; then
        info "Installing tui-input via pip..."
        pip install --user tui-input
    else
        die "No package installer found. Install uv, pipx, or pip first."
    fi
    ok "tui-input installed successfully."
}

# --- Detect shell RC file ----------------------------------------------------

detect_rc_file() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")

    case "$shell_name" in
        zsh)  echo "${HOME}/.zshrc" ;;
        bash)
            if [[ -f "${HOME}/.bashrc" ]]; then
                echo "${HOME}/.bashrc"
            else
                echo "${HOME}/.bash_profile"
            fi
            ;;
        *)    echo "${HOME}/.profile" ;;
    esac
}

# --- Detect installed agents -------------------------------------------------

detect_agents() {
    local found=()
    for agent in "${KNOWN_AGENTS[@]}"; do
        if command -v "$agent" &>/dev/null; then
            found+=("$agent")
        fi
    done
    echo "${found[@]}"
}

# --- Alias management --------------------------------------------------------

remove_alias_block() {
    local rc_file="$1"
    if grep -q "$GUARD_BEGIN" "$rc_file" 2>/dev/null; then
        # Create backup before modifying
        cp "$rc_file" "${rc_file}.tui-input.bak"
        # Remove the alias block (including guard comments)
        sed -i.tmp "/$GUARD_BEGIN/,/$GUARD_END/d" "$rc_file"
        rm -f "${rc_file}.tmp"
        info "Removed existing tui-input alias block from $rc_file"
    fi
}

add_alias_block() {
    local rc_file="$1"
    shift
    local agents=("$@")

    if [[ ${#agents[@]} -eq 0 ]]; then
        warn "No supported agents detected. You can add aliases manually:"
        warn "  alias <agent>='tui-input <agent>'"
        return
    fi

    # Remove existing block first (idempotent)
    remove_alias_block "$rc_file"

    # Build alias block
    {
        echo ""
        echo "$GUARD_BEGIN"
        for agent in "${agents[@]}"; do
            echo "alias ${agent}='tui-input ${agent}'"
        done
        echo "$GUARD_END"
    } >> "$rc_file"

    ok "Aliases registered in $rc_file for: ${agents[*]}"
}

# --- Uninstall ---------------------------------------------------------------

uninstall() {
    local rc_file
    rc_file=$(detect_rc_file)
    remove_alias_block "$rc_file"
    ok "tui-input aliases removed. Run 'pip uninstall tui-input' to remove the package."
    exit 0
}

# --- Main --------------------------------------------------------------------

main() {
    if [[ "${1:-}" == "--uninstall" ]]; then
        uninstall
    fi

    info "Setting up tui-input..."
    check_python
    check_tmux
    install_package

    local rc_file
    rc_file=$(detect_rc_file)
    info "Shell RC file: $rc_file"

    local agents
    read -ra agents <<< "$(detect_agents)"
    if [[ ${#agents[@]} -gt 0 ]]; then
        info "Detected agents: ${agents[*]}"
    fi

    # Backup RC file
    if [[ -f "$rc_file" ]]; then
        cp "$rc_file" "${rc_file}.tui-input.bak"
        info "Backed up $rc_file → ${rc_file}.tui-input.bak"
    fi

    add_alias_block "$rc_file" "${agents[@]}"

    echo ""
    ok "Installation complete!"
    info "Restart your shell or run: source $rc_file"
    info "Then just type your agent name (e.g., 'claude') to use tui-input."
}

main "$@"
