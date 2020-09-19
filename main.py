'''Aplicacion para configurar el cartel de distancimiento social
   de intelektron SA.
        
        Author: JS (Juan Schiavoni)
        Date: 17/09/2020 
'''
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.graphics import Color
from kivy import utils

from kivymd.app import MDApp
#from kivymd.uix.filemanager import MDFileManager
from kivymd.toast import toast
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog

from filemanager import MDFileManager

from serial_device import SerialDevice
import json

DEVICE_CLOSE = 0
DEVICE_CONNECTING = 1
DEVICE_CONNECTED = 2

from functools import partial

class ContentNavigationDrawer(BoxLayout):
    screen_manager = ObjectProperty()
    nav_drawer = ObjectProperty()

class ItkAware(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conn = SerialDevice()
        self.conn_event = None
        self.firmware_version = None
        self.json_fields = []
        self.conn_state = DEVICE_CLOSE
       # Window.bind(on_keyboard=self.events)
        self.manager_open = False
        self.write_ok_event = None
        self.save_params_event = None
        self.dialog = None
        self.file_manager = MDFileManager(
           exit_manager=self.exit_manager,
           select_path=self.select_path,
           preview=False)
        self.file_manager.ext.clear()
        self.file_manager.ext.append(".json")

    def on_start(self):
        self.conn_event = Clock.schedule_once(self.conn_callback, 1/100)
        
    def build(self):
        return Builder.load_file("layout.kv")

    def build_config(self, config):
        config.setdefaults('serial', {'port': ''})
        config.setdefaults('capture', {'fpath':'capture/', 'fname':'log_aware'})
        config.setdefaults('device-log', {'fpath':'log/', 'fname':'aware.log'})
        config.setdefaults('parameters-file', {'name':'aware_cfg', 'ext':'json', 'index':0})

    def file_manager_open(self):
        self.file_manager.save_mode = False
        self.file_manager.show('/home/jjsch/Desktop', "")  # output manager to the screen
        self.manager_open = True

    def file_manager_save(self):
        self.file_manager.save_mode = True
        self.file_manager.show('/home/jjsch/Desktop', "test.js")  # output manager to the screen
        self.manager_open = True

    def select_path(self, path):
        '''It will be called when you click on the file name
        or the catalog selection button.

        :type path: str;
        :param path: path to the selected directory or file;
        '''
        self.path = path
        self.exit_manager()

        if not self.file_manager.save_mode:
            self.show_alert_open_file()
              
    def show_alert_open_file(self):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Cargar archivo",
                text="Esta seguro que desea actualizar el equipo?",
                buttons=[
                    
                    MDFlatButton(
                        text="Cancelar", 
                        text_color=self.theme_cls.primary_color, 
                        on_release= self.close_alert_open_file
                    ),
                    MDRaisedButton(               
                        text="Aceptar", 
                        text_color=self.theme_cls.primary_color,
                        on_release=self.send_file
                    ),
                ],
            )
        self.dialog.set_normal_height()
        self.dialog.open()
    
    def close_alert_open_file(self, inst):
        self.dialog.dismiss()

    def send_file(self, inst):
        self.dialog.dismiss()

    def exit_manager(self, *args):
        '''Called when the user reaches the root of the directory tree.'''

        self.manager_open = False
        self.file_manager.close()

    def int_to_color(self, val):
        val = '{:06x}'.format(val, 'x') 
        kivy_color = utils.get_color_from_hex(val)
        return kivy_color

    def color_to_int(self, kyvi_color):
        hex_val = utils.get_hex_from_color(kyvi_color)
        val = hex_val.replace('#', '')
        val = val[:-2]
        integer = int(val, 16)
        return integer

    def set_fields(self):
        all_fields = True

        if "buzzer" in self.json_fields:
            self.root.ids.buzzer_enable.active = bool(self.json_fields["buzzer"])
        else:
            all_fields = False

        if "buzzer_ton" in self.json_fields:
            self.root.ids.buzzer_ton.text = str(self.json_fields["buzzer_ton"])
        else:
            all_fields = False
        
        if "buzzer_toff" in self.json_fields:
            self.root.ids.buzzer_toff.text = str(self.json_fields["buzzer_toff"])
        else:
            all_fields = False

        if "point_danger" in self.json_fields:
            self.root.ids.point_danger.text = str(self.json_fields["point_danger"])
        else:
            all_fields = False

        if "point_warning" in self.json_fields:
            self.root.ids.point_warning.text = str(self.json_fields["point_warning"])
        else:
            all_fields = False

        if "point_safe" in self.json_fields:
            self.root.ids.point_safe.text = str(self.json_fields["point_safe"])
        else:
            all_fields = False

        if "color_danger" in self.json_fields: 
            self.root.ids.color_danger.color = self.int_to_color(self.json_fields["color_danger"])
        else:
            all_fields = False

        if "color_warning" in self.json_fields: 
            self.root.ids.color_warning.color = self.int_to_color(self.json_fields["color_warning"])
        else:
            all_fields = False

        if "color_safe" in self.json_fields: 
            self.root.ids.color_safe.color = self.int_to_color(self.json_fields["color_safe"])
        else:
            all_fields = False

        if "ewma_alpha" in self.json_fields: 
            self.root.ids.ewma_alpha.text = str(self.json_fields["ewma_alpha"])
        else:
            all_fields = False

        if "hysterisis" in self.json_fields:
            self.root.ids.hysterisis.text = str(self.json_fields["hysterisis"]) 
        else:
            all_fields = False

        if "time_state" in self.json_fields:
            self.root.ids.time_state.text = str(self.json_fields["time_state"])  
        else:
            all_fields = False

        if not ("log_level" in self.json_fields):
            all_fields = False

        return all_fields

    # Funcion temporizada que conecta automaticamente el equipo
    def conn_callback(self, obj):
        if self.conn_state == DEVICE_CLOSE:
            if self.device_connect():
                self.conn_state = DEVICE_CONNECTING
        elif self.conn_state == DEVICE_CONNECTING:
            if self.establish_connection():
                self.conn_state = DEVICE_CONNECTED
            elif self.retry_conn >= 6:
                self.device_close()
                self.conn_state = DEVICE_CLOSE
        elif not self.conn.is_attached:
            self.device_close()
            self.conn_state = DEVICE_CLOSE
        
        self.conn_event = Clock.schedule_once(self.conn_callback, 1)

    def device_connect(self):
        self.retry_conn = 0
        try:
            if self.conn.open(self.config.get('serial', 'port')):
                Logger.info( "device open" )
                self.progress_spinner(active = True)
                return True
        except: pass
        
        self.device_close()
        return False

    def establish_connection(self):
        self.retry_conn = self.retry_conn + 1
 
        Logger.info( "connecting try %d", self.retry_conn )
        try:
            # desactiva el log para que el consumo de CPU disminuya.
            answ = self.conn.json_cmd("log_level", "0")
            if answ and ("log_level" in answ.keys()):
                self.json_fields = self.conn.json_cmd(key="info", value="version")
                if self.json_fields and ("version" in self.json_fields.keys()):
                    self.firmware_version = self.json_fields["version"]
                    self.show_firmware_version()
                    self.read_params()
                    self.usb_icon(on_line=True)
                    
                    Logger.info( "device connected" )

                    self.progress_spinner(active = False)
                    
                    return True
        except: pass
        
        return False

    def usb_icon(self, on_line):
        item = self.root.ids.toolbar.right_action_items[0][0]
        icon = "usb-port" if on_line else "ethernet-cable-off"
        if item != icon:
            self.root.ids.toolbar.right_action_items.pop(0)
            self.root.ids.toolbar.right_action_items.insert(0, [icon, lambda x: None])

    def progress_spinner(self, active):
        if self.root.ids.spinner_progress.active != active:
            self.root.ids.spinner_progress.active = active

    def device_close(self):
        self.retry_conn = 0

        self.progress_spinner(active = False)
        self.usb_icon(on_line=False)

        if self.conn.is_open:
            Logger.info( "device_close" )
                
        self.conn.close()
    
    def read_params(self):
        if not self.conn.is_open:
            toast("Dispositivo desconectado")
            return
   
        # Para evitar incosistencias, invalida los parametros leidos.
        self.valid_parameters = False
        self.json_fields = self.conn.json_cmd(key="info", value="all-params", timeout=3)
        self.valid_parameters = self.set_fields()

        # A partir de la version 1.8 la respuesta incluye el comando.
        self.json_fields.pop('info', None)
        
        if not self.valid_parameters:
            toast( "Problemas leyendo" )
    
    def write_ok_callback(self, obj):
        self.progress_spinner(active=False)
        toast("actualizado")

    def save_params_callback(self, data, *largs):
        if self.conn.is_open:
            data_json = json.dumps(data)
            if not self.conn.send_cmd(data_json) :
                toast("Problemas grabando")
            else:
                self.json_fields = data
                self.valid_parameters = True
                 
                self.write_ok_event = Clock.schedule_once(self.write_ok_callback, 1) 
        else:
            toast("Dispositivo desconectado")

    def write_params(self):
        if self.save_params_event:
            self.save_params_event.cancel()
       
        if self.write_ok_event:
            self.write_ok_event.cancel()

        self.progress_spinner(active=True)

        data = {}
        try:
            data["buzzer"] = self.root.ids.buzzer_enable.active
            data["buzzer_ton"] = int(self.root.ids.buzzer_ton.text)
            data["buzzer_toff"] = int(self.root.ids.buzzer_toff.text)
            data["point_danger"] = int(self.root.ids.point_danger.text)
            data["point_warning"] = int(self.root.ids.point_warning.text)
            data["point_safe"] = int(self.root.ids.point_safe.text)
            data["color_danger"] = self.color_to_int(self.root.ids.color_danger.color)
            data["color_warning"] = self.color_to_int(self.root.ids.color_warning.color)
            data["color_safe"] = self.color_to_int(self.root.ids.color_safe.color)
            data["ewma_alpha"] = float(self.root.ids.ewma_alpha.text) 
            data["hysterisis"] = int(self.root.ids.hysterisis.text)
            data["time_state"] = int(self.root.ids.time_state.text)
            data["log_level"] = 0
        except:
            toast("Parámetros fuera de rango")
            return

        #if self.ids.point_danger.min_value > data["point_danger" ] < self.ids.point_danger.max_value:
        #    toast("Peligro fuera de rango")

        if data["point_danger"] > data["point_warning"]:
            toast("Peligro debe ser menor que precaución")
            return

        if  data["point_warning"] > data["point_safe"]:
            toast("Precaución debe ser menor que seguro")
            return
            
        if self.conn.is_open: 
            self.save_params_event = Clock.schedule_once(partial(self.save_params_callback, data), 1/10) 
        else:
            toast("Dispositivo desconectado")

    def show_firmware_version(self):
        toast( "Firmware V" + self.firmware_version )
    
    def show_alert_factory_reset(self):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Resetear a fabrica?",
                text="Se cargaran en el dispositivo los valores de fabrica.",
                buttons=[
                    
                    MDFlatButton(
                        text="Cancelar", 
                        text_color=self.theme_cls.primary_color, 
                        on_release= self.close_alert_factory
                    ),
                    MDRaisedButton(               
                        text="Aceptar", 
                        text_color=self.theme_cls.primary_color,
                        on_release=self.on_load_default
                    ),
                ],
            )
        self.dialog.set_normal_height()
        self.dialog.open()
    
    def close_alert_factory(self, inst):
        self.dialog.dismiss()

    def on_load_default(self, inst):
        self.dialog.dismiss()

        if not self.conn.is_open: 
            toast("Dispositivo desconectado")
            return

        if self.json_fields:
            self.json_fields.clear()

        data = {}
        data["buzzer"] = False
        data["buzzer_ton"] = 200
        data["buzzer_toff"] = 2000
        data["point_danger"] = 800
        data["point_warning"] = 1000
        data["point_safe"] = 1200
        data["color_danger"] = 0xFF0000
        data["color_warning"] = 0x00FFFF00
        data["color_safe"] = 0xFF00
        data["ewma_alpha"] = 0.1
        data["hysterisis"] = 100
        data["time_state"] = 1000
        data["log_level"] = 0

        line = json.dumps(data)
        # Es una forma simple de convertir los false a False de Python 
        self.json_fields = json.loads( line )
        self.set_fields()

        self.write_params()


ItkAware().run()