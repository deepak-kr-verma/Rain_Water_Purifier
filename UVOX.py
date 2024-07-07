import smbus
import time
import requests
import RPi.GPIO as GPIO
import os

DL = 13.3
DL1 = 0.5

address = 0x28
address1 = 0x68
address2 = 0x6e

# Set up GPIO mode and pin number
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO_ALARM = 26
GPIO_PUMP = 20
GPIO_UV = 21

# Set up GPIO pin as Output
GPIO.setup(GPIO_ALARM, GPIO.OUT)
GPIO.setup(GPIO_PUMP, GPIO.OUT)
GPIO.setup(GPIO_UV, GPIO.OUT)

# Global variable to store pump start time
pump_start_time = None
uv_start_time = None
pump_runtime = None
uv_runtime = None

channel1 = 0x18   #Continuous conversion mode, Channel-1, 16-bit Resolution, gain 1
channel2 = 0x38   #Continuous conversion mode, Channel-2, 16-bit Resolution, gain 1
channel3 = 0x58   #Continuous conversion mode, Channel-3, 16-bit Resolution, gain 1
channel4 = 0x78   #Continuous conversion mode, Channel-4, 16-bit Resolution, gain 1
channel5 = 0x18   #Continuous conversion mode, Channel-1, 16-bit Resolution, gain 1
channel6 = 0x38   #Continuous conversion mode, Channel-2, 16-bit Resolution, gain 1
channel7 = 0x58   #Continuous conversion mode, Channel-3, 16-bit Resolution, gain 1
channel8 = 0x78   #Continuous conversion mode, Channel-4, 16-bit Resolution, gain 1

def get_mac_address(interface):
	try:
		# Read the MAC address directly from the system file
		with open(f'/sys/class/net/{interface}/address') as f:
			mac_address = f.read().strip()
		return mac_address
	except FileNotFoundError:
		return None
	except Exception as e:
		return str(e)

def get_active_interfaces():
	interfaces = []
	try:
		# List all network interfaces
		for interface in os.listdir('/sys/class/net/'):
			# Check if the interface is up by reading the operstate file
			with open(f'/sys/class/net/{interface}/operstate') as f:
				if f.read().strip() =='up':
					interfaces.append(interface)
	except Exception as e:
		return str(e)
	return interfaces

def read_humidity_temperature(bus, address):
	bus.write_byte(address, 0x80)
	time.sleep(DL1)
	data = bus.read_i2c_block_data(address, 0x00, 4)
	H1 = (((data[0] & 0x3F) * 256) + data[1]) / 16384.0 * 100.
	T3 = (((data[2] * 256) + (data[3] & 0xFC)) / 4) / 16384.0 * 165.0 - 40.0
	return H1, T3

def read_UV_sensor(bus, address1):
	bus.write_byte(address1, channel1)
	time.sleep(DL1)
	data1 = bus.read_i2c_block_data(address1, 0x00, 2)
	UV = ((data1[0] << 8) | data1[1])
	if (UV >= 32768):
		UV = 65536 - UV
	UV = UV / 10.00
	return UV

def read_temperature_in_UVOX(bus, address1):
	bus.write_byte(address1, channel2)
	time.sleep(DL1)
	data2 = bus.read_i2c_block_data(address1, 0x00, 2)
	raw_adc = ((data2[0] << 8) | data2[1])
	if (raw_adc >= 32768):
		raw_adc = 65536 - raw_adc
	T2 = (raw_adc - 32) / 1.8
	return T2

def read_temperature_in_pool(bus, address1):
	bus.write_byte(address1, channel3)
	time.sleep(DL1)
	data3 = bus.read_i2c_block_data(address1, 0x00, 2)
	raw_adc1 = ((data3[0] << 8) | data3[1])
	T1 = raw_adc1
	T1 = T1 / 100.0
	if (raw_adc1 >= 32768):
		raw_adc1 = 65536 - raw_adc1
	return raw_adc1, T1
	#T1 = (raw_adc1 - 32) / 1.8
	#return T1

def read_REDOX_sensor(bus, address1):
	bus.write_byte(address1, channel4)
	time.sleep(DL1)
	data = bus.read_i2c_block_data(address1, 0x00, 2)
	redox = ((data[0] << 8) | data[1])
	return redox

def convert_to_voltage(adc_value, pga = 1):
	# Vref for MCP3428 is 2.048V
	vref = 2.048
	vtg = ((adc_value / 32768.0) * vref / pga)
	return vtg * 10

def read_water_pressure(bus, address2):
	bus.write_byte(address2, channel5)
	time.sleep(DL1)
	data = bus.read_i2c_block_data(address2, 0x00, 2)
	pressure = ((data[0] << 8) | data[1])
	P2_bar = (pressure / 14.504)
	return P2_bar

def read_water_pressure_1(bus, address2):
	min_pressure = 0  # Minimum pressure in bar
	max_pressure = 10  # Maximum pressure in bar
	min_current = 4.0  # mA
	max_current = 20.0  # mA

	pressure_range = max_pressure - min_pressure
	current_range = max_current - min_current

	bus.write_byte(address2, channel6)
	time.sleep(DL1)
	val = bus.read_i2c_block_data(address2, 0x00, 2)
	pressure_raw = ((val[0] << 8) | val[1])
	pressure = ((pressure_raw - min_current) / current_range) * pressure_range + min_pressure
	return pressure
	'''P3_bar = (pressure_raw / 14.504)
	return P3_bar
'''
def read_flow_meter(bus, address2):
	bus.write_byte(address2, channel7)
	time.sleep(DL1)
	val1 = bus.read_i2c_block_data(address2, 0x00, 2)
	flow_data = ((val1[0] << 8) | val1[1])
	flow = flow_data / 7.5
	return flow

def turn_on_system_alarm():
	GPIO.output(GPIO_ALARM, GPIO.LOW)

def turn_off_system_alarm():
	GPIO.output(GPIO_ALARM,GPIO.HIGH)

def turn_on_pump():
	GPIO.output(GPIO_PUMP, GPIO.LOW)

def turn_off_pump():
	GPIO.output(GPIO_PUMP, GPIO.HIGH)

def turn_on_uv():
	GPIO.output(GPIO_UV, GPIO.LOW)

def turn_off_uv():
	GPIO.output(GPIO_UV, GPIO.HIGH)

def calculate_pump_running_time():
	if pump_start_time:
		return time.time() - pump_start_time
	else:
		return 0

def calculate_uv_running_time():
	if uv_start_time:
		return time.time() - uv_start_time
	else:
		return 0

def post_data(payloads):
	for item in payloads:
		response = requests.post(item["url"], json=item["data"])

def post_mac_address(mac_address):
	url = "http://uvoxapi.adequateshop.com/api/AddMacAddress"
	payload = {"address": mac_address}
	headers = {
		'Content-Type': 'application/json'
	}
	response = requests.post(url, json=payload, headers=headers)

def post_switch_address(type, status):
	url = "http://uvoxapi.adequateshop.com/api/UpdateAddressSwitch"
	payload = {"switchType":type,
		"status":status
	}
	headers = {
		'Content-type': 'application/json'
	}
	response = requests.post(url, json=payload, headers=headers)

def get_relay_status():
	url = "http://uvoxapi.adequateshop.com/api/GetDeviceAddress"
	# Send a GET request to the URL
	response = requests.get(url)
	if response.status_code == 200:
		data = response.json()
		return data
	else:
		return None

def main():
	global uv_start_time
	global pump_start_time
	global uv_runtime
	global pump_runtime

	active_interfaces = get_active_interfaces()
	if not active_interfaces:
		return

	for interface in active_interfaces:
		mac_address = get_mac_address(interface)
		if mac_address:
			post_mac_address(mac_address)

	# Get I2C bus
	bus = smbus.SMBus(1)

	while True:
		H1, T3 = read_humidity_temperature(bus, address)
		UV = read_UV_sensor(bus, address1)
		T2 = read_temperature_in_UVOX(bus, address1)
		adc_value, T1 = read_temperature_in_pool(bus, address1)
		REDOX = read_REDOX_sensor(bus, address1)
		P2 = read_water_pressure(bus, address2)
		P3 = read_water_pressure_1(bus, address2)
		FL = read_flow_meter(bus, address2)

		# Read Voltage
		voltage = convert_to_voltage(adc_value)
		print("Voltage: %.3f V" %voltage)
		T2 = (T2 * 1.111111)
		T3 = (T3 * 1.111111)

		# Relay switch status
		relay_state = get_relay_status()
		relayA = relay_state['relaySwitchA']
		relayB = relay_state['relaySwitchB']
		relayC = relay_state['relaySwitchC']

		if voltage > 7.7:
			turn_on_system_alarm()
			post_switch_address(0, True)
			print("Turn on relay A")
		else:
			turn_off_system_alarm()
			post_switch_address(0, False)
			print("turn off realy A")

		if relayB:
			print("turn on relay B")
			turn_on_pump()
			pump_start_time = time.time()  # Record pump start time
		else:
			print("turn off relay B")
			turn_off_pump()
			pump_runtime = calculate_pump_running_time()
			pump_runtime = pump_runtime / 3600

		if relayC:
			turn_on_uv()
			print("turn on relay C")
			uv_start_time = time.time()  # Record uv start time
		else:
			print("turn off relay C")
			turn_off_uv()
			uv_runtime = calculate_uv_running_time()
			uv_runtime = uv_runtime / 3600

		#print("Humidity Environment :     %.2f %%RH" % H1)
		#print("Temperature Environment :  %.2f C" % T3)
		#print("uv Sensor :                %.2f %%" % UV)
		#print("Temperature in UVOX :      %.2f C" % T2)
		#print("Temperature in pool :      %.2f C" % T1)
		#print("Water Pressure p2:         %.2f bar" % P2)
		#print("Water Pressure p3:         %.2f bar" % P3)
		#print("Water Flow Rate:           %.2f L/min" % FL)
		print("--------------------------------------------------------------")

		payloads = [
			{
				"url": "http://uvoxapi.adequateshop.com/api/AddTemperature",
				"data": {
					"pointId": 1002,
					"incelsius": T1,
					"unitType": "celsius"
					}
			},
			{
				"url": "http://uvoxapi.adequateshop.com/api/AddTemperature",
				"data": {
					"pointId": 4,
					"incelsius": T2,
					"unitType": "gr"
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddTemperature",
				"data": {
					"pointId": 3,
					"incelsius": T3,
					"unitType": "gr"
					}
			},
			{
				"url": "http://uvoxapi.adequateshop.com/api/AddHumidity",
				"data": {
					"pointId": 2,
					"valueInPercentage": H1
					}
			},
			{
				"url": "http://uvoxapi.adequateshop.com/api/AddSensor",
				"data": {
					"pointId": 1,
					"valueInPercentage": UV
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddFlowMeterData",
				"data": {
					"pointId": 1005,
					"value": FL,
					"unitType": "L/Min"
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddWaterPressureData",
				"data": {
					"pointId": 1004,
					"value": P2,
					"unitType": "bar"
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddWaterPressureData",
				"data":{
					"pointId": 1006,
					"value": P3,
					"unitType": "bar"
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddTimerData",
				"data":{
					"pointId": 1007,
					"value":uv_runtime ,
					"unitType": "hour"
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddTimerData",
				"data":{
					"pointId": 1008,
					"value": 1,
					"unitType": "hour"
					}
			},
			{
				"url":"http://uvoxapi.adequateshop.com/api/AddTimerData",
				"data":{
					"pointId": 1009,
					"value": 0,
					"unitType": "hour"
					}
			}

		]

		post_data(payloads)

if __name__ == "__main__":
	main()
