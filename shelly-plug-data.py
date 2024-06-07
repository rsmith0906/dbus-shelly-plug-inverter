#!/usr/bin/env python

# shelly-plug-details
import json
import os
import logging
import json
import http.client
import configparser # for config/ini file

def _getConfig():
  config = configparser.ConfigParser()
  config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
  return config;

def _getShellyStatusUrl():
  config = _getConfig()
  accessType = config['DEFAULT']['AccessType']

  if accessType == 'OnPremise': 
      URL = "%s" % (config['ONPREMISE']['Host'])
      URL = URL.replace(":@", "")
  else:
      raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))

  return URL

def _getShellyDeviceInfo():
    try:
      URL = _getShellyStatusUrl()
      data = {
          'id': 0,
          'method': 'Shelly.GetStatus'
      }

      conn = http.client.HTTPConnection(URL, 80, timeout=10)
      headers = {
          'Content-Type': 'application/json'
      }
      json_data = json.dumps(data)

      conn.request("POST", "/rpc", body=json_data, headers=headers)
      response = conn.getresponse()
      device_info = response.read().decode()

      # check for response
      if not device_info:
          raise ConnectionError("No response from Shelly Plug - %s" % (URL))

      dev_info = json.loads(device_info)

      # check for Json
      if not dev_info:
          raise ValueError("Converting response to JSON failed")

      return dev_info
    except Exception as e:
      logging.warning('Error at %s', 'GetShellyDeviceInfo', exc_info=e)
    return None

def generate_data():
    #configure logging
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO,
                        handlers=[
                          logging.FileHandler("%s/ShellDeviceInfo.log" % (os.path.dirname(os.path.realpath(__file__)))),
                          logging.StreamHandler()
                        ])

    device_info = _getShellyDeviceInfo()
    return device_info

if __name__ == "__main__":
    data = generate_data()
    print(json.dumps(data))
