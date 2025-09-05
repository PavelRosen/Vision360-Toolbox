# Vision360 Toolbox

A simple desktop application for Linux designed to streamline your Insta360 workflow. Built with Python and Tkinter, this tool allows for high-quality video conversion and precise GPS data extraction without needing the command line.

![Toolbox Logo](logo.png)



## Core Features
*   **High-quality 360° video conversion** from `.insv` to `.mp4`, powered by the official Insta360 Media SDK.
*   **Precise GPS data extraction** into `.gpx` files, utilizing the powerful ExifTool.
*   **Integrated map viewer** to immediately visualize your extracted GPX tracks.

---

## Like this Tool? 

This toolbox was built in my spare time to solve a real-world problem. If it saved you some time and a command-line headache, consider fueling future development!

*   You can buy me a coffee on **[Ko-fi](https://ko-fi.com/pavelrst)**.
*   Or toss some spare Bitcoin my way: `BC1QM2E6SE7FUE4WEPMXU2ASM47AS59WVX4WL6WRXW`

---

## For Users: Download the Application

The easiest way to use this tool is to download the pre-compiled, all-in-one executable.

1.  Go to the **[Releases Page](https://github.com/PavelRosen/Vision360-Toolbox/releases)**.
2.  Download the `vision360` file from the latest release.
3.  Open a terminal and make the file executable: `chmod +x vision360`
4.  Run the application: `./vision360`

**Compatibility Note:** This tool has been developed and tested on a **Debian Linux system**. While the Insta360 SDK is provided for Linux in general, the functionality of this toolbox has only been confirmed on Debian-based distributions (e.g., Debian, Ubuntu).

---

## For Developers: Building from Source

If you want to run or modify the source code, follow these steps:

1.  **Prerequisites:**
    *   Python 3.x
    *   **Insta360 Media SDK (Crucial Requirement):** This project is a wrapper around the official SDK and **will not run** without it. To get the necessary components, you need to request the **full, pre-compiled SDK** from Insta360 directly via their developer channels. The public **[C++ SDK GitHub repository](https://github.com/Insta360Develop/Desktop-MediaSDK-Cpp)** is available for reference, but may not contain the required executable demos and models.
    *   **System Tools:** Install `exiftool` and `ffprobe` using your system's package manager (e.g., `sudo apt install exiftool ffmpeg`).

2.  **Clone the repository:**
    ```bash
    git clone https://github.com/PavelRosen/Vision360-Toolbox.git
    cd Vision360-Toolbox
    ```

3.  **Install Python libraries:**
    ```bash
    pip install tkintermapview gpxpy
    ```

4.  **Run the application:**
    ```bash
    python vision360.py
    ```
---

<img width="899" height="834" alt="Screenshot_20250905_183935" src="https://github.com/user-attachments/assets/67554f28-1d1a-463d-9d4f-a215b3baaf3c" />

<img width="900" height="836" alt="Screenshot_20250905_183956" src="https://github.com/user-attachments/assets/6dbb273c-e551-4c0d-a775-2fa60a97efaa" />

<img width="902" height="839" alt="Screenshot_20250905_184008" src="https://github.com/user-attachments/assets/41a8a7f0-8610-4bd4-8ff7-4e9ab8d9c204" />


## Contact

For more detailed questions, feel free to send me an email at: `pavrst@proton.me`
