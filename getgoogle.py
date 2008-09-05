import simpleget
import boxmodel.layout as layout
import renderer

# Transform it into and HTMLDocument
doc = simpleget.get('http://google.com')

class DummyBrowser:
    def __init__(self):
        self.renderer = renderer.PygameRenderer()

browser = DummyBrowser()
boxes = layout.PageLayout(browser, doc, 800, 600)
b = boxes.nextBox()
