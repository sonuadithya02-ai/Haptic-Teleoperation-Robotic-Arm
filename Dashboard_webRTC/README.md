# Updated bundle (App-level WebRTC metrics + Dashboard)

## Why this version
aiortc can leave RTT/DC stats as None in DataChannel-only sessions. This version computes metrics at the app layer:
- RTT via PING/PONG over the DataChannel (works always)
- Throughput via counting bytes of messages sent/received
- Loss via seq gaps (CONTROL loss on Peer B, EVENT loss on Peer A)

## Files
- PeerA.py / PeerB.py: adds ping_loop + metric_loop and safe counters
- index.html: shows RTT, TX/RX kbps, ICE state, and loss %
- Signaling.py: unchanged (mirrors CONTROL/EVENT/METRIC to dashboards)

SIGNALING_URL is set to wss://signal.mkre.me
