import asyncio, serial, json, time, websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer

UART_PORT = "/dev/ttyS0"
UART_BAUD = 115200

PEER_ID = "B"
TARGET_ID = "A"
SIGNALING_URL = "wss://signal.mkre.me"

ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0)

pc = RTCPeerConnection(
    RTCConfiguration([RTCIceServer(urls="stun:stun.l.google.com:19302")])
)

uart_buf = ""
seq = 0
signal_ws = None

# ---- App-level WebRTC metrics (works with DataChannel-only) ----
bytes_sent = 0
bytes_recv = 0
msgs_sent = 0
msgs_recv = 0

last_bytes_sent = 0
last_bytes_recv = 0
last_metric_t = time.time()

rtt_ms = None
last_pong_t = None

# Loss tracking for CONTROL stream received on B (CONTROL seq from A)
control_expected_seq = None
control_lost = 0
control_received = 0

channel_ref = None

def ch_send_json(ch, obj: dict):
    global bytes_sent, msgs_sent
    s = json.dumps(obj)
    ch.send(s)
    msgs_sent += 1
    bytes_sent += len(s.encode("utf-8"))

def note_recv(raw: str):
    global bytes_recv, msgs_recv
    msgs_recv += 1
    bytes_recv += len(raw.encode("utf-8"))

# ---------------- DATA CHANNEL ----------------
@pc.on("datachannel")
def on_dc(channel):
    global channel_ref
    channel_ref = channel
    print("DC OPEN (SLAVE)")

    @channel.on("message")
    def on_msg(msg):
        global rtt_ms, last_pong_t, control_expected_seq, control_lost, control_received

        if not isinstance(msg, str):
            return

        note_recv(msg)

        try:
            pkt = json.loads(msg)
        except:
            return

        t = pkt.get("type")

        # --- PING/PONG for RTT ---
        if t == "PING":
            ch_send_json(channel, {
                "type": "PONG",
                "t0": pkt.get("t0"),
                "from": PEER_ID,
                "ts": time.time()
            })
            return

        if t == "PONG":
            t0 = pkt.get("t0")
            if isinstance(t0, (int, float)):
                rtt_ms = (time.time() - float(t0)) * 1000.0
                last_pong_t = time.time()
            return

        # --- Regular CONTROL from A -> B (P,... / UNBLOCK) ---
        payload = pkt.get("payload", "")
        if payload.startswith("P,") or payload == "UNBLOCK":
            # loss calc
            sseq = pkt.get("seq")
            if isinstance(sseq, int):
                control_received += 1
                if control_expected_seq is None:
                    control_expected_seq = sseq
                else:
                    if sseq > control_expected_seq + 1:
                        control_lost += (sseq - control_expected_seq - 1)
                    control_expected_seq = sseq

            ser.write((payload + "\n").encode())

    async def uart_loop():
        global uart_buf, seq

        while True:
            if ser.in_waiting:
                uart_buf += ser.read(ser.in_waiting).decode(errors="ignore")

                while "\n" in uart_buf:
                    line, uart_buf = uart_buf.split("\n", 1)
                    line = line.strip()

                    if line in ("BLOCK", "UNBLOCK_ACK"):
                        seq += 1
                        pkt = {
                            "seq": seq,
                            "ts": time.time(),
                            "from": PEER_ID,
                            "type": "EVENT",
                            "payload": line
                        }

                        # WebRTC path (real data)
                        ch_send_json(channel, pkt)

                        # Telemetry mirror
                        if signal_ws:
                            await signal_ws.send(json.dumps(pkt))

            await asyncio.sleep(0.001)

    asyncio.create_task(uart_loop())

# ---------------- RTT PING LOOP ----------------
async def ping_loop():
    while True:
        try:
            if channel_ref:
                ch_send_json(channel_ref, {
                    "type": "PING",
                    "t0": time.time(),
                    "from": PEER_ID
                })
        except Exception:
            pass
        await asyncio.sleep(1.0)

# ---------------- METRIC LOOP (mirror to dashboard) ----------------
async def metric_loop():
    global last_bytes_sent, last_bytes_recv, last_metric_t

    while True:
        try:
            now = time.time()
            dt = max(1e-6, now - last_metric_t)

            tx_kbps = ((bytes_sent - last_bytes_sent) * 8.0) / dt / 1000.0
            rx_kbps = ((bytes_recv - last_bytes_recv) * 8.0) / dt / 1000.0

            # CONTROL loss percentage on B (received from A)
            denom = control_received + control_lost
            control_loss_pct = (control_lost / denom * 100.0) if denom > 0 else 0.0

            metric = {
                "ts": now,
                "from": PEER_ID,
                "type": "METRIC",
                "metric": "webrtc_app",
                "iceConnectionState": pc.iceConnectionState,
                "connectionState": pc.connectionState,
                "signalingState": pc.signalingState,

                "rtt_ms": rtt_ms,
                "dc_tx_kbps": tx_kbps,
                "dc_rx_kbps": rx_kbps,
                "dc_bytes_sent": bytes_sent,
                "dc_bytes_recv": bytes_recv,
                "dc_messages_sent": msgs_sent,
                "dc_messages_recv": msgs_recv,

                "control_loss_pct": control_loss_pct,
                "control_lost": control_lost,
                "control_received": control_received
            }

            if signal_ws:
                await signal_ws.send(json.dumps(metric))

            last_bytes_sent = bytes_sent
            last_bytes_recv = bytes_recv
            last_metric_t = now
        except Exception:
            pass

        await asyncio.sleep(1.0)

# ---------------- SIGNALING ----------------
async def signaling():
    global signal_ws

    async with websockets.connect(SIGNALING_URL) as ws:
        signal_ws = ws
        await ws.send(PEER_ID)

        async for msg in ws:
            m = json.loads(msg)
            if m.get("to") == PEER_ID and m.get("type") == "offer":
                await pc.setRemoteDescription(
                    RTCSessionDescription(**m["data"])
                )

                ans = await pc.createAnswer()
                await pc.setLocalDescription(ans)

                await ws.send(json.dumps({
                    "from": PEER_ID,
                    "to": TARGET_ID,
                    "type": "answer",
                    "data": pc.localDescription.__dict__
                }))

# ---------------- MAIN ----------------
async def main():
    await asyncio.gather(signaling(), ping_loop(), metric_loop())

asyncio.run(main())
