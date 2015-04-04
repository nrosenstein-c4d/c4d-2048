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
import copy
import collections
import math
import random
import time
import unittest

RUN_TESTS = True
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


Coord = collections.namedtuple('Coord', 'x y')


class Tile(object):
    """
    This class represents a tile in the TwentyFortyEight game.

    .. attribute:: coord

        The coordinate of the tile in the grid.

    .. attribute:: value

        The value of the tile. Zero indicates an empty tile.

    .. attribute:: prev_value

        The previous value of the tile.

    .. attribute:: merged_from

        A list of the coordinates the tiles value originates from.
        The list can be empty and contain up to two elements.
    """

    __slots__ = ('coord', 'value', 'prev_value', 'merged_from', 'age')

    def __init__(self, col, row, value=0):
        super(Tile, self).__init__()
        self.coord = Coord(col, row)
        self.value = value
        self.merged_from = []
        self.age = 0

    def __repr__(self):
        return str(self.value)

    def clear(self):
        """
        Empties the tile.
        """

        self.age = 0
        self.value = 0
        self.merged_from = []

    def is_merged(self):
        """
        is_merged() -> bool

        Returns True if this is a merged tile, False if not. A merged
        tile has exactly two elements in its :attr:`merged_from` list.
        """

        assert len(self.merged_from) <= 2
        return len(self.merged_from) == 2

    @staticmethod
    def merge_tiles(tiles):
        """
        merge_tiles(tiles) -> integer

        Merges all :class:`Tile`s in the list *tiles*. The actual Tile
        objects stay at the same position in the grid, only their
        attributes will be adjusted.

        Returns the score achieved by the merge.
        """

        score = 0
        last_index = 0

        for index, curr in enumerate(tiles):
            del curr.merged_from[:]
            curr.age += 1
            if index == 0:
                continue

            target = tiles[last_index]

            # Check if we can merge this tile into its predecesor.
            if curr.value != 0 and target.value == curr.value:
                score += curr.value * 2
                target.value += curr.value
                target.merged_from.append(curr.coord)
                curr.clear()
                last_index += 1

            # Is this current tile not empty? Then we might need to
            # move its data to the next free tile.
            elif curr.value != 0:

                # If the current slot isn't free, then the next is
                # for sure!
                if target.value != 0:
                    assert (last_index + 1) <= index
                    last_index += 1
                    target = tiles[last_index]

                # No point in moving the tile to itself though!
                if last_index != index:
                    target.age = curr.age
                    target.value = curr.value
                    target.merged_from.append(curr.coord)
                    curr.clear()

            # If the value of the current tile dropped to zero, make
            # sure to re-set its age to zero as well.
            if curr.value == 0:
                curr.age = 0

        return score


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
        # an edge index to pass all tiles in that row/column. The 2nd
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

        self.score = 0
        self.grid = [[Tile(x, y) for y in xrange(self.height)]
                                for x in xrange(self.width)]
        self.new_tile(count=2)

    def new_tile(self, count=1):
        """
        new_tile([count=1]) -> bool

        Randomly selects *count* empty tiles (with the value 0) and
        initializes them with the value 2 or 4 with the probability of
        90% and 10%, respectively.

        Returns True if the tiles were created, False if there are
        fewer than *count* empty tiles and no tiles have been
        initialized.
        """

        empty_tiles = []
        for tile in self.iter_tiles():
            if tile.value == 0:
                empty_tiles.append(tile)

        if len(empty_tiles) < count:
            return False

        for __ in xrange(count):
            # Randomly choose an element and pop it from the list.
            index = random.randint(0, len(empty_tiles) - 1)
            tile = empty_tiles.pop(index)
            tile.value = 2 if random.random() <= 0.9 else 4

        return True

    def iter_tiles(self):
        """
        iter_tiles() -> iterator of Tile

        Use this function to iterate over all tiles in the grid.
        """

        for row in self.grid:
            for tile in row:
                yield tile

    def move(self, move):
        """
        Performs a move on the game grid, updates the score and creates
        a new tile at a random location.

        :param move: Must be one of the following values:

            - :data:`MOVE_UP`
            - :data:`MOVE_DOWN`
            - :data:`MOVE_LEFT`
            - :data:`MOVE_RIGHT`
        """

        direction, steps = self.directions[move]
        for start_index in self.edges[move]:

            # Get all tiles in a list and merge their values.
            tiles = []
            for col, row in traverse_grid(start_index, direction, steps):
                tiles.append(self.grid[col][row])

            self.score += Tile.merge_tiles(tiles)

        self.new_tile()


class AnimationGuide(object):
    """
    This is a helper class for percentage based animation with a fixed
    duration. You pass in a time in seconds and it will let you
    calculate how far the animation must have progressed at the time
    you call :meth:`progress()`.

    Use :meth:`reached` to check if the animation should by finished by
    the time it is called.
    """

    def __init__(self, duration):
        super(AnimationGuide, self).__init__()
        self.start_time = time.time()
        self.duration = duration

    def reached(self):
        """
        reached() -> bool

        Returns True if the animation goal was reached and the duration
        was occupied, False if not.
        """

        passed = time.time() - self.start_time
        return passed >= self.duration

    def progress(self):
        """
        progress() -> float

        Returns the progress of the animation as a floating point
        number between zero and one. If called after the animation is
        already completed, may return values larger than one.
        """

        passed = time.time() - self.start_time
        return passed / self.duration


class TFE_View(c4d.gui.GeUserArea):
    """
    This class implements the visual representation of the 2048 grid.
    """

    def __init__(self, game, tilesize=48, tilespace=8, animation_time=0.2):
        super(TFE_View, self).__init__()
        self.game = game
        self.tilesize = tilesize
        self.tilespace = tilespace
        self.animation_time = animation_time
        self.animation = None

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

        This is a helper function to compute the pixel offset of the
        tile at *index*, excluding the initial left padding. This
        function works for both the horizontal as well as the vertical
        offset as the tile size and spacing are the same.
        """

        return index * self.tilesize + index * self.tilespace

    def perform_move(self, move):
        """
        Calls :meth:`TwentyFortyEight.move` and starts an animation
        moving the tiles into the specified direction. This will
        override any existing animation state.
        """

        self.animation = AnimationGuide(self.animation_time)
        self.SetTimer(int(1.0 / 60.0 * 1000))
        self.game.move(move)

    def draw_tile(self, origin, coord, tween_coord, value, tile_age,
            progress, color_low, color_high):
        """
        Helper function to draw a tile. If *value* is zero, an empty
        tile will be drawn. The color of empty tiles is automatically
        retrieved.

        Will use the currently selected text color for the tile values.

        :param origin: The upper-left corner of the game grid.
        :param coord: The coordinate to render.
        :param tween_coord: If specified, will be used as the tweening
            coordinate for tile animation.
        :param value: The value of the tile.
        :param tile_age: The age of the tile, used to determine if the
            tile just spawned and deserves a spawn animation.
        :param progress: The animation progress, or None.
        :param color_low: The low value color of the tile. This
            parameter should be passed for performance reasons in
            order to fetch it only once in DrawMsg().
        :param color_high: The high value color of the tile. This
            parameter should be passed for performance reasons in
            order to fetch it only once in DrawMsg().
        """

        # Calculate the tile's position on the User Area for both
        # components and convert it to a Coord object immediately.
        pos = Coord(*map(self.calc_tile_offset, coord))

        # Compute tile position based on animation progress and
        # tween coordinate.
        if progress is not None and tween_coord is not None:
            source = Coord(*map(self.calc_tile_offset, tween_coord))
            pos = Coord(
                int(pos.x * progress + source.x * (1.0 - progress)),
                int(pos.y * progress + source.y * (1.0 - progress)))

        # Now it's time to make the coordinate absolute.
        pos = Coord(origin.x + pos.x, origin.y + pos.y)

        if value != 0:
            # We use the logarithm to the base of 2 to convert the
            # exponential scaling of tile values into a linear curve.
            exponent = math.log(value, 2)
            percent = exponent / 11.0
            color = (1.0 - percent) * color_low + percent * color_high
        else:
            color = c4d.COLOR_BG

        size = Coord(self.tilesize, self.tilesize)

        # Let's add some nice growth effect to a newly spawned tile.
        if progress is not None and value != 0 \
                and tween_coord is None and tile_age == 0:
            pos = Coord(
                int(round(pos.x + (size.x / 2) * (1.0 - progress))),
                int(round(pos.y + (size.x / 2) * (1.0 - progress))))
            size = Coord(
                int(round(size.x * progress)),
                int(round(size.y * progress)))

        self.DrawSetPen(color)
        self.DrawRectangle(pos.x, pos.y, pos.x + size.x, pos.y + size.x)

        if value != 0:
            # Draw the value of the tile into its center.
            flags = c4d.DRAWTEXT_HALIGN_CENTER | c4d.DRAWTEXT_VALIGN_CENTER
            self.DrawText(
                str(value), pos.x + size.x / 2, pos.y + size.y / 2, flags)

    def DrawMsg(self, x1, y1, x2, y2, msg):
        """
        This method is called to render the content of the view.
        """

        # Enables double buffering to avoid flickering.
        self.OffScreenOn()

        # Draw the background.
        self.DrawSetPen(c4d.COLOR_BGEDIT)
        self.DrawRectangle(x1, y1, x2, y2)

        # The two colors for the tiles which we'll fade between.
        color_low = self.get_color_vector(c4d.COLOR_TEXTFOCUS)
        color_high = self.get_color_vector(c4d.COLOR_SYNTAX_COMMENTWRONG)

        # Set the text color and font, we only need to do this once.
        self.DrawSetTextCol(c4d.COLOR_BGEDIT, c4d.COLOR_TRANS)
        self.DrawSetFont(c4d.FONT_BOLD)

        # Determine the vertical and horizontal margin of the
        # grid view so we can center it.
        size = self.GetMinSize()
        origin = Coord(
            (self.GetWidth()  - size[0]) / 2 + self.tilespace,
            (self.GetHeight() - size[1]) / 2 + self.tilespace)

        progress = None
        if self.animation and self.animation.reached():
            # If we had an animation in progress and if it is finished
            # now, we erase it and disable the timer we used to redraw
            # the view.
            self.animation = None
            self.SetTimer(0)
        elif self.animation:
            # If the animation is still in progress, retrieve this
            # progress so we can use it to calculate the intermediate
            # tile locations.
            progress = self.animation.progress()


        # Draw the background of all tiles.
        for tile in self.game.iter_tiles():
            self.draw_tile(
                origin, tile.coord, None, 0, 0,
                progress, color_low, color_high)

        # Draw all the tiles.
        for tile in self.game.iter_tiles():
            # If the animation is in progress and the tile has original
            # coordinates it has either been moved or merged.
            if progress is not None and tile.merged_from:
                prev_value = tile.value / 2 if tile.is_merged() else tile.value
                for prev_coord in tile.merged_from:
                    self.draw_tile(
                        origin, tile.coord, prev_coord, prev_value, 0,
                        progress, color_low, color_high)

            # Otherwise, we only need to draw the tile if it has value
            # since we drew the tile backgrounds already.
            elif tile.value != 0:
                self.draw_tile(
                    origin, tile.coord, None, tile.value, tile.age,
                    progress, color_low, color_high)


    def GetMinSize(self):
        width = self.calc_tile_offset(self.game.width) + self.tilespace
        height = self.calc_tile_offset(self.game.height) + self.tilespace
        return (width, height)

    def Timer(self, msg):
        # We use SetTimer() in perform_move() to periodically redraw
        # the User Area in this method.
        self.Redraw()


class TFE_Dialog(c4d.gui.GeDialog):
    """
    This dialog contains the :class:`TFE_View` class and displays
    it in its very own window.
    """

    # Symbolic IDs for parameters in the dialog.
    ID_SCORE = 1000
    ID_TFEVIEW = 1001


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
            if channel == c4d.KEY_UP:
                self.view.perform_move(TwentyFortyEight.MOVE_UP)
            elif channel == c4d.KEY_DOWN:
                self.view.perform_move(TwentyFortyEight.MOVE_DOWN)
            elif channel == c4d.KEY_LEFT:
                self.view.perform_move(TwentyFortyEight.MOVE_LEFT)
            elif channel == c4d.KEY_RIGHT:
                self.view.perform_move(TwentyFortyEight.MOVE_RIGHT)
            elif channel == c4d.KEY_BACKSPACE:
                self.game.reset()
            else:
                handled = False

            if handled:
                self.sync_gui()
            return handled

        return False

    def sync_gui(self):
        """
        We call this method to synchronize the game state with all
        data that is displayed on the UI. Currently, this will just
        redraw the TFE_View and update the score.
        """

        self.SetString(self.ID_SCORE, "Score: {0}".format(self.game.score))
        self.LayoutChanged(self.ID_SCORE)
        self.view.Redraw()

    def CreateLayout(self):
        self.SetTitle("2048")

        # Add the field to display the score in the menu line of
        # the dialog.
        self.GroupBeginInMenuLine()
        self.AddStaticText(self.ID_SCORE, 0)
        self.GroupEnd()

        # Add and attach the TFE_View to the main dialog area.
        self.AddUserArea(self.ID_TFEVIEW, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT)
        self.AttachUserArea(self.view, self.ID_TFEVIEW)

        self.sync_gui()
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


# Unit Tests

class TileMergeTest(unittest.TestCase):
    """
    Tests the merging result of cells.
    """

    # Test case input values and expected results.
    cases = {
        ( 0,  0,  0,  0): ( 0,  0,  0,  0),
        ( 2,  0,  2,  0): ( 4,  0,  0,  0),
        ( 2,  0,  0,  2): ( 4,  0,  0,  0),
        ( 0,  2,  2,  0): ( 4,  0,  0,  0),
        ( 2,  4,  0,  4): ( 2,  8,  0,  0),
        (16,  8,  8,  0): (16, 16,  0,  0),
        ( 4, 16,  0, 16): ( 4, 32,  0,  0),
        (32, 16,  8,  2): (32, 16,  8,  2),
    }

    def test_merge(self):
        for input_values, output_values in self.cases.iteritems():
            tiles = [Tile(0, i, x) for i, x in enumerate(input_values)]
            Tile.merge_tiles(tiles)
            values = tuple(t.value for t in tiles)
            self.assertEquals(output_values, values)


def get_test_suite():
    """
    Searches for subclasses of the :class:`unittest.TestCase` class
    in all global variables and adds them to a TestSuite with all
    their test methods.
    """

    suite = unittest.TestSuite()
    for value in globals().values():
        # We can only check with issubclass() if the value is a
        # type object.
        if not isinstance(value, type):
            continue

        # Is the type a TestCase subclass? Well then
        if not issubclass(value, unittest.TestCase):
            continue

        # Create a TestCase for all its methods that start with
        # the word "test" and add them to the suite.
        for name in dir(value):
            if name.startswith('test'):
                suite.addTest(value(name))

    return suite


if __name__ == "__main__":
    if RUN_TESTS:
        print "Running Unit Tests for 2048 ..."
        suite = get_test_suite()
        runner = unittest.TextTestRunner()
        runner.run(suite)

    # Register the Plugin Command.
    TFE_Command().register()
    print "2048 registered. Visit http://niklasrosenstein.com/"
