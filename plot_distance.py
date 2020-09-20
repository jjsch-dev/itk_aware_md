from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.event import EventDispatcher

from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
import matplotlib.pyplot as plt
from collections import deque

import json
import pathlib
import os
from time import localtime, strftime

class PlotDistance(EventDispatcher):
    def __init__(self, fname_log, fpath_image, fname_image, point_danger ,point_warning, point_safe, 
                 color_danger, color_warning, color_safe, **kwargs):
        self.fname_log = fname_log
        self.fpath_image = fpath_image
        self.fname_image = fname_image
        self.point_danger = point_danger
        self.point_warning = point_warning
        self.point_safe = point_safe
        self.color_danger = color_danger
        self.color_warning = color_warning
        self.color_safe = color_safe

        self.plot_max_len = 500
        # Grafico 
        self.raw_x = deque([0])
        self.raw_y = deque([0])
        self.filtered_x = deque([0])
        self.filtered_y = deque([0])
        self.state_x = deque([0])
        self.state_y = deque([0])
        self.log_time = deque([0])
        
        self.index = 0
        
        self.fig, self.ax = plt.subplots()  # Create a figure and an axes.
        self.line_raw = self.ax.plot(self.raw_x, self.raw_y, label='sensor')  # Plot some data on the axes.
        self.line_filtered = self.ax.plot(self.filtered_x, self.filtered_y, label='filtro')
        self.line_state = self.ax.plot(self.state_x, self.state_y, label='estado', color = self.color_safe)
        self.ax.set_xlabel('segundos')  # Add an x-label to the axes.
       
        h = self.ax.set_ylabel('mm')  # Add a y-label to the axes.
        h.set_rotation(0) # Horizontal
        self.ax.yaxis.set_label_coords(-0.1, 1.02) # Arriba a la izquierda
        
        self.ax.legend()  # Add a legend.
        self.ax.set_xlim(0, self.plot_max_len)
        self.ax.set_ylim(0, 8500)
        
        self.box = BoxLayout(orientation = "vertical", padding = 10, spacing = 10)
        self.button_layout = BoxLayout(size_hint = (1, 0.1), orientation = "horizontal") 
        self.play_button = ToggleButton(text = "Comenzar") 
        self.log_button = ToggleButton(text = "Log")
        self.picture_button = Button(text = "Foto")
        self.exit_button = Button(text = "Salir")
        self.button_layout.add_widget(self.play_button)
        self.button_layout.add_widget(self.log_button)
        self.button_layout.add_widget(self.picture_button)
        self.button_layout.add_widget(self.exit_button)
        
        self.fig_canvas = FigureCanvasKivyAgg(plt.gcf())
        self.box.add_widget(self.fig_canvas)
        self.box.add_widget(self.button_layout)

        self.register_event_type('on_plot_close')
        
        def on_play_text(self):
            self.text = "Detener" if self.state == "down" else "Comenzar"

        self.play_button.bind(on_press = on_play_text)
        self.picture_button.bind(on_press = self.capture_picture)

    def capture_picture(self, obj):
        try:
            local_path = str(pathlib.Path().absolute())
            results_dir = os.path.join(local_path, self.fpath_image)

            if not os.path.isdir(results_dir):
                os.makedirs(results_dir)

            now_time = strftime("_%H%M%S_%d%m%Y.png", localtime())

            fname = results_dir + self.fname_image + now_time

            plt.savefig(fname, bbox_inches='tight')
        except: pass

    def add_y(self, buf, val):
        len_buf = len(buf)
        if len_buf >= self.plot_max_len:
            buf.rotate(-1)
            buf.pop()

        buf.append(val)

    def add_x(self, buf, val):
        len_buf = len(buf)
        if len_buf < self.plot_max_len:
            buf.append(val)

    def update_plot_axis_x_ticks(self):
        xticks = list()
        tick = 0

        while len(self.log_time) > tick:
            xticks.append( "{:10.1f}".format(self.log_time[ tick ] / 1000) )
            tick += int((self.plot_max_len / 6))

        self.ax.set_xticklabels(xticks)

    def add(self, fields):
        if self.index < self.plot_max_len:
            self.index += 1

        self.add_y(self.log_time, fields["time"])
        self.add_x(self.raw_x, self.index)
        self.add_y(self.raw_y, fields["raw"])
   
        self.add_x(self.filtered_x, self.index)
        self.add_y(self.filtered_y, fields["filtered"])

        self.add_x(self.state_x, self.index)

        # Dependiendo del valor, cambia el color de toda la linea y usa el
        # valor del punto para el eje Y.
        if fields["state"] == 3:
            self.line_state[0].set_color(self.color_safe)
            self.add_y(self.state_y, self.point_safe) 
        elif fields["state"] == 2:
            self.line_state[0].set_color(self.color_warning)
            self.add_y(self.state_y, self.point_warning)  
        elif fields["state"] == 1:
            self.line_state[0].set_color(self.color_danger) 
            self.add_y(self.state_y, self.point_danger)
        else:
            self.line_state[0].set_color("black") 
            self.add_y(self.state_y, 0)

        if (self.play_button.state == "down") and (self.log_button.state == "down"):
            with open(self.fname_log, 'a') as stream:
                stream.write(json.dumps(fields, indent=None, sort_keys=True))
                stream.write("\n")
                stream.close 

    def update(self):
        if self.play_button.state == "down":
            self.line_state[0].set_ydata(self.state_y)
            self.line_state[0].set_xdata(self.state_x)
            self.line_raw[0].set_ydata(self.raw_y)
            self.line_raw[0].set_xdata(self.raw_x)
            self.line_filtered[0].set_ydata(self.filtered_y)
            self.line_filtered[0].set_xdata(self.filtered_x)
            
            self.update_plot_axis_x_ticks()
            
            self.fig.canvas.draw()

    def start(self):
        self.popup = Popup(title = "Grafica de detección y distancia", 
                           content = self.box, 
                           size_hint = (.9, .9),
                           auto_dismiss = False) 
        
        self.exit_button.bind(on_press = self.on_exit)

        self.popup.open() 
    
    def on_plot_close(self):
        pass

    def on_exit(self, obj):
        self.popup.dismiss()
        self.dispatch('on_plot_close')
