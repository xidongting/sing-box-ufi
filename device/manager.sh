#!/system/bin/sh
set -eu
umask 077
HOME_DIR=${SBU_HOME:-/data/local/tmp/sing-box-ufi}
BOOT_FILE=${SBU_BOOT:-/sdcard/ufi_tools_boot.sh}
fail() { echo "$*" >&2; exit 1; }
[ ! -L "$HOME_DIR" ] || fail 'Refusing symlink data directory'
mkdir -p "$HOME_DIR"
chmod 700 "$HOME_DIR"
cd "$HOME_DIR"
case "${1:-}" in
    status|config|logs|env) ;;
    *)
        mkdir .lock 2>/dev/null || fail 'Another operation is running (.lock); do not retry concurrently'
        trap 'rm -f "${tmp:-}"; rmdir "$HOME_DIR/.lock"' EXIT
        trap 'exit 1' HUP INT TERM
        ;;
esac
running() {
    [ -f sing-box.pid ] || return 1
    pid=$(cat sing-box.pid)
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$HOME_DIR/sing-box" ] || return 1
    kill -0 "$pid" 2>/dev/null
}
stop() {
    if running; then
        kill "$pid"
        count=0
        while running; do
            count=$((count + 1))
            [ "$count" -lt 10 ] || fail 'Process did not stop; leaving binary untouched'
            sleep 1
        done
    fi
    rm -f sing-box.pid
}
start() {
    if running; then echo 'Already running'; return; fi
    [ -f config.json ] || fail 'Provide config.json before starting'
    ./sing-box check -c config.json
    # shortcut: rotate only on start; add bounded live logging if long-running logs exhaust storage.
    if [ -f sing-box.log ] && [ "$(wc -c < sing-box.log)" -gt 4194304 ]; then
        mv sing-box.log sing-box.log.old
    fi
    nohup "$HOME_DIR/sing-box" run -c config.json </dev/null >>sing-box.log 2>&1 &
    echo "$!" > sing-box.pid
    sleep 1
    running || { tail -n 30 sing-box.log >&2; fail 'sing-box exited; see log'; }
    echo started
}
install_core() {
    case "$1" in ''|*[!0-9a-f]*) fail 'Invalid SHA-256' ;; esac
    [ "${#1}" = 64 ] || fail 'Invalid SHA-256 length'
    [ -f incoming ] && [ ! -L incoming ] || fail 'Missing incoming binary'
    printf '%s  incoming\n' "$1" | sha256sum -c -
    chmod 700 incoming
    # Verify executability, not configuration compatibility.
    ./incoming version
    stop
    mv incoming sing-box
    echo 'Installed; stopped. Start manually.'
}
set_autostart() {
    [ ! -L "$BOOT_FILE" ] || fail 'Refusing symlink boot script'
    tmp=$(mktemp "${BOOT_FILE}.XXXXXX")
    {
        printf '#!/system/bin/sh\n'
        if [ "$1" = on ]; then
            printf "[ ! -f '%s/manager.sh' ] || sh '%s/manager.sh' start >/dev/null 2>&1 & # sing-box-ufi\n" "$HOME_DIR" "$HOME_DIR"
        fi
        if [ -f "$BOOT_FILE" ]; then
            sed '1{/^#!/d;}; /# sing-box-ufi$/d' "$BOOT_FILE"
        fi
    } > "$tmp"
    # /sdcard may not support chmod; UFI Tools invokes this script with sh.
    # Rename preserves the previous complete script if writing the replacement fails.
    if [ -f "$BOOT_FILE" ]; then
        chmod "$(stat -c '%a' "$BOOT_FILE" 2>/dev/null || echo 600)" "$tmp" 2>/dev/null || true
    fi
    mv "$tmp" "$BOOT_FILE"
}
case "${1:-}" in
    status)
        if running; then echo "running pid=$pid"; else echo stopped; fi
        [ ! -x sing-box ] || ./sing-box version
        if [ -f "$BOOT_FILE" ] && grep -q '# sing-box-ufi$' "$BOOT_FILE"; then echo autostart=on; else echo autostart=off; fi
        ;;
    autostart)
        case "${2:-}" in on|off) set_autostart "$2" ;; *) fail 'Expected on or off' ;; esac
        ;;
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    install) install_core "${2:-}" ;;
    download)
        url=${2:-}
        case "$url" in
            https://github.com/*/*/releases/download/core-v*/sing-box-android-arm|https://github.com/*/*/releases/download/core-v*/sing-box-android-arm64) ;;
            *) fail 'Expected GitHub core release asset URL' ;;
        esac
        curl_bin=$(command -v curl || true)
        if [ -z "$curl_bin" ]; then curl_bin=/data/data/com.minikano.f50_sms/files/curl; fi
        [ -x "$curl_bin" ] || fail 'curl missing; open UFI Tools terminal or install curl first'
        tmp=$(mktemp "$HOME_DIR/.download.XXXXXX")
        "$curl_bin" --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 65 --output "$tmp" "$url"
        mv "$tmp" incoming
        install_core "${3:-}"
        ;;
    env)
        id
        printf 'Android='; getprop ro.build.version.release
        printf 'SDK='; getprop ro.build.version.sdk
        printf 'ABI='; getprop ro.product.cpu.abilist
        printf 'Model='; getprop ro.product.model
        printf 'Working directory=%s\n' "$HOME_DIR"
        for tool in nohup sha256sum base64 curl; do command -v "$tool" || true; done
        ;;
    uninstall)
        case "${2:-keep}" in keep|purge) ;; *) fail 'Expected keep or purge' ;; esac
        stop
        set_autostart off
        rm -f sing-box incoming sing-box.log sing-box.log.old
        if [ "${2:-keep}" = purge ]; then rm -f config.json; fi
        echo 'Removed core; manager remains for reinstall. External files are untouched.'
        ;;
    save)
        tmp=$(mktemp "$HOME_DIR/.config.XXXXXX")
        cat > "$tmp"
        ./sing-box check -c "$tmp"
        mv "$tmp" config.json
        echo 'Saved; restart manually to apply'
        ;;
    config) [ ! -f config.json ] || cat config.json ;;
    check) ./sing-box check -c config.json ;;
    logs) [ ! -f sing-box.log ] || tail -n 200 sing-box.log ;;
    *) fail 'Unknown command' ;;
esac
