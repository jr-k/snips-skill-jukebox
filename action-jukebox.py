#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from snipsTools import SnipsConfigParser
import paho.mqtt.publish as publish
import paho.mqtt.client as paho
import time
import json
import requests
import urllib
import os
import random
import re
from pytube import YouTube

CONFIG_INI = "config.ini"
MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))
ACK = [u"Très bien", "OK", "daccord", u"C'est fait", u"Pas de problème", "entendu"]
regex = r"<a\b(?=[^>]* class=\"[^\"]*(?<=[\" ])yt-uix-tile-link[\" ])(?=[^>]* href=\"([^\"]*))"

class Jukebox(object):
    """Class used to wrap action code with mqtt connection

        Please change the name refering to your application
    """
    def __init__(self):
        # get the configuration if needed
        try:
            self.config = SnipsConfigParser.read_configuration_file(CONFIG_INI)
        except :
            self.config = None

        self.publicServerAudioDir = self.config["global"]["artifice_public_server_audio_dir"]
        self.publicServerPort = self.config["global"]["artifice_public_server_port"]

        # start listening to MQTT
        self.tmpClient = paho.Client("snips-skill-jukebox-" + str(int(round(time.time() * 1000))))
        self.tmpClient.on_message = self.on_message
        self.tmpClient.on_log = self.on_log
        self.tmpClient.connect(MQTT_IP_ADDR, MQTT_PORT)
        self.tmpClient.subscribe("hermes/intent/#")
        self.tmpClient.loop_forever()

    def on_message(self, client, userdata, message):
        topic = message.topic
        msg = str(message.payload.decode("utf-8", "ignore"))
        msgJson = json.loads(msg)

        intent_name = msgJson["intent"]["intentName"]

        if ':' in intent_name:
            intent_name = intent_name.split(":")[1]

        if intent_name == "searchMusic":
            self.searchMusicAction(payload=msgJson)

    def on_log(self, client, userdata, level, buf):
        if level != 16:
            print("log: ", buf)

    def searchMusicAction(self, payload):
        print "[searchMusicAction]"
        self.tmpClient.publish("hermes/dialogueManager/endSession", json.dumps({'sessionId': payload["sessionId"], "text": "daccord"}))
        musicQuery = payload["input"].replace(" ", "+")

        base = "https://www.youtube.com/results?search_query="
        qstring = musicQuery

        print "Searching music: " + base + qstring

        r = requests.get(base + qstring)
        page = r.text

        matches = re.finditer(regex, page, re.MULTILINE)
        videolist = []

        for matchNum, match in enumerate(matches, start=1):
            if "list" not in match.group(1):
                tmp = 'https://www.youtube.com' + match.group(1)
                videolist.append(tmp)

        if len(videolist) == 0:
            self.tmpClient.publish("hermes/dialogueManager/startSession", json.dumps({"siteId": payload["siteId"], "init": {"type": "notification", "text": u"Je n'ai pas trouvé de musique correspondant à cette recherche"}}))
            return False

        item = videolist[0]

        # print "Wait..."
        # time.sleep(5)
        # print "Wait ended"

        streams = YouTube(item).streams.filter(progressive=True, file_extension='mp4').order_by('resolution')

        if streams.count() == 0:
            self.tmpClient.publish("hermes/dialogueManager/startSession", json.dumps({"siteId": payload["siteId"], "init": {"type": "notification", "text": u"Une erreur est survenue"}}))
            return False

        print "Music found: " + item

        if not os.path.isfile(self.publicServerAudioDir + '/' + streams.first().default_filename):
            streams.first().download()
            os.rename(streams.first().default_filename, self.publicServerAudioDir + '/' + streams.first().default_filename)

        media = urllib.pathname2url(streams.first().default_filename)

        # medias = ["Kaaris%20-%20Or%20Noir.mp4", "Jul%20-%20On%20Mappelle%20Lovni%20%20Clip%20Officiel%20%202016.mp4"]
        # media = medias[random.randint(0, len(medias) - 1)]

        print "Broadcast media: " + media

        self.tmpClient.publish("hermes/artifice/media/audio/play", json.dumps({'siteId': payload["siteId"], "port": self.publicServerPort, 'media': 'audio/' + media}))


if __name__ == "__main__":
    Jukebox()



