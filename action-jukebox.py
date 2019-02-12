#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from snipsTools import SnipsConfigParser
from hermes_python.hermes import Hermes
from hermes_python.ontology import *
import paho.mqtt.client as paho
import paho.mqtt.publish as publish
import json
import os
import random
from bs4 import BeautifulSoup as bs
import requests
from pytube import YouTube
import urllib

CONFIG_INI = "config.ini"

MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

ACK = [u"Très bien", "OK", "daccord", u"C'est fait", u"Pas de problème", "entendu"]

AUDIO_SERVER_PORT = 8300

print u"[INSTALL] Installation commands:"
print u"[INSTALL] npm install -g http-server"
print u"[INSTALL] npm install -g forever"
print u"[INSTALL] mkdir -p /var/lib/snips/skills/snips-skill-jukebox/audio"
print u"[INSTALL] forever start -c http-server /var/lib/snips/skills/snips-skill-jukebox/audio -a 0.0.0.0 -p " + str(AUDIO_SERVER_PORT)

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

        # start listening to MQTT
        self.start_blocking()

    # --> Sub callback function, one per intent
    def setSearchMusicCallback(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")

        # action code goes here...
        print '[Received] intent: {}'.format(intent_message.intent.intent_name)

        musicQuery = intent_message.input.lower().replace(" ", "+")

        base = "https://www.youtube.com/results?search_query="
        qstring = musicQuery

        print "Searching music: " + base + qstring

        r = requests.get(base + qstring)
        page = r.text
        soup = bs(page, 'html.parser')

        vids = soup.findAll('a', attrs={'class': 'yt-uix-tile-link'})

        videolist = []

        for v in vids:
            tmp = 'https://www.youtube.com' + v['href']
            videolist.append(tmp)

        if len(videolist) == 0:
            hermes.publish_start_session_notification(intent_message.site_id, u"Je n'ai pas trouvé de musique correspondant à cette recherche", "")
            return False

        item = videolist[0]
        streams = YouTube(item).streams.filter(progressive=True, file_extension='mp4').order_by('resolution')

        if streams.count() == 0:
            hermes.publish_start_session_notification(intent_message.site_id, u"Une erreur est survenue",  "")
            return False

        print "Music found: " + item

        if not os.path.isfile('audio/'+streams.first().default_filename):
            streams.first().download()
            os.rename(streams.first().default_filename, 'audio/'+streams.first().default_filename)

        media = urllib.pathname2url(streams.first().default_filename)

        print "Broadcast media: " + media

        publish.single('hermes/artifice/media/audio/play', payload=json.dumps({'siteId': intent_message.site_id, 'port': AUDIO_SERVER_PORT, 'media': media}), hostname=MQTT_IP_ADDR, port=MQTT_PORT)

        # if need to speak the execution result by tts
        hermes.publish_start_session_notification(intent_message.site_id, ACK[random.randint(0,len(ACK) - 1)], "")

    # --> Master callback function, triggered everytime an intent is recognized
    def master_intent_callback(self,hermes, intent_message):

        intent_name = intent_message.intent.intent_name
        if ':' in intent_name:
            intent_name = intent_name.split(":")[1]
        if intent_name == 'searchMusic':
            self.setSearchMusicCallback(hermes, intent_message)

    # --> Register callback function and start MQTT
    def start_blocking(self):
        with Hermes(MQTT_ADDR) as h:
            h.subscribe_intents(self.master_intent_callback).start()

if __name__ == "__main__":
    Jukebox()