import asyncio
import logging
import sys

import yarl

from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from . import di, signals, get_logger

log = get_logger()


@di.inject('config')
def mqtt_client_factory(config, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    c = MQTTClient(
        client_id=config.SERVICE_NAME,
    )

    return c

di.register_factory(MQTTClient, mqtt_client_factory, scope='global')


@di.inject('config', MQTTClient)
async def mqtt_client_connect(config, mqtt_client):
    log.debug('Connecting to MQTT')
    await mqtt_client.connect(config.MQTT_URL)


@di.inject(MQTTClient)
async def queue_to_play(mqttc: MQTTClient, uri, content_type: str='generic'):
    log.debug("Queuing uri=%s content_type=%s", uri, content_type)

    topic = 'ledbot/play/%s' % content_type

    buri = str(uri).encode()
    log.debug("topic=%s buri=%s", topic, buri)

    m = await mqttc.publish(topic, buri, qos=QOS_0)

    log.debug('m=%s', m)

    log.info('Queued buri=%s', buri)

