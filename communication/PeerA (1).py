import asyncio, serial, json, time, websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer

UART_PORT = "/dev/ttyS0"
UART_BAUD = 115200

PEER_ID = "A"
TARGET_ID = "B"
SIGNALING_URL = "wss://signal.mkre.me"

ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0)

pc = RTCPeerConnection(
    RTCConfiguration([RTCIceServer(urls="stun:stun.l.google.com:19302")])
)

dc = pc.createDataChannel("uart")
dc_ready = asyncio.Event()

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

# Loss tracking for EVENT stream received on A (EVENT seq from B)
event_expected_seq = None
event_lost = 0
event_received = 0

def dc_send_json(obj: dict):
    global bytes_sent, msgs_sent
    s = json.dumps(obj)
    dc.send(s)
    msgs_sent += 1
    bytes_sent += len(s.encode("utf-8"))

def note_recv(raw: str):
    global bytes_recv, msgs_recv
    msgs_recv += 1
    bytes_recv += len(raw.encode("utf-8"))

# ---------------- DATA CHANNEL ----------------
@dc.on("open")
def on_open():
    dc_ready.set()
    print("DC OPEN (MASTER)")

@dc.on("message")
def on_msg(msg):
    global rtt_ms, last_pong_t, event_expected_seq, event_lost, event_received

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
        # reply immediately
        dc_send_json({
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

    # --- Regular EVENT from B -> A (BLOCK / UNBLOCK_ACK) ---
    if pkt.get("payload") in ("BLOCK", "UNBLOCK_ACK"):
        # loss calc
        sseq = pkt.get("seq")
        if isinstance(sseq, int):
            event_received += 1
            if event_expected_seq is None:
                event_expected_seq = sseq
            else:
                if sseq > event_expected_seq + 1:
                    event_lost += (sseq - event_expected_seq - 1)
                event_expected_seq = sseq

        ser.write((pkt["payload"] + "\n").encode())
        print("FROM SLAVE:", pkt["payload"])

# ---------------- UART -> SLAVE ----------------
async def uart_loop():
    global uart_buf, seq

    await dc_ready.wait()

    while True:
        if ser.in_waiting:
            uart_buf += ser.read(ser.in_waiting).decode(errors="ignore")

            while "\n" in uart_buf:
                line, uart_buf = uart_buf.split("\n", 1)
                line = line.strip()

                if line.startswith("P,") or line == "UNBLOCK":
                    seq += 1
                    pkt = {
                        "seq": seq,
                        "ts": time.time(),
                        "from": PEER_ID,
                        "type": "CONTROL",
                        "payload": line
                    }

                    # WebRTC path (real data)
                    dc_send_json(pkt)

                    # Telemetry mirror
                    if signal_ws:
                        await signal_ws.send(json.dumps(pkt))

        await asyncio.sleep(0.001)

# ---------------- RTT PING LOOP ----------------
async def ping_loop():
    await dc_ready.wait()
    while True:
        dc_send_json({
            "type": "PING",
            "t0": time.time(),
            "from": PEER_ID
        })
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

            # EVENT loss percentage on A (received from B)
            denom = event_received + event_lost
            event_loss_pct = (event_lost / denom * 100.0) if denom > 0 else 0.0

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

                "event_loss_pct": event_loss_pct,
                "event_lost": event_lost,
                "event_received": event_received
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

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await ws.send(json.dumps({
            "from": PEER_ID,
            "to": TARGET_ID,
            "type": "offer",
            "data": pc.localDescription.__dict__
        }))

        async for msg in ws:
            m = json.loads(msg)
            if m.get("to") == PEER_ID and m.get("type") == "answer":
                await pc.setRemoteDescription(
                    RTCSessionDescription(**m["data"])
                )

# ---------------- MAIN ----------------
async def main():
    await asyncio.gather(signaling(), uart_loop(), ping_loop(), metric_loop())

asyncio.run(main())
