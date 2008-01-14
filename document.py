import xml.dom.minidom as dom


from twisted.web import microdom

import tidy
tidy_options = dict(output_xhtml=1,
                    add_xml_decl=1,
                    tidy_mark=0,
                    char_encoding='utf8')

def clean_document(doc_str):
    tidy_doc = tidy.parseString(doc_str, **tidy_options)
    return str(tidy_doc)

def getDocument(document_start):
    """ Return a DOM Document. TODO: make this take into account the
    document_start parameter, so that it picks the best DOM based on that """
    return microdom.parseString
    

class TidyDomDocument:
    """ A browser DOM Document interface. Handles converting HTML and XML
    into a DOM tree. Uses utidylib to convert whatever is passed in into
    valid xhtml before parsing it. Can handle incremental loading, but who
    knows how well.."""
    
    def __init__(self):
        self._buffer = ''
        self.parse()

    def write(self, data):
        """ Adds data to the internal representation of the document """
        self._buffer += data
        self.parse()

    def parse(self):
        """ Parses the internal file buffer into a DOM tree.
        Uses tidy to convert it into valid XHTML first """
        tidy_doc = tidy.parseString(self._buffer, **tidy_options)
        self.dom = dom.parseString(str(tidy_doc))

    def calculate_boxes(self, body_width):
        """ Goes down the DOM tree and calculates the boxes for each Node
        body_width is the width, in pixels of the body element"""
        
        
