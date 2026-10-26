# MR Colonoscopy Simulation — Setup & Operating Guide

Step-by-step instructions to **install, configure and run** the system on a new PC.

**Code:** [MR-Colonoscopy-Simulation — `ros2-package` branch](https://github.com/BeatriceBertolozzi00/MR-Colonoscopy-Simulation/tree/ros2-package)  
**Unity project:** `Tesi_simulazione_colonoscopy_Unity.zip` (shared separately with wetransfer).  
**Video server:** separate component; obtain its script and startup command from the project maintainer.

![Tracking and endoscopic video connections](docs/images/ros-video-overview.png)

> **Two independent connections:** tracking uses **ROS–TCP / port 10000**; endoscopic video uses **HTTP MJPEG / port 5000**. Both must be configured when the PC IP changes.

## 1. Requirements

**Hardware**
- PC with Windows + Ubuntu 22.04 (WSL 2), or native Ubuntu 22.04.
- NDI Aurora, field generator, calibration probe (**port 0A**) and endoscope sensor (**port 0B**).
- Colon phantom, support and colonoscope.
- Video capture device, endoscopic video source and HoloLens 2.
- PC and HoloLens connected to a network that permits communication.

**Software**
- [ROS 2 Humble](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html), Python 3, Git, `colcon`, `rosdep`.
- ROS–TCP Endpoint (installed in Part A); ROS–TCP Connector (included in the Unity project).
- Unity Hub + Editor version in `ProjectSettings/ProjectVersion.txt`.
- Visual Studio with the components required to build/deploy the existing HoloLens UWP project.
- MJPEG video server and capture-device drivers (Part C).

---

## Part A — ROS 2 & Aurora Tracking

**Run A1–A5 once on each new PC. Run A6–A7 for each session.**

### A1. Install ROS 2 tools — once

1. Install **ROS 2 Humble** for Ubuntu 22.04 using the link above.
2. In an **Ubuntu / WSL terminal**, run:

```bash
sudo apt update
sudo apt install -y git python3-pip python3-colcon-common-extensions python3-rosdep
```

3. Initialize `rosdep` **only if not already initialized**, then update:

```bash
sudo rosdep init    # skip if already initialized
rosdep update
```

### A2. Download the ROS 2 packages — once

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src

git clone -b ros2-package --single-branch https://github.com/BeatriceBertolozzi00/MR-Colonoscopy-Simulation.git

git clone -b main-ros2 https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git ros_tcp_endpoint
```

**Use branch `ros2-package`.**

### A3. Build the workspace — once / after code changes

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
ros2 pkg list | grep -E 'aurora_ndi_ros2_driver|ros_tcp_endpoint'
```

Expected: both packages are listed.

### A4. Connect Aurora to Ubuntu / WSL — new PC

1. Connect the **Aurora control unit** to the PC and turn it on.
2. If using **WSL 2**, install [`usbipd-win`](https://learn.microsoft.com/windows/wsl/connect-usb) on Windows. Open **PowerShell (Administrator)**:

```powershell
usbipd list
usbipd bind --busid <BUS_ID>
```

3. With Ubuntu/WSL running, attach the Aurora device in **PowerShell**:

```powershell
usbipd attach --wsl --busid <BUS_ID>
```

4. In **Ubuntu**, locate the serial port:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
ls -l /dev/serial/by-id/* 2>/dev/null
```

5. If permission is denied and the device uses the `dialout` group:

```bash
sudo usermod -aG dialout "$USER"
```

Sign out and back in once. **Replace `<BUS_ID>` with the Aurora USB bus ID** shown by `usbipd list`.

### A5. Check PC-specific ROS configuration — new PC

1. Open the project configuration:

```bash
cd ~/ros2_ws/src/MR-Colonoscopy-Simulation
nano config/aurora_config.yaml
```

2. Find `tool_rom_files`. It **must contain exactly one** `__AURORA_ROM_PATH__` placeholder, for example:

```yaml
tool_rom_files:
  - "__AURORA_ROM_PATH__"
```

3. Keep the existing YAML indentation. Do **not** paste an old `/home/...` path: the startup script generates the ROM path automatically.
4. Check the installed ROM file:

```bash
ls -l rom/610029_AuroraMini6DOF_1.8x9mm/610029-6DOF.rom
grep -n -A 5 'tool_rom_files' config/aurora_config.yaml
```

5. Open `scripts/startup/bringup_aurora_unity.sh`. Check these values **only if different on this PC**:

| Setting | Default | Change when... |
|---|---|---|
| `WS_DIR` | `${HOME}/ros2_ws` | The ROS workspace has another location |
| `ROS_DISTRO` | `humble` | The project has been ported and tested on another ROS distribution (Humble is the baseline) |
| `AURORA_SERIAL_BYID` | `/dev/ttyUSB0` | Aurora uses another serial port; prefer `/dev/serial/by-id/...` |
| `ROM_FILE` | ROM inside `rom/` | The connected Aurora tool requires a different ROM |

**Keep `ROS_IP_VALUE="0.0.0.0"` and `ROS_TCP_PORT="10000"`** in the startup script. The **new PC IP is set in Unity** (Part B), not here.

### A6. Connect sensors — every session

1. Place the Aurora field generator near the phantom.
2. Connect the **calibration probe to 0A**.
3. Connect the **endoscope sensor to 0B**.
4. Power on Aurora and confirm the serial device is visible in Ubuntu (repeat A4 after reconnecting WSL USB, if necessary).

### A7. Start and check ROS 2 — every session

1. In an **Ubuntu terminal**, run:

```bash
bash ~/ros2_ws/src/MR-Colonoscopy-Simulation/scripts/startup/bringup_aurora_unity.sh
```

2. Expected output: `[OK] ROS 2 pipeline processes started.`  
   The script starts **T1 Aurora driver**, **T2 Python pose publisher**, **T3 ROS–TCP Endpoint**.
3. In a **second Ubuntu terminal**, check:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 topic list
ros2 topic echo /aurora/sensor1 --once
ros2 topic hz /aurora/sensor1
```

Expected topics: `/aurora/sensor0`, `/aurora/sensor1`, `/aurora_pose_1`, `/aurora_pose_2`.

4. If an error occurs, read the logs:

```bash
tail -n 40 ~/.ros/aurora_unity_logs/T1_aurora_driver.log
tail -n 40 ~/.ros/aurora_unity_logs/T2_camera_adapter.log
tail -n 40 ~/.ros/aurora_unity_logs/T3_unity_endpoint.log
```

5. **Leave the first terminal open** during the session. Use `Ctrl+C` to stop.

> **Tracking validity:** `/aurora_pose_2` can fall back to sensor 0 if sensor 1 is invalid. Check **sensor 1 itself** before interpreting the displayed pose as valid endoscope tracking.

---

## Part B — Unity & HoloLens 2

**Complete B1–B5 on a new PC or whenever its IP changes.**

### B1. Open the Unity project — once

1. Obtain `Tesi_simulazione_colonoscopy_Unity.zip` from wetransfer.
2. **Extract** the archive. Locate the folder containing `Assets/`, `Packages/`, `ProjectSettings/`.
3. Check `ProjectSettings/ProjectVersion.txt` and install **that Unity Editor version** in Unity Hub.
4. In **Unity Hub → Add → Add project from disk**, select that folder.
5. Open the main application scene under `Assets/` (use the scene supplied with the project). Allow Unity to import all packages.

**Do not remove `.meta` files.** Unity regenerates `Library/` automatically.

### B2. Find the new PC IP — new PC / network change

1. On the **Windows PC**, open **Command Prompt**.
2. Run:

```cmd
ipconfig
```

3. Copy the **Wi-Fi/Ethernet IPv4 address** on the HoloLens network: call it `<PC_IP>`.
4. Do **not** use the internal WSL IP unless the headset can reach it directly.

### B3. Set Unity ROS settings — new PC / IP change

![Illustrative guide to Unity ROS and video settings](docs/images/unity-network-settings.png)

1. In Unity, open **Robotics → ROS Settings** from the top menu.
2. Set **ROS IP Address** = `<PC_IP>` (the PC running ROS 2).
3. Set **Host Port** = `10000`.
4. Select **ROS 2** if the installed connector version shows a protocol selector.
5. Save the project. If a scene component or C# script overrides these settings, update it too (`ROSConnection`, `RosIPAddress`).

**Do not change `ROS_IP_VALUE="0.0.0.0"` in the ROS startup script.**

### B4. Configure the Endoscopic Video Connection — New PC

**Step 1 — Find the PC IP address**

1. Open Windows Command Prompt.
2. Run `ipconfig`.
3. Note the IPv4 address of the PC connected to the HoloLens 2 network.

**Step 2 — Update the video IP in Unity**

1. Open the Unity project.
2. Locate the `MjpegStream.cs` script in `Assets`.
3. Find the following configuration:

   ```csharp
   [SerializeField] private string serverIP = "192.168.0.239";
   [SerializeField] private int serverPort = 5000;
   [SerializeField] private string endpoint = "/video_feed";
   ```

4. Replace `192.168.0.239` with the **new PC IP address**.
5. In Unity, select the GameObject containing the `MjpegStream` component and check the **Server IP** field in the Inspector. Update it to the new IP as well, if necessary.
6. Keep `serverPort = 5000` and `endpoint = "/video_feed"` unchanged.
7. Save the project.

**Step 3 — Verify and deploy**

1. Start the Python MJPEG server on the Windows PC (Part C).
2. Test the video in Unity Play Mode.
3. Rebuild and redeploy the application to HoloLens 2.

**Note:** The video IP is configured independently of the ROS–TCP connection (B3). Both settings must be updated when changing PC.
### B5. Check connectivity — after IP changes

1. Start the ROS pipeline (**A7**) and the MJPEG server (**C2**).
2. Check that HoloLens can reach the **PC's TCP port 10000** and **HTTP port 5000**.
3. If ROS runs in **WSL 2**, configure Windows↔WSL networking/port forwarding as needed. Allow the required inbound ports in the firewall. See [WSL networking](https://learn.microsoft.com/windows/wsl/networking).
4. In Unity Editor, press **Play** and check tracking and video **separately**.

### B6. Build and deploy to HoloLens 2 — after changes

1. Open **File → Build Settings** (or **Build Profiles**, depending on the Unity version).
2. Select the project's existing **Universal Windows Platform / HoloLens 2** build configuration.
3. Include the main scene; use the project's configured XR settings and **ARM64** target.
4. Enable **Developer Mode** on HoloLens 2 and connect/pair it with the PC.
5. **Build** to a new output folder. Open the generated solution in **Visual Studio**.
6. Select **Release / ARM64** and the appropriate **Device or Remote Machine** deployment target (following the project's tested setup).
7. Deploy to HoloLens 2, launch the app.

**Changing the IP in Unity does not update the HoloLens app already installed. Rebuild and redeploy if the address is stored in the build.**

---

## Part C — Endoscopic Video Streaming

**The video server runs on Windows, independently of ROS 2.**

### C1. Connect the Video Source — Every Session

1. Connect the endoscopic video capture device to the Windows PC.
2. Verify that Windows detects the device.

### C2. Install Python Dependencies — Once per PC

1. Install Python 3 on Windows.
2. Open **PowerShell** and run:

   ```powershell
   py -m pip install opencv-python flask
   ```

### C3. Configure the Video Server — New PC

1. Open `endoscope.py`.
2. Verify the camera index:

   ```python
   camera_index = 1
   ```

   Change it only if the capture device uses a different index.

3. Keep the following settings unchanged:

   ```python
   server_host = "0.0.0.0"
   server_port = 5000
   ```

4. Save the script.

### C4. Start the Video Server — Every Session

1. On Windows, open the repository folder `scripts/video`.
2. Open PowerShell in this folder.
3. Run:

   ```powershell
   py server_endoscope.py
   ```



**Note:** Run the video server on Windows, not Ubuntu/WSL.

### C5. Verify the Video Stream

1. Open a browser on the Windows PC.
2. Enter:

   `http://127.0.0.1:5000/video_feed`

3. Verify that the live endoscopic video is displayed.
4. Ensure that HoloLens 2 can reach the PC on port `5000` (check Windows Firewall if necessary).
5. Launch the Unity/HoloLens application and verify the video display.

**Important:** Unity connects using `http://<PC_IP>:5000/video_feed`, where `<PC_IP>` is the Windows PC IPv4 address. Configure this address in `MjpegStream` as described in **Part B4**.

**Note:** The MJPEG server is independent of ROS–TCP. Both services must be running during the simulation.

---
## Part D — Using the HoloLens Application

### D1. Launch the Application

1. Turn on HoloLens 2 and connect it to the same network as the PC.
2. Make sure the ROS 2 pipeline and endoscopic video server are running.
3. Open the **Dino Unity** application on HoloLens 2.
4. Grant the required permissions when prompted.

A **Startup Panel** appears, allowing the user to select the calibration procedure.

### D2. Select the Calibration Mode

Choose one of the following options:

| Option | When to use |
|---|---|
| **Use Saved Setup** | The phantom, QR marker and Aurora tracking setup have not moved since the previous calibration. |
| **Full Recalibration** | First use, no saved calibration, or the phantom/QR marker has moved. |
| **Aurora Only** | The virtual phantom is correctly aligned, but the Aurora tracking setup has changed (e.g., the field generator has moved). |

**Note:** For the first use on a new HoloLens 2, select **Full Recalibration**.

### D3. Full Calibration — QR Alignment

*Skip this step if Aurora Only was selected.*

1. Press **Full Recalibration** on the Startup Panel.
2. Look at the QR marker on the physical setup through HoloLens 2.
3. Wait for the virtual colon to align with the physical phantom.
4. Check the alignment using the displayed reference markers (sphere and plane).
5. If the alignment is satisfactory, press **Confirm CAD Alignment**.
6. Otherwise, check the QR alignment again before confirming.

The Aurora calibration interface will appear.

**Important:** Do not move the phantom, QR marker or Aurora field generator during calibration.

### D4. Aurora Calibration — 7-Point Registration

1. Take the Aurora calibration probe connected to **port 0A**.
2. Starting from the **leftmost pillar**, follow the seven physical calibration pillars in **clockwise order (left to right)**.
3. Touch the first pillar with the probe tip.
4. Hold the probe steady and press **Acquire**.
5. Wait for **Point 1/7 saved**.
6. Repeat for all seven pillars in the correct order.
7. Use **Delete Last** if the previous point was acquired incorrectly.
8. After **7/7 points**, press **Calibrate**.

**Notes:**
- Each point is acquired using 30 tracking samples. Keep the probe steady during acquisition.
- If a point is rejected due to instability, repeat **Acquire** before moving to the next pillar.

### D5. Check and Save Calibration

After pressing **Calibrate**, the calibration results are displayed.

1. Check the reported **FIT** and **LOO** errors.
2. Verify that the virtual tracking markers are correctly positioned.
3. Select:
   - **Save** — Accept and save the calibration.
   - **Recalibrate** — Repeat the seven-point registration if the result is unsatisfactory.

After pressing **Save**, the calibration panel closes and the application automatically enters **Simulation Mode**.

### D6. Use Saved Setup

If the physical setup has not changed:

1. Open the **Dino Unity** application.
2. Select **Use Saved Setup**.
3. Wait for the saved calibration to load.
4. Verify the virtual phantom alignment and endoscope tracking.

The application automatically enters **Simulation Mode**.

If no compatible calibration is found, perform **Full Recalibration**.

### D7. Simulation Mode

Once calibration is completed or a saved setup is loaded, the application displays:

- **Endoscopic Video** — Live video from the physical endoscope.
- **Virtual Tip View** — Virtual camera following the tracked endoscope tip.
- **Colon Transparency Control** — Adjusts the transparency of the virtual colon.
- **Trial Interface** — Controls for selecting the simulation mode and viewing results.
- **Tracked Endoscope Tip** — Real-time virtual representation of the endoscope tip.

Before starting, verify the virtual phantom alignment, endoscope tracking and video streaming.

### D8. Run a Simulation Trial

**Step 1 — Select the Simulation Mode**

Select one of the three available conditions:

- **MR OFF**
- **MR ON**
- **MR PLUS**

**Step 2 — Start the Trial**

1. Position the endoscope tip near the colon entrance.
2. Move the tip towards the opening to automatically start the trial.
3. The initial instructions disappear and the simulation begins.

**Step 3 — Insertion Phase**

1. Advance the endoscope through the colon.
2. Continue until reaching the end of the colon.
3. The application displays **End of Insertion**, indicating that the insertion phase is complete.

**Step 4 — Withdrawal and Trial Completion**

1. Slowly withdraw the endoscope through the colon.
2. Continue until the tip exits through the colon entrance.
3. The trial ends automatically.
4. The application displays the computed performance metrics.
5. The trial results are automatically saved in the **HoloLens 2 local storage**.

**Important:** Keep the ROS 2 tracking pipeline and endoscopic video server running throughout the trial.
### D9. Access and Export Trial Results

After each completed trial, the results are automatically generated and saved as CSV files on HoloLens 2.

**Step 1 — Retrieve the Results**

1. Connect HoloLens 2 to the Windows PC using a USB cable.
2. Keep HoloLens 2 turned on and unlocked.
3. Open **File Explorer** on the PC.
4. Navigate to:

   `This PC → HoloLens 2 → Internal Storage → Documents → TrialMetrics`

5. Copy the CSV files to the PC for further analysis.

**Step 2 — Identify the CSV Files**

The application generates three CSV outputs:

| File | Content |
|---|---|
| `*_raw.csv` | Raw tracking samples, tip position, progress and tracking validity during the trial. |
| `*_report.csv` | Detailed metrics report for each individual trial. |
| `TrialMetrics_Summary_BoxGates_V4_Excel.csv` | Cumulative summary containing the results of all completed trials. |

The first two files are created separately for each trial, with participant ID, condition and timestamp in their filenames.

**Step 3 — Metrics Processing**

All metric calculations and CSV exports are managed by **`TrialMetricsManager.cs`**, located in the Unity project's `Assets` folder.

The script automatically:

- Records endoscope-tip tracking data and evaluates tracking validity.
- Calculates trial duration, insertion time and centerline progression.
- Computes centerline deviation, path length, progression efficiency and backward movements.
- Evaluates movement speed and time spent outside the centerline corridor.
- Stores separate insertion-phase metrics for experimental comparison.
- Generates and saves the CSV results at the end of each trial.

**Note:** The CSV files are initially saved in the application's local storage. On HoloLens 2, the script also attempts to copy them to `Documents/TrialMetrics`. If this folder is missing, check the application's Documents access permissions or retrieve the files from its local storage using Windows Device Portal.

## Daily Startup — Quick Checklist

- [ ] **Hardware:** Connect Aurora, colonoscope, calibration probe (0A), endoscope sensor (0B) and video capture device.
- [ ] **Network:** Connect PC and HoloLens 2 to the same network; verify ROS and video IP settings.
- [ ] **ROS 2:** Run `bringup_aurora_unity.sh` and verify Aurora tracking.
- [ ] **Video:** Run `py server_endoscope.py` on Windows and verify `/video_feed`.
- [ ] **HoloLens:** Open **Dino Unity**, load or perform calibration, and check tracking and video.
- [ ] **Simulation:** Select MR OFF / MR ON / MR PLUS and complete the trial.
- [ ] **Session end:** Copy the CSV results from HoloLens, stop the servers and power off the devices.

---

## Key Project Files

### ROS 2 Repository

| File | Purpose |
|---|---|
| `config/aurora_config.yaml` | Aurora configuration and ROM template |
| `scripts/startup/bringup_aurora_unity.sh` | Starts Aurora tracking, pose publisher and ROS–TCP Endpoint |
| `scripts/tracking/aurora_sensor0_tip_and_sensor1_publisher.py` | Processes calibration-probe and endoscope poses |
| `scripts/video/server_endoscope.py` | Windows MJPEG server for live endoscopic video |
| `launch/aurora_pub.launch.py` | Aurora ROS 2 driver launch |
| `rom/610029_AuroraMini6DOF_1.8x9mm/610029-6DOF.rom` | Aurora sensor ROM |
| `src/`, `include/`, `msg/` | ROS 2 driver and message definitions |

### Unity Project (Provided Separately)

| Script | Purpose |
|---|---|
| `MjpegStream.cs` | Receives and displays the endoscopic video stream |
| `AppUIManager.cs` | Manages startup, calibration and simulation interfaces |
| `Calibration.cs` | QR alignment, Aurora calibration and saved setup |
| `TrialMetricsManager.cs` | Automatic trial control, performance metrics and CSV export |

---

**References:** [ROS 2 Humble](https://docs.ros.org/en/humble/) · [Unity ROS–TCP](https://github.com/Unity-Technologies/Unity-Robotics-Hub) · [WSL USB](https://learn.microsoft.com/windows/wsl/connect-usb) · [WSL Networking](https://learn.microsoft.com/windows/wsl/networking)



> Research prototype for simulated colonoscopy. Retain original driver attribution and comply with third-party licenses/ROM redistribution rules.







