import asyncio
import itertools

import six
import attr
import yarl

from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from .. import di, utils
from ..log import get_logger
from ..debug import pp, pf, see

from . import aioslack

log = get_logger()


@attr.s(repr=False)
class SlackMessage(aioslack.RtmEvent):

    async def queue_to_play(self):
        log.debug('Trying to play %s', self)

        for attach in itertools.chain(self.iter_files(), self.iter_attachments()):
            log.debug('Checking attachment=%s', attach)

            uri = attach.get_uri()
            if not uri:
                continue

            log.debug("Playing attachment=%s", attach)
            await queue_to_play(uri)
            return

        log.error('Not playable %s', self)


@di.inject(MQTTClient)
async def queue_to_play(mqttc: MQTTClient, uri, content_type: str='generic'):
    log.debug("Queuing uri=%s content_type=%s", uri, content_type)

    topic = 'ledbot/play/%s' % content_type

    buri = str(uri).encode()
    log.debug("topic=%s buri=%s", topic, buri)

    m = await mqttc.publish(topic, buri, qos=QOS_0)

    log.debug('m=%s', m)

    log.info('Queued buri=%s', buri)


@di.inject('config', aioslack.Client)
async def ainit(config, slack_client, loop):
    log.debug('ainit')

    slack_client.on('message')(_on_slack_message)


async def _on_slack_message(event):
    """Slack message faucet."""
    msg = await SlackMessage.from_aioslack_event(event.event, event.client)
    await msg.queue_to_play()
