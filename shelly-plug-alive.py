#!/usr/bin/env python

# shelly-plug-details
import json
import os
import logging
import json
import socket
import configparser # for config/ini file

def _getConfig():
  config = configparser.ConfigParser()
  config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
  return config;

def _isAlive():
    try:
      config = _getConfig()
      IP = config['ONPREMISE']['Host']
      isAlive = test_device(IP)
      return isAlive
    except Exception as e:
      logging.warning('Error at %s', 'GetShellyDeviceInfo', exc_info=e)
    return None

def test_device(ip):
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

def generate_data():
    #configure logging
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO,
                        handlers=[
                          logging.FileHandler("%s/ShellDeviceInfo.log" % (os.path.dirname(os.path.realpath(__file__)))),
                          logging.StreamHandler()
                        ])

    is_alive = _isAlive()
    return is_alive

if __name__ == "__main__":
    data = generate_data()
    print(json.dumps(data))
