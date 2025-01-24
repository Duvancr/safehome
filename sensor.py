#mas avanzado

from machine import Pin, ADC, PWM, SoftI2C
import network, time, math, dht
from ssd1306 import SSD1306_I2C
import ujson
from umqtt.simple import MQTTClient


# MQTT Server Parameters
MQTT_CLIENT_ID = "clienteunicosafehome"
MQTT_BROKER    = "broker.hivemq.com"
#MQTT_BROKER    = "192.168.20.25"  #  en docker apuntar al host local
MQTT_USER      = ""
MQTT_PASSWORD  = ""
MQTT_TOPIC     = "andina/diplomado/safehome"


led_rojo = Pin(27, Pin.OUT)
led_verde = Pin(25, Pin.OUT)
led_nrj = Pin(26, Pin.OUT)
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
pantalla = SSD1306_I2C(128, 64, i2c)
buzzer = PWM(Pin(32)) 
sensor_mq4 = ADC(Pin(36))
sensor = dht.DHT22(Pin(4))
sensor_mq4.atten(ADC.ATTN_11DB)  
sensor_mq4.width(ADC.WIDTH_10BIT)  

# Parámetros del sensor MQ4
R_L = 10.0  # Resistencia de carga (en kilo-ohms)
Vcc = 3.3   # Voltaje de alimentación del sensor (en volts)
Ro = 10.0   # Resistencia del sensor en aire limpio (en kilo-ohms)
m = -0.35   # Pendiente de la curva para CH4
b = 2.3     # Intersección de la curva para CH4

# Función para calcular Rs
def calculate_rs(voltage):
    if voltage == 0:  # Para evitar divisiones por cero
        voltage = 0.001
    return R_L * ((Vcc - voltage) / voltage)

# Función para calcular ppm
def calculate_ppm(rs):
    if rs <= 0:
        raise ValueError("Rs no puede ser 0 o negativo.")
    ratio = rs / Ro
    if ratio <= 0:
        raise ValueError("El ratio Rs/Ro no puede ser 0 o negativo.")
    log_ppm = (m * math.log10(ratio)) + b
    return 10**log_ppm

# Conversión de lectura ADC a voltaje
def adc_to_voltage(adc_value):
    return adc_value * (Vcc / 1023.0)

# Calibrar el sensor para obtener Ro
def calibrate_mq4():
    total_rs = 0.0
    for _ in range(50):  # Promedio de 50 lecturas
        adc_value = sensor_mq4.read()
        voltage = adc_to_voltage(adc_value)
        total_rs += calculate_rs(voltage)
        time.sleep(0.1)
    return total_rs / 50

# Configurar WiFi
# Importaciones (mantener igual)

def conectaWifi(red, password):
    
    #Conexión a WiFi con manejo de reconexión.
    
    buzzer.duty(0)
    global miRed
    miRed = network.WLAN(network.STA_IF)
    miRed.active(True)
    if not miRed.isconnected():
        print('Conectando a la red', red + "…")
        miRed.connect(red, password)
        timeout = time.time()
        while not miRed.isconnected():
            if time.ticks_diff(time.time(), timeout) > 10:
                print("No se pudo conectar a WiFi.")
                return False
    print("Conexión WiFi establecida.")
    return True


def connect_mqtt():
    
    #Conexión al servidor MQTT con manejo de reconexión.
    
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD)
    try:
        client.connect()
        print("Conexión al servidor MQTT establecida.")
        return client
    except Exception as e:
        print("Error conectando a MQTT:", e)
        return None


def main_loop():
    mqtt_client = connect_mqtt()
    print("Calibrando el sensor MQ-4...")
    Ro = calibrate_mq4()
    print("Calibración completada. Ro =", Ro, "kΩ")
    
    while True:
        try:
            
            adc_value = sensor_mq4.read()
            voltage = adc_to_voltage(adc_value)
            rs = calculate_rs(voltage)
            ppm = calculate_ppm(rs)
            
            sensor.measure()  
            temp = sensor.temperature() 
            hum = sensor.humidity()
            
            # Formatear datos
            ppm_form = "{:.2f}".format(ppm)
            temp_form = "{:.2f}".format(temp)
            hum_form = "{:.2f}".format(hum)
            
            # Mensaje de estado según PPM y temperatura
            if temp > 35:
                mensaje = "Peligro: Temp"
            elif 30 <= temp <= 35:
                mensaje = "Atencion: Temp"
            else:
                if ppm < 500:
                    mensaje = "Seguro"
                elif 500 <= ppm < 1000:
                    mensaje = "Atencion"
                else:
                    mensaje = "Peligro"


            # Mostrar en pantalla
            pantalla.fill(0)
            pantalla.text(mensaje, 10, 10)
            pantalla.text("PPM: " + ppm_form, 0, 30)
            pantalla.text("Temp: " + temp_form, 0, 40)
            pantalla.text("Hum: " + hum_form, 0, 50)
            pantalla.show()

            # Manejo de Umbrales
            # Umbrales para temperatura
            if temp > 35:
                led_rojo.on()  # Alarma crítica por temperatura
                led_verde.off()
                led_nrj.off()
                buzzer.duty(512)
                buzzer.freq(1000)
                time.sleep(1)
            elif 30 <= temp <= 35:
                led_nrj.on()  # Advertencia por temperatura
                led_rojo.off()
                led_verde.off()
                buzzer.freq(1000)
                buzzer.duty(512)
                time.sleep(0.5)
                buzzer.duty(0)
                time.sleep(1)
            else:
                # Umbrales para PPM
                if ppm < 500:
                    led_verde.on()
                    led_rojo.off()
                    led_nrj.off()
                    buzzer.duty(0)
                elif 500 <= ppm < 1000:
                    led_nrj.on()
                    led_rojo.off()
                    led_verde.off()
                    buzzer.freq(1000)
                    buzzer.duty(512)
                    time.sleep(0.5)
                    buzzer.duty(0)
                    time.sleep(1)
                elif ppm >= 1000:
                    led_rojo.on()
                    led_verde.off()
                    led_nrj.off()
                    buzzer.duty(512)
                    buzzer.freq(1000)
                    time.sleep(1)


            # Verificar y reconectar WiFi si está desconectado
            if not miRed.isconnected():
                print("WiFi desconectado. Intentando reconectar...")
                conectaWifi("DUVAN", "1007161216")
                
                if wifi_connected:
                    mqtt_client = connect_mqtt()  # Reconectar MQTT si WiFi vuelve
            
            # Publicar datos en MQTT si está conectado
            if mqtt_client:
                try:
                    message = ujson.dumps({
                        "PPM": ppm_form,
                        "Temperatura": temp_form,
                        "Humedad": hum_form,
                        "Estado": mensaje
                    })
                    mqtt_client.publish(MQTT_TOPIC, message)
                    print("Publicado a MQTT:", message)
                    
                except Exception as e:
                    print("Error publicando a MQTT:", e)
                    mqtt_client = connect_mqtt()  # Intentar reconectar MQTT
              
              
            time.sleep(5)  # Esperar antes de la siguiente iteración


        except Exception as e:
            print("Error en el bucle principal:", e)
            time.sleep(3)  # Pausa antes de intentar nuevamente


# Inicio del programa
if conectaWifi("DUVAN", "1007161216"):
    main_loop()
else:
    print("No se pudo establecer conexión WiFi. Continuando en modo offline.")
    main_loop()



