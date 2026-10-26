# Mixed Reality Guidance for Simulated Colonoscopy Procedures

Mixed Reality system for evaluating spatial and orientation support during simulated colonoscopy, integrating Unity, Microsoft HoloLens 2, ROS 2, and NDI Aurora electromagnetic tracking.


## Table of Contents

1. [Project Description](#1-project-description)
2. [Installation](#2-installation)
3. [System Startup](#3-system-startup)
4. [Data Acquisition](#4-data-acquisition)
5. [Metrics Analysis](#5-metrics-analysis)
6. [Scripts Reference](#6-scripts-reference)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Project Description

The system integrates the following components:

- **Physical setup:** A colon phantom housed in a rigid support structure, used with a conventional colonoscope.
- **Electromagnetic tracking:** An NDI Aurora system for tracking the endoscopic tip and a calibration probe.
- **ROS 2:** Acquisition and processing of tracking data, and communication with Unity.
- **Unity:** Virtual environment and spatial/orientation guidance components.
- **Microsoft HoloLens 2:** Mixed Reality visualization during simulated colonoscopy.

### System Workflow

1. Connect and initialize the Aurora tracking system.
2. Start the ROS 2 tracking and communication pipeline.
3. Start the video stream, if required by the Unity application.
4. Launch the Unity-based MR application on HoloLens 2.
5. Perform the required calibration and registration procedures.
6. Perform the simulated colonoscopy in the selected experimental condition.
7. Record and save the tracking data.
8. Process the recorded data to compute the evaluation metrics.

---

## 2. Installation

This section describes the initial setup required on a new PC. Installation and system startup are separate: the steps in Section 2 generally need to be completed only once.

### 2.1 Prerequisites

### 2.1 Prerequisites

**Hardware**

- NDI Aurora electromagnetic tracking system
- Aurora calibration probe and endoscope tracking sensor
- Colon phantom, conventional colonoscope, and rigid support
- Microsoft HoloLens 2 with the MR application installed
- PC with a compatible connection to the Aurora control unit

**Software**

- Ubuntu 22.04 (native installation or WSL 2)
- ROS 2 Humble
- Python 3
- Git, `colcon`, and `rosdep`
- ROS–TCP Endpoint
- Additional Python dependencies required by the project

Install common ROS 2 workspace tools:

```bash
sudo apt update
sudo apt install -y git python3-pip python3-colcon-common-extensions python3-rosdep
```

If `rosdep` has not previously been initialized on this installation, run:

```bash
sudo rosdep init
```

Then run:

```bash
rosdep update
```


### 2.2 ROS 2 Workspace Setup

**Step 1 — Create a ROS 2 workspace**

Install ROS 2 Humble before proceeding. Open an Ubuntu terminal:

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
```

**Step 2 — Clone the project repository**

This project includes an adapted version of the `aurora_ndi_ros2_driver`, originally developed by Edoardo Guida.

```bash
cd ~/ros2_ws/src
git clone https://github.com/BeatriceBertolozzi00/MR-Colonoscopy-Simulation.git
```

> Check that the repository is accessible and contains the ROS 2 packages expected by `colcon`. If the repository is private, authorized GitHub access is required.

**Step 3 — Install ROS–TCP Endpoint**

ROS–TCP Endpoint provides the ROS 2 side of the communication interface with Unity:

```bash
cd ~/ros2_ws/src
git clone -b main-ros2 https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git ros_tcp_endpoint
```

**Step 4 — Build the ROS 2 workspace**

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Check that the required ROS 2 packages can be found:

```bash
ros2 pkg list | grep -E 'aurora|ros_tcp_endpoint'
```

Package names may differ from repository folder names; verify the actual package names if a package is missing.

**Step 5 — Configure the Aurora tracking system**

```bash
cd ~/ros2_ws/src/MR-Colonoscopy-Simulation
nano config/aurora_config.yaml
```

Check the actual YAML parameter names, including:

- **Serial port:** Aurora control-unit connection (for example, `/dev/ttyUSB0` if that is the detected device).
- **Port 0A:** Calibration Aurora probe.
- **Port 0B:** Endoscope tracking sensor.
- **ROM file:** Absolute path to the ROM file required by the configured tool.
- **Frequency:** Confirm the configured tracking/publishing rate in the driver; the nominal rate used in this project is 40 Hz.

From the repository root, obtain the absolute ROM path:

```bash
realpath rom/610029_AuroraMini6DOF_1.8x9mm/610029-6DOF.rom
```

Use the returned path under `tool_rom_files` in `config/aurora_config.yaml`. This path is specific to the installation and must be updated when the repository is moved.

Confirm that the ROM file exists and inspect the configured ports:

```bash
ls -l rom/610029_AuroraMini6DOF_1.8x9mm/610029-6DOF.rom
grep -n -A 8 'tool_rom_files' config/aurora_config.yaml
```

**Step 6 — Configure serial port permissions**

First identify the serial device. The name may differ between computers:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

If the device belongs to the `dialout` group, grant your user access:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and log back in. Verify the group membership and device permissions:

```bash
groups
ls -l /dev/ttyUSB0
```

Replace `/dev/ttyUSB0` with the device found on your machine. This permission step does not replace USB passthrough configuration when using WSL 2.


## 3. System Startup

### 3.1 ROS 2 Tracking and Communication Pipeline

1. Connect the calibration probe to Aurora port **0A**.
2. Connect the endoscope tracking sensor to Aurora port **0B**.
3. Connect the Aurora control unit to the PC and power it on.
4. Verify that the configured serial device is available in Ubuntu.

Start the pipeline using the project startup script:

```bash
bash ~/ros2_ws/src/MR-Colonoscopy-Simulation/scripts/startup/bringup_aurora_unity.sh
```

The intended pipeline consists of:

- **Aurora driver:** Reads electromagnetic tracking data.
- **Pose processing/publisher:** Converts and publishes poses used by the Unity application.
- **ROS–TCP Endpoint:** Provides the ROS 2–Unity TCP communication interface.

> Verify that the current `bringup_aurora_unity.sh` actually starts all three processes, and that the script exists at the path shown above. Keep it running during the simulation; use `Ctrl+C` for shutdown if the script handles child processes correctly.

**Expected ROS 2 topics (confirm against the running nodes)**

| Topic | Intended content |
|---|---|
| `/aurora/sensor0` | Tracking data from the calibration probe |
| `/aurora/sensor1` | Tracking data from the endoscope sensor |
| `/aurora_pose_1` | Processed pose associated with sensor 0 |
| `/aurora_pose_2` | Processed pose associated with sensor 1; inspect any implemented fallback behavior |

A fallback to sensor 0 must **not** be interpreted as valid measured tracking of the endoscope sensor when computing objective performance metrics.

### 3.2 Network and Video Streaming

The ROS 2 PC (or Windows/WSL host) and HoloLens 2 must be connected through a network that allows the application to reach the services hosted on the PC.

**Step 1 — Identify the reachable PC address**

On a native Ubuntu installation:

```bash
hostname -I
```

Select the network interface accessible from HoloLens 2. If using WSL 2 with its default NAT networking, the IP reported by this command may be an internal WSL address and **may not be directly reachable from HoloLens 2**. In that case, configure networking appropriately and use the externally reachable host address.

**Step 2 — Check ROS–TCP communication**

Ensure that the ROS–TCP Endpoint listens on the configured interface and port, and that the Unity ROS–TCP Connector uses the corresponding address and port. Check relevant firewall rules if the connection fails.

**Step 3 — Start the video stream if required**

The project also uses an MJPEG video client in Unity. When its HTTP server is enabled, the Unity client connects to:

```text
http://<PC_IP>:5000/video_feed
```

The Unity client reads JPEG frames from the MJPEG stream and updates the displayed video. **This video connection is separate from the ROS–TCP Endpoint.**

> **Complete before publication:** Specify the command/script that starts the MJPEG server, whether it is included in the main startup script, and any camera source configuration. Do not assume the video server is started automatically.

### 3.3 Unity and HoloLens Startup

1. Make sure the ROS 2 pipeline is running.
2. Start the video streaming server if required by the application.
3. Turn on HoloLens 2 and connect it to the configured network.
4. Launch the installed Unity Mixed Reality application.
5. Verify that the application receives the expected ROS 2 poses.
6. Verify that the video is displayed, if the video stream is enabled.
7. Perform calibration and registration before starting a trial.

> **Complete before publication:** Describe the actual application deployment method, the name of the HoloLens app, the Unity scene, and the steps used to start the relevant interfaces.

### 3.4 Calibration and Registration

Perform the procedures required by the final Unity application and experimental protocol:

- **Aurora probe-tip calibration:** Determine the calibration probe tip location relative to its tracked sensor frame.
- **Point-based registration:** Establish the spatial transformation between the relevant physical/tracking and virtual reference frames.
- **QR-code-based alignment:** Apply the appropriate alignment procedure for the Mixed Reality visualization.

Verify the final alignment of the virtual colon phantom with the physical setup before proceeding. The exact UI controls, sequence, inputs, and file persistence behavior should be documented from the Unity implementation.

### 3.5 System Verification

Open a second Ubuntu terminal:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
```

**Check the running nodes and topics:**

```bash
ros2 node list
ros2 topic list
```

**Check sensor messages:**

```bash
ros2 topic echo /aurora/sensor0 --once
ros2 topic echo /aurora/sensor1 --once
```

**Measure the ROS 2 topic publishing rates:**

```bash
ros2 topic hz /aurora/sensor0
```

In a separate terminal, if necessary:

```bash
ros2 topic hz /aurora/sensor1
```

The rate should be consistent with the configured system frequency; 40 Hz is a nominal target, not a guaranteed observed rate.

**Check processed pose topics:**

```bash
ros2 topic info /aurora_pose_1
ros2 topic info /aurora_pose_2
```

Finally, confirm inside HoloLens 2 that the tracked tip moves consistently with the physical sensor and that the virtual colon is correctly aligned with the phantom.

---

## 4. Data Acquisition

The tracking data recorded during simulated colonoscopy trials are used for offline computation of objective navigation metrics.

### 4.1 Acquisition Procedure

1. Verify that the system has initialized successfully and calibration/registration have been completed.
2. Select the intended experimental condition (conventional or the relevant MR configuration).
3. Start the project's data acquisition procedure before the trial.
4. Perform the insertion phase of the simulated colonoscopy.
5. Stop acquisition at the defined end of the trial.
6. Save the recorded data and associate them with the correct trial/condition identifier.

> **Complete before publication:** Insert the actual acquisition command or Unity control, the recording start/stop criteria, the file format, the output directory, and an example filename. The README must document what the repository actually saves, not a hypothetical CSV or ROS bag.

### 4.2 Data Validation

Before metric computation, verify:

- That timestamps and sensor poses have been recorded for the intended trial.
- That tracking validity and missing samples can be identified.
- That sensor identities and reference frames have been interpreted correctly.
- That any sensor-0 fallback used for display or testing is **not counted as genuine endoscope tracking**.
- That the trial meets the data completeness criteria defined in the experimental protocol.

For replication of the thesis experiments, document the tracking-validity threshold (reported as at least **90%** in the project protocol) and the successful-completion criteria, including how invalid samples and excluded trials are handled.

---

## 5. Metrics Analysis

The recorded tracking data are processed offline to evaluate navigation performance during the **insertion phase** of the simulated colonoscopy.

### 5.1 Objective Metrics

The objective analysis includes the metrics used in the thesis:

- **Insertion time**
- **Progression efficiency**
- **Centerline-related navigation metric** (insert the exact metric name used in the analysis script)
- **Backward-motion metric** (insert the exact metric name used in the analysis script)

> **Complete before publication:** For each metric, add its definition, units, input columns, preprocessing steps, executable script, and output format. Use the same metric names and definitions as in the thesis and implementation.

### 5.2 Statistical Analysis

For the repeated-measures comparison of the experimental configurations, the thesis used non-parametric procedures, including the **Friedman test** for an overall comparison and **paired Wilcoxon signed-rank tests** for applicable post-hoc comparisons.

Document the actual post-hoc correction, significance threshold, and treatment of incomplete or excluded trials by referencing the analysis code. Avoid implying that every pairwise comparison was performed irrespective of the global test result.

### 5.3 Subjective Assessment

Where the associated files are provided, explain how **SUS** and **SURG-TLX** questionnaire results are processed. Keep subjective questionnaire analysis distinct from the objective tracking-based metrics.

---

## 6. Scripts Reference

| File / component | Purpose |
|---|---|
| `config/aurora_config.yaml` | Aurora serial connection, sensor-port configuration, and tool ROM paths |
| `scripts/startup/bringup_aurora_unity.sh` | Entry point for the ROS 2 tracking/communication startup pipeline; verify the actual launched processes |
| `rom/610029_AuroraMini6DOF_1.8x9mm/610029-6DOF.rom` | Device-specific ROM file referenced by the Aurora configuration |
| Pose publisher (**path to confirm**) | Processes tracking data and publishes the Unity-facing pose topics |
| MJPEG server (**path to confirm**) | Exposes the video stream consumed by the Unity client |
| Acquisition script/component (**path to confirm**) | Records trial data |
| Metrics analysis scripts (**paths to confirm**) | Computes and exports the objective evaluation metrics |

Replace the entries marked *path to confirm* with actual repository-relative paths before publication.

---

## 7. Troubleshooting

| Problem | What to check |
|---|---|
| Aurora serial connection fails | Correct port name, control-unit power, USB connection/passthrough, and serial permissions |
| ROM file cannot be opened | File exists and `tool_rom_files` contains the correct **absolute** path |
| ROS 2 package not found | Workspace was built successfully and `~/ros2_ws/install/setup.bash` was sourced |
| Tracking topic is missing | Driver logs, Aurora initialization, sensor-port configuration, and node status |
| Unity cannot connect to ROS 2 | Endpoint process, network-reachable host IP, TCP port, WSL 2 networking, and firewalls |
| Unity receives a pose but it is incorrect | Sensor mapping, coordinate transforms, calibration, and potential fallback behavior |
| Video does not appear in Unity | MJPEG server is running and `http://<PC_IP>:5000/video_feed` is reachable from the client network |
| Recorded tracking data are incomplete | Tracking validity, acquisition start/stop conditions, timestamps, and invalid/fallback sample handling |

---

### External References

- [Unity ROS–TCP Endpoint](https://github.com/Unity-Technologies/ROS-TCP-Endpoint)
- [Unity ROS–TCP Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector)
- [Unity Robotics Hub — ROS–Unity setup](https://github.com/Unity-Technologies/Unity-Robotics-Hub/blob/main/tutorials/ros_unity_integration/setup.md)
- [Microsoft — USB devices in WSL](https://learn.microsoft.com/windows/wsl/connect-usb)
- [Microsoft — WSL networking](https://learn.microsoft.com/windows/wsl/networking)
