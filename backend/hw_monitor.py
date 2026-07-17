#!/usr/bin/env python3
"""
eBALIK Hardware Monitor
Scans for a connected Arduino, connects via serial, and streams
real-time serial traffic with color-coded output and timestamps.

On successful handshake, POSTs status to Flask's /api/hw-status endpoint
so the dashboard badge updates in real time.

Usage:
    python hw_monitor.py            # auto-scan and connect
    python hw_monitor.py COM3       # connect to specific port
"""

import sys
import time
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[!] pyserial is required. Install with: pip install pyserial")
    input("Press Enter to close this window...")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None


# ── Colors (ANSI) ──────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GRN  = "\033[42m"


BAUD = 115200
TIMEOUT = 1
PING_TIMEOUT = 3
BOOT_DELAY = 3.5
FLASK_API = "http://localhost:5000/api/hw-status"


def ts():
    return datetime.now().strftime("%H:%M:%S")


def post_status(connected, port="", vid_pid=""):
    if requests is None:
        return
    try:
        requests.post(FLASK_API, json={
            "connected": connected,
            "port": port,
            "vid_pid": vid_pid,
        }, timeout=2)
    except Exception:
        pass


def scan_ports():
    from app.hw_utils import list_candidate_ports
    return list_candidate_ports()


def print_banner():
    print(f"""
{C.BOLD}{C.CYAN}  ╔══════════════════════════════════════════╗
  ║     eBALIK Hardware Monitor  v1.0       ║
  ╚══════════════════════════════════════════╝{C.RESET}
""")


def print_status_line(label, value, color=C.WHITE):
    print(f"  {C.DIM}{label:.<22}{C.RESET} {color}{value}{C.RESET}")


def colorize_line(line):
    upper = line.upper().strip()

    if upper.startswith("HELLO"):
        return f"{C.GREEN}{C.BOLD}{line}{C.RESET}", "HELLO"
    if upper.startswith("RFID,"):
        return f"{C.CYAN}{C.BOLD}{line}{C.RESET}", "RFID"
    if upper.startswith("STATUS,"):
        status = upper.split(",", 1)[1] if "," in upper else ""
        color = C.YELLOW
        if "OBSTRUCTION" in status:
            color = C.RED
        elif "SLOT_CLOSED" in status:
            color = C.GREEN
        return f"{color}{line}{C.RESET}", "STATUS"
    if upper.startswith("RETURN_SUCCESS"):
        return f"{C.GREEN}{C.BOLD}{line}{C.RESET}", "RETURN_SUCCESS"
    if upper.startswith("RETURN_FAILED"):
        return f"{C.RED}{C.BOLD}{line}{C.RESET}", "RETURN_FAILED"
    if upper.startswith("VALID,"):
        return f"{C.GREEN}{line}{C.RESET}", "VALID"
    if upper.startswith("INVALID,"):
        return f"{C.RED}{line}{C.RESET}", "INVALID"
    if upper.startswith("PING"):
        return f"{C.MAGENTA}{line}{C.RESET}", "PING"
    if upper.startswith("RESET"):
        return f"{C.YELLOW}{C.BOLD}{line}{C.RESET}", "RESET"

    return f"{C.WHITE}{line}{C.RESET}", "OTHER"


def try_ping(ser):
    deadline = time.time() + PING_TIMEOUT
    while time.time() < deadline:
        ser.reset_input_buffer()
        ser.write(b"PING\n")
        wait_until = time.time() + 1.0
        while time.time() < wait_until:
            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line.upper().startswith("HELLO"):
                    return True, line
    return False, ""


def connect_and_monitor(target_port=None):
    print_banner()

    ser = None
    selected = None

    while True:
        print(f"  {C.BOLD}Scanning for serial ports...{C.RESET}")
        ports = scan_ports()

        if not ports:
            print(f"\n  {C.YELLOW}No USB-serial adapters found.{C.RESET}")
            print(f"  {C.DIM}Plug in the Arduino via USB, then press Enter to rescan (or type 'quit').{C.RESET}")
            try:
                user_input = input(f"  {C.CYAN}> {C.RESET}").strip()
            except EOFError:
                user_input = "quit"
            if user_input.upper() in ("QUIT", "EXIT", "Q"):
                return
            continue

        print(f"  {C.GREEN}Found {len(ports)} candidate port(s):{C.RESET}\n")
        for i, port in enumerate(ports, 1):
            vid = port["vid_pid"][0] + ":" + port["vid_pid"][1]
            label = f" {C.GREEN}(CH340) {C.RESET}" if port["is_ch340"] else f" {C.DIM}(generic){C.RESET}"
            marker = " <--" if target_port and port["device"].upper() == target_port.upper() else ""
            print(f"    {C.CYAN}{i}.{C.RESET} {C.BOLD}{port['device']}{C.RESET}  {C.DIM}{port['description']}{C.RESET}{label}{C.YELLOW}{marker}{C.RESET}")

        if target_port:
            selected = target_port
            desc = next((p["description"] for p in ports if p["device"].upper() == target_port.upper()), "?")
            print(f"\n  {C.BOLD}Connecting to {C.CYAN}{selected}{C.RESET} {C.DIM}({desc}){C.RESET}...")
        elif len(ports) == 1:
            selected = ports[0]["device"]
            print(f"\n  {C.BOLD}Auto-connecting to {C.CYAN}{selected}{C.RESET}...")
        else:
            print()
            while True:
                try:
                    choice = input(f"  {C.CYAN}Select port number (1-{len(ports)}) or 'quit': {C.RESET}").strip()
                except EOFError:
                    choice = "quit"
                if choice.upper() in ("QUIT", "EXIT", "Q"):
                    return
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(ports):
                        selected = ports[idx]["device"]
                        break
                except ValueError:
                    pass
                print(f"  {C.RED}Invalid choice.{C.RESET}")
            print(f"\n  {C.BOLD}Connecting to {C.CYAN}{selected}{C.RESET}...")

        try:
            ser = serial.Serial(selected, BAUD, timeout=TIMEOUT)
        except serial.SerialException as e:
            print(f"\n  {C.BG_RED}{C.WHITE} CONNECTION FAILED {C.RESET}")
            print(f"  {C.RED}{e}{C.RESET}")
            print(f"  {C.DIM}Tip: Close any other program using {selected} (Arduino IDE, PuTTY, etc.){C.RESET}")
            print(f"  {C.DIM}Press Enter to retry, or type 'quit'.{C.RESET}")
            try:
                user_input = input(f"  {C.CYAN}> {C.RESET}").strip()
            except EOFError:
                user_input = "quit"
            if user_input.upper() in ("QUIT", "EXIT", "Q"):
                return
            selected = None
            continue

        print(f"  {C.DIM}Waiting {BOOT_DELAY}s for Arduino to finish booting...{C.RESET}")
        time.sleep(BOOT_DELAY)
        print(f"  {C.GREEN}Serial port opened: {selected} @ {BAUD} baud{C.RESET}")
        break

    print(f"\n  {C.BOLD}Sending PING...{C.RESET}")
    ok, hello_line = try_ping(ser)
    vid_pid = ""
    for p in scan_ports():
        if p["device"] == selected:
            vid_pid = ":".join(p["vid_pid"])
            break

    if ok:
        print_status_line("Arduino", "CONNECTED", C.GREEN)
        print_status_line("Response", hello_line, C.GREEN)
        print_status_line("Port", selected, C.CYAN)
        print_status_line("Baud", str(BAUD), C.CYAN)
        post_status(True, selected, vid_pid)
        print(f"\n  {C.GREEN}{C.BOLD}Handshake confirmed.{C.RESET}")
        print(f"  {C.DIM}Enable SERIAL_ENABLED=true and restart Flask to activate live dashboard integration.{C.RESET}")
    else:
        print(f"\n  {C.YELLOW}No HELLO response received.{C.RESET}")
        print(f"  {C.DIM}Arduino may be running older firmware or still resetting.{C.RESET}")
        print(f"  {C.DIM}Entering monitor mode anyway -- watch for incoming data.{C.RESET}")
        print_status_line("Port", selected, C.CYAN)
        print_status_line("Baud", str(BAUD), C.CYAN)

    print(f"""
{C.BOLD}{C.GREEN}  ── Live Monitor ────────────────────────────{C.RESET}
  {C.DIM}Type {C.CYAN}PING{C.DIM} to check, {C.CYAN}RESET{C.DIM} to reset, {C.CYAN}reconnect{C.DIM} to rescan, {C.CYAN}quit{C.DIM} to exit.{C.RESET}
{C.DIM}  ──────────────────────────────────────────────{C.RESET}
""")

    try:
        while True:
            try:
                raw = ser.readline()
                if raw:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if line:
                        colored, msg_type = colorize_line(line)
                        print(f"  {C.DIM}[{ts()}]{C.RESET} {colored}")
            except (serial.SerialException, OSError):
                print(f"\n  {C.RED}[{ts()}] Serial connection lost!{C.RESET}")
                print(f"  {C.DIM}Arduino may have been unplugged.{C.RESET}")
                post_status(False)
                print(f"  {C.DIM}Press Enter to rescan, or type 'quit'.{C.RESET}")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                while True:
                    try:
                        user_input = input(f"  {C.CYAN}> {C.RESET}").strip()
                    except EOFError:
                        user_input = "quit"
                    if user_input.upper() in ("QUIT", "EXIT", "Q"):
                        return
                    if user_input.upper() == "RECONNECT" or user_input == "":
                        break
                target_port = None
                selected = None
                while True:
                    print(f"\n  {C.BOLD}Scanning for serial ports...{C.RESET}")
                    ports = scan_ports()
                    if not ports:
                        print(f"  {C.YELLOW}No USB-serial adapters found.{C.RESET}")
                        print(f"  {C.DIM}Plug in the Arduino, then press Enter to rescan (or type 'quit').{C.RESET}")
                        try:
                            user_input = input(f"  {C.CYAN}> {C.RESET}").strip()
                        except EOFError:
                            user_input = "quit"
                        if user_input.upper() in ("QUIT", "EXIT", "Q"):
                            return
                        continue
                    print(f"  {C.GREEN}Found {len(ports)} candidate port(s):{C.RESET}\n")
                    for i, port in enumerate(ports, 1):
                        label = f" {C.GREEN}(CH340) {C.RESET}" if port["is_ch340"] else f" {C.DIM}(generic){C.RESET}"
                        print(f"    {C.CYAN}{i}.{C.RESET} {C.BOLD}{port['device']}{C.RESET}  {C.DIM}{port['description']}{C.RESET}{label}")
                    if len(ports) == 1:
                        selected = ports[0]["device"]
                        print(f"\n  {C.BOLD}Auto-connecting to {C.CYAN}{selected}{C.RESET}...")
                    else:
                        print()
                        while True:
                            try:
                                choice = input(f"  {C.CYAN}Select port number (1-{len(ports)}) or 'quit': {C.RESET}").strip()
                            except EOFError:
                                choice = "quit"
                            if choice.upper() in ("QUIT", "EXIT", "Q"):
                                return
                            try:
                                idx = int(choice) - 1
                                if 0 <= idx < len(ports):
                                    selected = ports[idx]["device"]
                                    break
                            except ValueError:
                                pass
                            print(f"  {C.RED}Invalid choice.{C.RESET}")
                        print(f"\n  {C.BOLD}Connecting to {C.CYAN}{selected}{C.RESET}...")
                    try:
                        ser = serial.Serial(selected, BAUD, timeout=TIMEOUT)
                        print(f"  {C.DIM}Waiting {BOOT_DELAY}s for Arduino to finish booting...{C.RESET}")
                        time.sleep(BOOT_DELAY)
                        print(f"  {C.GREEN}Reconnected: {selected} @ {BAUD} baud{C.RESET}")
                        print(f"  {C.DIM}Type {C.CYAN}PING{C.DIM} to verify connection.{C.RESET}\n")
                        break
                    except serial.SerialException as e:
                        print(f"  {C.RED}Connection failed: {e}{C.RESET}")
                        print(f"  {C.DIM}Press Enter to retry, or type 'quit'.{C.RESET}")
                        try:
                            user_input = input(f"  {C.CYAN}> {C.RESET}").strip()
                        except EOFError:
                            user_input = "quit"
                        if user_input.upper() in ("QUIT", "EXIT", "Q"):
                            return

            if sys.stdin.readable():
                import msvcrt
                if msvcrt.kbhit():
                    cmd = input(f"  {C.CYAN}> {C.RESET}").strip()
                    if not cmd:
                        continue
                    upper = cmd.upper()
                    if upper in ("QUIT", "EXIT", "Q"):
                        print(f"\n  {C.DIM}Closing connection...{C.RESET}")
                        break
                    elif upper == "PING":
                        print(f"  {C.MAGENTA}[{ts()}] Sending PING...{C.RESET}")
                        ok, hello = try_ping(ser)
                        if ok:
                            print(f"  {C.GREEN}[{ts()}] {hello}{C.RESET}")
                        else:
                            print(f"  {C.RED}[{ts()}] No response{C.RESET}")
                    elif upper == "RESET":
                        print(f"  {C.YELLOW}[{ts()}] Sending RESET...{C.RESET}")
                        ser.write(b"RESET\n")
                    elif upper == "RECONNECT":
                        raise serial.SerialException("User requested reconnect")
                    else:
                        ser.write((cmd + "\n").encode("utf-8"))
                        print(f"  {C.DIM}[{ts()}] Sent: {cmd}{C.RESET}")

    except KeyboardInterrupt:
        print(f"\n\n  {C.DIM}Interrupted.{C.RESET}")
    finally:
        if ser:
            try:
                ser.close()
            except Exception:
                pass
        post_status(False)
        print(f"  {C.GREEN}Port closed. Goodbye.{C.RESET}\n")


def main():
    target_port = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        connect_and_monitor(target_port)
    except Exception:
        import traceback
        traceback.print_exc()
    input("\nPress Enter to close this window...")


if __name__ == "__main__":
    main()
