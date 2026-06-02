# University Gate ANPR System — Project Specification

> **Target Region:** Sindh, Pakistan | **Hardware:** Raspberry Pi 3 Model B

---

## 1. Project Identity

| Field | Details |
|---|---|
| **Project Name** | University Gate Automatic Number Plate Recognition (ANPR) |
| **Target Region** | Sindh, Pakistan |
| **Plate Formats** | `ABC-123`, `AB-1234`, `A-1234` |
| **Controller** | Raspberry Pi 3 Model B (1.2GHz Quad-Core, 1GB RAM) |
| **Camera** | Hikvision DS-2CD1063G2-LIU (6MP IP Camera via RTSP) |

---

## 2. Technical Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.9+ |
| **Computer Vision** | OpenCV (`cv2`) |
| **OCR Engine** | Tesseract (Primary — Speed) / EasyOCR (Secondary — Accuracy) |
| **Database** | SQLite3 (Local file-based) |
| **Web Framework** | Flask (Micro-framework) |
| **Frontend** | HTML5, CSS3 (Tailwind or Bootstrap), JavaScript |

---

## 3. System Workflow (Optimized for Pi 3)

To prevent the Raspberry Pi 3 from crashing under high CPU load, the system uses a **Trigger-Capture** model rather than constant full-frame OCR.

```
┌─────────────────────────────────────────────────────────┐
│                   SYSTEM WORKFLOW                       │
│                                                         │
│  1. Low-Res Monitor  →  Sub-Stream (640×480) via RTSP   │
│  2. Motion Detection →  Frame Differencing in ROI       │
│  3. Hi-Res Trigger   →  6MP Snapshot from Main Stream   │
│  4. Preprocessing    →  Grayscale → Bilateral Filter    │
│                         → Canny Edge → Contour Detection│
│  5. OCR Processing   →  Crop Plate → Tesseract/EasyOCR  │
│                         → Regex Validation              │
│  6. Persistence      →  Save to SQLite3                 │
│  7. Dashboard Update →  Push to Flask Web Interface     │
└─────────────────────────────────────────────────────────┘
```

### Step-by-Step Breakdown

**Step 1 — Low-Res Monitoring**
The Pi continuously pulls the Hikvision Sub-Stream at 640×480 resolution via RTSP to minimize CPU usage.

**Step 2 — Motion Detection**
A simple Frame Differencing algorithm monitors a defined "Entry Zone" (Region of Interest). Only movement within this ROI triggers further processing.

**Step 3 — High-Res Trigger**
On motion detection, the Pi requests a single high-resolution (6MP) frame from the Main Stream for accurate plate reading.

**Step 4 — Image Preprocessing**
- Convert to Grayscale
- Apply Bilateral Filtering (noise removal, edge preservation)
- Canny Edge Detection + Contour Analysis to locate the rectangular plate region

**Step 5 — OCR Processing**
- Crop the detected plate area
- Run OCR with alphanumeric character whitelist
- Validate output with Sindh-specific Regex: `^[A-Z]{1,3}-\d{3,4}$`

**Step 6 — Persistence**
Store `plate_text`, `timestamp`, and `image_filename` in the SQLite database.

**Step 7 — Dashboard Update**
Push the new entry to the Flask web interface for real-time display.

---

## 4. Database Schema

```sql
CREATE TABLE vehicles (
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,
    plate_number     TEXT     NOT NULL,
    entry_timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP,
    exit_timestamp   DATETIME,
    image_path       TEXT,
    status           TEXT     DEFAULT 'Entered'  -- 'Entered' or 'Exited'
);
```

---

## 5. Regional Constraints & Configuration

### Sindh Plate Characteristics

| Plate Type | Background Color | Text Color |
|---|---|---|
| Private Vehicle | Yellow | Black |
| Government Vehicle | Green | Black/White |

> **OCR Focus:** Extract black text from colored backgrounds.

### RTSP URL Formats

```
# Main Stream (High-Resolution — 6MP)
rtsp://admin:password@<CAM_IP>:554/Streaming/Channels/101

# Sub Stream (Low-Resolution — 640×480)
rtsp://admin:password@<CAM_IP>:554/Streaming/Channels/102
```

---

## 6. Functional Requirements

### A. Camera Logic

- **RTSP Reconnection Handler:** If the camera drops, the script must automatically reconnect without crashing.
- **Region of Interest (ROI):** Configurable zone to ignore movement outside the vehicle entry/exit area.

### B. OCR Logic

- **Character Whitelist:** `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-`
- **Confidence Threshold:** Only save plates with **>70% OCR confidence** to reduce false positives.
- **Regex Validation Pattern:** `^[A-Z]{1,3}-\d{3,4}$`

### C. Dashboard Logic

- **Real-Time Feed:** Display the most recent 10 vehicle entries.
- **Search Feature:** Query SQLite by `plate_number`.
- **Status Toggle:** Mark a vehicle as "Exited" manually, or automatically if the same plate is detected again after a configurable time window (e.g., X hours).

---

## 7. Performance Optimization *(Critical for Pi 3)*

### Multithreading Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Thread A   │    │   Thread B   │    │   Thread C   │
│  Video       │───▶│  OCR         │───▶│  Web Server  │
│  Capture     │    │  Processing  │    │  (Flask)     │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Optimization Rules

| Optimization | Details |
|---|---|
| **Frame Skipping** | Process **1 out of every 5 frames** during motion events |
| **Trigger-Based OCR** | Never run OCR on every frame; only on motion-triggered hi-res captures |
| **Swap Space** | Configure at least **2GB of Swap** on the Pi's SD card to handle peak RAM during OCR |
| **Sub-Stream Monitoring** | Use 640×480 stream for continuous monitoring; 6MP only on trigger |

### Enabling Swap Space on Raspberry Pi

```bash
# Edit swap configuration
sudo nano /etc/dphys-swapfile

# Set CONF_SWAPSIZE=2048

# Restart swap service
sudo systemctl restart dphys-swapfile

# Verify
free -h
```

---

## 8. Project Structure (Suggested)

```
university-anpr/
├── main.py                  # Entry point — spawns all threads
├── camera/
│   ├── capture.py           # RTSP capture & reconnect logic (Thread A)
│   └── motion.py            # Frame differencing & ROI logic
├── ocr/
│   ├── preprocessor.py      # Grayscale, filter, edge detection
│   ├── recognizer.py        # Tesseract / EasyOCR wrapper (Thread B)
│   └── validator.py         # Regex validation for Sindh plates
├── database/
│   └── db.py                # SQLite3 CRUD operations
├── web/
│   ├── app.py               # Flask server (Thread C)
│   ├── templates/
│   │   └── dashboard.html   # Real-time dashboard UI
│   └── static/              # CSS, JS assets
├── captured_plates/         # Saved plate images
├── config.py                # RTSP URLs, thresholds, ROI coords
└── requirements.txt
```

---

## 9. Configuration Reference (`config.py`)

```python
# Camera Settings
RTSP_MAIN   = "rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101"
RTSP_SUB    = "rtsp://admin:password@192.168.1.64:554/Streaming/Channels/102"

# ROI (x, y, width, height) — adjust to your camera angle
ROI = (100, 150, 500, 300)

# Processing
FRAME_SKIP          = 5          # Process every Nth frame
OCR_CONFIDENCE      = 70         # Minimum confidence threshold (%)
PLATE_REGEX         = r"^[A-Z]{1,3}-\d{3,4}$"

# Auto-exit detection window
AUTO_EXIT_HOURS     = 8

# Database
DB_PATH             = "anpr.db"
IMAGE_SAVE_DIR      = "captured_plates/"
```

---

## 10. Dependencies (`requirements.txt`)

```
opencv-python==4.8.1.78
pytesseract==0.3.10
easyocr==1.7.0
flask==3.0.0
Pillow==10.0.0
numpy==1.24.4
```

> **System dependency:** `sudo apt install tesseract-ocr -y`

---

*Document Version: 1.0 | Region: Sindh, Pakistan | Platform: Raspberry Pi 3 Model B*
