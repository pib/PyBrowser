import simpleget
import boxmodel.layout as layout
import renderer

# Transform it into and HTMLDocument
#doc = simpleget.get('http://google.com')
doc = simpleget.get('http://mail.python.org/pipermail/python-list/2005-May/322354.html')

class DummyBrowser:
    def __init__(self):
        self.renderer = renderer.PygameRenderer_BoxDump()

browser = DummyBrowser()
boxes = layout.PageLayout(browser, doc, 800, 600)
b = boxes.nextBox()

print repr(b.childBoxes)
browser.renderer.render_box(b)
