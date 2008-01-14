import re
import string
import cairo

def _set4_mux(obj, items, val):
	vals = val.split(' ')
	for i in zip(items, vals):
		setattr(obj, *i)
	if len(vals) in (2,3):
		setattr(obj, items[3], vals[1])
	if len(vals) in (1,2):
		setattr(obj, items[2], vals[0])
	if len(vals) == 1:
		setattr(obj, items[1], vals[0])
		setattr(obj, items[2], vals[0])
		setattr(obj, items[3], vals[0])

def _get_demux(obj, items):
	return ' '.join([str(getattr(obj, item)) for item in items])

# used for getting and setting multiple items like margin = margin-left, margin-top, etc...
_mux4 = {'get':_get_demux, 'set':_set4_mux}

class GetSet:
	def __init__(self, getset, items):
		self.__get = getset['get']
		self.__set = getset['set']
		self.items = items
	def get(self, obj):
		return self.__get(obj, self.items)
	def set(self, obj, val):
		self.__set(obj, self.items, val)
		

# matches a number, followed by em, ex, px, in, cm, mm, pt, pc, or %
# or it matches the word 'auto' or 'inherit'
_size = '-?[0-9]*.?[0-9]*(?:e[mx]|p[txc]|in|[cm]m|%)','auto','inherit'
_box_defaults = {'display':'inline', 'position':'static', 'top':'auto', 
		'right':'auto', 'bottom':'auto', 'left':'auto',
		'float':'none', 'clear':'none',
		'margin-top':0, 'margin-bottom':0,
		'margin-left':0, 'margin-right':0,
		'padding-top':0, 'padding-bottom':0,
		'padding-left':0, 'padding-right':0,
		'height':'auto', 'width':'auto'}
_box_allowed = {'display':('inline', 'block', 'none', 'inherit'),
		'position':('static','relative','absolute','fixed','inherit'),
		'top':_size,'right':_size,'bottom':_size,'left':_size,
		'float':('left','right','none','inherit'),
		'clear':('none','left','right','both','inherit'),
		'margin-top':_size, 'margin-bottom':_size,
		'margin-left':_size, 'margin-right':_size,
		'padding-top':_size, 'padding-bottom':_size,
		'padding-left':_size, 'padding-right':_size,
		'height':_size, 'width':_size}
_box_special = {'margin':GetSet(_mux4, ('margin-top', 'margin-right', 'margin-bottom', 'margin-left')),
'padding':GetSet(_mux4, ('padding-top', 'padding-right', 'padding-bottom', 'padding-left'))
}
# compile all the regular expressions
_re_pool = {} # we'll store just one instance of each re
for k in _box_allowed:
	list = '|'.join(sorted(_box_allowed[k])) #make a RE from it
	if list in _re_pool: # if we have it already, use it
		_box_allowed[k] = _re_pool[list]
	else: # otherwise, compile the re and then use it
		_re_pool[list]= re.compile(list)
		_box_allowed[k] = _re_pool[list]

class PropertyHolder(object):
	""" an object which allows for semi-automated checking of attributes"""

	def __init__(self, default_props, allowed_props, special_props):
		self.__dict__['props'] = {}
		self.__dict__['default_props'] = default_props
		self.__dict__['allowed_props'] = allowed_props
		self.__dict__['special_props'] = special_props
	def __getattr__(self, name):
		if name in self.special_props:
			return self.special_props[name].get(self)
		if name not in self.default_props:
			raise AttributeError, name
		return self.props.get(name, self.default_props[name]) 
	def __setattr__(self, name, value):
		if name in self.allowed_props:
			if self.allowed_props[name].match(value): 
				self.props[name] = value
			else: 
				raise ValueError(
				"illegal value '%s' for property '%s',\n"\
				"expected one of these: '%s'" % 
				(value, name, 
				self.allowed_props[name].pattern))
		elif name in self.special_props:
			self.special_props[name].set(self, value);
		else:
			self.__dict__[name] = value
	def __delattr__(self, name):
		if name in self.allowed_props:
			del self.props[name]
		else:
			del self.__dict__[name]

class Box(object):
	""" The basic Box, abstract class, it doesn't know how to draw itself"""
	def __init__(self):
		self._height = 0; # calculated height
		self._width = 0; # calculated width
		self.children = []
	style = PropertyHolder(_box_defaults, _box_allowed, _box_special)

	def addSubBox(self, sub):
		if sub:
			self._height = max(self._height, sub.getHeight())
			self.children.append(sub)

	def getHeight(self):
		return self._height

	def getWidth(self):
		return self._width
	
	def draw(self, ctx, x, y):
		raise NotImplementedError

	def setWidth(self, width):
		pass

class LineBox(Box):
	"""A box representing the implied box used for standard inline layout"""
	
	def getHeight(self):
		height = 0
		for box in self.children:
			height += box.getHeight()
		return height

	def draw(self, ctx, x, y, width):
		if len(self.children):
			ctx.move_to(x,y+self.children[0].getHeight())
		for box in self.children:
			box.draw(ctx, x, y, width)
			y += box.getHeight()

	def setWidth(self, width):
		self._width = width

		i = 0
		while i < len(self.children):
			box = self.children[i]
			box.setWidth(width)
			if box.getWidth() > width:
				boxes = box.split(width)
				self.children[i:i+1] = boxes
			i += 1
		
class TextBox(Box):
	""" A break-up-able box which stores just text """
	def __init__(self, text):
		self.text = text
		self.comp_text = text.replace("\n"," ").replace("\t"," ")
		while '  ' in self.comp_text:
			self.comp_text = self.comp_text.replace('  ',' ')
		surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1,1)
		ctx = cairo.Context(surf)
		self.x_bear, self.y_bear, width, height = \
				ctx.text_extents(self.comp_text)[:4]
		self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1,1)
		self.ctx = cairo.Context(self.surf)
		self.ctx.move_to(0,height)
		self.ctx.show_text(self.comp_text)
		self.ctx.stroke()
		self._height = height
		self._width = width

		#calculate the breakable positions here
		self.breaks = []
		i = 0
		while i != -1:
			i = self.comp_text.find(' ', i+1)
			self.breaks.append(int(ctx.text_extents(self.comp_text[:i])[2]))

	def draw(self, ctx, x, y, width):
		ctx.move_to(x, y+self._height)
		ctx.show_text(self.comp_text)

	def getHeight(self):
		return self._height-self.y_bear
	
	def split(self, width):
		""" Split the text at the specified width """
		last = 0
		for i in self.breaks:
			if i > width: break
			last = i
		if last == 0: return [self]
		if last < width:
			return [TextBox(self.comp_text[:last]), 
				TextBox(self.comp_text[last+1:])]
		return [self]
			
