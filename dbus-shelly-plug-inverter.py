#!/usr/bin/env python

# import normal packages
import datetime
import platform
import logging
import socket
import sys
import os
import sys
import json
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file
# from pushbullet import Pushbullet
from datetime import datetime

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusShelly1pmService:
  pb = None
  appStarted = False

  def __init__(self, servicename, paths, productname='Shelly Plug', connection='Shelly Plug HTTP JSON service'):
    config = self._getConfig()
    deviceinstance = int(config['DEFAULT']['Deviceinstance'])
    customname = config['DEFAULT']['CustomName']
    pbApiKey = config['DEFAULT']['PushBulletKey']

    self.appStarted = False
    # self.pb = Pushbullet(pbApiKey)

    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    self._paths = paths

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)

    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    #self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
    self._dbusservice.add_path('/ProductId', 0xFFFF) # id assigned by Victron Support from SDM630v2.py
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/CustomName', customname)
    self._dbusservice.add_path('/Connected', 1)

    self._dbusservice.add_path('/Latency', None)
    self._dbusservice.add_path('/FirmwareVersion', self._getShellyFWVersion())
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Position', int(config['DEFAULT']['Position']))
    self._dbusservice.add_path('/Serial', self._getShellySerial())
    self._dbusservice.add_path('/UpdateIndex', 0)
    #self._dbusservice.add_path('/State', 0)  # Dummy path so VRM detects us as a inverter.

    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

    # last update
    self._lastUpdate = 0
    self._checkSecs = 1
    self._cachePower = -1

    # add _update function 'timer'
    gobject.timeout_add(500, self._update) # pause 500ms before the next request

    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)

  def _getShellySerial(self):
    device_info = self._getShellyDeviceInfo()
    if device_info:
      if not device_info['result']['mac']:
          raise ValueError("Response does not contain 'mac' attribute")

      serial = device_info['result']['mac']
      return serial
    else:
      return "00000"

  def _getShellyFWVersion(self):
    device_info = self._getShellyDeviceInfo()
    if device_info:
      if not device_info['result']['fw_id']:
          raise ValueError("Response does not contain 'result/fw_id' attribute")

      ver = device_info['result']['fw_id']
      return ver
    else:
      return "9.0"

  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config;


  def _getSignOfLifeInterval(self):
    config = self._getConfig()
    value = config['DEFAULT']['SignOfLifeLog']

    if not value:
        value = 0

    return int(value)


  def _getShellyStatusUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']

    if accessType == 'OnPremise': 
        #URL = "http://%s:%s@%s/rpc" % (config['ONPREMISE']['Username'], config['ONPREMISE']['Password'], config['ONPREMISE']['Host'])
        URL = "http://%s/rpc" % (config['ONPREMISE']['Host'])
        URL = URL.replace(":@", "")
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))

    return URL

  def _isShellyAlive(self):
     try:
      config = self._getConfig()
      IP = config['ONPREMISE']['Host']
      isAlive = self.test_device(IP)
      return isAlive
     except Exception as e:
      logging.warning('Error at %s', 'getShellyData', exc_info=e)
      return False

  def _getShellyDeviceInfo(self):
    isAlive = self._isShellyAlive()
    if isAlive:
      URL = self._getShellyStatusUrl()

      data = {
          'id': 0,
          'method': 'Shelly.GetDeviceInfo'
      }

      json_data = json.dumps(data)
      device_info = requests.post(url = URL, data=json_data, headers={'Content-Type': 'application/json'})

      # check for response
      if not device_info:
          raise ConnectionError("No response from Shelly Plug - %s" % (URL))

      dev_info = device_info.json()

      # check for Json
      if not dev_info:
          raise ValueError("Converting response to JSON failed")

      return dev_info
    else:
      return None

  def _getShellyData(self):
    try:
      URL = self._getShellyStatusUrl()

      data = {
          'id': 0,
          'method': 'Shelly.GetStatus'
      }

      json_data = json.dumps(data)
      meter_r = requests.post(url = URL, data=json_data, headers={'Content-Type': 'application/json'})

      # check for response
      if not meter_r:
          raise ConnectionError("No response from Shelly Plug - %s" % (URL))

      meter_data = meter_r.json()

      # check for Json
      if not meter_data:
          raise ValueError("Converting response to JSON failed")

      return meter_data
    except Exception as e:
      logging.warning('Error at %s', 'getShellyData', exc_info=e)

  def test_device(self, ip):
    try:
        # Create a socket object
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Set a timeout for the connection
            s.settimeout(1)
            # Try to connect to the specified IP and port
            s.connect((ip, 80))
            return True
    except socket.error as e:
        return False

  def _signOfLife(self):
    logging.info("Start: sign of life - Last _update() call: %s" % (self._lastUpdate))
    return True

  def _update(self):
    #while True:
    try:
      config = self._getConfig()
      updateData = True

      if not self.appStarted:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        # push = self.pb.push_note("Shelly Plug Inverter Started", f"Started at {now_str}")
        self.appStarted = True

      isAlive = self._isShellyAlive()
      if isAlive:
        #get data from Shelly Plug
        try:
          meter_data = self._getShellyData()
          if meter_data:
            inverter_phase = config['DEFAULT']['Phase']

            #send data to DBus
            for phase in ['L1']:
              pre = '/Ac/Out/' + phase

              if phase == inverter_phase:
                result = meter_data['result']
                if result:
                  switch = result['switch:0']
                  if switch:
                    power = switch['apower']
                    voltage = switch['voltage']
                    current = switch['current']

                    self._dbusservice[pre + '/V'] = voltage
                    self._dbusservice[pre + '/I'] = current
                    self._dbusservice[pre + '/P'] = power

                    if power > 0:
                      if power > 5:
                        self._dbusservice['/State'] = 9
                        self._dbusservice['/Mode'] = 2
                      else:
                        self._dbusservice['/State'] = 1
                        self._dbusservice['/Mode'] = 5
                    else:
                      self._dbusservice['/State'] = 0
                      self._dbusservice['/Mode'] = 5

              if not self._cachePower == power:
                self.save_data("Inverter", f"{{ \"Power\": \"{power}\" }}")
                self._cachePower = power
              else:
                updateData = False
          else:
            logging.warning(f"meter_data not available")
            # push = self.pb.push_note("meter_data not available")

        except Exception as e:
          logging.warning('Error at %s', '_update', exc_info=e)
          # push = self.pb.push_note("Shell Plug Inverter Warning", e)
      else:
        self._dbusservice['/Ac/Out/L1/P'] = 0
        self._dbusservice['/State'] = 0
        self._dbusservice['/Mode'] = 4

      if updateData:
        self._signalChanges()

      #update lastupdate vars
      self._lastUpdate = time.time()

      inverter_phase = str(config['DEFAULT']['Phase'])
    except Exception as e:
      logging.critical('Error at %s', '_update', exc_info=e)
      meter_data = None
      # push = self.pb.push_note("Shell Plug Inverter Error", e)
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
      
    return True

  def _signalChanges(self):
    # increment UpdateIndex - to show that new data is available
    index = self._dbusservice['/UpdateIndex'] + 1  # increment index
    if index > 255:   # maximum value of the index
      index = 0       # overflow from 255 to 0
    self._dbusservice['/UpdateIndex'] = index

  def save_data(self, key, value):
    file = open(f"/tmp/{key}.json", 'w') 
    file.write(value) 
    file.close() 

  def read_data(self, key):
    try:
      if os.path.exists(f"/tmp/{key}.json"):
        with open(f"{key}.json", 'r') as file:
          return json.load(file)
      else:
        return None
    except Exception as e:
      return None

  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change

def main():
  #configure logging
  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.INFO,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])

  try:
      logging.info("Start");

      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)

      #formatting
      _kwh = lambda p, v: (str(round(v, 2)) + 'kWh')
      _state = lambda p, v: (str(v))
      _mode = lambda p, v: (str(v))
      _a = lambda p, v: (str(round(v, 1)) + 'A')
      _w = lambda p, v: (str(round(v, 1)) + 'W')
      _v = lambda p, v: (str(round(v, 1)) + 'V')

      #start our main-service
      pvac_output = DbusShelly1pmService(
        servicename='com.victronenergy.inverter',
        paths={
          '/Ac/Out/L1/V': {'initial': 0, 'textformat': _v},
          '/Ac/Out/L1/I': {'initial': 0, 'textformat': _a},
          '/Ac/Out/L1/P': {'initial': 0, 'textformat': _w},
          '/Ac/Voltage': {'initial': 0, 'textformat': _v},
          '/State': {'initial': 0, 'textformat': _state},
          '/Mode': {'initial': 4, 'textformat': _mode},
        })

      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
