'''Lib de comunicacion serie en formato JSON.
        
        Author: JS (Juan Schiavoni)
        Date: 10/09/2020 
'''
from kivy.utils import platform
from kivy.logger import Logger

if platform == 'android':
    from usb4a import usb
    from usbserial4a import serial4a
else:
    import serial
    import serial.tools.list_ports

from serial.serialutil import Timeout

import json
import time
import threading
from queue import Queue

class SerialDevice():
    def __init__(self, *args, **kwargs):
        self.device = None
        self.read_thread = None
        self.port_thread_lock = threading.Lock()
        self.close_event = threading.Event()

        self.recv_queue = Queue(100)
        self.port = None

    def find_device_port(self):
        ports = {}

        try:
            if platform == 'android':
                ports = usb.get_usb_device_list()
                port = ports[0].getDeviceName()
                return port
            else:
                ports = serial.tools.list_ports.comports()
                for port in ports:
                    if ("VID:PID=1A86:7523" in port.hwid) or ("VID:PID=2341:0043" in port.hwid):
                        return port.device
        except: pass

        return ""  

    @property
    def is_attached(self):
        ports = {}
        if self.is_open:
            try:
                if platform == 'android':
                    ports = usb.get_usb_device_list()
                    port = ports[0].getDeviceName()
                    return bool(port == self.port)
                else:
                    ports = serial.tools.list_ports.comports()
                    for port in ports:
                        if port.device == self.port:
                            return True
            except: pass
        return False  

    def open(self, port):
        if not port:
            port = self.find_device_port()
        try:
            if not port:
                return False
            
            if platform == 'android':
                device = usb.get_usb_device(port)
                Logger.info( "Serial device open device: %s", device )
                if not usb.has_usb_permission(device):
                    usb.request_usb_permission(device)
                    return
                self.device = serial4a.get_serial_port(port, 115200, 8, 'N', 1, timeout=1)

                if platform == 'android':
                    self.device.USB_READ_TIMEOUT_MILLIS = 1000
            else:
                self.device = serial.Serial(port, 115200, 8, 'N', 1, timeout=1)
        except:
            return False
        
        # Inicializa la señal de stop del thread de recepcion.
        self.close_event.clear()

        # Abre el thread de recepcion de mensajes JSON.
        if self.is_open and not self.read_thread:
            self.read_thread = threading.Thread(target = self.read_msg_thread)
            self.read_thread.start()
        
        # Guarda el puerto para detectar desconexion de USB
        self.port = port 
        
        return True

    def close(self):
        try:
            if self.is_open:
                # Le informa al thread de recepcion que la conexion se cerro.
                self.close_event.set()
                with self.port_thread_lock:
                    Logger.info( "Serial device close" )
                    self.device.close()
            
            self.port = None
            return True
        except:
            return False
    
    @property
    def is_open(self):
        try:
            return self.device and self.device.is_open
        except:
            return False

    def send_cmd(self, msg):
        try:
            if self.is_open: 
                Logger.info( "send_cmd - msg: %s", msg )
                self.device.write(msg.encode(encoding='ascii')) 
        except:
            return False

        return bool(self.is_open) 

    def read_cmd(self, timeout):
        try:
            return self.recv_queue.get(block=True, timeout=timeout)
        except:
            return {}

    '''Send an information command and wait for the response in JSON format
        
        Parameters:
            key (string): json key
            value (string): required field.
            timeout (float): maximum time to wait for message reception.
        Returns:
            msg (dictionary): empty when not received. 
    '''
    def json_cmd(self, key, value, timeout=1):
        msg = "{" + key + ":'" + value + "'}"
        if self.send_cmd(msg) == True:
           return self.json_answ(key, value, timeout)
        return {}   

    def json_answ(self, key, value, timeout=1):
        timer = Timeout(timeout)
        while not timer.expired():
            msg = self.read_cmd(timeout)
            if msg and (key in msg.keys()):
                if msg[key] == value:
                    return msg
        return {}

    '''Message reception thread in JSON format.
       Insert a new dictionary into the message queue
    '''
    def read_msg_thread(self):
        line = ""
        while True:
            try:
                with self.port_thread_lock:
                    if self.close_event.is_set():
                        break

                    i = max(1, self.device.in_waiting)
                    msg = self.device.read(i).decode("utf-8")

                if msg:
                    line += msg
                    while line:
                        start_char = line.find("{")
                        end_char = line.find("}")

                        # Si el comienzo es mayor que el final, descarta el principio.
                        if (end_char != -1) and (start_char >= end_char):
                            line = line[start_char:]
                        # Corta el string cuando encuentra el final y principio.
                        elif (start_char != -1) and (end_char != -1):
                            json_msg = line[ start_char:end_char+1 ]

                            # Busca desde el final la ocurrencia de un nuevo comienzo
                            start_char = json_msg.rfind("{")
                            if start_char > 0:
                                json_msg = json_msg[ start_char: ]

                            json_msg = json_msg.replace('\r\n', '')
                            json_dict = json.loads(json_msg)
                            
                            # Si hay un diccionario valido lo inserta en la queue
                            self.queue_put(json_dict)
                            
                            # Descarta el tramo del mensaje procesado
                            line = line[end_char+2:]
                        else:
                            break                        
            except:
                with self.port_thread_lock:
                    self.device.close()
                    break

        self.read_thread = None

    # Si hay un diccionario valido lo inserta en la queue
    def queue_put(self, json_dict):
        if json_dict:
            if  self.recv_queue.full():
                msg = self.recv_queue.get()

            self.recv_queue.put(json_dict)
        return self.recv_queue.qsize()
            
    def rcv_timeout(self, seconds):
        try:
            self.device.timeout = seconds
        except: pass
        