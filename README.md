# Haptic Teleoperation Robotic Arm
### Real-Time Master–Slave Robotic Control System with Bidirectional Feedback

A low-latency, internet-enabled teleoperation system designed for precision remote manipulation in surgical, hazardous, and high-risk environments.

This project demonstrates a full-stack robotics architecture integrating embedded systems, real-time communication, force feedback safety logic, and WebRTC-based monitoring.

---
## 🚀 Overview

This system implements a real-time master–slave robotic architecture where human hand movements are captured, transmitted over a network, and replicated by a remote robotic arm with synchronized feedback.

Unlike basic teleoperation demos, this platform includes:

Bidirectional communication

Real-time haptic lock mechanism

Emergency force-based interruption

Network latency measurement

Web-based monitoring dashboard

The design prioritizes responsiveness, stability, and modular scalability.

---
## 🧠 System Architecture

```text

Operator (Master)
   ↓
ESP32 + ADS1115 (Motion Capture)
   ↓
Raspberry Pi (Packet Relay)
   ↓
WebRTC / Wi-Fi
   ↓
Raspberry Pi (Slave Gateway)
   ↓
ESP32 (Actuation Control)
   ↓
Robotic Arm (MG996R + Stepper)
```

---
## ⚙️ Core Components
### 🔹 Master Side

Precision potentiometer-based motion sensing

ADS1115 16-bit ADC

ESP32 for real-time input processing

MG90S servo-based haptic feedback mechanism

Raspberry Pi for network communication

### 🔹 Slave Side

MG996R high-torque servo actuators

TB6600 stepper motor driver for base articulation

Dual Force-Sensing Resistors (FSR) for impact detection

ESP32 for low-level control

Raspberry Pi as communication bridge

### 🔁 Communication Layer

WebRTC-based peer-to-peer data channel

Real-time packet transmission

App-layer RTT measurement (PING/PONG mechanism)

Throughput estimation (TX/RX kbps)

Sequence-based loss detection

The system enforces packet freshness to prevent motion queuing and ensures immediate response to operator input.

---
## 🛡 Safety & Control Logic

The platform implements a force-based safety mechanism:

FSR sensors continuously monitor contact force

Threshold breach triggers immediate actuator freeze

Emergency signal sent upstream

Master-side haptic lock engaged

Manual confirmation required for reactivation

This architecture mimics reflex-based safety systems used in advanced teleoperation environments.

---
## 📊 Real-Time Metrics

The WebRTC dashboard provides:

RTT (Round Trip Time)

Data channel throughput

Packet loss percentage

ICE connection state

This allows continuous monitoring of network stability during remote operation.

---
## 📂 Repository Structure

```text
.
├── firmware/
│   ├── master_esp32/
│   └── slave_esp32/
│
├── communication/
│   ├── PeerA.py
│   ├── PeerB.py
│   └── Signaling.py
│
├── dashboard/
│
└── media/

```

---
## 🎥 Demonstration

The media/ directory contains working demonstrations of:

Master-to-slave synchronized motion

Multi-axis teleoperation

Real-time response behavior

---
## 🎯 Applications

This architecture is designed for scalability into:

Remote surgical assistance systems

Hazardous material manipulation

Bomb disposal robotics

Space or underwater teleoperation

Remote industrial precision control

Training simulators

---
## 🔬 Engineering Highlights

Deterministic low-level servo control

Microcontroller–SBC hybrid architecture

Bidirectional data synchronization

Force-triggered reflex safety logic

Modular communication stack

Network-aware teleoperation framework

---
## 🔮 Future Expansion

Stereo vision integration

Predictive motion smoothing

AI-assisted control stabilization

Adaptive latency compensation

Autonomous subtask handling

ROS2-based integration layer

---
## 👨‍💻 Author

Molanguru Sonu Adithya
Embedded Systems & Robotics Engineer
