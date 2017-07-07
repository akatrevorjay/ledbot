from sanic.blueprints import Blueprint
from sanic.response import json
from sanic_openapi import doc

from .models import Status, Media

play_bp = Blueprint('Play', '/play')


@play_bp.get("/")
@doc.summary("Play remote media uri on screen")
@doc.consumes(dict(uri=str))
@doc.produces([Status])
def play_play(request):
    return json([{"success": True}])
