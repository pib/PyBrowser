class PageLayout:
    """ This class lays out boxes on a page. It does so incrementally, so if fed
    DOM elements bit by bit it could theoretically display a page incrementally
    as it is being downloaded.

    Keeps context so, for example, if an
    """

    def __init__(self, document, width, height, medium='screen'):
        """ Initialize the document, width, height, and medium of the page to
        be laid out.
        Currently 'screen' is the default and only supported value of medium
        """
        self._width = width
        self._height = height
        self._medium = medium

        self._current_node = document.firstChild
        self._current_containing_block = BlockBox(document, None, width, height)

    def nextBox(self):
        """ Returns the next block box. Either an actual block box or an
        implied LineBoxBox containg a collection of inline boxes
        Uses the following algorithm:

        - nextElement()
        - If the element is a block element:
          - Create a new BlockBox
          - layoutBlockBox
        - Else if the element is an inline element:
          - create a new LineBoxBox
          - Call layoutInlineBoxes with the new LineBoxBox
        - return the resulting block box
          
        """

    def nextElement(self):
        """
        - If there are elements in the element queue
          - Pop and return the first element from the element queue
        - else
          - Read the next element:
            - If the current element has children:
              - next element is current_element.firstChild
            - else if the current element is followed by a sibling:
              - next element is current_element.nextSibling
            - else
              - Go up the tree until a node with a nextSibling is found
              - If such a node is found:
                - next element is that nextSibling
              - else:
                - return None
        """

    def prevElement(self):
        """
        - If the current element has prevSibling
          - if prevSibling has children:
            - go down tree, following prevSibling.lastChild.lastChild...until we
              find a node which has no children.
          - else
            - prev element is current_element.prevSibling
        - else
          - prev element is current_element.parentNode
    
        """
    def layoutInlineBoxes(self, box):
        """ Lays out a series of inline boxes into line boxes, contained in a
        LineBoxBox. Stops when a block box is encountered and returns the
        LineBoxBox with all the inline boxes up to that point.
        Uses the following algorithm:

        - 
        """
    
    def layoutBlockBox(self, box):
        """ Lays out a block box.
        Uses the following algorithm:

        - Get the next box inside this one (self.nextBox())
        - If there are no remaining boxes inside this one:
          - Finish laying out this box
            - Set the final height/width of the box based on contained boxes
            - Set any overflow attributes as needed
        - If the box is a visible box (display is not == 'none':
          - If the block box is absolutely positioned:
            - Set the block's containing box according to CSS rules
            - Layout the block as defined
          - Else
            - If the block box is floating:
              - move the default position of the next box to the top right
                outer corner of this box
            - else
              - move the default position of the next box to the bottom left
                corner of this block
            - if the box is relatively positioned:
              - Offset the box's final position appropriately
           
        """

class BlockBox:
    """ Represents a CSS block box """
    def __init__(self, ownerNode, parentBox, width=None, height=None):
        
        

class InlineBox:
    """ Represents an inline box. An inline box can be split into multiple
    smaller inline boxes """

class LineBox(BlockBox):
    """ Represents a box which can hold inline boxes. This specialized box only
    holds a single line of inline boxes and has its width fixed to the width
    allowed by its containing box and any floats to either side of it
    """

class LineBoxBox(BlockBox):
    """ Represents the implicit box which contains line boxes """
