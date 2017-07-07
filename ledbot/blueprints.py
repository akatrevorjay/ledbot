import sanic

from sanic import blueprints, response
from sanic_openapi import doc

from .log import get_logger
from . import models, mqtt

log = get_logger()

play_bp = blueprints.Blueprint('Play', '/play')


@play_bp.get("/")
@doc.summary("Play remote media uri on screen")
@doc.consumes(dict(uri=str))
@doc.produces([models.Status])
async def play(request: sanic.request.Request):
    log.debug('API request to play uri=%s', uri)

    uri = request.args['url']
    await mqtt.queue_to_play(uri, 'api')

    return response.json([{"success": True}])

