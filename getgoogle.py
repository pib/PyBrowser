import simpleget
import boxmodel.layout as layout

# Transform it into and HTMLDocument
doc = simpleget.get('http://google.com')

boxes = layout.PageLayout(doc, 800, 600)
