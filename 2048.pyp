# Copyright (C) 2015  Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE
"""
2048 - A Cinema 4D implementation
=================================

This plugin implements the 2048 game using the Cinema 4D GUI.
"""

__author__ = 'Niklas Rosenstein <rosensteinniklas(at)gmail.com>'
__version__ = '1.0'

import c4d
import math
import random

PLUGIN_ID = 1035109


def traverse_grid(start_index, direction, steps):
    """
    traverse_grid(start_index, direction, steps) -> iterator of (x, y)

    This is a generator function to compute grid indices based on a
    starting index and a grid direction. It will yield *steps* items
    that are computed from the *start_index* and *direction*. Both
    are assumed to be two-element sequences.
    """

    for index in xrange(steps):
        x = start_index[0] + index * direction[0]
        y = start_index[1] + index * direction[1]
        yield (x, y)


def merge(values):
    """
    merge(values) -> list

    Implementation of an algorithm to merge a sequence of values
    in 2048-style. Returns a list of the new values.
    """

    # Since values could be a generator, we'll count the elements
    # it yielded.
    count = 0
    result = []

    for value in values:
        count += 1

        # Check if we can merge this value with the last one.
        if result and result[-1] == value and result[-1] < 2048:
            result[-1] += value
        elif value != 0:
            result.append(value)

    # Zero-fill the result.
    result.extend(0 for __ in xrange(count - len(result)))

    return result


class TwentyFortyEight(object):
    """
    The 2048 game logic is burried in this class.
    """

    MOVE_UP = 1
    MOVE_DOWN = 2
    MOVE_LEFT = 3
    MOVE_RIGHT = 4

    def __init__(self, grid_width, grid_height):
        super(TwentyFortyEight, self).__init__()
        self.width = grid_width
        self.height = grid_height
        self.reset()

        # Pre-compute the indices of the grid edges so move() can
        # use them right away. The edge indices are the starting
        # points for the merge algorithm.
        maxcol = self.width - 1
        maxrow = self.height - 1
        self.edges = {
            self.MOVE_UP:    [(x, 0)      for x in xrange(grid_width)],
            self.MOVE_DOWN:  [(x, maxrow) for x in xrange(grid_width)],
            self.MOVE_LEFT:  [(0, x)      for x in xrange(grid_height)],
            self.MOVE_RIGHT: [(maxcol, x) for x in xrange(grid_height)],
        }

        # Pre-define the directions in which you need to travel from
        # an edge index to pass all cells in that row/column. The 2nd
        # element describes the grid size in that direction.
        self.directions = {
            self.MOVE_UP:    ((0,  1), grid_height),
            self.MOVE_DOWN:  ((0, -1), grid_height),
            self.MOVE_LEFT:  (( 1, 0), grid_width),
            self.MOVE_RIGHT: ((-1, 0), grid_width),
        }

    def reset(self):
        """
        Resets the 2048 grid and randomly creates two initial tiles.
        """

        # The grid is created in column-first order.
        self.grid = [[0] * self.width for __ in xrange(self.height)]
        self.new_tile(count=2)

    def new_tile(self, count=1):
        """
        new_tile([count=1]) -> bool

        Randomly selects *count* empty tiles (with the value 0) and
        initializes them with the value 2 or 4 with the probability of
        90% and 10%, respectively.

        Returns True if the tiles were  created, False if there are
        fewer than *count* empty tiles and no tiles have been
        initialized.
        """

        empty_tiles = []
        for value, pos in self.iter_cells():
            if value == 0:
                empty_tiles.append(pos)

        if len(empty_tiles) < count:
            return False

        for __ in xrange(count):
            # Randomly choose an element and remove it from the list.
            index = random.randint(0, len(empty_tiles) - 1)
            column, row = empty_tiles.pop(index)
            self.grid[column][row] = 2 if random.random() <= 0.9 else 4

        return True

    def iter_cells(self):
        """
        iter_cells() -> iterator of (value, (column, row))

        Use this function to iterate over all cells in the grid.
        """

        for column, tile_row in enumerate(self.grid):
            for row, value in enumerate(tile_row):
                yield value, (column, row)

    def move(self, move):
        """
        move(move) -> bool

        Performs a move on the game grid. *move* must be one of the
        constants :data:`MOVE_UP`, :data:`MOVE_DOWN`, :data:`MOVE_LEFT`
        or :data:`MOVE_RIGHT`.

        Returns True if the move resulted in a 2048 being created.
        """

        has_2048 = False
        direction, steps = self.directions[move]
        for start_index in self.edges[move]:

            # Get a list of the indices to traverse.
            indices = list(traverse_grid(start_index, direction, steps))

            # Now get a list of all the values in the grid cells
            # of which we calculated the indices for.
            values = (self.grid[column][row] for (column, row) in indices)

            # Merge the values in 2048-style (it supports generators :-).
            values = merge(values)

            # And set them back on the grid.
            for (column, row), value in zip(indices, values):
                if value == 2048:
                    has_2048 = True
                self.grid[column][row] = value

        self.new_tile()
        return has_2048


class TFE_View(c4d.gui.GeUserArea):
    """
    This class implements the visual representation of the 2048 grid.
    """

    def __init__(self, game, tilesize=48, tilespace=8):
        super(TFE_View, self).__init__()
        self.game = game
        self.tilesize = tilesize
        self.tilespace = tilespace

    def get_color_vector(self, color_id):
        """
        get_color_vector(color_id) -> c4d.Vector

        Returns a color :class:`c4d.Vector` for *color_id*. The
        existing :meth:`GetColorRGB` method returns a dictionary
        with RGB values in range [0,255] which is rather inconvenient.
        """

        data = self.GetColorRGB(color_id)
        rgbv = c4d.Vector(data['r'], data['g'], data['b'])
        return rgbv ^ c4d.Vector(1.0 / 255.0)

    def calc_tile_offset(self, index):
        """
        calc_tile_offset(index) -> integer

        This is a helper function to compute the pixel offse of the
        tile at *index*. This function works for both the horizontal
        as well as the vertical offset as the tile size and spacing
        are the same.
        """

        return index * self.tilesize + (index + 1) * self.tilespace

    def DrawMsg(self, x1, y1, x2, y2, msg):
        """
        This method is called to render the content of the view.
        """

        # Enables double buffering to avoid flickering.
        self.OffScreenOn()

        # Draw the background.
        self.DrawSetPen(c4d.COLOR_BGEDIT)
        self.DrawRectangle(x1, y1, x2, y2)

        # Determine the vertical and horizontal margin of the
        # grid view so we can center it.
        size = self.GetMinSize()
        xpos = (self.GetWidth() - size[0]) / 2
        ypos = (self.GetHeight() - size[1]) / 2

        # The two colors for the tiles which we'll fade between.
        color_low = self.get_color_vector(c4d.COLOR_BG)
        color_high = self.get_color_vector(c4d.COLOR_SYNTAX_COMMENTWRONG)

        # Set the text color and font, we only need to do this once.
        self.DrawSetTextCol(c4d.COLOR_TEXT, c4d.COLOR_TRANS)
        self.DrawSetFont(c4d.FONT_BOLD)

        # Render the tiles.
        for value, pos in self.game.iter_cells():
            # Don't forget, the game grid is indexed column-first.
            xoff = xpos + self.calc_tile_offset(pos[0])
            yoff = ypos + self.calc_tile_offset(pos[1])

            # The color of the tile will be based on the value that is
            # inside the tile which we will fade between two Cinema 4D
            # color constants.
            #
            # We use the logarithm to determine the exponent of base two
            # of the current value to result in a linear color fading.
            # The maximum exponent value is 11 (2 ** 11 = 2048).
            #
            # Taking the empty cell in account, we need 12 grading steps.
            if value != 0:
                exponent = math.log(value, 2)
                percent = (exponent + 1) / 12.0
            else:
                percent = 0.0

            # Compute the color for the tile and draw it.
            color = (1.0 - percent) * color_low + percent * color_high
            self.DrawSetPen(color)
            self.DrawRectangle(xoff, yoff, xoff + self.tilesize, yoff + self.tilesize)

            # Now put the tile value in the middle.
            if value != 0:
                flags = c4d.DRAWTEXT_HALIGN_CENTER | c4d.DRAWTEXT_VALIGN_CENTER
                self.DrawText(
                    str(value), xoff + self.tilesize / 2,
                    yoff + self.tilesize / 2, flags)

    def GetMinSize(self):
        width = self.calc_tile_offset(self.game.width)
        height = self.calc_tile_offset(self.game.height)
        return (width, height)


class TFE_Dialog(c4d.gui.GeDialog):
    """
    This dialog contains the :class:`TFE_View` class and displays
    it in its very own window.
    """

    def __init__(self):
        super(TFE_Dialog, self).__init__()
        self.game = TwentyFortyEight(4, 4)
        self.view = TFE_View(self.game)

    def input_event(self, msg):
        """
        The :class:`GeUserArea` class has an overwritable method
        `ÌnputEvent()`` but we need to catch it manually in the
        :meth:`Message` method of the dialog.
        """

        if msg.GetInt32(c4d.BFM_INPUT_DEVICE) == c4d.BFM_INPUT_KEYBOARD:
            channel = msg.GetInt32(c4d.BFM_INPUT_CHANNEL)
            handled = True
            if channel == c4d.KEY_LEFT:
                self.game.move(self.game.MOVE_LEFT)
            elif channel == c4d.KEY_RIGHT:
                self.game.move(self.game.MOVE_RIGHT)
            elif channel == c4d.KEY_UP:
                self.game.move(self.game.MOVE_UP)
            elif channel == c4d.KEY_DOWN:
                self.game.move(self.game.MOVE_DOWN)
            elif channel == c4d.KEY_ESC:
                self.game.reset()
            else:
                handled = False

            self.view.Redraw()
            return handled

        return False

    def CreateLayout(self):
        self.SetTitle("2048")
        self.AddUserArea(1000, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT)
        self.AttachUserArea(self.view, 1000)
        return True

    def Message(self, msg, result):
        if msg.GetId() == c4d.BFM_INPUT:
            return self.input_event(msg)
        return super(TFE_Dialog, self).Message(msg, result)


class TFE_Command(c4d.plugins.CommandData):
    """
    This plugin class opens the :class:`TFE_Dialog` when it is
    selected from the Plugin's menu.
    """

    @property
    def dialog(self):
        """
        Returns the :class:`TFE_Dialog` that is managed by this command
        plugin. The dialog is generated on-demand to avoid creating it
        when it would never be opened by the user.
        """

        dialog = getattr(self, '_dialog', None)
        if dialog is None:
            dialog = TFE_Dialog()
            self._dialog = dialog

        return dialog

    def register(self):
        """
        Registers the plugin command to Cinema 4D.
        """

        flags = 0
        icon = None
        help_ = "The 2048 game for Cinema 4D."
        return c4d.plugins.RegisterCommandPlugin(
            PLUGIN_ID, "2048", flags, icon, help_, self)

    def Execute(self, doc):
        return self.dialog.Open(c4d.DLG_TYPE_ASYNC, PLUGIN_ID)


if __name__ == "__main__":
    TFE_Command().register()
