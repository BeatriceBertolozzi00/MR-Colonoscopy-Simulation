
#!/usr/bin/env bash

# ============================================================
# MR Colonoscopy Simulation — ROS 2 Startup Pipeline
#
# T1) NDI Aurora tracking driver
# T2) Python pose publisher
#     - subscribes to /aurora/sensor0 and /aurora/sensor1
#     - applies sensor0 tip offset -> /aurora_pose_1
#     - uses valid sensor1, otherwise sensor0 -> /aurora_pose_2
# T3) ROS-TCP Endpoint for Unity / HoloLens 2
#
# The Aurora ROM path is resolved automatically.
# ============================================================

set -euo pipefail

# ======================
# CONFIGURATION
# ======================

DEBUG=1
ROS_DISTRO="humble"

# ROS 2 workspace
WS_DIR="${HOME}/ros2_ws"
WS_SETUP="${WS_DIR}/install/setup.bash"

# Resolve repository location automatically
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

# Aurora ROS 2 driver
AURORA_PKG="aurora_ndi_ros2_driver"
AURORA_LAUNCH="aurora_pub.launch.py"

# Original YAML template in the repository
AURORA_CONFIG_TEMPLATE="${PROJECT_DIR}/config/aurora_config.yaml"

# ROM file included in the repository
ROM_FILE="${PROJECT_DIR}/rom/610029_AuroraMini6DOF_1.8x9mm/610029-6DOF.rom"

# Aurora serial interface
AURORA_SERIAL_BYID="/dev/ttyUSB0"

# Python pose publisher
SCRIPTS_DIR="${PROJECT_DIR}/scripts/tracking"
CALIB_SCRIPT="aurora_sensor0_tip_and_sensor1_publisher.py"

# ROS-TCP Endpoint
ROS_TCP_PKG="ros_tcp_endpoint"
ROS_TCP_EXEC="default_server_endpoint"
ROS_IP_VALUE="0.0.0.0"
ROS_TCP_PORT="10000"

# Log directory
LOG_DIR="${HOME}/.ros/aurora_unity_logs"
mkdir -p "$LOG_DIR"

# Runtime YAML generated for this computer
AURORA_CONFIG="${LOG_DIR}/aurora_config_runtime.yaml"


# ======================
# LOGGING AND CLEANUP
# ======================

log_dbg() {
    if [[ "${DEBUG}" -eq 1 ]]; then
        echo "[DBG] $*" >&2
    fi
}

CHILD_PIDS=()

cleanup() {
    trap - EXIT INT TERM

    echo -e "\n[STOP] Closing started processes..."

    local pid

    for pid in "${CHILD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    for pid in "${CHILD_PIDS[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM


# ======================
# SERIAL PORT DETECTION
# ======================

auto_detect_serial() {

    if [[ -n "$AURORA_SERIAL_BYID" &&
          -e "$AURORA_SERIAL_BYID" ]]; then

        log_dbg "Found serial interface: $AURORA_SERIAL_BYID"
        echo "$AURORA_SERIAL_BYID"
        return
    fi

    # Try stable device paths
    if ls /dev/serial/by-id/* >/dev/null 2>&1; then

        local cand

        cand=$(ls /dev/serial/by-id/* 2>/dev/null |
               head -n1 || true)

        if [[ -n "$cand" ]]; then
            log_dbg "Found serial device: $cand"
            echo "$cand"
            return
        fi
    fi

    # Fallback to USB/ACM devices
    local dev

    dev=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null |
          head -n1 || true)

    if [[ -n "$dev" ]]; then
        log_dbg "Found fallback device: $dev"
        echo "$dev"
    fi
}


# ======================
# ROS 2 ENVIRONMENT
# ======================

set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"

if [[ -f "$WS_SETUP" ]]; then
    source "$WS_SETUP"
else
    echo "[ERR] ROS 2 workspace setup not found: $WS_SETUP" >&2
    echo "      Build the workspace before running this script." >&2
    exit 1
fi

set -u


# ======================
# INITIAL CHECKS
# ======================

[[ -f "$AURORA_CONFIG_TEMPLATE" ]] || {
    echo "[ERR] Aurora YAML template not found:" >&2
    echo "      $AURORA_CONFIG_TEMPLATE" >&2
    exit 1
}

[[ -f "$ROM_FILE" ]] || {
    echo "[ERR] Aurora ROM file not found:" >&2
    echo "      $ROM_FILE" >&2
    exit 1
}

[[ -f "$SCRIPTS_DIR/$CALIB_SCRIPT" ]] || {
    echo "[ERR] Python pose publisher not found:" >&2
    echo "      $SCRIPTS_DIR/$CALIB_SCRIPT" >&2
    exit 1
}

ros2 pkg prefix "$AURORA_PKG" >/dev/null || {
    echo "[ERR] Aurora ROS 2 package not available." >&2
    exit 1
}

ros2 pkg prefix "$ROS_TCP_PKG" >/dev/null || {
    echo "[ERR] ROS-TCP Endpoint package not available." >&2
    exit 1
}


# ======================
# GENERATE AURORA YAML
# ======================

echo "[INFO] Configuring Aurora ROM path..."

# Replace the placeholder with the ROM absolute path
# for the current computer.
# The original repository YAML is not modified.

python3 - \
    "$AURORA_CONFIG_TEMPLATE" \
    "$AURORA_CONFIG" \
    "$ROM_FILE" <<'PY'

import sys
from pathlib import Path

template_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
rom_path = Path(sys.argv[3]).resolve()

placeholder = "__AURORA_ROM_PATH__"

content = template_path.read_text()

if content.count(placeholder) != 1:
    raise SystemExit(
        "[ERR] Expected exactly one "
        "__AURORA_ROM_PATH__ placeholder in the YAML."
    )

content = content.replace(
    placeholder,
    str(rom_path)
)

output_path.write_text(content)

print("[OK] Runtime Aurora configuration generated.")
print("[INFO] ROM file:", rom_path)
print("[INFO] Runtime YAML:", output_path)

PY


# ======================
# CONFIGURATION DEBUG
# ======================

log_dbg "PROJECT_DIR   = $PROJECT_DIR"
log_dbg "WS_DIR        = $WS_DIR"
log_dbg "ROM_FILE      = $ROM_FILE"
log_dbg "AURORA_CONFIG = $AURORA_CONFIG"
log_dbg "SCRIPTS_DIR   = $SCRIPTS_DIR"
log_dbg "LOG_DIR       = $LOG_DIR"


# ======================
# T1: AURORA DRIVER
# ======================

SERIAL_PORT=$(auto_detect_serial || true)

if [[ -n "${SERIAL_PORT:-}" ]]; then

    echo "[INFO] Serial port: $SERIAL_PORT"

    SERIAL_ARG=("serial_port:=${SERIAL_PORT}")

else

    echo "[WARN] No serial interface detected."
    echo "       Driver will use its configured default."

    SERIAL_ARG=()

fi


echo "[RUN][T1] Starting Aurora driver..."

ros2 launch "$AURORA_PKG" "$AURORA_LAUNCH" \
    "config_file:=${AURORA_CONFIG}" \
    "${SERIAL_ARG[@]}" \
    >"${LOG_DIR}/T1_aurora_driver.log" 2>&1 &

CHILD_PIDS+=("$!")


# Wait for the Aurora publisher node
echo "[INFO] Waiting for Aurora node..."

AURORA_READY=0

for attempt in $(seq 1 20); do

    if ros2 node list 2>/dev/null |
       grep -Eq '(^|/)aurora_publisher_node$'; then

        AURORA_READY=1
        break
    fi

    if ! kill -0 "${CHILD_PIDS[0]}" 2>/dev/null; then
        break
    fi

    sleep 1
done

if [[ "$AURORA_READY" -ne 1 ]]; then

    echo "[ERR] Aurora publisher node is not active." >&2
    echo "      Check ${LOG_DIR}/T1_aurora_driver.log" >&2
    exit 1

fi

echo "[OK] Aurora publisher node detected."


# ======================
# T2: PYTHON POSE PUBLISHER
# ======================

echo "[RUN][T2] Starting Python pose publisher..."

(
    cd "$SCRIPTS_DIR"
    exec python3 "$CALIB_SCRIPT"
) >"${LOG_DIR}/T2_camera_adapter.log" 2>&1 &

CHILD_PIDS+=("$!")


# ======================
# T3: ROS-TCP ENDPOINT
# ======================

echo "[RUN][T3] Starting ROS-TCP Endpoint..."
echo "[INFO] TCP IP: $ROS_IP_VALUE"
echo "[INFO] TCP port: $ROS_TCP_PORT"

ros2 run "$ROS_TCP_PKG" "$ROS_TCP_EXEC" \
    --ros-args \
    -p ROS_IP:="${ROS_IP_VALUE}" \
    -p ROS_TCP_PORT:="${ROS_TCP_PORT}" \
    >"${LOG_DIR}/T3_unity_endpoint.log" 2>&1 &

CHILD_PIDS+=("$!")


# ======================
# STARTUP VERIFICATION
# ======================

sleep 2

for pid in "${CHILD_PIDS[@]}"; do

    if ! kill -0 "$pid" 2>/dev/null; then

        echo "[ERR] A pipeline process exited." >&2
        echo "      Check the log files in $LOG_DIR" >&2
        exit 1

    fi

done


# ======================
# PIPELINE STATUS
# ======================

echo ""
echo "============================================"
echo "[OK] ROS 2 pipeline processes started."
echo "============================================"
echo ""
echo "Aurora driver:"
echo "  ${LOG_DIR}/T1_aurora_driver.log"
echo ""
echo "Python pose publisher:"
echo "  ${LOG_DIR}/T2_camera_adapter.log"
echo ""
echo "Unity ROS-TCP Endpoint:"
echo "  ${LOG_DIR}/T3_unity_endpoint.log"
echo ""
echo "Runtime Aurora configuration:"
echo "  ${AURORA_CONFIG}"
echo ""
echo "Expected ROS 2 topics:"
echo "  /aurora/sensor0"
echo "  /aurora/sensor1"
echo "  /aurora_pose_1"
echo "  /aurora_pose_2"
echo ""
echo "Press CTRL+C to stop the pipeline."
echo ""

# Stop remaining processes if one process exits.
wait -n "${CHILD_PIDS[@]}" || true
