import re

findwhitespace = re.compile('\s', re.MULTILINE)

class Box:
    """ Base Box Class """
    def __init__(self, ownerNode, parentBox):
        self.ownerNode = ownerNode
        self.parentBox = parentBox

        #the fact that these are set to none will cause issues.
        # subclasses need to set these properly
        self.x = None
        self.y = None
        self.width = self.height = None

        self.childBoxes = []

    def addChildBox(self, box):
        self.childBoxes.append(box)

    def floatsAt(self, y):
        """ Returns a (potentially empty) array of floating elements which will
        affect elements at the specified y coordinate
        """
        # TODO: implement floats and add them to this function
        return []

    def rightOfLeftFloats(floats):
        """ Static function to determine the rightmost left float in a set of
        floats. Used to determine how wide a LineBox can be at any given point.
        """
        rm_right = self.x
        for box in floats:
            right = box.x + box.getWidth()
            if right > lm_right:
                rm_right = right
        return rm_right
            

    def leftOfRightFloats(floats):
        """ Static function to determine the leftmost right float in a set of
        floats. Used to determine how wide a LineBox can be at any given point.
        """
        lm_left = self.x+self.getWidth()
        for box in floats:
            left = box.x
            if left > lm_left:
                lm_left = left
        return lm_left

    def widthAtY(self, y):
        """ Returns the width available at the specified y location, taking
        floats into account
        """
        floats = self.floatsAt(y)
        if floats:
            width = (Box.leftOfRightFloats(floats) -
                     Box.rightOfLeftFloats(floats))
        else:
            width = self.width

        return width
        
class CSSBoxProps:
    """ A class used to hold quads of values and access them by left, right,
    top, and bottom.
    """
    def __init__(self, top=0, right=0, bottom=0, left=0):
        self.top = top
        self.right = right
        self.bottom = bottom
        self.left = left
        
class CSSBorderProps:
    """ A class used to hold all the info about a box's borders """
    def __init__(self, tw, rw, bw, lw, # border widths
                 tc, rc, bc, lc,       # border colors
                 ts, rs, bs, ls):      # border styles
        self.width = CSSBoxProps(tw, rw, bw, lw)
        self.color = CSSBoxProps(tc, rc, bc, lc)
        self.style = CSSBoxProps(ts, rs, bs, ls)

class BlockBox(Box):
    """ Represents a CSS block box """
    def __init__(self, ownerNode, parentBox, x, y):
        Box.__init__(self, ownerNode, parentBox)
        if parentBox:
            self.width = parentBox.widthAtY(y)
        if ownerNode:
            style = ownerNode.ownerDocument.defaultView.getComputedStyle(ownerNode,
                                                                         None)
            self.margin = CSSBoxProps(style.marginTop, style.marginRight,
                                      style.marginBottom, style.marginLeft)
            self.border = CSSBorderProps(
                style.borderTopWidth, style.borderRightWidth,
                style.borderBottomWidth, style.borderLeftWidth,
                style.borderTopColor, style.borderRightColor,
                style.borderBottomColor, style.borderLeftColor,
                style.borderTopStyle, style.borderRightStyle,
                style.borderBottomStyle, style.borderLeftStyle)
            self.x = self._current_x = x
            self.y = self._current_y = y
            self.style = style

class InlineBox(Box):
    """ Base class for inline boxes. An inline box can (potentially)
    be split into multiple smaller inline boxes, and can also contain
    other inline boxes"""
    def split(self, width):
        """ Split this box at the specified width. Margins and borders are
        taken into consideration.
        Return the two new boxes in an array.
        If the box can't be split, return self in an array.
        """
        return [self]

class TextBox(InlineBox):
    """ Represents a box which wraps around a text element. Actually
    represents the series of boxes which wrap around this particular
    element. Potentially has multiple borders/paddings/margins: one
    for each containing inline element.  This box can be split at word
    boundaries if it needs to be.
    """
    FULL  = 0 # Full text element, not split
    LEFT  = 1 # Left box after an initial split
    MID   = 2 # Middle box ( left box after two or more splits)
    RIGHT = 3 # Right box after split
    def __init__(self, elem, renderer, text=None, parentBox=None,
                 type=0):
        InlineBox.__init__(self, elem, parentBox)
        self.ownerNode = elem
        self.parentBox = parentBox
        self._renderer = renderer

        # type tells us whether we need to draw the left and right borders,
        # paddings, and margins
        self._type = type

        # TODO: implement different white-space settings

        # compress down whitespace
        if not text:
            text = elem.nodeValue
        else:
            text = text.strip()
        self.text = re.sub('\s+', ' ', text)
        
        (self.width, self.height) = renderer.text_size(self.text,
                                                       self.ownerNode)
        self._calc_size()

    def _calc_size(self):
        self._left_width = 0
        self._right_width = 0
        self._full_width = self.width

        return # TODO: make the following code work correctly

        style = self.ownerNode.ownerDocument.getComputedStyle(
            self.ownerNode, None)
        self._left_width = style.marginLeft + style.borderLeftWidth + \
                           style.paddingLeft
        self._right_width = style.paddingRight + style.borderRightWidth + \
                            style.marginRight

        self._full_width = self.width + self._left_width + self._right_width

    def fullWidth(self):
        return self._full_width
        
    def split(self, width):
        if width > self._full_width:
            return [self]

        text = self.text
        whitespace = findwhitespace.search(text)
        
        if not whitespace:
            return [self]

        # find all the positions which we can split at:
        splits = []
        while whitespace:
            splits.append(whitespace.start())
            whitespace = findwhitespace.search(text, whitespace.end())

        split = None
        for s in splits:
            (w, h) =  self._renderer.text_size(text[:s], self.ownerNode)
            split_width = w + self._left_width

            # we want this to be as long as possible without being longer than
            # width.
            
            # If a split is too wide 
            if split_width > width:
                # ...and we found a thinner one previously, use the previous one
                if split:
                    break
                # ...and it's the first split we found, use it
                split = s
                break

            # otherwise, store the split in case the next one is too wide
            split = s
            # In the unlikely case that the split is exactly width, use it
            if split_width == width:
                break

        lefttext = text[:split]
        righttext = text[split:]

        # Pick the type of the two sub-boxes based on the current type
        (lt, rt) = {
            TextBox.FULL: (TextBox.LEFT, TextBox.RIGHT),
            TextBox.LEFT: (TextBox.LEFT, TextBox.MID),
            TextBox.MID:  (TextBox.MID, TextBox.MID),
            TextBox.RIGHT:(TextBox.MID, TextBox.RIGHT)
            }[self._type]

        return [TextBox(self.ownerNode, self._renderer, lefttext, self, lt),
                TextBox(self.ownerNode, self._renderer, righttext, self, rt)]
        

class LineBox(BlockBox):
    """ Represents a box which can hold inline boxes. This specialized
    box only holds a single line of inline boxes and has its width
    fixed to the width allowed by its containing box and any floats to
    either side of it.
    It can also be overflowed if an inline box placed into it doesn't fit.
    """
    def __init__(self, ownerNode, parentBox, x, y):
        BlockBox.__init__(self, ownerNode, parentBox, x, y)
        self.width = 0
        self.height = 0
    def addChildBox(self, box):
        BlockBox.addChildBox(self, box)
        #print 'x', box.x, 'width', self.width
        box.x = self.x + self.width
        box.y = self.y
        self.width += box.width
        self.height = max(self.height, box.height)

class LineBoxBox(BlockBox):
    """ Represents the implicit box which contains line boxes """
    def __init__(self, ownerNode, parentBox, x=None, y=None):
        BlockBox.__init__(self, ownerNode, parentBox, x, y)
        # remaining space on the current line, starts at zero so we add a new
        # line for the first inline box added.
        self._remaining_width = 0

    def addLine(self):
        if len(self.childBoxes) > 0:
            self._current_y += self.childBoxes[-1].height
        width = self.widthAtY(self._current_y)
        #print 'width', width, 'remainint', self._remaining_width
        self.addChildBox(LineBox(self.ownerNode, self,
                                 self.x, self._current_y))
        self._remaining_width = width

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

        nextbox = box
        while nextbox:
            box = nextbox
            nextbox = None

            width = box.fullWidth()
            height = box.height

            # TODO: put float handling code in here

            if self._remaining_width <= 0:
                self.addLine()
        
            if width > self._remaining_width:
                boxes = box.split(self._remaining_width)
                box = boxes[0]
                #import pdb
                #pdb.set_trace()
                #continue if the box was split
                if len(boxes) == 2:
                    nextbox = boxes[1]
                # if the returned box doesn't fit on the current line and there
                # are already elements on the current line, add a new line
                if box.fullWidth() > self._remaining_width and \
                       len(self.childBoxes[-1].childBoxes) > 0:
                    self.addLine()
                 
            self.childBoxes[-1].addChildBox(box)
            self._remaining_width -= width
