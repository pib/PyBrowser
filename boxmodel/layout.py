from box import *

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

        self._document = document
        self._current_node = document
        self._initial_containing_block = BlockBox(document, None, width, height)
        self._current_box = self._initial_containing_block

    def nextBox(self):
        """ Returns the next block box. Either an actual block box or an
        implied LineBoxBox containg a collection of inline boxes
        Uses the following algorithm:

        - nextElement()
        - If the element has display: none
          - skip until one isn't display: none is found
        - If the element is a block element:
          - Create a new BlockBox
          - layoutBlockBox
        - Else if the element is an inline element:
          - create a new LineBoxBox
          - Call layoutInlineBoxes with the new LineBoxBox
        - return the resulting block box
          
        """
        elem = self.nextElement()

        style = elem._computed_style

        while style.display == 'none':
            elem = self.skipElement()
            if not elem:
                return None
            style = elem._computed_style

        if style.display == 'inline':
            box = LineBoxBox(elem, self._current_box)
            self.layoutInlineBoxes(box)
        elif style.display == 'block':
            box = BlockBox(elem, self._current_box)
            self.layoutBlockBox(box)
        return box


    def layoutInlineBoxes(self, box):
        """ Lays out a series of inline boxes into line boxes, contained in a
        LineBoxBox. Stops when a block box is encountered or when the current
        node is no longer an ancestor of the starting node and returns the
        LineBoxBox with all the inline boxes up to that point.
        Uses the following algorithm:

        - loop
          - if current element is a block element:
            - prevElement()
            - return
          - if current element is display: none:
            - skipElement()
          - if there are no more elements:
            - return

          - if the current element is a text element:
            - 
          - nextElement()
        """
        elem = self._current_element

        while elem:
            if elem._style.display is not 'block':
                self.prevElement()
                break

            if elem._style.display is 'none':
                elem = self.skipElement()

            if not elem: break

            

            
    
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
              - move the default position of the next box to the top left
                outer corner of this box
              - Add the floating box to the float list of it's parent block
            - else
              - move the default position of the next box to the bottom left
                corner of this block
            - if the box is relatively positioned:
              - Offset the box's final position appropriately
           
        """

    def skipElement(self, pretend=False, inlineboxes=False):
        """ Moves the internal pointer to the next element which is not a child
        of the current element. This is used when an element has display: none

        - If the current node has a nextSibling:
          - set current_element to current_element.nextSibling
        - else if the current node has a parentNode
          - go up until a node with a nextSibling is found
          - If such a node is found:
            - next element is that nextSibling
          - else:
            - return None
        """
        old_node = self._current_node # backup in case there's no next
        old_box = self._current_box
        
        while (not self._current_node.nextSibling and
               self._current_node.parentNode):
            self._current_node = self._current_node.parentNode
            if inlineboxes:
                self._current_box = self._current_box.parentBox
            
        if not self._current_node.nextSibling:
            self._current_node = old_node
            self._current_box = old_box
            return None
        self._current_node = self._current_node.nextSibling
        if inlineboxes:
            self._current_box = InlineBox(self._current_node,
                                          self._current_box)
        
        elem = self._current_node
        elem._style = self._document.defaultView.getComputedStyle(
            elem, None)

        box = self._current_box
        
        if pretend:
            self._current_node = old_node
            self._current_box = old_box

        if inlineboxes:
            return (elem, box)
            
        return elem        
        
    def nextElement(self, inlineboxes=False):
        """ Moves the internal pointer to and returns the next element.
        Leaves the internal pointer as is and returns None if there is no next
        element
        
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
        if self._current_node.childNodes:
            self._current_node = self._current_node.firstChild
            if inlineboxes:
                self._current_box = InlineBox(self._current_node,
                                              self._current_box)
        else:
            return self.skipElement(inlineboxes=inlineboxes)
        elem = self._current_node
        elem._style = self._document.defaultView.getComputedStyle(
            elem, None)
        
        if inlineboxes:
            return (elem, self._current_box)
        return elem

    def prevElement(self, pretend=False):
        """ Moves the internal pointer to and returns the previous element.
        Leaves the internal pointer as is and returns None if there is no next
        element
        
        - If the current element has prevSibling
          - if prevSibling has children:
            - go down tree, following prevSibling.lastChild.lastChild...until
              we find a node which has no children.
          - else
            - prev element is current_element.prevSibling
        - else
          - prev element is current_element.parentNode
        """
        old_node = self._current_node
        
        if self._current_node.prevSibling:
            self._current_node = self._current_node.prevSibling
            while self._current_node.childNodes:
                self._current_node = self._current_node.lastChild
        else:
            if not self._current_node.parentNode:
                return None
            self._current_node = self._current_node.parentNode    
        elem = self._current_node
        elem._style = self._document.defaultView.getComputedStyle(
            elem, None)

        if pretend:
            self._current_node = old_node
        
        return elem
