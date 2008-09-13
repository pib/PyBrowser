import re

class Renderer:
    def text_size(self, text, elem):
        """ Return a tuple (width, height) of the size the text would be if
        rendered.
        """
        raise NotImplementedError

    def render_box(self, box):
        """ Render onto the internal canvas of the renderer the contents of the given box
        """
        raise NotImplementedError

import pygame

class PygameRenderer(Renderer):
    def __init__(self, width, height):
        self.box_counter = 0
        self.boxes = []
        self.width = width
        self.height = height
        self.iwidth = width
        self.iheight = height
        pygame.font.init()
        self.font = pygame.font.SysFont('Times New Roman', 16)

    def text_size(self, text, elem):
        # Todo: make this actually determine the font to use from the CSS of
        #       the element the text is in. Also honor white-space property

        #compress whitespace:
        #text = re.sub('\s+', ' ', text)
        
        (width, height) = self.font.size(text)
        return (width, self.font.get_linesize())

    def renderAll(self):
        page = pygame.Surface((self.width, self.height))
        page.fill((255,255,255))
        for box, img in self.boxes:
            page.blit(img, (box.x, box.y))
        pygame.draw.rect(page, (0,0,0), 
                         pygame.Rect(0,0, self.iwidth, self.iheight),
                         1)
        return page

    def render_box(self, box):
        if box.__class__.__name__ == 'TextBox':
            #print 'about to render box %d: "%s": %d,%d' % (self.box_counter, box.text, box.x, box.y)

            box_render = self.font.render(box.text, True, (0,0,0))#, (255,255,255))
            #pygame.image.save(box_render, 'box_dumps/box%d.bmp' % self.box_counter)
            self.box_counter += 1
            self.width = max(self.width, box.x + box.width)
            self.height = max(self.height, box.y + box.height)
            self.boxes.append((box, box_render))
        else:
            for child in box.childBoxes:
                self.render_box(child)
        
    
        
