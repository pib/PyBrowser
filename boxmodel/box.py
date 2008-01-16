class Box:
    """ Base Box Class """
    def __init__(self, ownerNode, parentBox, width=None, height=None):):
        self.ownerNode = ownerNode
        self.parentBox = parentBox        
        self._width = width or parentBox.width
        self._height = height
        self._x = None
        self._y = None

        if parentBox:
            parentBox.addChildBox(self)
        self.childBoxes = []

    def addChildBox(self, box):
        self.childBoxes.append(box)

    def getWidth(self):
        return self._width
    def getHeight(self):
        return self._height

    def getX(self):
        return self._x
    def getY(self):
        return self._y

    
class BlockBox(Box):
    """ Represents a CSS block box """

class InlineBox(Box):
    """ Base class for inline boxes. An inline box can (potentially)
    be split into multiple smaller inline boxes, and can also contain
    other inline boxes"""

class TextBox(InlineBox):
    """ Represents a box which wraps around a text element. Actually
    represents the series of boxes which wrap around this particular
    element. Potentially has multiple borders/paddings/margins: one
    for each containing inline element.  This box can be split at word
    boundaries if it needs to be.
    """

class LineBox(BlockBox):
    """ Represents a box which can hold inline boxes. This specialized
    box only holds a single line of inline boxes and has its width
    fixed to the width allowed by its containing box and any floats to
    either side of it.
    It can also be overflowed if an inline box placed into it doesn't fit.
    """

class LineBoxBox(BlockBox):
    """ Represents the implicit box which contains line boxes """
    def __init__(self, ownerNode, parentBox, width=None, height=None):
        BlockBox.__init__(self, ownerNode, parentBox, width, height)
        self._lines = []
        # remaining space on the current line, starts at zero so we add a new
        # line for the first inline box added.
        self._remaining_space = 0

    def addLine(self):
        self._lines.append(LineBox(self.ownerNode, self, self.getWidth()))

    def addInlineBox(self, box):
        """ Add an inline box into the current line box or to a new
        one if the new inline box won't fit in the current line box.

        - If the new inline box is too wide to fit at the current location and
          there are one or more floats at the current y position:
          - Add a new line box
          - move the y position of current line box down past any floats which
            it won't fit next to.
        - If the new inline box fits in the current line box:
          - add the new inline box
          - reduce the remaining space by the width of the new box
        - else if the new inline box doesn't fit in the current line box:
          - if there are elements in the current line box:
            - Add a new line box
          - Add the new box to this box
          - set the status of this box to overflowed,
        """
