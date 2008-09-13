import simpleget
import boxmodel.layout as layout
import renderer
import pygame

# Transform it into and HTMLDocument
#doc = simpleget.get('http://google.com')
#doc = simpleget.get('file:///home/pib/projects/browser/pybrowser/test.html')
#doc = simpleget.get('http://mail.python.org/pipermail/python-list/2005-May/322354.html')

class DumbBrowser:
    def __init__(self, width=800, height=600):
        self.renderer = renderer.PygameRenderer(800, 600)
        self.width = width
        self.height = height
    def showPage(self, url):
        pygame.display.init()

        doc = simpleget.get(url)
        boxes = layout.PageLayout(browser, doc, 800, 600)
        b = boxes.nextBox()
        self.renderer.render_box(b)
        page = self.renderer.renderAll()

        pygame.display.set_mode((self.width, self.height), 
                                pygame.HWSURFACE | pygame.DOUBLEBUF)
        screen = pygame.display.get_surface()
        screen.blit(page, (0,0))
        pygame.display.flip()
        
        while pygame.event.wait().type != pygame.QUIT:
            pass
        


browser = DumbBrowser()
browser.showPage('file:///home/pib/projects/browser/pybrowser/test.html')

