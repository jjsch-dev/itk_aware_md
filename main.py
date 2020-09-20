'''Aplicacion para configurar el cartel de distancimiento social
   de intelektron SA.
        
        Author: JS (Juan Schiavoni)
        Date: 17/09/2020 
'''
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.graphics import Color
from kivy import utils
from kivy.utils import platform

from kivymd.app import MDApp
#from kivymd.uix.filemanager import MDFileManager
from kivymd.toast import toast
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.slider import MDSlider
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout

from filemanager import MDFileManager

from serial_device import SerialDevice
import json
import ntpath
import pathlib
from functools import partial
import os

if platform == 'android':
    from android.storage import primary_external_storage_path
    from android.permissions import request_permissions, Permission
else:    
    from plot_distance import PlotDistance

DEVICE_CLOSE = 0
DEVICE_CONNECTING = 1
DEVICE_CONNECTED = 2
DEVICE_READ_PARAMS = 3
DEVICE_IS_REMOVE = 4

APP_TITLE = "Intelektron Aware"

class ContentNavigationDrawer(BoxLayout):
    screen_manager = ObjectProperty()
    nav_drawer = ObjectProperty()

class ProgressDialog(MDBoxLayout):
    pass

class SliderOnRelease(MDSlider):
    def __init__(self, **kwargs):
        self.register_event_type('on_release')
        super(SliderOnRelease, self).__init__(**kwargs)

    def on_release(self):
        pass

    def on_touch_up(self, touch):
        super(SliderOnRelease, self).on_touch_up(touch)
        if touch.grab_current == self:
            self.dispatch('on_release')
            return True

class ItkAware(MDApp):
    title = APP_TITLE
    icon = './images/distance_2_red.png'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conn = SerialDevice()
        self.conn_event = None
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
        self.progress_dialog = None
        self.event_plot = None
        self.plot = None

    def on_start(self):
        self.conn_event = Clock.schedule_once(self.conn_callback, 1/100)
        
        self.path = self.config.get('last-path', 'path')
        
        if not self.path:
            if platform == 'android':
                request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])

                dir_primary = primary_external_storage_path()
                self.path = os.path.join(dir_primary, 'Download')
            else:
                # Carga el ultimo path.
                self.path = str(pathlib.Path().absolute())
        
        Logger.info( "folder path: %s", self.path )
        
    def build(self):
        return Builder.load_file("layout.kv")

    def build_config(self, config):
        config.setdefaults('serial', {'port':''})
        config.setdefaults('capture', {'fpath':'capture/', 'fname':'log_aware'})
        config.setdefaults('device-log', {'fpath':'log/', 'fname':'aware.log'})
        config.setdefaults('parameters-file', {'name':'aware_cfg', 'ext':'json', 'index':0})
        config.setdefaults('last-path', {'path':''})

    def on_navdrawer(self):
        self.root.ids.nav_drawer.set_state("open")
        
        if self.root.ids.screen_manager.current == "graph_state":
            self.on_finish_plot()
        
    def get_path(self):
        if not os.path.isdir(self.path):
            return os.path.dirname(self.path)
        
        return self.path

    def file_manager_open(self):
        self.file_manager.edit_name = False
        self.file_manager.show(self.get_path())  
        self.manager_open = True

    def file_manager_save(self):
        # Genera un archivo con identificador incremental.
        index = self.config.getint('parameters-file', 'index')
        fname = "{}_{}.{}".format(self.config.get('parameters-file', 'name'), 
                                index, 
                                self.config.get('parameters-file', 'ext') )
        self.config.set('parameters-file', 'index', index + 1)
        self.config.write()

        self.file_manager.edit_name = True
        self.file_manager.show(self.get_path(), fname)  
        self.manager_open = True

    def select_path(self, path):
        '''It will be called when you click on the file name
        or the catalog selection button.

        :type path: str;
        :param path: path to the selected directory or file;
        '''
        self.path = path
        self.exit_manager()

        self.config.set('last-path', 'path', self.get_path())
        self.config.write()

        if not self.file_manager.edit_name:
            self.show_alert_open_file()
        else:
            self.save_file()
              
    def show_alert_open_file(self):
        if not self.dialog:
            self.dialog = MDDialog(
                text="Esta seguro que desea actualizar el equipo?",
                buttons=[
                    
                    MDFlatButton(
                        text="Cancelar", 
                        text_color=self.theme_cls.primary_color, 
                        on_release= self.close_alert_open_file
                    ),
                    MDRaisedButton(               
                        text="Aceptar", 
                        on_release=self.send_file
                    ),
                ],
            )
        self.dialog.title = "Cargar [{}]".format(ntpath.basename(self.path))
        self.dialog.set_normal_height()
        self.dialog.open()
    
    def set_app_title(self):
        caption = "{} [{}]".format(APP_TITLE, ntpath.basename(self.path))
        app = App.get_running_app()
        app._app_window.set_title(caption)

    def close_alert_open_file(self, inst):
        self.dialog.dismiss()
        
    def send_file(self, inst):
        self.dialog.dismiss()

        # Por ahora no se emite un mensaje cuando falta seleccionar un archivo.
        try:
            with open(self.path) as stream:
                line = stream.read()
            
            self.json_fields = json.loads( line )
            
            if self.set_fields():
                self.write_params()
            else:
                toast("Archivo corrupto")
            
            self.set_app_title()
        except: 
            toast("Problemas leyendo archivo")
    
    def save_file(self):
        if not self.conn.is_open: 
            toast("Dispositivo desconectado")
            return

        if not self.valid_parameters:
            toast("Parametros fuera de rango") 

        try:
            with open(self.path, 'w') as stream:
                stream.write(json.dumps(self.json_fields, indent=4, sort_keys=True))
            
            self.set_app_title()
        except:
           toast("Problemas creando el archivo") 

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
            self.root.ids.buzzer_ton.value = int(self.json_fields["buzzer_ton"]/100)
        else:
            all_fields = False
        
        if "buzzer_toff" in self.json_fields:
            self.root.ids.buzzer_toff.value = str(self.json_fields["buzzer_toff"]/100)
        else:
            all_fields = False

        if "point_danger" in self.json_fields:
            self.root.ids.point_danger.value = str(self.json_fields["point_danger"] / 100)
        else:
            all_fields = False

        if "point_warning" in self.json_fields:
            self.root.ids.point_warning.value = str(self.json_fields["point_warning"] / 100)
        else:
            all_fields = False

        if "point_safe" in self.json_fields:
            self.root.ids.point_safe.value = str(self.json_fields["point_safe"] / 100)
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
            self.root.ids.ewma_alpha.value = str(self.json_fields["ewma_alpha"] * 20)
        else:
            all_fields = False

        if "hysterisis" in self.json_fields:
            self.root.ids.hysterisis.value = str(self.json_fields["hysterisis"] / 100) 
        else:
            all_fields = False

        if "time_state" in self.json_fields:
            self.root.ids.time_state.value = str(self.json_fields["time_state"] / 100)  
        else:
            all_fields = False

        if not ("log_level" in self.json_fields):
            all_fields = False

        return all_fields

    def progress_dialog_start(self, value=0, title=None, text=None):
        """Called when a click on a edit button."""
        if not self.progress_dialog:
            self.progress_dialog = MDDialog(
                type="custom",
                content_cls=ProgressDialog(),
            )
        self.progress_dialog_update(value, title, text)
        self.progress_dialog.set_normal_height()  
        self.progress_dialog.open()
    
    def progress_dialog_close(self):
        if self.progress_dialog:
            self.progress_dialog.dismiss()
    
    def progress_dialog_update(self, value, title=None, text=None):
        if not self.progress_dialog:
            return

        if title:
            self.progress_dialog.title = title

        if text:
             self.progress_dialog.content_cls.children[2].text = text

        self.progress_dialog.content_cls.children[0].value = value 

    # Funcion temporizada que conecta automaticamente el equipo
    def conn_callback(self, obj):
        if self.conn_state == DEVICE_CLOSE:
            if self.device_connect():
                self.conn_state = DEVICE_CONNECTING
        elif self.conn_state == DEVICE_CONNECTING:
            if self.establish_connection():
                self.conn_state = DEVICE_READ_PARAMS
            elif self.retry_conn >= 6:
                self.device_close()
                self.conn_state = DEVICE_CLOSE
        elif self.conn_state == DEVICE_READ_PARAMS:
            self.read_params()
            self.progress_dialog_update(1)
            self.conn_state = DEVICE_CONNECTED
        elif self.conn_state == DEVICE_CONNECTED:
            if self.retry_conn >= 1:
               self.progress_dialog_close() 
               self.conn_state = DEVICE_IS_REMOVE
            else:
                self.retry_conn += 1
        elif not self.conn.is_attached:
            self.device_close()
            self.conn_state = DEVICE_CLOSE
        
        self.conn_event = Clock.schedule_once(self.conn_callback, 1)

    def device_connect(self):
        self.retry_conn = 0
        try:
            if self.conn.open(self.config.get('serial', 'port')):
                Logger.info( "device open" )
                self.progress_dialog_start(title="Conexión", text="Conectado")
                return True
        except: pass
        
        self.device_close()
        return False

    def establish_connection(self):
        self.retry_conn = self.retry_conn + 1

        self.progress_dialog_update(self.retry_conn/6)

        Logger.info( "connecting try %d", self.retry_conn )
        try:
            # desactiva el log para que el consumo de CPU disminuya.
            answ = self.conn.json_cmd("log_level", "0")
            if answ and ("log_level" in answ.keys()):
                self.json_fields = self.conn.json_cmd(key="info", value="version")
                if self.json_fields and ("version" in self.json_fields.keys()):
                    
                    self.root.ids.firmware_version.text = self.json_fields["version"]
                    
                    self.progress_dialog_update(0.8, 
                                                text="Firmware V" + self.json_fields["version"],
                                                title="Leyendo")
                    # Resetea el contador para que muestre el mensaje de version
                    # por unos segundos.
                    self.retry_conn = 0
                    self.usb_icon(on_line=True)
                    
                    Logger.info( "device connected" )
                   
                    return True
        except: pass
        
        return False

    def usb_icon(self, on_line):
        item = self.root.ids.toolbar.right_action_items[0][0]
        icon = "usb-port" if on_line else "ethernet-cable-off"
        if item != icon:
            self.root.ids.toolbar.right_action_items.pop(0)
            self.root.ids.toolbar.right_action_items.insert(0, [icon, lambda x: None])

    def device_close(self):
        self.retry_conn = 0

        self.usb_icon(on_line=False)
        self.progress_dialog_close()
        self.root.ids.firmware_version.text = ""

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
        self.progress_dialog_close()

    def save_params_callback(self, data, *largs):
        # Indica que se completaron dos tercios de la operacion.
        self.progress_dialog_update(2/3)

        if self.conn.is_open:
            data_json = json.dumps(data)
            if not self.conn.send_cmd(data_json) :
                toast("Problemas grabando")
            else:
                self.json_fields = data
                self.valid_parameters = True
                
                self.progress_dialog_update(1, text="actualizado")

                self.write_ok_event = Clock.schedule_once(self.write_ok_callback, 1) 
        else:
            toast("Dispositivo desconectado")

    def write_params(self):
        if self.save_params_event:
            self.save_params_event.cancel()
       
        if self.write_ok_event:
            self.write_ok_event.cancel()

        # Se completo un tercio de la operacion.
        self.progress_dialog_start(1/3, title="Actualizando", text="configuración") 

        data = {}
        try:
            data["buzzer"] = self.root.ids.buzzer_enable.active
            data["buzzer_ton"] = int(self.root.ids.buzzer_ton.value) * 100
            data["buzzer_toff"] = int(self.root.ids.buzzer_toff.value) * 100
            data["point_danger"] = int(self.root.ids.point_danger.value) * 100
            data["point_warning"] = int(self.root.ids.point_warning.value) * 100
            data["point_safe"] = int(self.root.ids.point_safe.value) * 100
            data["color_danger"] = self.color_to_int(self.root.ids.color_danger.color)
            data["color_warning"] = self.color_to_int(self.root.ids.color_warning.color)
            data["color_safe"] = self.color_to_int(self.root.ids.color_safe.color)
            data["ewma_alpha"] = float(self.root.ids.ewma_alpha.value/20) 
            data["hysterisis"] = int(self.root.ids.hysterisis.value) * 100
            data["time_state"] = int(self.root.ids.time_state.value) * 100
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
    
    def show_alert_factory_reset(self):
        # Los parametros no se pueden modificar cuando esta graficando los estados
        if self.root.ids.screen_manager.current == "graph_state":
            return

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

    def is_level_json(self):
        try:
            if self.valid_parameters and self.json_fields["log_level"] == 2:
                return True
        except:
            return False

    def on_plot(self):
        if platform == 'android':
            toast("No soportado")
        else:
            if not self.conn.is_open:
                toast("Dispositivo desconectado")
                return

            if not self.valid_parameters:
                toast("Lea los parametros del equipo")
                return
                
            if not self.is_level_json():
                json_level = self.conn.json_cmd("log_level", "2")

                if not json_level:
                    toast("No se pudo activar el log")
                    return 

            local_path = str(pathlib.Path().absolute())
            fname_log = os.path.join(local_path, "itk-aware.log")
        
            self.plot = PlotDistance(self.root.ids.plot_box,
                                fname_log = fname_log, 
                                fpath_image = self.config.get("capture", "fpath"),
                                fname_image = self.config.get("capture", "fname"),
                                point_danger = self.json_fields["point_danger"],
                                point_warning = self.json_fields["point_warning"],
                                point_safe = self.json_fields["point_safe"],
                                color_danger = self.root.ids.color_danger.color,
                                color_warning = self.root.ids.color_warning.color,
                                color_safe = self.root.ids.color_safe.color )
            
            def update_plot(self, obj):
                try:
                    for i in range(20):
                        log_fields = self.conn.json_answ(key="info", value="log", timeout=1/100)
                        # Verifica que el JSON retornado contenga los campos
                        # necesarios para graficar.
                        s1 = set(["time", "raw", "filtered", "state"]) 
                        if s1.issubset( log_fields.keys() ) == True:
                            self.plot.add( log_fields )
                        else:    
                            break
                        
                    self.plot.update()
                except: pass

            self.event_plot = Clock.schedule_interval(partial(update_plot, self), 1/100)
            
    def on_finish_plot(self):
        if self.event_plot:
            self.event_plot.cancel()
        
        self.conn.json_cmd("log_level", "0")
        
        if self.plot:
            self.plot.close()

ItkAware().run()