import simpleget
import boxmodel

# Transform it into and HTMLDocument
doc = simpleget.get('http://google.com')

boxes = boxmodel.PageLayout(doc, 800, 600)
