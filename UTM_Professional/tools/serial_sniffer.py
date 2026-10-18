import serial
import time
import sys

def run_sniffer(port='COM3', baudrate=9600):
    print("==================================================")
    print("   UTM SERIAL INTERCEPTOR (SNIFFER)")
    print("==================================================")
    print(f"Listening on {port} at {baudrate} baud...")
    print("Waiting for the old software to send the password...\n")

    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.1)
    except Exception as e:
        print(f"ERROR: Cannot open {port}. Make sure it is not being used by another program.")
        sys.exit(1)

    try:
        while True:
            if ser.in_waiting > 0:
                raw_data = ser.read(ser.in_waiting)
                print(f"\n[INTERCEPTED DATA] -> {repr(raw_data)}")
                
                # Also try to print it as standard text
                try:
                    text = raw_data.decode('ascii', errors='ignore')
                    if text.strip():
                        print(f"[AS TEXT]        -> {text}")
                except:
                    pass
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nSniffer stopped by user.")
    finally:
        ser.close()

if __name__ == "__main__":
    # You can change COM3 to whatever port your adapter is using
    run_sniffer('COM3', 9600)
