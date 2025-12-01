## Using Raspberry Pi to Run WebQuiz

This section describes how to prepare a **Raspberry Pi** to work with **WebQuiz** using a ready-made system image.
As a result, you will have a device that automatically launches a local testing server on your Wi-Fi network.

---

### Downloading the Ready-Made Image

[Download **Raspberry Pi Image**](https://drive.google.com/file/d/1WGOqSV0EW4xdvod2N4VoU_q6p2plXO9z/view?usp=sharing).
Use the standard **Raspberry Pi Imager** program or any other image writer to write it to an SD card.

During setup in **Raspberry Pi Imager**, don't forget to:
- set the correct Wi-Fi network (SSID and password);
- enable SSH (optional);
- specify username and password if you plan further administration.

After writing, insert the SD card into your Raspberry Pi and start the device.

---

### First Boot

The first boot of Raspberry Pi is intended for **initial SD card partitioning**.
The system will automatically prepare the file structure and perform basic setup actions.

After this process completes, you can shut down the Raspberry Pi, remove the SD card, and perform further preparation on a computer.

---

### SD Card Partitioning

After the first boot, you need to **split the SD card into two areas**:

1. **Main System Area**
   Don't change its contents — only reduce its size to free up space for the second part.
   This area contains the operating system and installed WebQuiz.

2. **Data Area**
   Create a new partition in **exFAT** format and name it **`data`**.
   WebQuiz will use this partition to store tests, results, and configuration files.

The `data` partition is accessible from any OS (Windows, macOS, Linux).
You can copy, edit, or delete files directly.

---

### Recommended Partitioning Software

You can use the following programs to create and edit partitions:

- **Windows:**
  - [MiniTool Partition Wizard](https://www.partitionwizard.com/)
  - [AOMEI Partition Assistant](https://www.diskpart.com/)
  - Built-in **Disk Management (diskmgmt.msc)** utility

- **macOS:**
  - Built-in **Disk Utility** application
  - [Paragon Hard Disk Manager](https://www.paragon-software.com/home/hdm-mac/)

- **Linux:**
  - **GParted** (graphical utility)
  - Command-line tools: `fdisk`, `parted`, `lsblk`, `mkfs.exfat`

Make sure the new partition is created in **exFAT** format and the system part remains unchanged.

---

### Second Boot of Raspberry Pi

After partitioning, insert the SD card back into the Raspberry Pi and start the device.
**The second boot** may take up to **30 minutes** — during this time the system automatically:

- connects to Wi-Fi (configured in Raspberry Pi Imager);
- downloads necessary packages from the [Ansible repository](https://github.com/oduvan/webquiz-ansible);
- installs all dependencies for WebQuiz;
- prepares the file structure.

---

> ⚠️ **Tip:** The second boot may take up to 30 minutes.
> During this period, Raspberry Pi automatically installs all necessary packages.
> Don't turn off the power until the SD card activity indicator stops flashing.

---

### Wi-Fi Configuration

After the second boot, a **`wifi.conf.example`** file will appear in the **`data`** partition, which serves as a template for creating your own **`wifi.conf`** file.
The system uses **`wifi.conf`** to connect to Wi-Fi or create its own access point (*Hotspot*).

#### `wifi.conf` File

To activate Wi-Fi or create an access point, create a file in the `data` partition:

```
wifi.conf
```

Depending on your needs, it can have one of the configurations shown below.

---

#### Connecting to an Existing Wi-Fi Network

```
SSID="tp-fregat2"
PASSWORD="0675225288"
```

In this case, Raspberry Pi will connect to an existing Wi-Fi network.

---

#### Creating Your Own Access Point (Hotspot)

```
HOTSPOT=1
SSID="dov"
PASSWORD="11223344"
IPADDR="10.42.0.1/24"
```

In this mode, Raspberry Pi creates its own Wi-Fi network named `dov` with password `11223344`.
IP address `10.42.0.1` is reserved for Raspberry Pi itself — the WebQuiz server will be accessible in the browser at this address.

> ⚠️ **Limitation:** Raspberry Pi can work as an access point, but simultaneously supports a limited number of clients (usually no more than 5–6).
> After that, speed problems or user disconnections are possible.

> **Recommendation:** If you need to connect more devices, it's better to use a separate Wi-Fi router connected to Raspberry Pi in **Bridge (Repeater / Access Point Client)** mode.
> Such a router will extend the Wi-Fi coverage area and allow more users to work safely.

---

#### Example with Fixed IP Address for Home Network

```
SSID="my_home_wifi"
PASSWORD="12345678"
IPADDR="192.168.0.150/24"
```

In this case, Raspberry Pi will connect to an existing Wi-Fi network and automatically assign IP address `192.168.0.150`.
The WebQuiz server will be accessible at:

```
http://192.168.0.150:8080
```

---

### Behavior in Hotspot Mode

When Raspberry Pi operates in access point mode:
- When a user connects to the Wi-Fi network, a browser page automatically opens with a **"Start Test"** button.
- This way, the user doesn't need to enter the address manually.
- The testing web interface launches immediately after connecting.

---

### Additional Raspberry Pi Features

WebQuiz on Raspberry Pi also includes a **built-in file server**.
This server allows hosting educational materials that can be downloaded from the same page where tests are conducted.

Teachers can upload PDF documents, presentations, or video files to the appropriate directory in the `data` partition.
After that, all students who joined the network will be able to:
- take tests;
- **view or download educational materials** on the local network without internet.

---

### Finishing Setup

After creating or modifying the `wifi.conf` file, restart Raspberry Pi.
After booting, the system will automatically activate the connection and start the **WebQuiz** server.

You can connect to it through a browser at:
```
http://raspberrypi.local:8080
```
or at the IP address specified in the configuration file.

---

### Tips and Notes

- The **`data`** partition is used for all created tests, logs, results, and Wi-Fi configurations.
- If you need to reinstall the system, you can simply rewrite the image **without deleting the `data` partition** — all files will remain.
- To change Wi-Fi settings, just edit `wifi.conf` and restart the device.
- If the device doesn't connect to Wi-Fi, check that the SSID and password are correct, or try Hotspot mode.
