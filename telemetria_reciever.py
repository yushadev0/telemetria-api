import socket
import json

UDP_IP = "127.0.0.1"
UDP_PORT = 4433  # Hamilton (44) vs Verstappen (33) Easter Egg Portu!

# UDP Soketini oluştur ve 4433 numaralı kapıyı dinlemeye başla
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"🏁 Telemetria Pit Duvarı Dinlemede! (Port: {UDP_PORT})")
print("Delphi'den gelecek canlı veriler bekleniyor...\n")

while True:
    # Delphi'den gelen paketi yakala (4096 byte'lık buffer yeter de artar)
    data, addr = sock.recvfrom(4096) 
    
    try:
        # Gelen veriyi UTF-8'den çöz ve JSON objesine dönüştür
        telemetry = json.loads(data.decode('utf-8'))
        
        # Terminale şık bir yarış mühendisi ekranı gibi yazdır
        print(f"🏎️ Hız: {telemetry['speed']} km/h | Vites: {telemetry['gear']} | RPM: {telemetry['rpm']} | Gaz: %{int(telemetry['gas']*100)}")
        print(f"🔥 Lastikler (FL-FR-RL-RR): {telemetry['tyre_fl']}°C | {telemetry['tyre_fr']}°C | {telemetry['tyre_rl']}°C | {telemetry['tyre_rr']}°C")
        print("-" * 60)
        
    except Exception as e:
        print("Hatalı paket geldi veya JSON çözülemedi:", e)