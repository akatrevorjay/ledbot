from rgbmatrix import graphics
import rgbmatrix
import time
import collections

rgb = collections.namedtuple('RGB', ['r', 'g', 'b'])

def matrix_factory(rows=32, chain=6, parallel=1, luminance=True, pwm_bits=11, brightness=50):
    matrix = rgbmatrix.RGBMatrix(rows, chain, parallel)
    matrix.pwmBits = pwm_bits
    matrix.brightness = brightness
    matrix.luminanceCorrect = True
    return matrix

matrix = matrix_factory()


def scroll(text="Call me maybe baby", font='fonts/10x20.bdf', color=rgb(0, 0, 255), y=10, speed=1, delay=0.01):
    """Display a runtext with double-buffering."""
    offscreen_canvas = matrix.CreateFrameCanvas()

    gfont = graphics.Font()
    gfont.LoadFont(font)

    gcolor = graphics.Color(*color)

    pos = offscreen_canvas.width

    while True:
        offscreen_canvas.Clear()

        length = graphics.DrawText(offscreen_canvas, gfont, pos, y, gcolor, text)

        pos -= speed
        if pos + length < 0:
            pos = offscreen_canvas.width
            return

        time.sleep(delay)

        offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)



def write(text="Call me maybe baby", font='fonts/helvR12.bdf', x=0, y=15, color=rgb(0, 255, 0)):
    """Display a runtext with double-buffering."""
    offscreen_canvas = matrix.CreateFrameCanvas()

    gfont = graphics.Font()
    gfont.LoadFont(font)

    gcolor = graphics.Color(*color)

    length = graphics.DrawText(offscreen_canvas, gfont, x, y, gcolor, text)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)


def scroll2(text="Call me maybe baby", font='fonts/10x20.bdf', color=rgb(0, 0, 255)):
    """Display a runtext with double-buffering."""
    offscreen_canvas = matrix.CreateFrameCanvas()

    gfont = graphics.Font()
    gfont.LoadFont(font)

    gcolor = graphics.Color(*color)

    pos = offscreen_canvas.width

    while True:
        offscreen_canvas.Clear()

        length = graphics.DrawText(offscreen_canvas, gfont, pos, 10, gcolor, text)

        pos -= 1
        if pos + length < 0:
            pos = offscreen_canvas.width
            return

        time.sleep(0.05)

        offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)

