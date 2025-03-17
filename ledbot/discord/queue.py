import asyncio
import itertools

import six
import attr
import yarl
import validators

from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from .. import di, utils
from ..log import get_logger
from ..debug import pp, pf, see

log = get_logger()


def validate_url(uri: str) -> bool:
    return validators.url(uri)


@di.inject(MQTTClient)
async def queue_to_play(mqttc: MQTTClient, uri, content_type: str = 'discord_message'):
    log.debug("Queuing uri=%s content_type=%s", uri, content_type)

    topic = 'ledbot/play/%s' % content_type

    buri = str(uri).encode()
    log.debug("topic=%s buri=%s", topic, buri)

    m = await mqttc.publish(topic, buri, qos=QOS_0)

    log.debug('m=%s', m)

    log.info('Queued buri=%s', buri)


@di.inject('config')
async def ainit(config, loop):
    log.debug('ainit')

