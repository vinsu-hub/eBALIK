import serial.tools.list_ports

CH340_IDS = {("1A86", "7523"), ("1A86", "5523")}

def list_candidate_ports():
    candidates = []
    for port in serial.tools.list_ports.comports():
        if port.vid is None or port.pid is None:
            continue
        vid_pid = (f"{port.vid:04X}", f"{port.pid:04X}")
        is_ch340 = vid_pid in CH340_IDS or (port.description and "CH340" in port.description.upper())
        candidates.append({
            "device": port.device,
            "description": port.description,
            "vid_pid": vid_pid,
            "is_ch340": is_ch340,
        })
    candidates.sort(key=lambda c: not c["is_ch340"])
    return candidates

def find_arduino_port():
    candidates = list_candidate_ports()
    for c in candidates:
        if c["is_ch340"]:
            return c["device"]
    return None
