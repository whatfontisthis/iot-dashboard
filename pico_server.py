import network
import socket
import json
import time
from machine import Pin, I2C, PWM
import neopixel
from ahtx0 import AHT20

# ---- WiFi 설정 ----
WIFI_SSID = ""  # WiFi 이름을 입력하세요
WIFI_PASSWORD = ""  # WiFi 비밀번호를 입력하세요

# ---- I2C 설정 (GP4=SDA, GP5=SCL) ----
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)

# ---- 부저 설정 (GP22) ----
buzzer = PWM(Pin(22))
buzzer.freq(440)  # 주파수 440Hz
buzzer.duty_u16(0)  # 초기에는 소리 끄기

# ---- 네오픽셀 LED 설정 (GP21) ----
PIXEL_PIN = 21  # 데이터 핀 (GP21)
PIXEL_COUNT = 1  # LED 개수 (1개)
np = neopixel.NeoPixel(Pin(PIXEL_PIN), PIXEL_COUNT)

# ---- 센서 객체 만들기 ----
try:
    sensor = AHT20(i2c)  # 주소 0x38 기본
    print("AHT20 센서 초기화 성공")
except Exception as e:
    print("AHT20 초기화 실패. 배선/전원 확인:", e)
    raise SystemExit


# ---- WiFi 연결 함수 ----
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print(f"WiFi 연결 중... ({WIFI_SSID})")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        # 연결 대기 (최대 10초)
        timeout = 0
        while not wlan.isconnected() and timeout < 100:
            time.sleep(0.1)
            timeout += 1
            print(".", end="")

        if wlan.isconnected():
            print(f"\nWiFi 연결 성공!")
            print(f"IP 주소: {wlan.ifconfig()[0]}")
            return wlan.ifconfig()[0]
        else:
            print("\nWiFi 연결 실패!")
            return None
    else:
        print(f"이미 WiFi 연결됨: {wlan.ifconfig()[0]}")
        return wlan.ifconfig()[0]


# ---- LED 제어 함수들 ----
def led_green():
    """LED 초록색으로 설정 (정상 상태)"""
    np[0] = (0, 255, 0)  # (빨강, 초록, 파랑) - 초록색
    np.write()
    print("🟢 LED 초록색 - 정상 상태")


def led_red():
    """LED 빨간색으로 설정 (위험 상태)"""
    np[0] = (255, 0, 0)  # (빨강, 초록, 파랑) - 빨간색
    np.write()
    print("🔴 LED 빨간색 - 위험 상태!")


# ---- 부저 제어 함수들 ----
def buzzer_on():
    """부저 켜기"""
    buzzer.duty_u16(30000)  # 볼륨 켜기 (0 ~ 65535 중간값 정도)
    print("🔊 부저 켜짐 - 온도 위험!")


def buzzer_off():
    """부저 끄기"""
    buzzer.duty_u16(0)  # 볼륨 끄기
    print("🔇 부저 꺼짐")


def check_temperature_alarm(temperature):
    """온도 알람 체크 및 부저/LED 제어"""
    if temperature > 30.0:
        buzzer_on()
        led_red()
        return True  # 알람 상태
    else:
        buzzer_off()
        led_green()
        return False  # 정상 상태


# ---- 센서 데이터 읽기 함수 ----
def read_sensors():
    try:
        temperature = sensor.temperature
        humidity = sensor.relative_humidity

        # 온도 알람 체크
        alarm_active = check_temperature_alarm(temperature)

        return {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "timestamp": time.time(),
            "alarm": alarm_active,
        }
    except Exception as e:
        print(f"센서 읽기 오류: {e}")
        buzzer_off()  # 오류 시 부저 끄기
        return {
            "temperature": 0.0,
            "humidity": 0.0,
            "timestamp": time.time(),
            "alarm": False,
        }


# ---- HTTP 응답 생성 함수 ----
def create_response(status_code, content_type, body):
    response = f"HTTP/1.1 {status_code}\r\n"
    response += f"Content-Type: {content_type}\r\n"
    response += "Access-Control-Allow-Origin: *\r\n"
    response += "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
    response += "Access-Control-Allow-Headers: Content-Type\r\n"
    response += f"Content-Length: {len(body)}\r\n"
    response += "Connection: close\r\n"
    response += "\r\n"
    response += body
    return response


# ---- 메인 서버 함수 ----
def start_server():
    # WiFi 연결
    ip_address = connect_wifi()
    if not ip_address:
        print("WiFi 연결 실패로 서버 시작 불가")
        return

    # 소켓 생성
    addr = socket.getaddrinfo("0.0.0.0", 8080)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)

    # LED 초기화 (초록색으로 시작)
    led_green()

    print(f"서버 시작됨: http://{ip_address}:8080")
    print("=" * 50)
    print("📊 IoT 모니터링 대시보드")
    print("=" * 50)
    print("대시보드 접속:")
    print(f"🌐 http://localhost:8000/modern_dashboard.html")
    print("")
    print("센서 API 엔드포인트:")
    print(f"📡 http://{ip_address}:8080/sensors")
    print("")
    print("🔊 알람 기능:")
    print("   - 온도 30°C 초과 시 부저 자동 작동")
    print("   - 부저 핀: GP22")
    print("")
    print("💡 LED 상태 표시:")
    print("   - 초록색: 정상 상태 (온도 ≤ 30°C)")
    print("   - 빨간색: 위험 상태 (온도 > 30°C)")
    print("   - LED 핀: GP21")
    print("=" * 50)

    while True:
        try:
            cl, addr = s.accept()
            print(f"클라이언트 연결: {addr}")

            # 요청 받기
            request = cl.recv(1024).decode("utf-8")
            print(f"요청: {request[:100]}...")

            # 요청 파싱
            if "OPTIONS" in request:
                # CORS preflight 요청 처리
                response = create_response(200, "text/plain", "")
                cl.send(response.encode("utf-8"))
                print("CORS preflight 요청 처리됨")

            elif "GET /sensors" in request:
                # 센서 데이터 읽기
                sensor_data = read_sensors()
                json_data = json.dumps(sensor_data)

                # JSON 응답 전송
                response = create_response(200, "application/json", json_data)
                cl.send(response.encode("utf-8"))
                print(f"센서 데이터 전송: {sensor_data}")

            elif "GET /" in request:
                # 기본 페이지 (상태 확인용)
                html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Pico Sensor Server</title></head>
                <body>
                    <h1>Pico 센서 서버</h1>
                    <p>IP: {ip_address}</p>
                    <p>센서 데이터: <a href="/sensors">/sensors</a></p>
                    <p>현재 시간: {time.time()}</p>
                </body>
                </html>
                """
                response = create_response(200, "text/html", html)
                cl.send(response.encode("utf-8"))

            else:
                # 404 오류
                response = create_response(404, "text/plain", "Not Found")
                cl.send(response.encode("utf-8"))

            cl.close()

        except Exception as e:
            print(f"서버 오류: {e}")
            cl.close()
            time.sleep(1)


# ---- 프로그램 시작 ----
if __name__ == "__main__":
    print("Pico 센서 서버 시작...")
    start_server()
