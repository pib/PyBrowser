from BeautifulSoup import * 
import cairo
import boxmodel

TYPES_TO_IGNORE = (Declaration, Comment)
TAGS_TO_IGNORE = ("script", "style")
	
class PageNode:
	""" This is a basic, inline page element. Block elements will come later
	"""
	children = None
	def __init__(self, soup, parent):
		self.parent = parent
		if soup.__class__ in TYPES_TO_IGNORE:
			self.type = 'ignored'
		elif isinstance(soup, Tag):
			self.type = 'tag'
			self.attributes = dict(soup.attrs)
			if soup.name not in TAGS_TO_IGNORE:
				self.children = [PageNode(node, self) 
						 for node in soup.contents]
			self.tagtype = soup.name
		elif isinstance(soup, NavigableString): 
			self.type = 'text'
		else:
			self.type = 'unknown'
		self.text = str(soup)		

	def makeBox(self):
		if self.type is 'text':
			return boxmodel.TextBox(self.text)
		if self.type == 'ignored': return None
		box = boxmodel.LineBox()
		if self.children:
			for child in self.children:
				subbox = child.makeBox()
				box.addSubBox(subbox) 
		self.box = box
		return box

	def makeImage(self, width):
		self.box.setWidth(width)
		height = self.box.getHeight()
		img = cairo.ImageSurface(cairo.FORMAT_ARGB32, 
				width, int(height))
		ct = cairo.Context(img)
		self.box.draw(ct,0,0, width);
		return img


