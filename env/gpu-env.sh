#!/usr/bin/env bash
# GPU defaults and launch-time overrides shared by the SCOBA scripts.
SC2_DEFAULT_GAME_GPU="${SC2_DEFAULT_GAME_GPU:-0000:09:00.0}"
SC2_DEFAULT_FG_GPU="${SC2_DEFAULT_FG_GPU:-0000:03:00.0}"

sc2_dri_prime_for_pci() {
    local gpu="$1"
    local dri="pci-${gpu//:/_}"
    printf '%s\n' "${dri//./_}"
}

sc2_apply_gpu_env() {
    local game_gpu="${SCOBA_GAME_GPU:-$SC2_DEFAULT_GAME_GPU}"
    if [ -n "${SCOBA_GAME_GPU:-}" ] || [ -z "${DRI_PRIME:-}" ]; then
        DRI_PRIME="$(sc2_dri_prime_for_pci "$game_gpu")"
        export DRI_PRIME
    fi
    if [ -n "${LSFGVK_ENV:-}" ]; then
        LSFGVK_GPU="${LSFGVK_GPU:-${SCOBA_FG_GPU:-$SC2_DEFAULT_FG_GPU}}"
        export LSFGVK_GPU
    fi
}