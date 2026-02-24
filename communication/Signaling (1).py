import asyncio, websockets, json

peers = {}
dashboards = set()

async def handler(ws):
    try:
        hello = await ws.recv()
    except:
        return

    role = "dashboard" if hello == "DASHBOARD" else "peer"
    peer_id = None

    if role == "dashboard":
        dashboards.add(ws)
        print("[SERVER] Dashboard connected")
    else:
        peer_id = hello
        peers[peer_id] = ws
        print(f"[SERVER] Peer {peer_id} connected")

    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
            except:
                continue

            # Mirror ONLY data packets to dashboards
            if data.get("type") in ("CONTROL", "EVENT", "METRIC"):
                for d in list(dashboards):
                    try:
                        await d.send(json.dumps(data))
                    except:
                        dashboards.discard(d)

            # Forward signaling messages peer-to-peer
            tgt = data.get("to")
            if tgt in peers:
                await peers[tgt].send(msg)

    except websockets.ConnectionClosed:
        pass
    finally:
        if role == "dashboard":
            dashboards.discard(ws)
        else:
            peers.pop(peer_id, None)
        print(f"[SERVER] {hello} disconnected")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("[SERVER] Running on :8765")
        await asyncio.Future()

asyncio.run(main())
