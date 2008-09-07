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

class PygameRenderer_BoxDump(Renderer):
    def __init__(self):
        self.box_counter = 0
    def text_size(self, text, elem):
        # Todo: make this actually determine the font to use from the CSS of
        #       the element the text is in. Also honor white-space property

        #compress whitespace:
        text = re.sub('\s+', ' ', text)
        
        pygame.font.init()
        font = pygame.font.SysFont('Times New Roman', 12)
        (width, height) = font.size(text)
        return (width, font.get_linesize())

    def render_box(self, box):
        if box.__class__.__name__ == 'TextBox':
            #print 'about to render box %d: "%s": %d,%d' % (self.box_counter, box.text, box.x, box.y)
            pygame.font.init()
            font = pygame.font.SysFont('Times New Roman', 12)

            box_render = font.render(box.text, True, (0,0,0), (255,255,255))
            #pygame.image.save(box_render, 'box_dumps/box%d.bmp' % self.box_counter)
            self.box_counter += 1
        else:
            for child in box.childBoxes:
                self.render_box(child)
        
    
        
