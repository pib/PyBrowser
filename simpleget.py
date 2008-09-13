import domhtml
import pxdom
import tidy
import urllib2

tidy_options = dict(output_xhtml=1,
                    add_xml_decl=1,
                    wrap=0,
                    tidy_mark=0)

def get(uri):
  """ Parse complete document from a URI into an HTMLDocument
  """
  
  stream = urllib2.urlopen(uri)

  tidy_doc = tidy.parseString(stream.read(), **tidy_options)

  document = domhtml.parseString(str(tidy_doc), uri)

  return document


