import re

class Renderer:
    def text_size(self, text, elem):
        """ Return a tuple (width, height) of the size the text would be if
        rendered.
        """

import pygame

class PygameRenderer(Renderer):
    def text_size(self, text, elem):
        # Todo: make this actually determine the font to use from the CSS of
        #       the element the text is in. Also honor white-space property

        #compress whitespace:
        text = re.sub('\s+', ' ', text)
        
        pygame.font.init()
        font = pygame.font.SysFont('Times New Roman', 12)
        (width, height) = font.size(text)
        return (width, font.get_linesize())
    
        
