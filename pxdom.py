""" pxdom - stand-alone embeddable pure-Python DOM implementation

Fully-compliant with DOM Level 3 Core/XML and Load/Save Recommendations.
Includes pure-Python non-validating parser .
"""

__version__= 1,4
__author__ = 'Andrew Clover <and@doxdesk.com>'
__date__   = '19 July 2006'
__all__    = [
  'getDOMImplementation', 'getDOMImplementations', 'parse', 'parseString'
]


# Setup, utility functions
# ============================================================================

import os, sys, string, StringIO, urlparse, urllib, httplib
r= string.replace

def _insertMethods():
  """ In this source, not all members are defined directly inside their class
      definitions; some are organised into aspects and defined together later
      in the file, to improve readability. This function is called at the end
      to combine the externally-defined members, whose names are in the format
      _class__member, into the classes they are meant to be in.
  """
  for key, value in globals().items():
    if key[:1]=='_' and string.find(key, '__')>=1:
      class_, method= string.split(key[1:], '__', 1)
      setattr(globals()[class_], method, value)


# Backwards-compatibility boolean type (<2.2.1)
#
try:
  True
except NameError:
  globals()['True'], globals()['False']= None is None, None is not None

# Use sets where available for low-level character matching
#
try:
  from sets import ImmutableSet
except ImportError:
  ImmutableSet= lambda x: x

# Check unicode is supported (Python 1.6+), provide dummy class to use with
# isinstance
#
try:
  import unicodedata
except ImportError:
  globals()['unicode']= None
  class Unicode: pass
else:
  Unicode= type(unicode(''))
  import unicodedata, codecs

# XML character classes. Provide only an XML 1.1 character model for NAMEs, as
# 1.0's rules are insanely complex.
#
DEC= ImmutableSet('0123456789')
HEX= ImmutableSet('0123456789abcdefABDCDEF')
LS= ('\r\n', '\r')
WHITE= ' \t\n\r'

NOTCHAR= ImmutableSet(
  '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0B\x0C\x0E\x0F'
  '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x7F'
)
NOTFIRST= ImmutableSet('.-0123456789')
NOTNAME= ImmutableSet(' \t\n\r!"#$%&\'()*+,/;<=>?@[\\]^`{|}~')
NOTURI= ImmutableSet(
  string.join(map(chr, range(0, 33)+range(127,256)), '')+'<>"{}\^`'
)

if unicode is not None:
  LSU= unichr(0x85), unichr(0x2028)
  WHITEU= unichr(0x85)+unichr(0x2028)
  NOTCHARU= ImmutableSet(
    unicode(
      '\x80\x81\x82\x83\x84\x86\x87\x88\x89\x8A\x8B\x8C\x8D\x8E\x8F'
      '\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9A\x9B\x9C\x9D\x9E\x9F',
      'iso-8859-1'
    )+unichr(0xFFFE)+unichr(0xFFFF)
  )
  NOTFIRSTU= (0xB7,0xB8), (0x300,0x370), (0x203F,0x2041)
  NOTNAMEU= (
    (0x80,0xB7), (0xB8,0xC0), (0xD7,0xD8), (0xF7,0xF8), (0x037E,0x037F),
    (0x2000,0x200C), (0x200E,0x203F), (0x2041,0x2070), (0x2190,0x2C00),
    (0x2FF0,0x3001), (0xE000,0xF900), (0xFDD0,0xFDF0), (0xFFFE, 0x10000)
  )

# Unicode character normalisation (>=2.3). Also includes a kludge for
# composing-characters that we can't check through unicodedata, see
# 'Character Model for the World Wide Web', Appendix C
#
CNORM= False
if unicode is not None:
  if hasattr(unicodedata, 'normalize'):
    CNORM= True
    EXTRACOMPOSERS= string.join(map(unichr, [
      0x09BE, 0x09D7, 0x0B3E, 0x0B56, 0x0B57, 0x0BBE, 0x0BD7, 0x0CC2, 0x0CD5,
      0x0CD6, 0x0D3E, 0x0D57, 0x0DCF, 0x0DDF, 0x0FB5, 0x0FB7, 0x102E
    ] + range(0x1161, 0x1176) + range(0x11A8, 0x11C2) ), '')

def dictadd(a, b):
  ab= a.copy()
  ab.update(b)
  return ab

REPR_MAX_LEN= 12
REPR_MAX_LIST=3

# Special namespace URIs
#
XMNS= 'http://www.w3.org/XML/1998/namespace'
NSNS= 'http://www.w3.org/2000/xmlns/'
HTNS= 'http://www.w3.org/1999/xhtml'
DTNS= 'http://www.w3.org/TR/REC-xml'
FIXEDNS= {'xmlns': NSNS, 'xml': XMNS}

class _NONS:
  """ Singleton value type used internally as a value for namespaceURI
      signifying that a non-namespace version of a node or method is in use;
      the accompanying localName is then the complete nodeName. This is
      different to None, which is a null namespace value.
  """
  def __str__(self):
    return '(non-namespace)'
NONS= _NONS()

# Media types to allow in addition to anything labelled '...+xml' when using
# parameter supported-media-types-only
#
XMLTYPES= [
  'text/xml', 'application/xml', 'application/xml-dtd', 'text/xsl'
  'text/xml-external-parsed-entity','application/xml-external-parsed-entity'
]

# Elements defined as EMPTY in XHTML for parameter pxdom-html-compatible
#
HTMLEMPTY= [
  'area', 'base', 'basefont', 'br', 'col', 'frame', 'hr', 'img',
  'input', 'isindex', 'link', 'meta', 'param'
]

def _checkName(name, nc= False):
  """ Check name string, raise exception if not well-formed. Optionally check
      it also matches NCName (no colons).
  """
  if name=='':
    raise InvalidCharacterErr(name, '')
  if name[0] in NOTFIRST:
    raise InvalidCharacterErr(name, name[0])
  if isinstance(name, Unicode):
    for c0, c1 in NOTFIRSTU:
      if ord(name[0])>=c0 and ord(name[0])<c1:
        raise InvalidCharacterErr(name, char)
  for char in name:
    if char in NOTNAME or char in NOTCHAR:
      raise InvalidCharacterErr(name, char)
    if isinstance(char, Unicode):
      if char in NOTCHARU:
        raise InvalidCharacterErr(name, char)
      for c0, c1 in NOTNAMEU:
        if ord(char)>=c0 and ord(char)<c1:
          raise InvalidCharacterErr(name, char)
  if nc and ':' in name:
      raise NamespaceErr(name, None)

def _splitName(name):
  """ Utility function to split a qualified name into prefix and localName.
      prefix may be None if no prefix is used; both will be None if the name
      is not a valid qualified name.
  """
  parts= string.split(name, ':', 2)
  if '' not in parts:
    if len(parts)==2:
      return tuple(parts)
    if len(parts)==1:
      return (None, name)
  return (None, None)

def _encodeURI(s):
  """ Utility function to turn a string from a SYSTEM ID or xml:base attribute
      into a URI string, with disallowed characters %-encoded.
  """
  if isinstance(s, Unicode):
    s= s.encode('utf-8')
  uri= ''
  for c in s:
    if c in NOTURI:
      uri= uri+'%%%02X'%ord(c)
    else:
      uri= uri+c
  return uri


class DOMObject:
  """ Base class that allows access to properties through calling getter and
      setter methods of the form _get_propertyName. Immutable properties can
      be made by providing no _set_propertyName method; immutable objects are
      made by setting the readonly property.
  """
  def __init__(self, readonly= False):
    self._readonly= readonly
  def _get_readonly(self):
    return self._readonly
  def _set_readonly(self, value):
    self._readonly= value

  def __getattr__(self, key):
    if key[:1]=='_':
      raise AttributeError, key
    try:
      getter= getattr(self, '_get_'+key)
    except AttributeError:
      raise AttributeError, key
    return getter()

  def __setattr__(self, key, value):
    if key[:1]=='_':
      self.__dict__[key]= value
      return

    # When an object is readonly, there are a few attributes that can be set
    # regardless. Readonly is one (obviously), but due to a nasty hack in the
    # DOM spec it must also be possible to set nodeValue and textContent to
    # anything on nodes where these properties are defined to be null (with no
    # effect).
    #
    if self._readonly and key not in ('readonly', 'nodeValue', 'textContent'):
      raise NoModificationAllowedErr(self, key)
    try:
      setter= getattr(self, '_set_'+key)
    except AttributeError:
      if hasattr(self, '_get_'+key):
        raise NoModificationAllowedErr(self, key)
      raise AttributeError, key
    setter(value)


# Node-structure classes
# ============================================================================

class DOMList(DOMObject):
  """ A list structure that can be accessed either using the DOM IDL methods
      or Python list accessor constructs.
  """
  def __init__(self, initial= None):
    DOMObject.__init__(self)
    if initial is None:
      self._list= []
    else:
      self._list= initial
  def  __repr__(self):
    l= repr(self._list[:REPR_MAX_LIST])
    if len(self._list)>REPR_MAX_LIST:
      l= l+'...'
    return '<pxdom.%s %s>' % (self.__class__.__name__, l)

  # DOM-style methods
  #
  def _get_length(self):
    return len(self._list)

  def item(self, index):
    if index<0 or index>=len(self._list):
      return None
    return self._list[index]

  def contains(self, str):
    return str in self._list

  # Python-style methods
  #
  def __len__(self):
    return len(self._list)

  def __getitem__(self, index):
    return self._list[index]

  def __setitem__(self, index, value):
    raise NoModificationAllowedErr(self, 'item(%s)' % str(index))

  def __delitem__(self, index):
    raise NoModificationAllowedErr(self, 'item(%s)' % str(index))

  # Mutable sequence convenience methods for internal use
  #
  def _index(self, value):
    return self._list.index(value)

  def _append(self, value):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'item(%s)' % str(len(self._list)))
    self._list.append(value)

  def _insertseq(self, index, values):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'item(%s)' % str(index))
    self._list[index:index]= values


class NodeList(DOMList):
  """ Abstract list of nodes dependent on an owner node.
  """
  def __init__(self, ownerNode= None):
    DOMList.__init__(self)
    self._ownerNode= ownerNode


class ChildNodeList(NodeList):
  """ A NodeList of children of the owner node. Alterations to the list result
      in calls to the parent's DOM methods (this seems to be required by the
      Python DOM bindings, although never actually used in practice).
  """
  def __setitem__(self, index, value):
    self._ownerNode.replaceChild(value, self._list[index])

  def __delitem__(self, index):
    self._ownerNode.removeChild(self._list[index])


class NodeListByTagName(NodeList):
  """ A NodeList returned by an Element.getElementsByTagName[NS] method. This
      is still 'live' - the internal _list acts only as a cache, and is
      recalculated if the owner Element's contents have changed since it was
      last built.
  """
  def __init__(self, ownerNode, namespaceURI, localName):
    NodeList.__init__(self, ownerNode)
    self._namespaceURI= namespaceURI
    self._localName= localName
    self._sequence= None

  def _get_length(self):
    if self._sequence!=self._ownerNode._sequence: self._calculate()
    return NodeList._get_length(self)

  def item(self, index):
    if self._sequence!=self._ownerNode._sequence: self._calculate()
    return NodeList.item(self, index)

  def __getitem__(self, index):
    if self._sequence!=self._ownerNode._sequence: self._calculate()
    return NodeList.__getitem__(self, index)

  def __len__(self):
    if self._sequence!=self._ownerNode._sequence: self._calculate()
    return NodeList.__len__(self)

  def __repr__(self):
    try:
      self._calculate()
    except DOMException:
      pass
    return NodeList.__repr__(self)

  def _calculate(self):
    """ Recalculate the list. This method does the actual work of the
        Element.getElementsByTagName call.
    """
    self._list= []
    self._walk(self._ownerNode)
    self._sequence= self._ownerNode._sequence

  def _walk(self, element):
    """ Recursively add a node's child elements to the internal node list when
        they match the conditions passed to Element.getElementsByTagName.
    """
    for childNode in element.childNodes:
      if childNode.nodeType==Node.ELEMENT_NODE:
        if (
          self._localName=='*' and
          self._namespaceURI in ('*', NONS, childNode.namespaceURI)
        ) or (
          self._namespaceURI=='*' and
          self._localName==childNode.localName
        ) or (
          self._namespaceURI is NONS and
          self._localName==childNode.nodeName
        ) or (
          self._namespaceURI==childNode.namespaceURI and
          self._localName==childNode.localName
        ):
          self._list.append(childNode)
      if childNode.nodeType in (Node.ELEMENT_NODE,Node.ENTITY_REFERENCE_NODE):
        self._walk(childNode)


class NamedNodeMap(NodeList):
  """ Dictionary-style object used for mappings. Must be initialised with a
      nodeType for nodes it wishes to handle.
  """
  def __init__(self, ownerNode, childType):
    NodeList.__init__(self, ownerNode)
    self._childTypes= (childType,)

  def getNamedItemNS(self, namespaceURI, localName):
    if namespaceURI=='':
      namespaceURI= None
    for node in self._list:
      if (
        (namespaceURI is NONS and localName==node.nodeName) or
        (namespaceURI==node.namespaceURI and localName==node.localName)
      ):
        return node
    return None

  def setNamedItemNS(self, arg):
    node= self.getNamedItemNS(arg.namespaceURI, arg.localName)
    self._writeItem(node, arg)
    return node

  def removeNamedItemNS(self, namespaceURI, localName):
    node= self.getNamedItemNS(namespaceURI, localName)
    if node is None:
      raise NotFoundErr(self, namespaceURI, localName)
    self._writeItem(node, None)
    return node

  def getNamedItem(self, name):
    return self.getNamedItemNS(NONS, name)

  def setNamedItem(self, arg):
    node= self.getNamedItemNS(NONS, arg.nodeName)
    self._writeItem(node, arg)
    return node

  def removeNamedItem(self, name):
    return self.removeNamedItemNS(NONS, name)

  def _writeItem(self, oldItem, newItem):
    """ Internal alteration functions through which all add, remove and
        replace operations are made. If oldItem is not None it is removed;
        if newItem is not None it is added; if both not None the new item is
        written the previous position of the oldItem.
    """
    if self._readonly:
      raise NoModificationAllowedErr(self, 'namedItem')
    if newItem is not None:
      if newItem.nodeType not in self._childTypes:
        raise HierarchyRequestErr(newItem, self)
      if newItem.ownerDocument is not self._ownerNode.ownerDocument:
        raise WrongDocumentErr(self._ownerNode.ownerDocument, newItem)
    if oldItem is None:
      index= len(self._list)
    else:
      try:
        index= self._list.index(oldItem)
      except ValueError:
        raise NotFoundErr(self, NONS, oldItem.nodeName)
      oldItem._containerNode= None
    if newItem is not None:
      newItem._containerNode= self._ownerNode
      self._list[index:index+1]= [newItem]
    else:
      self._list[index:index+1]= []

  # Python dictionary-style methods for minidom compatibility. This is
  # inconsistent with how Python dictionaries normally work, and is subject
  # to change. It is recommended to use the standard DOM methods instead.
  #
  def __getitem__(self, key):
    if isinstance(key, type(0)):
      return self._list[key]
    elif isinstance(key, type(())):
      return self.getNamedItemNS(key[0], key[1])
    else:
      return self.getNamedItem(key)

  def __delitem__(self, key):
    if isinstance(key, type(0)):
      self._writeItem(self._list[key], None)
    elif isinstance(key, type(())):
      self.removeNamedItemNS(key[0], key[1])
    else:
      return self.removeNamedItem(key)

  def __setitem__(self, key, value):
    if isinstance(value, Attr):
      if isinstance(key, type(0)):
        self._writeItem(self._list[key], value)
      elif isinstance(key, type(())):
        self._ownerNode.setAttributeNodeNS(value)
      else:
        self._ownerNode.setAttributeNode(value)
    else:
      if isinstance(key, type(0)):
        self._list[key].value= value
      elif isinstance(key, type(())):
        return self._ownerNode.setAttributeNS(key[0], key[1], value)
      else:
        return self._ownerNode.setAttribute(key, value)

  def values(self):
    return self._list[:]
  def keys(self):
    return map(lambda a: a.nodeName, self._list)
  def items(self):
    return map(lambda a: (a.nodeName, a.value), self._list)
  def keysNS(self):
    return map(lambda a: (a.namespaceURI, a.localName), self._list)
  def itemsNS(self):
    return map(lambda a: ((a.namespaceURI,a.localName),a.value), self._list)


class AttrMap(NamedNodeMap):
  """ A node map used for storing the attributes of an element, and updating
      the defaulted attributes automatically on changes.
  """
  def __init__(self, ownerNode):
    NamedNodeMap.__init__(self, ownerNode, Node.ATTRIBUTE_NODE)
  def _writeItem(self, oldItem, newItem):
    if newItem is not None and newItem.nodeType==Node.ATTRIBUTE_NODE and (
      newItem._containerNode not in (None, self._ownerNode)
    ):
      raise InuseAttributeErr(newItem)
    NamedNodeMap._writeItem(self, oldItem, newItem)
    if oldItem is not None:
      if newItem is None or newItem.nodeName!=oldItem.nodeName:
        ownerDocument= self._ownerNode.ownerDocument
        if ownerDocument is not None:
          doctype= ownerDocument.doctype
          if doctype is not None:
            declarationList= doctype._attlists.getNamedItem(
              self._ownerNode.nodeName
            )
            if declarationList is not None:
              declaration= declarationList.declarations.getNamedItem(
                oldItem.nodeName
              )
              if (
                declaration is not None and declaration.defaultType in (
                  AttributeDeclaration.DEFAULT_VALUE,
                  AttributeDeclaration.FIXED_VALUE
                )
              ):
                declaration._createAttribute(self._ownerNode)


# Core non-node classes
# ============================================================================

class DOMImplementation(DOMObject):
  """ Main pxtl.dom implementation interface, a singleton class. The pxdom
      module itself implements the DOMImplementationSource interface, so you
      can get hold of an implementation with pxdom.getDOMImplementation('')
  """
  [MODE_SYNCHRONOUS,MODE_ASYNCHRONOUS
  ]=range(1, 3)

  _features= {
    'xml':  ['1.0', '2.0', '3.0'],
    'core':        ['2.0', '3.0'],
    'ls':                 ['3.0'],
    'xmlversion':  ['1.0', '1.1']
  }
  def hasFeature(self, feature, version):
    f= string.lower(feature)
    if f[:1]=='+':
      f= f[1:]
    if self._features.has_key(f):
      if version in self._features[f]+['', None]:
        return True
    return False
  def getFeature(self, feature, version):
    if self.hasFeature(feature, version):
      return self

  def createDocument(self, namespaceURI, qualifiedName, doctype):
    if namespaceURI=='':
      namespaceURI= None
    document= Document()
    if doctype is not None:
      document.appendChild(doctype)
    if qualifiedName is not None:
      root= document.createElementNS(namespaceURI, qualifiedName)
      document.appendChild(root)
    return document

  def createDocumentType(self, qualifiedName, publicId, systemId):
    _checkName(qualifiedName)
    if _splitName(qualifiedName)[1] is None:
      raise NamespaceErr(qualifiedName, None)
    doctype= DocumentType(None, qualifiedName, publicId, systemId)
    doctype.entities.readonly= True
    doctype.notations.readonly= True
    return doctype

_implementation= DOMImplementation()

def getDOMImplementation(features= ''):
  """ DOM 3 Core hook to get the Implementation object. If features is
      supplied, only return the implementation if all features are satisfied.
  """
  fv= string.split(features, ' ')
  for index in range(0, len(fv)-1, 2):
    if not _implementation.hasFeature(fv[index], fv[index+1]):
      return None
  return _implementation

def getDOMImplementationList(features= ''):
  """ DOM 3 Core method to get implementations in a list. For pxdom this will
      only ever be the single implementation, if any.
  """
  implementation= getDOMImplementation(features)
  implementationList= DOMImplementationList()
  if implementation is not None:
    implementationList._append(implementation)
  implementationList.readonly= True
  return implementationList


class DOMImplementationList(DOMList):
  """ List of DOMImplementation classes; no special features over DOMList.
  """
  pass


class DOMConfiguration(DOMObject):
  """ Object holding a mapping of parameter names to values, and performing
      the flag-flipping warts of infoset and canonical-form. _defaults holds
      the default values (mostly defined by the spec), together with a flag
      document whether each can be changed from the defaults (optional
      features relating to validation and character normalisation are not
      supported by pxdom).
  """
  _defaults= {
    # Core configuration
    'canonical-form':                            (False, True ),
    'cdata-sections':                            (True,  True ),
    'check-character-normalization':             (False, CNORM),
    'comments':                                  (True,  True ),
    'datatype-normalization':                    (False, False),
    'element-content-whitespace':                (True,  True ),
    'entities':                                  (True,  True ),
    'error-handler':                             (None,  True ),
    'ignore-unknown-character-denormalizations': (True,  False),
    'namespaces':                                (True,  True ),
    'namespace-declarations':                    (True,  True ),
    'normalize-characters':                      (False, CNORM),
    'schema-location':                           (None,  False),
    'schema-type':                               (None,  False),
    'split-cdata-sections':                      (True,  True ),
    'validate':                                  (False, False),
    'validate-if-schema':                        (False, False),
    'well-formed':                               (True,  True ),
    # LSParser-specific configuration
    'charset-overrides-xml-encoding':            (True,  True ),
    'disallow-doctype':                          (False, True ),
    'resource-resolver':                         (None,  True ),
    'supported-media-types-only':                (False, True),
    # LSSerializer-specific configuration
    'discard-default-content':                   (True,  True ),
    'format-pretty-print':                       (False, True ),
    'xml-declaration':                           (True,  True ),
    # Non-standard extensions
    'pxdom-assume-element-content':              (False, True ),
    'pxdom-resolve-resources':                   (True,  True ),
    'pxdom-html-compatible':                     (False, True ),
    # Switches to make required normalizeDocument operations optional
    'pxdom-normalize-text':                      (True,  True ),
    'pxdom-reset-identity':                      (True,  True ),
    'pxdom-update-entities':                     (True,  True ),
    'pxdom-preserve-base-uri':                   (True,  True ),
    'pxdom-examine-cdata-sections':              (True,  True ),
    # Normally used only inside an entity reference
    'pxdom-fix-unbound-namespaces':              (False, True )
  }

  _complexparameters= {
    'infoset': ((
        'cdata-sections', 'datatype-normalization', 'entities',
        'validate-if-schema'
      ), (
        'comments', 'element-content-whitespace', 'namespace-declarations',
        'namespaces', 'well-formed'
    )),
    'canonical-form': ((
        'cdata-sections', 'entities', 'format-pretty-print',
        'normalize-characters', 'discard-default-content', 'xml-declaration',
        'pxdom-html-compatible'
      ), (
        'element-content-whitespace', 'namespace-declarations', 'namespaces',
        'well-formed'
    ))
  }

  def __init__(self, copyFrom= None):
    """ Make a new DOMConfiguration mapping, using either default values or
        the current values of another DOMConfiguration, if using the
        copy-constructor feature.
    """
    DOMObject.__init__(self)
    self._parameters= {}
    for (name, (value, canSet)) in self._defaults.items():
      if copyFrom is not None:
        self._parameters[name]= copyFrom._parameters[name]
      else:
        self._parameters[name]= value

  def canSetParameter(self, name, value):
    name= string.lower(name)
    if name=='infoset':
      return True
    if self._parameters[name]==value:
      return True
    return self._defaults.get(name, (None, False))[1]

  def getParameter(self, name):
    name= string.lower(name)
    if self._complexparameters.has_key(name):
      for b in False, True:
        for p in self._complexparameters[name][b]:
          if self._parameters[p]!=b:
            return False
      if name=='infoset':
        return True
    if not self._parameters.has_key(name):
      raise NotFoundErr(self, None, name)
    return self._parameters[name]

  def setParameter(self, name, value):
    name= string.lower(name)
    if self._complexparameters.has_key(name):
      if value:
        for b in False, True:
          for p in self._complexparameters[name][b]:
            self._parameters[p]= b
      if name=='infoset':
        return
    if not self._defaults.has_key(name):
      raise NotFoundErr(self, None, name)
    if self._parameters[name]!=value:
      if not self._defaults[name][1]:
        raise NotSupportedErr(self, name)
      self._parameters[name]= value

  def _get_parameterNames(self):
    return DOMList(self._parameters.keys()+['infoset'])

  # Convenience method to do character normalization and/or check character
  # normalization on a string, depending on the parameters set on the config
  #
  def _cnorm(self, text, node, isParse= False):
    nc= self._parameters['normalize-characters']
    cn= self._parameters['check-character-normalization']
    if not nc and not cn or text=='' or not isinstance(text, Unicode):
      return text
    normal= unicodedata.normalize('NFC', text)
    if nc:
      text= normal
    if (not nc and text!=normal or cn and
      (unicodedata.combining(text[0])!=0 or text[0] in EXTRACOMPOSERS)
    ):
      self._handleError(CheckNormErr(node, isParse))
    return text

  # Convenience method for pxdom to callback the error-handler if one is set
  # on the DOMConfiguration, and raise an exception if the error or handler
  # says processing should not continue.
  #
  def _handleError(self, error):
    handler= self._parameters['error-handler']
    cont= None
    if handler is not None:
      cont= handler.handleError(error)
    if not error.allowContinue(cont):
      raise error


# LSParsers can't have well-formed set to False, and default entities and
# cdata-sections to False instead of True
#
class ParserConfiguration(DOMConfiguration):
  _defaults= dictadd(DOMConfiguration._defaults, {
    'well-formed': (True, False),
    'entities': (False, True),
    'cdata-sections': (False, True)
  })


# Predefined configurations for simple normalisation processes outside of the
# normalizeDocument method
#
DOMCONFIG_NONE= DOMConfiguration()
DOMCONFIG_NONE.setParameter('well-formed', False)
DOMCONFIG_NONE.setParameter('namespaces', False)
DOMCONFIG_NONE.setParameter('pxdom-normalize-text', False)
DOMCONFIG_NONE.setParameter('pxdom-update-entities', False)
DOMCONFIG_NONE.setParameter('pxdom-examine-cdata-sections', False)
DOMCONFIG_NONE.setParameter('pxdom-reset-identity', False)

DOMCONFIG_ENTS= DOMConfiguration(DOMCONFIG_NONE)
DOMCONFIG_ENTS.setParameter('pxdom-update-entities', True)
DOMCONFIG_ENTS_BIND= DOMConfiguration(DOMCONFIG_ENTS)
DOMCONFIG_ENTS_BIND.setParameter('pxdom-fix-unbound-namespaces', True)

DOMCONFIG_TEXT= DOMConfiguration(DOMCONFIG_NONE)
DOMCONFIG_TEXT.setParameter('pxdom-normalize-text', True)
if CNORM:
  DOMCONFIG_TEXT_CANONICAL= DOMConfiguration(DOMCONFIG_TEXT)
  DOMCONFIG_TEXT_CANONICAL.setParameter('normalize-characters', True)


class TypeInfo(DOMObject):
  """ Value type belonging to an Element or Attribute supplying information
      about its schema type. Since only DTDs are supported, this returns nulls
      except for Attribute typeNames, which might be grabbable from the
      internal subset's attlists.
  """
  [DERIVATION_RESTRICTION, DERIVATION_EXTENSION, DERIVATION_UNION,
  DERIVATION_LIST]= map(lambda n: 2**n, range(1, 5))

  def __init__(self, ownerNode):
    DOMObject.__init__(self, False)
    self._ownerNode= ownerNode
  def _get_typeNamespace(self):
    return self._getType()[0]
  def _get_typeName(self):
    return self._getType()[1]

  def _getType(self):
    if self._ownerNode.nodeType==Node.ATTRIBUTE_NODE:
      if (
        self._ownerNode.ownerElement is not None and
        self._ownerNode.ownerDocument is not None and
        self._ownerNode.ownerDocument.doctype is not None
      ):
        attlist= self._ownerNode.ownerDocument.doctype._attlists.getNamedItem(
          self._ownerNode.ownerElement.tagName
        )
        if attlist is not None:
          attdecl= attlist.declarations.getNamedItem(self._ownerNode.name)
          if attdecl is not None:
            return (
              DTNS, AttributeDeclaration.ATTR_NAMES[attdecl.attributeType]
            )
      if (self._ownerNode.name=='xml:id'):
        return (DTNS, 'ID')
    return (None, None)

  def isDerivedFrom(self, typeNamespaceArg, typeNameArg, derivationMethod):
    """ pxdom does not support XML Schema; for DTD schema this method always
        returns false.
    """
    return False


class DOMLocator(DOMObject):
  """ Value type used to return information on the source document and
      position of a node. Used in the standard DOM to locate DOMErrors; pxdom
      also allows any Node to be located this way.
  """
  def __init__(self, node= None, lineNumber= -1, columnNumber= -1, uri= None):
    self._relatedNode= node
    self._lineNumber= lineNumber
    self._columnNumber= columnNumber
    if uri is not None:
      self._uri= uri
    elif node is not None:
      self._uri= node._ownerDocument.documentURI
    else:
      self._uri= ''
  def _get_lineNumber(self):
    return self._lineNumber
  def _get_columnNumber(self):
    return self._columnNumber
  def _get_byteOffset(self):
    return -1
  def _get_utf16Offset(self):
    return -1
  def _get_relatedNode(self):
    return self._relatedNode
  def _get_uri(self):
    return self._uri


class UserDataHandler:
  """ Any Python object that supplies a 'handle' method can be bound to the
      DOM type UserDataHandler; this merely holds its static constants. NB.
      NODE_DELETED is never called because (as noted in the DOM Core spec)
      we have no idea when the object will be deleted by Python. No __del__
      handler is provided for this because it stops the garbage collector
      from freeing nodes with reference cycles (of which pxdom has many).
  """
  [NODE_CLONED, NODE_IMPORTED, NODE_DELETED, NODE_RENAMED, NODE_ADOPTED
  ]= range(1, 6)


# Core node classes
# ============================================================================

class Node(DOMObject):
  """ Abstract base class for all DOM Nodes.
  """
  [ELEMENT_NODE,ATTRIBUTE_NODE,TEXT_NODE,CDATA_SECTION_NODE,
  ENTITY_REFERENCE_NODE,ENTITY_NODE,PROCESSING_INSTRUCTION_NODE,COMMENT_NODE,
  DOCUMENT_NODE,DOCUMENT_TYPE_NODE,DOCUMENT_FRAGMENT_NODE,NOTATION_NODE
  ]= range(1,13)
  [ELEMENT_DECLARATION_NODE,ATTRIBUTE_DECLARATION_NODE,ATTRIBUTE_LIST_NODE
  ]= range(301, 304)
  [DOCUMENT_POSITION_DISCONNECTED,DOCUMENT_POSITION_PRECEDING,
  DOCUMENT_POSITION_FOLLOWING,DOCUMENT_POSITION_CONTAINS,
  DOCUMENT_POSITION_CONTAINED_BY,DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC
  ]= map(lambda n: 1<<n, range(6))

  # Node properties
  #
  def __init__(self,
    ownerDocument= None, namespaceURI= None, localName= None, prefix= None
  ):
    DOMObject.__init__(self)
    self._ownerDocument= ownerDocument
    self._containerNode= None
    self._namespaceURI= namespaceURI
    self._localName= localName
    self._prefix= prefix
    self._childNodes= ChildNodeList(self)
    self._attributes= None
    self._userData= {}
    self._childNodes.readonly= True
    self._sequence= 0
    self._row= -1
    self._col= -1
  def _cloneTo(self, node):
    node._ownerDocument= self._ownerDocument
    node._namespaceURI= self._namespaceURI
    node._localName= self._localName
    node._prefix= self._prefix
    node._row= self._row
    node._col= self._col

  def _get_ownerDocument(self): return self._ownerDocument
  def _get_parentNode(self): return self._containerNode
  def _get_nodeType(self): return None
  def _get_nodeName(self): return '#abstract-node'
  def _get_nodeValue(self): return None
  def _get_namespaceURI(self): return self._namespaceURI
  def _get_localName(self): return self._localName
  def _get_prefix(self): return self._prefix
  def _get_childNodes(self): return self._childNodes
  def _get_attributes(self): return self._attributes
  def _set_nodeValue(self, value):
    pass

  def __repr__(self):
    t= repr(self.nodeName)
    if len(t)>REPR_MAX_LEN:
      t= t[:REPR_MAX_LEN-2]+'...'
    if t[:1]=='u':
      t= t[1:]
    return '<pxdom.%s %s>' % (self.__class__.__name__, t)

  # Hierarchy access
  #
  def _get_firstChild(self):
    if self.childNodes.length>0:
      return self.childNodes.item(0)
    return None

  def _get_lastChild(self):
    if self.childNodes.length>0:
      return self._childNodes.item(self.childNodes.length-1)
    return None

  def _get_previousSibling(self):
    if self.parentNode is None:
      return None
    try:
      index= self.parentNode.childNodes._index(self)
    except ValueError:
      return None
    if index<1:
      return None
    return self.parentNode.childNodes.item(index-1)

  def _get_nextSibling(self):
    if self.parentNode is None:
      return None
    try:
      index= self.parentNode.childNodes._index(self)
    except ValueError:
      return None
    if index>=self.parentNode.childNodes.length-1:
      return None
    return self.parentNode.childNodes.item(index+1)

  def hasAttributes(self):
    if self._attributes is not None:
      if self._attributes.length>0:
        return True
    return False

  def hasChildNodes(self):
    return self._childNodes.length>0

  # Hierarchy alteration
  #
  _childTypes= (
    ELEMENT_NODE, COMMENT_NODE, ENTITY_REFERENCE_NODE,TEXT_NODE,
    CDATA_SECTION_NODE, PROCESSING_INSTRUCTION_NODE
  )

  def appendChild(self, newChild):
    if newChild is None:
      raise NotFoundErr(self, None, None)
    self._writeChild(newChild, None, False)
    return newChild
  def insertBefore(self, newChild, oldChild):
    if newChild is None:
      raise NotFoundErr(self, None, None)
    self._writeChild(newChild, oldChild, False)
    return newChild
  def replaceChild(self, newChild, refChild):
    if newChild is None or refChild is None:
      raise NotFoundErr(self, None, None)
    self._writeChild(newChild, refChild, True)
    return refChild
  def removeChild(self, oldChild):
    if oldChild is None:
      raise NotFoundErr(self, None, None)
    self._writeChild(None, oldChild, True)
    return oldChild

  def _writeChild(self, newChild, oldChild, removeOld):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'Child')
    if oldChild is not None and oldChild not in self._childNodes:
      raise NotFoundErr(self, oldChild.namespaceURI, oldChild.localName)
    if oldChild is newChild:
      return

    if newChild is not None:
      if newChild.ownerDocument not in (self._ownerDocument, None):
        raise WrongDocumentErr(newChild, self._ownerDocument)
      ancestor= self
      while ancestor is not None:
        if newChild is ancestor:
          raise HierarchyRequestErr(newChild, self)
        ancestor= ancestor.parentNode
      if newChild.nodeType==Node.DOCUMENT_FRAGMENT_NODE:
        newNodes= list(newChild._childNodes._list)
      else:
        newNodes= [newChild]
      for node in newNodes:
        if node.nodeType not in self._childTypes:
          raise HierarchyRequestErr(node, self)
        if node.parentNode is not None:
          node.parentNode.removeChild(node)

    self._childNodes.readonly= False
    if oldChild is None:
      index= self._childNodes.length
    else:
      index= self._childNodes._index(oldChild)
    if removeOld:
      oldChild._containerNode= None
      del self._childNodes._list[index]
    if newChild is not None:
      if newChild.ownerDocument is None:
        newChild._recurse(True, ownerDocument= self._ownerDocument)
      self._childNodes._insertseq(index, newNodes)
      for node in newNodes:
        node._containerNode= self
    self._childNodes.readonly= True
    self._changed()

  # DOM 3 UserData
  #
  def getUserData(self, key):
    return self._userData.get(key, (None, None))[0]

  def setUserData(self, key, data, handler):
    oldData= self.getUserData(key)
    self._userData[key]= (data, handler)
    return oldData

  def _callUserDataHandlers(self, operation, src, dst):
    """ Internal convenience method to dispatch callbacks to all registered
        UserDataHandlers.
    """
    for (key, (data, handler)) in self._userData.items():
      if handler is not None:
        handler.handle(operation, key, data, src, dst)

  def isSupported(self, feature, version):
    return _implementation.hasFeature(feature, version)

  def getFeature(self, feature, version):
    if _implementation.hasFeature(feature, version):
      return self
    return None

  def _get_pxdomLocation(self):
    return DOMLocator(self, self._row, self._col)
  def _setLocation(self, (row, col)):
    self._row= row
    self._col= col

  def _renameNode(self, namespaceURI, qualifiedName):
    raise NotSupportedErr(self, 'renameNode')

  def _changed(self):
    self._sequence= self._sequence+1
    if self._containerNode is not None:
      self._containerNode._changed()

  def _getDescendants(self, descendants):
    for child in self._childNodes:
      descendants.append(child)
      child._getDescendants(descendants)

  def _containsUnboundPrefix(self):
    if self._prefix is not None and self._namespaceURI is None:
      return True
    if self._attributes is not None:
      for attr in self._attributes:
        if attr._containsUnboundPrefix():
          return True
    for child in self._childNodes:
      if child._containsUnboundPrefix():
        return True
    return False


class NamedNode(Node):
  """ Base class for nodes who have specific names but no namespace
      capability (entity references and so on).
  """
  def __init__(self, ownerDocument= None, nodeName= None):
    Node.__init__(self, ownerDocument, None, None, None)
    if nodeName is not None:
      _checkName(nodeName)
    self._nodeName= nodeName
  def _cloneTo(self, node):
    Node._cloneTo(self, node)
    node._nodeName= self._nodeName
  def _get_nodeName(self):
    return self._nodeName


class NamedNodeNS(Node):
  """ Base class for nodes whose names are derived from their prefix and
      local name (Element and Attribute). In these nodes, namespaceURI may be
      stored internally as NONS, signifying a node created by Level 1 methods.
      In this case the node name is stored internally in localName, but
      trying to read either namespaceURI or localName will result in a null
      value as specified by DOM Level 2 Core.
  """
  def __init__(self,
    ownerDocument= None, namespaceURI= None, localName= None, prefix= None
  ):
    for name in (prefix, localName):
      if name is not None:
        _checkName(name, nc= namespaceURI is not NONS)
    Node.__init__(self, ownerDocument, namespaceURI, localName, prefix)
  def _get_nodeName(self):
    if self._namespaceURI is NONS or self._prefix is None:
      return self._localName
    return '%s:%s' % (self._prefix, self._localName)
  def _get_localName(self):
    if self._namespaceURI is NONS:
      return None
    return self._localName
  def _get_namespaceURI(self):
    if self._namespaceURI is NONS:
      return None
    return self._namespaceURI
  def _get_schemaTypeInfo(self):
    return TypeInfo(self)

  def _set_prefix(self, value):
    if value=='':
      value= None
    if value is not None:
      _checkName(value, True)
    if (value is not None and ':' in value or
      (self._namespaceURI in (None, NONS) and value is not None) or
      value=='xml' and self._namespaceURI!=XMNS or
      (value=='xmlns') != (self._namespaceURI==NSNS)
    ):
      raise NamespaceErr((value or '')+':'+self._localName,self._namespaceURI)
    self._prefix= value
    self._changed()

  def _renameNode(self, namespaceURI, qualifiedName):
    prefix, localName= _splitName(qualifiedName)
    if localName is None:
      _checkName(qualifiedName)
      if namespaceURI is not None:
        raise NamespaceErr(qualifiedName, namespaceURI)
      self._namespaceURI= NONS
      self._prefix= None
      self._localName= qualifiedName
    else:
      _checkName(localName, nc= True)
      if prefix is not None:
          _checkName(prefix, nc= True)
      if (
        namespaceURI is None and prefix is not None or
        prefix=='xml' and namespaceURI!=XMNS or
        (namespaceURI==NSNS) != ('xmlns' in (prefix, qualifiedName))
      ):
        raise NamespaceErr(qualifiedName, namespaceURI)
      self._namespaceURI= namespaceURI
      self._prefix= prefix
      self._localName= localName


class Document(Node):
  """ Implementation of DOM 3 Document interface.
  """
  def __init__(self):
    Node.__init__(self, self, None, None, None)
    self._xmlStandalone= False
    self._xmlVersion= '1.0'
    self._xmlEncoding= None
    self._inputEncoding= None
    self._documentURI= None
    self._strictErrorChecking= True
    self._domConfig= DOMConfiguration()
  def _cloneTo(self, node):
    Node._cloneTo(self, node)
    node._xmlStandalone= self._xmlStandalone
    node._xmlVersion= self._xmlVersion
    node._xmlEncoding= self._xmlEncoding
    node._inputEncoding= self._inputEncoding
    node._documentURI= self._documentURI
    node._strictErrorChecking= self._strictErrorChecking
    node._domConfig= DOMConfiguration(self._domConfig)

  def _get_nodeType(self):
    return Node.DOCUMENT_NODE
  def _get_nodeName(self):
    return '#document'
  def _get_ownerDocument(self):
    return None
  _childTypes= (
    Node.ELEMENT_NODE, Node.COMMENT_NODE, Node.PROCESSING_INSTRUCTION_NODE,
    Node.DOCUMENT_TYPE_NODE
  )

  def _get_implementation(self):
    return _implementation
  def _get_documentElement(self):
    for child in self._childNodes:
      if child.nodeType==Node.ELEMENT_NODE:
        return child
    return None
  def _get_doctype(self):
    for child in self._childNodes:
       if child.nodeType==Node.DOCUMENT_TYPE_NODE:
        return child
    return None
  def _get_domConfig(self):
    return self._domConfig

  def _get_xmlStandalone(self):
    return self._xmlStandalone
  def _set_xmlStandalone(self, value):
    self._xmlStandalone= value
  def _get_xmlVersion(self):
    return self._xmlVersion
  def _set_xmlVersion(self, value):
    if value not in ('1.0', '1.1'):
      raise NotSupportedErr(self, 'xmlVersion '+value)
    self._xmlVersion= value
  def _get_xmlEncoding(self):
    return self._xmlEncoding
  def _get_inputEncoding(self):
    return self._inputEncoding
  def _get_documentURI(self):
    return self._documentURI
  def _set_documentURI(self, value):
    self._documentURI= value
  def _get_strictErrorChecking(self):
    return self._strictErrorChecking
  def _set_strictErrorChecking(self, value):
    self._strictErrorChecking= value

  def createElement(self, tagName):
    element= Element(self, NONS, tagName, None)
    element._setDefaultAttributes()
    return element
  def createElementNS(self, namespaceURI, qualifiedName):
    if namespaceURI=='':
      namespaceURI= None
    _checkName(qualifiedName)
    prefix, localName= _splitName(qualifiedName)
    if (
      localName is None or
      namespaceURI is None and prefix is not None or
      prefix=='xml' and namespaceURI!=XMNS or
      (namespaceURI==NSNS) != ('xmlns' in (prefix, qualifiedName))
    ):
      raise NamespaceErr(qualifiedName, namespaceURI)
    element= Element(self, namespaceURI, localName, prefix)
    element._setDefaultAttributes()
    return element
  def createAttribute(self, name):
    return Attr(self, NONS, name, None, True)
  def createAttributeNS(self, namespaceURI, qualifiedName):
    if namespaceURI=='':
      namespaceURI= None
    _checkName(qualifiedName)
    prefix, localName= _splitName(qualifiedName)
    if (
      localName is None or
      namespaceURI is None and prefix is not None or
      prefix=='xml' and namespaceURI!=XMNS or
      (namespaceURI==NSNS) != ('xmlns' in (prefix, qualifiedName))
    ):
      raise NamespaceErr(qualifiedName, namespaceURI)
    return Attr(self, namespaceURI, localName, prefix, True)
  def createTextNode(self, data):
    node= Text(self)
    node.data= data
    return node
  def createComment(self, data):
    node= Comment(self)
    node.data= data
    return node
  def createCDATASection(self, data):
    node= CDATASection(self)
    node.data= data
    return node
  def createProcessingInstruction(self, target, data):
    node= ProcessingInstruction(self, target)
    node.data= data
    return node
  def createDocumentFragment(self):
    return DocumentFragment(self)
  def createEntityReference(self, name):
    node= EntityReference(self, name)
    node._normalize(DOMCONFIG_ENTS) # will also set readonly
    return node

  def getElementsByTagName(self, name):
    return NodeListByTagName(self, NONS, name)
  def getElementsByTagNameNS(self, namespaceURI, localName):
    if namespaceURI=='':
      namespaceURI= None
    return NodeListByTagName(self, namespaceURI, localName)
  def getElementById(self, elementId):
    return self._getElementById(self, elementId)
  def _getElementById(self, node, elementId):
    if node._attributes is not None:
      for attr in node._attributes:
        if attr.isId and attr.value==elementId:
          return node
    if Node.ELEMENT_NODE in node._childTypes:
      for child in node._childNodes:
        element= self._getElementById(child, elementId)
        if element is not None:
          return element
    return None

  def renameNode(self, n, namespaceURI, qualifiedName):
    if namespaceURI=='':
      namespaceURI= None
    if self._readonly:
      raise NoModificationAllowedErr(self, 'renameNode')
    if n._ownerDocument is not self:
      raise WrongDocumentErr(n, self)
    n._renameNode(namespaceURI, qualifiedName)
    n._changed()
    n._callUserDataHandlers(UserDataHandler.NODE_RENAMED, n, None)
    return n

  def _writeChild(self, newChild, oldChild, removeOld):
    """ Before allowing a child hierarchy change to go ahead, check that
        allowing it wouldn't leave the document containing two Element or two
        DocumentType children.
    """
    if newChild is not None:
      if newChild.nodeType==Node.DOCUMENT_FRAGMENT_NODE:
        newNodes= newChild._childNodes._list
      else:
        newNodes= [newChild]
      doctype= None
      documentElement= None
      afterNodes= list(self._childNodes._list)
      if removeOld and oldChild in afterNodes:
        afterNodes.remove(oldChild)
      for node in afterNodes+newNodes:
        if node.nodeType==Node.DOCUMENT_TYPE_NODE:
          if doctype not in (node, None):
            raise HierarchyRequestErr(node, self)
          doctype= node
        if node.nodeType==Node.ELEMENT_NODE:
          if documentElement not in (node, None):
            raise HierarchyRequestErr(node, self)
          documentElement= node
    Node._writeChild(self, newChild, oldChild, removeOld)

  def __repr__(self):
    if self.documentURI is not None:
      return '<pxdom.Document %s>' % repr(self.documentURI)
    else:
      return '<pxdom.Document>'


class DocumentFragment(Node):
  def __init__(self, ownerDocument= None):
    Node.__init__(self, ownerDocument, None, None, None)
  def _get_nodeType(self):
    return Node.DOCUMENT_FRAGMENT_NODE
  def _get_nodeName(self):
    return '#document-fragment'
  def __repr__(self):
    return '<pxdom.DocumentFragment>'


class Element(NamedNodeNS):
  """ Implementation of DOM 3 Element interface.
  """
  def __init__(self,
    ownerDocument= None, namespaceURI= None, localName= None, prefix= None
  ):
    NamedNodeNS.__init__(self, ownerDocument, namespaceURI, localName, prefix)
    self._attributes= AttrMap(self)
  def _get_nodeType(self):
    return Node.ELEMENT_NODE
  def _get_tagName(self):
    return self.nodeName

  def hasAttribute(self, name):
    return self._attributes.getNamedItem(name) is not None
  def getAttribute(self, name):
    attr= self._attributes.getNamedItem(name)
    if attr is None:
      return ''
    return attr.value
  def setAttribute(self, name, value):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'setAttribute')
    attr= self._attributes.getNamedItem(name)
    if attr is None:
      attr= Attr(self._ownerDocument, NONS, name, None, True)
      self._attributes.setNamedItem(attr)
    else:
      attr._specified= True
    attr.value= value
  def removeAttribute(self, name):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'removeAttribute')
    try:
      self._attributes.removeNamedItem(name)
    except NotFoundErr:
      pass
  def getAttributeNode(self, name):
    return self._attributes.getNamedItem(name)
  def setAttributeNode(self, node):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'setAttributeNode')
    return self._attributes.setNamedItem(node)
  def removeAttributeNode(self, node):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'removeAttributeNode')
    self._attributes._writeItem(node, None)
    return node

  def hasAttributeNS(self, namespaceURI, localName):
    return self._attributes.getNamedItemNS(namespaceURI,localName) is not None
  def getAttributeNS(self, namespaceURI, localName):
    attr= self._attributes.getNamedItemNS(namespaceURI, localName)
    if attr is None:
      return ''
    return attr.value
  def setAttributeNS(self, namespaceURI, qualifiedName, value):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'setAttributeNS')
    attr= self._attributes.getNamedItemNS(namespaceURI, qualifiedName)
    if attr is None:
      attr= self._ownerDocument.createAttributeNS(namespaceURI, qualifiedName)
      self._attributes.setNamedItemNS(attr)
    else:
      attr._specified= True
    attr.value= value
  def removeAttributeNS(self, namespaceURI, localName):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'removeAttributeNS')
    try:
      self._attributes.removeNamedItemNS(namespaceURI, localName)
    except NotFoundErr:
      pass
  def getAttributeNodeNS(self, namespaceURI, localName):
    return self._attributes.getNamedItemNS(namespaceURI, localName)
  def setAttributeNodeNS(self, node):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'setAttributeNodeNS')
    return self._attributes.setNamedItemNS(node)

  def getElementsByTagName(self, name):
    return NodeListByTagName(self, NONS, name)
  def getElementsByTagNameNS(self, namespaceURI, localName):
    if namespaceURI=='':
      namespaceURI= None
    return NodeListByTagName(self, namespaceURI, localName)

  def setIdAttribute(self, name, isId):
    node= self.getAttributeNode(name)
    if node is None:
      raise NotFoundErr(self._attributes, NONS, name)
    self.setIdAttributeNode(node, isId)
  def setIdAttributeNS(self, namespaceURI, localName, isId):
    node= self.getAttributeNodeNS(namespaceURI, localName)
    if node is None:
      raise NotFoundErr(self._attributes,namespaceURI, localName)
    self.setIdAttributeNode(node, isId)
  def setIdAttributeNode(self, idAttr, isId):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'setIdAttribute')
    if idAttr not in self._attributes._list:
      raise NotFoundErr(self._attributes, NONS, idAttr.name)
    idAttr._isId= isId

  def _renameNode(self, namespaceURI, qualifiedName):
    self._setDefaultAttributes(False)
    NamedNodeNS._renameNode(self, namespaceURI, qualifiedName)
    self._setDefaultAttributes()


  def _setDefaultAttributes(self, set= True):
    """ Set or remove an element's default attributes.
    """
    if self._ownerDocument is None or self._ownerDocument.doctype is None:
      return
    declarationList= self._ownerDocument.doctype._attlists.getNamedItem(
      self.tagName
    )
    if declarationList is not None:
      for declaration in declarationList.declarations:
        if declaration.defaultType in (
          AttributeDeclaration.DEFAULT_VALUE, AttributeDeclaration.FIXED_VALUE
        ):
          oldNode= self.getAttributeNode(declaration.nodeName)
          if set:
            if oldNode is None:
              declaration._createAttribute(self)
          elif oldNode is not None and not oldNode.specified:
            self.removeAttributeNode(oldNode)

class Attr(NamedNodeNS):
  def __init__(self,
    ownerDocument= None,
    namespaceURI= None, localName= None, prefix= None, specified= True
  ):
    NamedNodeNS.__init__(self, ownerDocument, namespaceURI, localName, prefix)
    self._specified= specified
    self._isId= False
  def _cloneTo(self, node):
    NamedNodeNS._cloneTo(self, node)
    node._isId= self._isId
    node._specified= self._specified

  def _get_nodeType(self):
    return Node.ATTRIBUTE_NODE
  def _get_nodeValue(self):
    return self.textContent
  def _get_name(self):
    return self.nodeName
  def _get_value(self):
    c= self._childNodes
    if c.length==1 and c[0].nodeType==Node.TEXT_NODE:
      value= c[0].data
    else:
      value= self.textContent
    if self.schemaTypeInfo.typeName in ('CDATA', None):
      return value
    else:
      return string.join(
        filter(lambda s: s!='', string.split(value, ' ')),
      ' ')
  def _set_nodeValue(self, value):
    self.value= value

  def _set_value(self, value):
    while self.firstChild is not None:
      self.removeChild(self.firstChild)
    if value!='':
      self.appendChild(self._ownerDocument.createTextNode(value))
    self._specified= True

  _childTypes= (Node.TEXT_NODE, Node.ENTITY_REFERENCE_NODE)
  def _get_parentNode(self):
    return None
  def _get_ownerElement(self):
    return self._containerNode
  def _get_schemaTypeInfo(self):
    return TypeInfo(self)

  def _get_specified(self):
    return self._specified
  def _get_isId(self):
    return self._isId or self.schemaTypeInfo.typeName=='ID'

  def _renameNode(self, namespaceURI, qualifiedName):
    owner= self._containerNode
    if owner is not None:
      owner.removeAttributeNode(self)
    NamedNodeNS._renameNode(self, namespaceURI, qualifiedName)
    if owner is not None:
      owner.setAttributeNodeNS(self)


class CharacterData(Node):
  def __init__(self, ownerDocument= None):
    Node.__init__(self, ownerDocument, None, None, None)
    self._data= ''
  def _cloneTo(self, node):
    Node._cloneTo(self, node)
    node._data= self._data

  _childTypes= ()
  def _get_nodeName(self):
    return '#character-data'
  def _get_nodeValue(self):
    return self.data
  def _set_nodeValue(self, value):
    self.data= value

  def _get_data(self):
    return self._data
  def _get_length(self):
    return len(self._data)
  def _set_data(self, value):
    self._data= value

  def substringData(self, offset, count):
    if offset<0 or count<0 or offset>len(self._data):
      raise IndexSizeErr(self._data, offset)
    return self._data[offset:offset+count]
  def appendData(self, arg):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'data')
    self._data= self._data+arg
  def insertData(self, offset, arg):
    self.replaceData(offset, 0, arg)
  def deleteData(self, offset, count):
    self.replaceData(offset, count, '')
  def replaceData(self, offset, count, arg):
    if self._readonly:
      raise NoModificationAllowedErr(self, 'data')
    if offset<0 or count<0 or offset>len(self._data):
      raise IndexSizeErr(self._data, offset)
    self._data= self._data[:offset]+arg+self._data[offset+count:]

  def __repr__(self):
    t= repr(self.nodeValue)
    if len(t)>REPR_MAX_LEN:
      t= t[:REPR_MAX_LEN-2]+'...'
    if t[:1]=='u':
      t= t[1:]
    return '<pxdom.%s %s>' % (self.__class__.__name__, t)


class Comment(CharacterData):
  def _get_nodeType(self):
    return Node.COMMENT_NODE
  def _get_nodeName(self):
    return '#comment'


class Text(CharacterData):
  def _get_nodeType(self):
    return Node.TEXT_NODE
  def _get_nodeName(self):
    return '#text'

  def _get_isElementContentWhitespace(self, config= None):
    """ Return whether a node is whitespace in an element whose content model
        is declared in the document type as element-only (not ANY). If we
        don't know the content model, guess either ANY (by default), or
        element-only (if the appropriate config parameter is set).
    """
    # Find the nearest element ancestor, as we might be in nested entity
    # references.
    #
    pn= self.parentNode
    while pn is not None:
      if pn.nodeType==Node.ENTITY_REFERENCE_NODE:
        pn= pn.parentNode
        continue
      if pn.nodeType==Node.ELEMENT_NODE:
        break
      return False
    else:
      return False

    # Get the DOMConfiguration to look at - usually the current Document's,
    # but an LS process might pass an alternative in. Get the default content
    # model from this.
    #
    if config is None:
      config= self._ownerDocument.domConfig
    contentType= ElementDeclaration.ANY_CONTENT
    if config.getParameter('pxdom-assume-element-content'):
      contentType= ElementDeclaration.ELEMENT_CONTENT

    # See if the element has a different content model declared. If the final
    # content model is not element-only, can't be ECW.
    #
    if self._ownerDocument.doctype is not None:
      eldecl= self._ownerDocument.doctype._elements.getNamedItem(pn.nodeName)
      if eldecl is not None:
        contentType= eldecl.contentType
    if contentType!=ElementDeclaration.ELEMENT_CONTENT:
      return False

    # Finally check the node does only have whitespaces. (For it not to do so
    # would be invalid, but still well-formed.)
    #
    for c in self._data:
      if not(c in WHITE or isinstance(c, Unicode) and c in WHITEU):
        return False
    return True

  def splitText(self, offset):
    """ Move character data following the offset point from this node to a new
        (next sibling) node of the same type (could be subclass CDATASection).
    """
    newNode= self.cloneNode(False)
    self.deleteData(offset, len(self._data)-offset)
    newNode.deleteData(0, offset)
    if self.parentNode is not None:
      self.parentNode.insertBefore(newNode, self.nextSibling)
    return newNode


class CDATASection(Text):
  def _get_nodeType(self):
    return Node.CDATA_SECTION_NODE
  def _get_nodeName(self):
    return '#cdata-section'


class ProcessingInstruction(NamedNode):
  def __init__(self, ownerDocument= None, target= None):
    NamedNode.__init__(self, ownerDocument, target)
    self._data= ''
  def _cloneTo(self, node):
    NamedNode._cloneTo(self, node)
    node._data= self._data

  _childTypes= ()
  def _get_nodeType(self):
    return Node.PROCESSING_INSTRUCTION_NODE
  def _get_nodeValue(self):
    return self.data
  def _set_nodeValue(self, value):
    self.data= value

  def _get_target(self):
    return self.nodeName
  def _get_data(self):
    return self._data
  def _set_data(self, value):
    self._data= value


class EntityReference(NamedNode):
  def __init__(self, ownerDocument= None, nodeName= None):
    NamedNode.__init__(self, ownerDocument, nodeName)
  def _get_nodeType(self):
    return Node.ENTITY_REFERENCE_NODE


class DocumentType(NamedNode):
  """ Implementation of DocumentType interface. Goes a little beyond the DOM 3
      interface in providing maps for attlists and entity declarations of the
      internal subset (attlists are required internally to support attribute
      defaulting).
  """
  def __init__(self,
    ownerDocument= None, name= None, publicId=None, systemId= None
  ):
    NamedNode.__init__(self, ownerDocument, name)
    self._publicId= publicId
    self._systemId= systemId
    self._internalSubset= None
    self._entities= NamedNodeMap(self, Node.ENTITY_NODE)
    self._notations= NamedNodeMap(self, Node.NOTATION_NODE)
    self._elements= NamedNodeMap(self, Node.ELEMENT_DECLARATION_NODE)
    self._attlists= NamedNodeMap(self, Node.ATTRIBUTE_LIST_NODE)
    self._processed= True
  def _cloneTo(self, node):
    NamedNode._cloneTo(self, node)
    node._publicId= self._publicId
    node._systemId= self._systemId
    node._internalSubset= self._internalSubset
  def _get_nodeType(self):
    return Node.DOCUMENT_TYPE_NODE

  def _get_name(self):
    return self.nodeName
  def _get_publicId(self):
    return self._publicId
  def _get_systemId(self):
    return self._systemId
  def _get_internalSubset(self):
    return self._internalSubset
  def _get_entities(self):
    return self._entities
  def _get_notations(self):
    return self._notations
  def _get_pxdomElements(self):
    return self._elements
  def _get_pxdomAttlists(self):
    return self._attlists
  def _get_pxdomProcessed(self):
    return self._processed
  def _set_internalSubset(self, value):
    self._internalSubset= value


class Entity(NamedNode):
  def __init__(self,
    ownerDocument= None, nodeName= None, publicId= None, systemId= None,
    notationName= None, baseURI= None
  ):
    NamedNode.__init__(self, ownerDocument, nodeName)
    self._publicId= publicId
    self._systemId= systemId
    self._notationName= notationName
    self._baseURI= baseURI
    self._xmlVersion= None
    self._xmlEncoding= None
    self._inputEncoding= None
    self._documentURI= None
    self._available= False
  def _cloneTo(self, node):
    NamedNode._cloneTo(self, node)
    node._publicId= self._publicId
    node._systemId= self._systemId
    node._notationName= self._notationName
    node._available= self._available
    node._xmlVersion= self._xmlVersion
    node._xmlEncoding= self._xmlEncoding
    node._inputEncoding= self._inputEncoding
    node._documentURI= self._documentURI
  def _get_nodeType(self):
    return Node.ENTITY_NODE
  def _get_parentNode(self):
    return None
  def _get_publicId(self):
    return self._publicId
  def _get_systemId(self):
    return self._systemId
  def _get_notationName(self):
    return self._notationName
  def _get_xmlVersion(self):
    return self._xmlVersion
  def _get_xmlEncoding(self):
    return self._xmlEncoding
  def _get_inputEncoding(self):
    return self._inputEncoding
  def _get_pxdomAvailable(self):
    return self._available
  def _get_pxdomDocumentURI(self):
    return self._documentURI

class Notation(NamedNode):
  def __init__(self, ownerDocument= None,
    nodeName= None, publicId= None, systemId= None, baseURI= None
  ):
    NamedNode.__init__(self, ownerDocument, nodeName)
    self._publicId= publicId
    self._systemId= systemId
    self._baseURI= baseURI
  def _cloneTo(self, node):
    NamedNode._cloneTo(self, node)
    node._publicId= self._publicId
    node._systemId= self._systemId
  def _get_nodeType(self):
    return Node.NOTATION_NODE
  def _get_parentNode(self):
    return None
  def _get_publicId(self):
    return self._publicId
  def _get_systemId(self):
    return self._systemId


# Extended pxdom node classes for doctype parts not currently modelled in the
# standard DOM
# ============================================================================

class ElementDeclaration(NamedNode):
  """ Node representing an <!ELEMENT> declaration in document type. Prescribed
      content is described by 'contentType' and 'elements', which is null for
      EMPTY and ANY content, or a ContentDeclaration for Mixed and element
      content.
  """
  [EMPTY_CONTENT, ANY_CONTENT, MIXED_CONTENT, ELEMENT_CONTENT
  ]= range(1, 5)
  def __init__(
    self, ownerDocument= None, nodeName= None,
    contentType= ANY_CONTENT, elements= None
  ):
    NamedNode.__init__(self, ownerDocument, nodeName)
    self._contentType= contentType
    self._elements= elements
  def _cloneTo(self, node):
    NamedNode._cloneTo(self, node)
    node._contentType= self._contentType
    node._elements= self._elements
  def _get_nodeType(self):
    return Node.ELEMENT_DECLARATION_NODE
  def _get_contentType(self):
    return self._contentType
  def _get_elements(self):
    return self._elements
  def _get_parentNode(self):
    return None


class ContentDeclaration(DOMList):
  """ A list representing part of the content model given in an <!ELEMENT>
      declaration. Apart from normal DOMList accessors, has flags specifying
      whether the group is optional, can be included more than once (or both),
      and whether it's a sequence or a choice. List items are element name
      strings or, in the case of element content, ContentDeclarations. In
      mixed content the initial #PCDATA is omitted and nesting is not used.
  """
  def __init__(self):
    DOMList.__init__(self)
    self._isOptional= False
    self._isMultiple= False
    self._isSequence= False
  def _get_isOptional(self):
    return self._isOptional
  def _get_isMultiple(self):
    return self._isMultiple
  def _get_isSequence(self):
    return self._isSequence
  def _set_isOptional(self, value):
    self._isOptional= value
  def _set_isMultiple(self, value):
    self._isMultiple= value
  def _set_isSequence(self, value):
    self._isSequence= value


class AttributeListDeclaration(NamedNode):
  def __init__(self, ownerDocument= None, nodeName= None):
    NamedNode.__init__(self, ownerDocument, nodeName)
    self._declarations= NamedNodeMap(self, Node.ATTRIBUTE_DECLARATION_NODE)
  def _cloneTo(self, node):
    NamedNode._cloneTo(self, node)
  def _get_nodeType(self):
    return Node.ATTRIBUTE_LIST_NODE
  def _get_parentNode(self):
    return None
  def _get_declarations(self):
    return self._declarations


class AttributeDeclaration(NamedNode):
  """ Node representing the declaration of a single attribute in an attlist.
      The type of attribute is made known, along with a list of values or
      notation names if the type is Enumeration or Notation. The defaulting
      is made known; if it is #FIXED or defaulted, the child Nodes of the
      declaration are the child nodes to be used by the attribute.
  """
  [REQUIRED_VALUE,IMPLIED_VALUE,DEFAULT_VALUE,FIXED_VALUE
  ]= range(1,5)
  [ID_ATTR,IDREF_ATTR,IDREFS_ATTR,ENTITY_ATTR,ENTITIES_ATTR,NMTOKEN_ATTR,
  NMTOKENS_ATTR,NOTATION_ATTR,CDATA_ATTR,ENUMERATION_ATTR
  ]= range(1,11)
  ATTR_NAMES= [ None,
    'ID', 'IDREF', 'IDREFS', 'ENTITY', 'ENTITIES', 'NMTOKEN', 'NMTOKENS',
    'NOTATION', 'CDATA', 'ENUMERATION'
  ]
  def __init__(self,
    ownerDocument= None, nodeName= None, attributeType= None,
    typeValues= None, defaultType= None
  ):
    NamedNode.__init__(self, ownerDocument, nodeName)
    self._attributeType= attributeType
    self._typeValues= typeValues
    self._defaultType= defaultType
  def _cloneTo(self, node):
    Node._cloneTo(self, node)
    node._attributeType= self.attributeType
    node._typeValues= self.typeValues
    node._defaultType= self.defaultType
  _childTypes= (Node.TEXT_NODE, Node.ENTITY_REFERENCE_NODE)
  def _get_nodeType(self):
    return Node.ATTRIBUTE_DECLARATION_NODE
  def _get_parentNode(self):
    return None
  def _get_attributeType(self):
    return self._attributeType
  def _get_typeValues(self):
    return self._typeValues
  def _get_defaultType(self):
    return self._defaultType
  def _get_nodeValue(self):
    return self.textContent

  def _createAttribute(self, element):
    prefix, localName= _splitName(self.nodeName)
    if localName is None:
      attr= element.ownerDocument.createAttribute(self.nodeName)
    else:
      if 'xmlns' in (prefix, self.nodeName):
        namespaceURI= NSNS
      elif prefix=='xml':
        namespaceURI= XMNS
      elif prefix is None:
        namespaceURI= None
      else:
        namespaceURI= element.lookupNamespaceURI(prefix)
      attr=element.ownerDocument.createAttribute(self.nodeName)
      attr._namespaceURI= namespaceURI
      attr._prefix, attr._localName= _splitName(self.nodeName)
    for child in self._childNodes:
      attr.appendChild(child.cloneNode(True))
    element.setAttributeNodeNS(attr)
    attr._specified= False


# Recursive node operations: clone, adopt, import (=clone+adopt) and, for
# entity-reference purporses, recursive-set-readonly.
# ============================================================================

def _Node__cloneNode(self, deep):
  """ Make an identical copy of a node, and optionally its descendants.
  """
  return self._recurse(deep, clone= True)

def _Attr__cloneNode(self, deep):
  """ Attributes become always specified if cloned directly, but not if cloned
      as part of an ancestor's deep clone.
  """
  r= self._recurse(deep, clone= True)
  r._specified= True
  return r

def _Document__cloneNode(self, deep):
  """ Make a copy of a document. This is 'implementation dependent' in the
      spec; we allow it and make a new document in response, copying any child
      nodes in importNode-style if deep is True, otherwise just making an
      empty documentElement.
  """
  doc= Document()
  self._cloneTo(doc)
  doc._ownerDocument= doc
  if deep:
    doc._childNodes.readonly= False
    for child in self._childNodes:
      r= child._recurse(True, clone= True, ownerDocument=doc)
      doc._childNodes._append(r)
      r._containerNode= doc
    doc._childNodes.readonly= True
  else:
    ns, name= self.documentElement.namespaceURI, self.documentElement.nodeName
    doc.appendChild(doc.createElementNS(ns, name))
  return doc

def _Document__adoptNode(self, source):
  """ Take over a node and its descendants from a potentially different
      document.
  """
  # Adoption of Documents and - for some reason - DocumentTypes is explicitly
  # disallowed by the spec.
  #
  if source.nodeType in (Node.DOCUMENT_NODE, Node.DOCUMENT_TYPE_NODE):
    raise NotSupportedErr(source, 'beAdopted')

  # Try to remove the node from wherever it is in the current document. If it
  # has a proper parent node this is easy; otherwise we have to guess which
  # of its owner's NamedNodeMaps it is part of. Note that removing an Entity
  # or Notation will generally fail as these maps are by default readonly.
  #
  if source.parentNode is not None:
    source.parentNode.removeChild(source)
  elif source._containerNode is not None:
    nodeMap= getattr(source._containerNode, {
      Node.ATTRIBUTE_NODE: 'attributes', Node.ENTITY_NODE: 'entities',
      Node.NOTATION_NODE: 'notations', Node. ATTRIBUTE_LIST_NODE: 'attlists',
      Node.ATTRIBUTE_DECLARATION_NODE: 'declarations',
      Node.ELEMENT_DECLARATION_NODE: 'elements'
    }[source.nodeType])
    nodeMap._writeItem(source, None)

  if source.nodeType==Node.ATTRIBUTE_NODE:
    source._specified= True
  dest= source._recurse(True, ownerDocument= self)
  dest._normalize(DOMCONFIG_ENTS)
  return dest


def _Document__importNode(self, importedNode, deep):
  """ Make a copy of a node from another pxdom document, optionally
      including all descendants.
  """
  if importedNode.nodeType in (Node.DOCUMENT_NODE, Node.DOCUMENT_TYPE_NODE):
    raise NotSupportedErr(importedNode, 'beImported')
  return importedNode._recurse(deep, clone= True, ownerDocument= self)


def _Node___recurse(self,
  deep, clone= False, ownerDocument= None, readonly= None
):
  """ Perform operations on a node and, if 'deep', all its descendants
      recursively.
  """
  if not clone:
    node= self
  else:
    node= self.__class__()
    self._cloneTo(node)

  if ownerDocument is not None:
    node._ownerDocument= ownerDocument
  self._recurseTo(node, clone, ownerDocument, readonly)

  if deep:
    node._childNodes.readonly= False
    for child in self._childNodes:
      r= child._recurse(deep, clone, ownerDocument, readonly)
      if clone:
        node._childNodes._append(r)
        r._containerNode= node
    node._childNodes.readonly= True

  if readonly is not None:
    node.readonly= readonly
    if node._attributes is not None:
      node._attributes.readonly= readonly

  if clone:
    if ownerDocument is not None:
      self._callUserDataHandlers(UserDataHandler.NODE_IMPORTED, self, node)
    else:
      self._callUserDataHandlers(UserDataHandler.NODE_CLONED, self, node)
  elif ownerDocument is not None:
    self._callUserDataHandlers(UserDataHandler.NODE_ADOPTED, self, None)
  return node

def _Attr___recurse(self,
  deep, clone= False, ownerDocument= None, readonly= None
):
  """ Recursive operations on attributes are always 'deep'. Import/adoption
      operations also make all attributes 'specified' and discard user-
      determined isIDness.
  """
  r= Node._recurse(self, True, clone, ownerDocument, readonly)
  if ownerDocument is not None:
    r._specified= True
    r._isId= False
  return r

def _EntityReference___recurse(self,
  deep, clone= False, ownerDocument= None, readonly= None
):
  """ When an entity reference is cloned/imported/adopted, its children are
      recreated from the matching entity rather than deeply recursed.
  """
  nontrivial= clone or ownerDocument is not None
  if nontrivial:
    deep= False
  r= Node._recurse(self, deep, clone, ownerDocument, readonly)
  if nontrivial:
    r._normalize(DOMCONFIG_ENTS_BIND)
  return r

def _Node___recurseTo(self, node, clone, ownerDocument, readonly):
  """ Fire off recursive operations to child nodes and attributes. May be
      extended by specific node types to send the ops to other nodes they
      contain (not in child lists).
  """
  pass

def _Element___recurseTo(self, node, clone, ownerDocument, readonly):
  """ Elements pass recursive operations to their attributes. Non-specified
      attributes may be ignored (import), removed (adopt) or made specified
      (clone).
  """
  for attr in list(self._attributes._list):
    if not attr.specified:
      if (ownerDocument is not None and not clone):
        self.removeAttributeNode(attr)
      if (ownerDocument is not None):
        continue
    r= attr._recurse(True, clone, ownerDocument, readonly)
    if clone:
      node._attributes._append(r)
      r._containerNode= node
  node._setDefaultAttributes()

def _DocumentType___recurseTo(self, node, clone, ownerDocument, readonly):
  """ Distribute recursive operations to the nodes in a doctype's extra
      NamedNodeMaps.
  """
  for mapName in ('_entities', '_notations', '_elements', '_attlists'):
    selfMap= getattr(self, mapName)
    nodeMap= getattr(node, mapName)
    mro= nodeMap._readonly
    if readonly is not None:
      mro= readonly
    nodeMap._readonly= False
    for namedNode in selfMap._list:
      r= namedNode._recurse(True, clone, ownerDocument, readonly)
      if clone:
        nodeMap._append(r)
    nodeMap._readonly= mro

def _AttributeListDeclaration____recurseTo(
  self, node, clone, ownerDocument, readonly
):
  """ Distribute recursive operations to attribute declaration nodes.
  """
  for declaration in self._declarations:
    r= declaration._recurse(True, clone, ownerDocument, readonly)
    if clone:
      node._declarations._append(r)

# XML Base (DOM 3 baseURI)
# ============================================================================

# Most nodes have null baseURIs. PIs always have the same baseURI as their
# parents. Document nodes at the top duplicate documentURI.
#
def _Node___get_baseURI(self):
  return None
def _ProcessingInstruction___get_baseURI(self):
  return self._getParentURI()
def  _Document___get_baseURI(self):
  return self._documentURI

# Check elements for xml:base attributes that might affect the baseURI.
# Absolute values can be returned directly; relative ones may be affected by
# baseURI of parent.
#
def _Element___get_baseURI(self):
  global bitch
  bitch= self
  base= self._attributes.getNamedItemNS(XMNS, 'base')
  if base is not None:
    uri= _encodeURI(base.value)
    if urlparse.urlparse(uri)[0]!='':
      return uri
    return urlparse.urljoin(self._getParentURI(), uri)
  return self._getParentURI()

# Declaration baseURIs are the URIs of the entity they're defined in, stored
# in a static internal property.
#
def _Entity___get_baseURI(self):
  return self._baseURI
def _Notation___get_baseURI(self):
  return self._baseURI

# Entity references have the same baseURI as their associated definition,
# regardless of where they are in the document.
#
def _EntityReference___get_baseURI(self):
  document= self._ownerDocument
  entity= None
  if document.doctype is not None:
    entity= document.doctype.entities.getNamedItem(self.nodeName)
  if entity is not None:
    return entity._get_baseURI()
  return None

# Elements and PIs can inherit baseURIs from their parents. Step up the DOM
# hierarchy to a parent or, if unattached, the Document itself. If the parent
# is an entity/reference it overrides the parent URI, but with the absolute
# URI of the document it was read from, which is not the same as its baseURI.
#
def _Node___getParentURI(self):
  parent= self._containerNode
  document= self._ownerDocument
  if parent is None:
    return document.documentURI
  entity= None
  if parent.nodeType==Node.ENTITY_NODE:
    entity= parent
  elif parent.nodeType==Node.ENTITY_REFERENCE_NODE:
    if document.doctype is not None:
      entity= document.doctype.entities.getNamedItem(parent.nodeName)
  if entity is not None and entity._documentURI is not None:
    return entity._documentURI
  return parent.baseURI


# DOM 3 namespace inspection
# ============================================================================

# Public lookup interface
#
def _Node__lookupNamespaceURI(self, prefix):
  return self._getNamespaces({}).get(prefix, None)

def _Node__lookupPrefix(self, namespaceURI):
  if namespaceURI in (None, ''):
    return None
  return self._getNamespaces({}, True).get(namespaceURI, None)

def _Node__isDefaultNamespace(self, namespaceURI):
  return self._getNamespaces({}).get(None, NONS)==namespaceURI


# Public lookup on Document node redirects to document root element
#
def _Document__lookupNamespaceURI(self, prefix):
  return self.documentElement.lookupNamespaceURI(prefix)

def _Document__lookupPrefix(self, namespaceURI):
  return self.documentElement.lookupPrefix(namespaceURI)

def _Document__isDefaultNamespace(self, namespaceURI):
  return self.documentElement.isDefaultNamespace(namespaceURI)


def _Node___getNamespaces(self, store, inverted= False):
  """ Construct a lookup dictionary of in-scope namespaces.
  """
  if self._containerNode is not None:
    self._containerNode._getNamespaces(store, inverted)
  return store

def _Element___getNamespaces(self, store, inverted= False, ignoreSelf= False):
  if self.localName is not None:
    if not ignoreSelf:
      key, value= self.prefix, self.namespaceURI
      if inverted:
        key, value= value, key
      if not store.has_key(key):
        store[key]= value
    for attr in self.attributes:
      if attr.namespaceURI==NSNS:
        key= [attr.localName, None][attr.prefix is None]
        value= attr.value or None
        if inverted:
          key, value= value, key
        if not store.has_key(key):
          store[key]= value
  return NamedNodeNS._getNamespaces(self, store, inverted)

 
# Namespace normalisation
#
def _Element___getFixups(self, nsframe):
  """ For an element with a given in-scope-namespace lookup, return a list of
      new namespace declaration attributes to add, and a list of prefix
      changes to existing attributes. Note the nsframe of in-scope namespaces
      will be updated in-place.
  """
  # Ensure element's prefix maps to element's namespaceURI
  #
  create, reprefix= [], []
  if self._namespaceURI not in (NONS, nsframe.get(self.prefix, None)):
    create.append((self._prefix, self._namespaceURI))
    nsframe[self._prefix]= self._namespaceURI

  # Fix up each attribute
  #
  for attr in self._attributes:
    if attr._namespaceURI in (NONS, NSNS, XMNS):
      continue
    namespaceURI= None
    if attr._prefix is not None:
      namespaceURI= nsframe.get(attr._prefix, None)

    # If attribute prefix does not map to its namespace, will need new prefix.
    # Find one that matches the namespace
    #
    if attr._namespaceURI!=namespaceURI:
      prefix= None
      if attr._namespaceURI is not None:
        try:
          ix= nsframe.values().index(attr._namespaceURI)
          prefix= nsframe.keys()[ix]
        except ValueError:
          prefix= None

        # No match, have to create a new namespace declaration for it. Use
        # existing prefix if we can, else make up a new arbitrary name
        #
        if prefix is None:
          prefix= attr._prefix
          nsSuffix= 0
          while prefix is None or nsframe.has_key(prefix):
            nsSuffix= nsSuffix+1
            prefix= 'NS'+str(nsSuffix)
        create.append((prefix, attr._namespaceURI))
        nsframe[prefix]= attr._namespaceURI

      reprefix.append((attr, prefix))
  return create, reprefix


# DOM 3 node comparison
# ============================================================================

def _Node__isSameNode(self, other):
  return self is other

def _Node__isEqualNode(self, other):
  """ Check two nodes have the same properties and content.
  """
  ps=('nodeType','nodeName','localName','namespaceURI','prefix','nodeValue')
  for property in ps:
    if getattr(self, property)!=getattr(other, property):
      return False
  if (self.attributes is None)!=(other.attributes is None):
    return False
  if self.attributes is not None:
    if not self.attributes._isEqualMap(other.attributes):
      return False
  if self.childNodes.length!=other.childNodes.length:
    return False
  for index in range(self.childNodes.length):
    if not self.childNodes.item(index).isEqualNode(
      other.childNodes.item(index)
    ):
      return False
  return True

def _DocumentType__isEqualNode(self, other):
  """ Doctype nodes have additional properties that must match to be equal.
      The extension attlists and elements maps are not checked for equality as
      they are not part of the standard.
  """
  if not NamedNode.isEqualNode(self, other):
    return False
  ps= ('publicId', 'systemId', 'internalSubset')
  for property in ps:
    if getattr(self, property)!=getattr(other, property):
      return False
  if not self._entities._isEqualMap(other._entities):
    return False
  if not self._notations._isEqualMap(other._notations):
    return False
  return True


def _NamedNodeMap___isEqualMap(self, other):
  """ Test whether two maps have equal contents, though possibly in a
      different order.
  """
  if other is None:
    return False
  if len(self._list)!=len(other._list):
    return False
  for selfItem in self._list:
    for otherItem in other._list:
      if selfItem.isEqualNode(otherItem):
        break
    else:
      return False
  return True


def _canonicalAttrSort(self, other):
  """ Compare Attrs in terms of xmlnsness, namespaceURI and localName, for
      canonical-form ordering purposes.
  """
  if (self.namespaceURI==NSNS) and (other.namespaceURI==NSNS):
    if (self.prefix is None) != (other.prefix is None):
      return 1-(self.prefix is None)*2
    return cmp(self.localName, other.localName)
  if (self.namespaceURI==NSNS) != (other.namespaceURI==NSNS):
    return 1-(self.namespaceURI==NSNS)*2
  return cmp(
    (self.namespaceURI, self.localName),
    (other.namespaceURI, other.localName)
  )


def _Node__compareDocumentPosition(self, other):
  """ Get flags describing the document position of one node relative to
      another.
  """
  if other is self:
    return 0
  containers= []
  container= self
  while container is not None:
    containers.append(container)
    container= container._containerNode
  container= other
  other_determining= other
  while container is not None:
    if container in containers:
      index= containers.index(container)
      if index<1:
        index= 1
      self_determining= containers[index-1]
      break
    other_determining= container
    container= container._containerNode
  else:
    if id(other)>id(self):
      return (
        Node.DOCUMENT_POSITION_DISCONNECTED +
        Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC +
        Node.DOCUMENT_POSITION_FOLLOWING
      )
    return (
      Node.DOCUMENT_POSITION_DISCONNECTED +
      Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC +
      Node.DOCUMENT_POSITION_PRECEDING
    )
  if container is other:
    return (
      Node.DOCUMENT_POSITION_CONTAINS + Node.DOCUMENT_POSITION_PRECEDING
    )
  if container is self:
    return (
      Node.DOCUMENT_POSITION_CONTAINED_BY + Node.DOCUMENT_POSITION_FOLLOWING
    )
  if (other_determining in container._childNodes):
    if (self_determining in container._childNodes):
      if (
        container._childNodes._index(other_determining) >
        container._childNodes._index(self_determining)
      ):
        return Node.DOCUMENT_POSITION_FOLLOWING
      return Node.DOCUMENT_POSITION_PRECEDING
    return Node.DOCUMENT_POSITION_FOLLOWING
  if (self_determining in container._childNodes):
    return Node.DOCUMENT_POSITION_PRECEDING
  if other_determining.nodeType!=self_determining.nodeType:
    if other_determining.nodeType>self_determining.nodeType:
      return Node.DOCUMENT_POSITION_FOLLOWING
    return Node.DOCUMENT_POSITION_PRECEDING
  if self_determining.nodeType==Node.ATTRIBUTE_NODE:
    attrs= container.attributes
    if attrs._index(other_determining)>attrs._index(other_determining):
      return (
        Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC +
        Node.DOCUMENT_POSITION_FOLLOWING
      )
    return (
      Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC +
      Node.DOCUMENT_POSITION_PRECEDING
    )
  if id(other_determining)>id(self_determining):
    return (
      Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC +
      Node.DOCUMENT_POSITION_FOLLOWING
    )
  return (
    Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC +
    Node.DOCUMENT_POSITION_PRECEDING
  )


# DOM 3 textual content access
# ============================================================================

def _Node___set_textContent(self, value):
  if self.readonly:
    raise NoModificationAllowedErr(self, 'textContent')
  if (Node.TEXT_NODE not in self._childTypes):
    raise HierarchyRequestErr(self, Text())
  while self._childNodes.length>0:
    self.removeChild(self.firstChild)
  text= Text(self._ownerDocument)
  text.data= value
  self.appendChild(text)

def _CharacterData___set_textContent(self, value):
  if self.readonly:
    raise NoModificationAllowedErr(self, 'textContent')
  self.data= value
def _ProcessingInstruction___set_textContent(self, value):
  if self.readonly:
    raise NoModificationAllowedErr(self, 'textContent')
  self.data= value

def _Document___set_textContent(self, value):
  return
def _DocumentType___set_textContent(self, value):
  return
def _Notation___set_textContent(self, value):
  return


def _Node___get_textContent(self):
  value= ''
  for index in range(self._childNodes.length):
    child= self._childNodes.item(index)
    if child.nodeType not in [
      Node.COMMENT_NODE, Node.PROCESSING_INSTRUCTION_NODE
    ]:
      value= value+child.textContent
  return value

def _Attr___get_textContent(self):
  value= ''
  for index in range(self._childNodes.length):
    child= self._childNodes.item(index)
    if child.nodeType==Node.TEXT_NODE:
      value= value+child.textContent
    elif child.nodeType==Node.ENTITY_REFERENCE_NODE:
      value= value+r(r(r(child.textContent, '\n',' '), '\t',' '),'\r',' ')
  return value

def _CharacterData___get_textContent(self):
  return self.data

def _ProcessingInstruction___get_textContent(self):
  return self.data

def _Text___get_textContent(self):
  if self.isElementContentWhitespace:
    return ''
  return CharacterData._get_textContent(self)

def _Document___get_textContent(self):
  return None
def _DocumentType___get_textContent(self):
  return None
def _Notation___get_textContent(self):
  return None


def _Text___get_wholeText(self):
  value= ''
  for node in self._getLogicallyAdjacentTextNodes():
    value= value+node.data
  return value

def _Text__replaceWholeText(self, value):
  replacement= None
  haveReplaced= False
  if self._readonly and value!='':
    replacement= self._ownerDocument.createTextNode(value)
  nodes= self._getLogicallyAdjacentTextNodes()
  removables= []
  for node in nodes:
    if node is self and not (value=='' or self._readonly):
      continue
    while node.parentNode is not None:
      if not node.parentNode.readonly:
        if node not in removables:
          removables.append(node)
        break
      node= node.parentNode
  for removable in removables:
    descendants= []
    removable._getDescendants(descendants)
    for node in descendants:
      if node.nodeType!=Node.ENTITY_REFERENCE_NODE and node not in nodes:
        raise NoModificationAllowedErr(node.parentNode, 'removeChild')
    if replacement is not None and not haveReplaced:
      removable.parentNode.replaceChild(replacement, removable)
    else:
      removable.parentNode.removeChild(removable)
  if replacement is not None:
    return replacement
  if value=='':
    return None
  self._data= value
  return self

def _Text___getLogicallyAdjacentTextNodes(self):
  ok= (Node.TEXT_NODE, Node.CDATA_SECTION_NODE, Node.ENTITY_REFERENCE_NODE)
  node= self
  goin= False
  while True:
    previous= None
    if goin:
      previous= node.lastChild
    if previous is None:
      previous= node.previousSibling
      goin= True
    if previous is None:
      previous= node.parentNode
      goin= False
      if previous is None or previous.nodeType!=Node.ENTITY_REFERENCE_NODE:
        break
    if previous.nodeType not in ok:
      break
    node= previous
  nodes= []
  goin= True
  while True:
    if node.nodeType!=Node.ENTITY_REFERENCE_NODE:
      nodes.append(node)
    next= None
    if goin:
      next= node.firstChild
    if next is None:
      next= node.nextSibling
      goin= True
    if next is None:
      next= node.parentNode
      goin= False
      if next is None or next.nodeType!=Node.ENTITY_REFERENCE_NODE:
        break
    if next.nodeType not in ok:
      break
    node= next
  return nodes


# Normalization and canonicalization
# ============================================================================

def _Node__normalize(self):
  """ Perform text node concatenation and, if enabled in the domConfig,
      character normalisation. Hack around the fact that apparently check-
      character-normalization shouldn't do anything here.
  """
  if self._readonly:
    raise NoModificationAllowedErr(self, 'normalize')
  if self._ownerDocument.domConfig.getParameter('normalize-characters'):
    self._normalize(DOMCONFIG_TEXT_CANONICAL)
  else:
    self._normalize(DOMCONFIG_TEXT)
  self._changed()


def _Document__normalizeDocument(self):
  """ Perform all normalisations specified by the domConfig across the whole
      document.
  """
  # normalizeDocument doesn't return exceptions, even NO_MOD. Although there
  # is no reason a Document should ever be readonly anyway.
  #
  if self._readonly:
    return

  # Recursively normalise the document. Throw away DOMErrors, this method does
  # not return them other than to the error-handler.
  #
  try:
    self._normalize(self.domConfig)
  except DOMException:
    pass

  # In canonical-form mode, chuck away the doctype at the end
  #
  if self.domConfig.getParameter('canonical-form'):
    if self.doctype is not None:
      self.removeChild(self.doctype)
  self._changed()


def _Node___normalize(self, config):
  """ Normalisation back-end. Perform a number of different normalisations on
      child nodes, in the appropriate order.
  """
  p= config.getParameter

  # If entities are off, do a first pass replacing available entities with
  # their contents. Their contents may include other entity references so keep
  # doing this until there are no more available entity children. When
  # replacing try to preserve the baseURI.
  #
  if not p('entities'):
    doctype=self._ownerDocument.doctype
    if doctype is not None:
      while True:
        for child in self._childNodes._list[:]:
          if child.nodeType==Node.ENTITY_REFERENCE_NODE:
            entity= doctype.entities.getNamedItem(child.nodeName)
            if entity is not None and entity._available:
              child._normalize(DOMCONFIG_ENTS_BIND)
              child._recurse(True, readonly= False)
              for grandchild in child.childNodes._list[:]:
                if grandchild.nodeType not in self._childTypes:
                  config._handleError(InvalidEntityForAttrErr(child, False))
                else:
                  baseURI= grandchild.baseURI
                  self.insertBefore(grandchild, child)
                  if config.getParameter('pxdom-preserve-base-uri'):
                    if baseURI!=grandchild.baseURI:
                      if grandchild.nodeType==Node.ELEMENT_NODE:
                        baseAttr= self._ownerDocument.createAttributeNS(
                          XMNS, 'xml:base'
                        )
                        baseAttr.value= baseURI
                        specified= grandchild.hasAttributeNS(XMNS, 'xml:base')
                        grandchild.setAttributeNodeNS(baseAttr)
                        baseAttr._specified= specified
                      else:
                        config._handleError(
                          PIBaseURILostErr(grandchild, False)
                        )
              self.removeChild(child)
              break
        else:
          break

  # Main loop. Begin by normalising the children themselves
  #
  for child in self._childNodes._list[:]:
    child._normalize(config)

    # Remove comments if unwanted
    #
    if child.nodeType==Node.COMMENT_NODE and not p('comments'):
      self.removeChild(child)
      continue

    # If unwanted, change CDATA sections to text nodes
    #
    if child.nodeType==Node.CDATA_SECTION_NODE and not p('cdata-sections'):
      newChild= self.ownerDocument.createTextNode(child.data)
      self.replaceChild(newChild, child)
      child= newChild

    # Concatenate adjacent text nodes, remove ignorable whitespace
    #
    if child.nodeType==Node.TEXT_NODE:
      if (
        p('pxdom-normalize-text') and child.data=='' or not
        p('element-content-whitespace') and child.isElementContentWhitespace
      ):
        self.removeChild(child)
        continue
      elif p('pxdom-normalize-text'):
        previous= child.previousSibling
        if previous is not None and previous.nodeType==Node.TEXT_NODE:
          previous.data= config._cnorm(previous.data+child.data, child)
          self.removeChild(child)

    # Split CDATA sections including string ']]>'
    #
    if (
      child.nodeType==Node.CDATA_SECTION_NODE
      and p('pxdom-examine-cdata-sections')
      and string.find(child.data, ']]>')!=-1
    ):
      if not config.getParameter('split-cdata-sections'):
        config._handleError(WfInvalidCharacterErr(child))
      else:
        datas= string.split(child.data, ']]>')
        child.data= datas[0]+']]'
        refChild= child.nextSibling
        for data in datas[1:-1]:
          newChild= self._ownerDocument.createCDATASection('>'+data+']]')
          self.insertBefore(newChild, refChild)
        newChild= self._ownerDocument.createCDATASection('>'+datas[-1])
        self.insertBefore(newChild, refChild)
        config._handleError(CdataSectionsSplittedErr(child))


  # Some forms of normalisation might require NodeListByTagNames recalculated.
  # Don't bother bounce up to parents as with the normal _changed() method, as
  # they will already know about the normalization, but make sure our own
  # change count is updated.
  #
  self._sequence= self._sequence+1


def _NamedNode___normalize(self, config):
  """ Normalisations required by nodes with name values. Additionally to
      general node normalisations, character-normalise the node name. This
      could theoretically lead to two nodes of the same name in a
      NamedNodeMap; the DOM spec doesn't seem to say what to do in this
      situation, so for the moment we let it be.
  """
  self._nodeName= config._cnorm(self._nodeName, self)
  Node._normalize(self, config)


def _NamedNodeNS___normalize(self, config):
  """ Additional normalisations required by namespace-aware nodes.
  """
  # Character-normalise name parts.
  #
  self._localName= config._cnorm(self._localName, self)
  if self._prefix is not None:
    self._prefix= config._cnorm(self._prefix, self)

  # Generate a warning (but with ERROR severity due to spec) if Level 1 nodes
  # are encountered.
  #
  if config.getParameter('namespaces') and self._namespaceURI is NONS:
    config._handleError(Level1NodeErr(self))

  Node._normalize(self, config)

  # If we're in an entity reference and have a null namespace (that might be
  # unbound) see if we've inherited an in-scope namespace from outside that
  # might bind it up
  #
  if config.getParameter('pxdom-fix-unbound-namespaces'):
    if self._namespaceURI is None and self._containerNode is not None:
      self._namespaceURI= self._containerNode._getNamespaces(
        {}
      ).get(self._prefix, None)


def _Element___normalize(self, config):
  """ Normalisations required by elements. Additionally to general named node
      normalisations, may need to add namespace declarations make it
      namespace-well-formed, and normalise or remove some attributes.
  """
  # Normalise element and each attribute name, reordered if in canonical-form
  # mode
  #
  NamedNodeNS._normalize(self, config)
  for attr in self._attributes:
    attr._normalize(config)
  if config.getParameter('canonical-form'):
    self._attributes._list.sort(_canonicalAttrSort)

  # Fix element, attributes namespaces in place
  #
  if config.getParameter('namespaces'):
    create, reprefix= self._getFixups(
      self._getNamespaces(FIXEDNS.copy(), ignoreSelf= True)
    )
    for prefix, namespaceURI in create:
      name= 'xmlns'
      if prefix is not None:
        name= name+':'+prefix
      self.setAttributeNS(NSNS, name, namespaceURI or '')
    for attr, prefix in reprefix:
      attr._prefix= prefix

  # Remove any namespace declarations that are redundant in canonical-form
  # mode, or all of them if namespace-declarations is off
  #
  if config.getParameter('canonical-form'):
    nsframe= {}
    if self._containerNode is not None:
      nsframe= self._containerNode._getNamespaces({})
  for attr in self.attributes._list[:]:
    if attr.namespaceURI==NSNS:
      if not config.getParameter('namespace-declarations'):
        self.removeAttributeNode(attr)
      elif config.getParameter('canonical-form'):
        prefix= [attr.localName, None][attr.prefix is None]
        namespaceURI= nsframe.get(prefix, None) or ''
        if attr.value==namespaceURI:
          self.removeAttributeNode(attr)


def _Attr___normalize(self, config):
  """ Normalisation for attributes. User-determined isIDness is discarded.
  """
  NamedNodeNS._normalize(self, config)
  if config.getParameter('pxdom-reset-identity'):
    self._isId= False

def _CharacterData___normalize(self, config):
  """ Normalisation for text-based nodes. Only need to normalise characters.
  """
  Node._normalize(self, config)
  self._data= config._cnorm(self._data, self)


def _Comment___normalize(self, config):
  """ Normalisations for comment nodes. Only need to check well-formedness.
  """
  CharacterData._normalize(self, config)
  if config.getParameter('well-formed') and (
    self._data[-1:]=='-' or string.find(self._data, '--')!=-1
  ):
    config._handleError(WfInvalidCharacterErr(self))


def _ProcessingInstruction___normalize(self, config):
  """ Normalisations for PI nodes. Only need to check well-formedness.
  """
  NamedNode._normalize(self, config)
  if config.getParameter('well-formed') and string.find(self._data, '?>')!=-1:
    config._handleError(WfInvalidCharacterErr(self))


def _EntityReference___normalize(self, config):
  """ Normalisations for entity references. Remove any child nodes and replace
      them with up-to-date replacement nodes from the doctype's entity list.
  """
  if config.getParameter('pxdom-update-entities'):
    self._readonly= False

    while self._childNodes.length>0:
      self.removeChild(self._childNodes.item(0))
    if self._ownerDocument.doctype:
      entity=self._ownerDocument.doctype.entities.getNamedItem(self.nodeName)
      if entity is not None:
        for child in entity.childNodes:
          clone= child._recurse(True, clone= True, readonly= False)
          self.appendChild(clone)

    bind= config.getParameter('pxdom-fix-unbound-namespaces')
    config.setParameter('pxdom-fix-unbound-namespaces', True)
    try:
      NamedNode._normalize(self, config)
    finally:
      config.setParameter('pxdom-fix-unbound-namespaces', bind)
    self._recurse(True, readonly= True)


# DOM 3 LS Load features
# ============================================================================

def _DOMImplementation__createLSParser(
  self, mode= DOMImplementation.MODE_SYNCHRONOUS, schemaType= None
):
  if mode!=DOMImplementation.MODE_SYNCHRONOUS:
    raise NotSupportedErr(self, 'createLSParser.mode')
  if schemaType is not None and schemaType!=DTNS:
    raise NotSupportedErr(self, 'createLSParser.schemaType')
  return LSParser()

def _DOMImplementation__createLSInput(self):
  return LSInput()


class LSInput(DOMObject):
  """ Abstraction of possible source of serialised XML data. Can have
      character or byte stream objects attached (in Python terms, objects
      having a read() method that returns Unicode or narrow strings,
      respectively), plain string input (either type) or a resolvable Id/URI
      to get data from.
  """
  def __init__(self):
    DOMObject.__init__(self)
    self._characterStream= None
    self._byteStream= None
    self._stringData= None
    self._systemId= None
    self._publicId= None
    self._baseURI= None
    self._encoding= None
    self._certifiedText= False

  def _get_characterStream(self): return self._characterStream
  def _get_byteStream(self): return self._byteStream
  def _get_stringData(self): return self._stringData
  def _get_systemId(self): return self._systemId
  def _get_publicId(self): return self._publicId
  def _get_baseURI(self): return self._baseURI
  def _get_encoding(self): return self._encoding
  def _get_certifiedText(self): return self._certifiedText

  def _set_characterStream(self, value):
    self._characterStream= value
  def _set_byteStream(self, value):
    self._byteStream= value
  def _set_stringData(self, value):
    self._stringData= value
  def _set_systemId(self, value):
    self._systemId= value
  def _set_publicId(self, value):
    self._publicId= value
  def _set_baseURI(self, value):
    self._baseURI= value
  def _set_encoding(self, value):
    self._encoding= value
  def _set_certifiedText(self, value):
    self._certifiedText= value


class InputBuffer:
  """ Wrapper for reading from an LSInput (or user object implementing this
      interface) or other resource with possible encoding change if an XML
      declaration is encountered.
  """
  def __init__(self, input, offset, config, isDocument):
    self.config= config
    charsetCertain= config.getParameter('charset-overrides-xml-encoding')
    checkMT= isDocument and config.getParameter('supported-media-types-only')

    # URI of input source
    #
    self.uri= None
    if input.systemId is not None:
      self.uri= _encodeURI(input.systemId)
      if input.baseURI is not None:
        self.uri= urlparse.urljoin(input.baseURI, self.uri)

    # Hold encoding currently in use, and bytes or chars read from the input
    # source. If both bytes and chars are non-None, we are uncertain that the
    # encoding will prove to be correct; an XML declaration could override it.
    #
    self.bytes= None
    self.encoding= None
    self.chars= None

    # Whilst parsing, keep pointer into character data. Keep an offset into
    # data from uri so that we can know what the 'real' index was when dealing
    # with internal entity values. Store pointer to parent buffer as a hack
    # for parameter entity parsing.
    #
    self.offset= offset
    self.parent= None
    self.reset()

    # Read data from the input source as characters or bytes. If we come out
    # of this with bytes and an encoding, that encoding's certainty is
    # dependent on the charset-overrides-xml-encoding parameter.
    #
    if input.characterStream is not None:
      self.chars= input.characterStream.read()
      if unicode is not None:
        self.encoding= 'utf-16'
      else:
        self.encoding= 'utf-8'
    elif input.byteStream is not None:
      self.bytes= input.byteStream.read()
    elif input.stringData not in (None, ''):

      # Hack. Allow string data to be a blank string by hiding it in a tuple.
      #
      if isinstance(input.stringData, type(())):
        data= input.stringData[0]
      else:
        data= input.stringData

      # Treat stringData as bytes if it's a narrow string, or chars in Unicode
      #
      if isinstance(data, Unicode):
        self.chars= data
        self.encoding= 'utf-16'
      else:
        self.bytes= data
        self.encoding= 'utf-8'

    elif self.uri is not None:
      try:
        stream= urllib.urlopen(self.uri)
      except IOError, e:
        self.config._handleError(IOErrorErr(e))
      if checkMT:
        contentType= stream.info().type
        if contentType not in XMLTYPES and contentType[-4:]!='+xml':
          self.config._handleError(UnsupportedMediaTypeErr(None))
      self.encoding= stream.info().getparam('charset')
      self.bytes= stream.read()
      stream.close()
    else:
      self.config._handleError(NoInputErr(None))

    # If we have bytes, attempt to convert them to characters. If we are
    # certain of the encoding, drop the original bytes on the floor.
    #
    if self.chars is None:
      certain= self.encoding is not None and charsetCertain
      if self.encoding is None:
        if self.bytes[:2] in ('\xff\xfe', '\xfe\xff'):
          self.encoding= 'utf-16'
        else:
          self.encoding= 'utf-8'
      self.decode(True)
      if certain:
        self.bytes= None
    else:
      self.decode(False)

  def setEncoding(self, xmlEncoding= None):
    """ Finished checking for encoding in possible XML declaration. If we were
        uncertain about the character encoding to use before, update the chars
        from the bytes again with the new encoding.
    """
    if self.bytes is not None:
      if xmlEncoding is not None and xmlEncoding!=self.encoding:
        self.encoding= xmlEncoding
        self.decode(True)
      self.bytes= None
    for ch in NOTCHAR:
      if ch in self.chars:
        self.index= string.find(self.chars, ch)
        self.config._handleError(ParseErr(self,'Invalid chr '+hex(ord(ch))))
    if isinstance(self.chars, Unicode):
      for ch in NOTCHARU:
        if ch in self.chars:
          self.index= string.find(self.chars, ch)
          self.config._handleError(ParseErr(self,'Invalid chr '+hex(ord(ch))))

  def decode(self, fromBytes= True):
    """ Take input from chars or bytes (decoding through encoding property),
        send result with normalised newlines and no BOM.
    """
    if fromBytes:
      if unicode is not None:
        try:
          codec= codecs.lookup(self.encoding)
        except LookupError:
          self.config._handleError(UnsupportedEncodingErr(None))
        if codec==codecs.lookup('utf-16'):
          if self.bytes[:2]=='\xff\xfe':
            self.encoding= 'utf-16le'
          elif self.bytes[:2]=='\xfe\xff':
            self.encoding= 'utf-16be'
        self.chars= unicode(self.bytes, self.encoding, 'replace')
      else:
        self.chars= self.bytes
    for ls in LS:
      self.chars= r(self.chars, ls, '\n')
    if isinstance(self.chars, Unicode):
      for ls in LSU:
        self.chars= r(self.chars, ls, '\n')
      if self.chars[:1]==unichr(0xFEFF):
        self.chars= self.chars[1:]

  def getLocation(self):
    """ Return (line, column) position corresponding to the current index.
    """
    # Get (line, col) position relative to start of entity, caching the
    # calculated location for the given index to reduce the amount of
    # string to search through next time
    #
    line= string.count(self.chars, '\n', self.cIndex, self.index)
    if line==0:
      line= self.cLocation[0]
      col= self.cLocation[1]+self.index-self.cIndex
    else:
      line= self.cLocation[0]+line
      col= self.index-string.rfind(self.chars, '\n', self.cIndex,self.index)-1
    self.cLocation= (line, col)
    self.cIndex= self.index

    # Return the relative-index added to the entity offset. (1-based)
    #
    if line==0:
      col= col+self.offset[1]
    else:
      col= col+1
    line= line+self.offset[0]
    return (line, col)

  def reset(self):
    """ Set the index point back to the beginning of this buffer in order to
        allow it to be read again.
    """
    self.index= 0
    self.cIndex= 0
    self.cLocation= (0, 0)

  def swallow(self):
    """ Throw away any previously-parsed part of this buffer.
    """
    if self.index!=0:
      self.offset= self.getLocation()
      self.chars= self.chars[self.index:]
      self.index= 0


# Convenience method for parsers to get an InputBuffer object for a resource
# with possible resourceResolver redirection.
#
def _DOMConfiguration___resolveResource(self, publicId, systemId, baseURI):
  if not self._parameters['pxdom-resolve-resources']:
    return None
  input= None
  if self._parameters['resource-resolver'] is not None:
    input= self._parameters['resource-resolver'].resolveResource(
      DTNS, None, publicId, systemId, baseURI
    )
  if input is None:
    input= LSInput()
    input.publicId= publicId
    input.systemId= systemId
    input.baseURI= baseURI
  return InputBuffer(input, (1, 1), self, False)


class NodeFilter(DOMObject):
  [SHOW_ELEMENT,SHOW_ATTRIBUTE,SHOW_TEXT,SHOW_CDATA_SECTION,
  SHOW_ENTITY_REFERENCE,SHOW_ENTITY,SHOW_PROCESSING_INSTRUCTION,SHOW_COMMENT,
  SHOW_DOCUMENT,SHOW_DOCUMENT_TYPE,SHOW_DOCUMENT_FRAGMENT,SHOW_NOTATION
  ]= map(lambda n: 2**n, range(1, 13))
  SHOW_ALL= 2**13-1;
  [FILTER_ACCEPT,FILTER_REJECT,FILTER_SKIP,FILTER_INTERRUPT
  ]= range(1, 5)
  def __init__(whatToShow):
    DOMObject.__init__()
    self._whatToShow= whatToShow
  def _get_whatToShow(self):
    return self._whatToShow
  def _set_whatToShow(self, value):
    self._whatToShow= value
  def acceptNode(self, n):
    return NodeFilter.FILTER_ACCEPT


def _acceptNode(filter, node, startElement= False):
  """ Convenience function to pass a node to a filter, if it exists and wants
      to see it, and return the result or the right default. 
  """
  if filter is None:
    return NodeFilter.FILTER_ACCEPT
  if node.nodeType>=32 or (filter.whatToShow & (1<<(node.nodeType-1)) == 0):
    return NodeFilter.FILTER_ACCEPT
  if startElement:
    accepted= filter.startElement(node)
  else:
    accepted= filter.acceptNode(node)
  if accepted==NodeFilter.FILTER_INTERRUPT:
    raise LSFilterInterrupt()
  return accepted

class LSFilterInterrupt(Exception):
  """ Exception raised when an LSFilter has returned a FILTER_INTERRUPT, 
      causing the process to stop and return to the caller.
  """
  pass


class LSParser(DOMObject):
  """ DOM Level 3 LS  XML parser.
  """
  [ACTION_APPEND_AS_CHILDREN,ACTION_REPLACE_CHILDREN,ACTION_INSERT_BEFORE,
  ACTION_INSERT_AFTER,ACTION_REPLACE
  ]= range(1, 6)
  _CHARCHUNK= 1024
  def __init__(self, config= None):
    DOMObject.__init__(self)
    if config is None:
      config= ParserConfiguration()
    self._domConfig= config
    self._filter= None
  def _get_domConfig(self):
    return self._domConfig
  def _get_filter(self):
    return self._filter
  def _set_filter(self, value):
    self._filter= value
  def _get_async(self):
    return False
  def _get_busy(self):
    return False
  def abort(self):
    pass

  # Standard public parse interfaces
  #
  def parse(self, input):
    """ Parse complete document from an InputSource.
    """
    document= Document()
    self.pxdomParseBefore(input, document, None)
    return document

  def parseURI(self, uri):
    """ Parse complete document from a URI.
    """
    input= LSInput()
    input.systemId= uri
    document= Document()
    self.pxdomParseBefore(input, document, None)
    return document
    
  def parseWithContext(self, input, contextArg, action):
    """ Parse a fragment of document (pxdom interprets this as being the
        same as an external parsed entity) into a point described by a node
        and relationship.
    """
    # Find the node that will contain the new content, either the contextArg
    # or, for certain actions, its parent. Check it can receive content.
    #
    pnode= [contextArg.parentNode, contextArg][action in (
      LSParser.ACTION_APPEND_AS_CHILDREN, LSParser.ACTION_REPLACE_CHILDREN
    )]
    if pnode is None or pnode.nodeType not in (
      Node.DOCUMENT_NODE, Node.ELEMENT_NODE, Node.DOCUMENT_FRAGMENT_NODE
    ):
      raise NotSupportedErr([pnode,contextArg][pnode is None], 'context')

    # Determine where to put the newly-parsed nodes
    #
    if action==LSParser.ACTION_INSERT_BEFORE:
      parentNode= contextArg.parentNode
      nextSibling= contextArg
    elif action in [LSParser.ACTION_INSERT_AFTER, LSParser.ACTION_REPLACE]:
      parentNode= contextArg.parentNode
      nextSibling= contextArg.nextSibling
    elif action in [
      LSParser.ACTION_REPLACE_CHILDREN, LSParser.ACTION_APPEND_AS_CHILDREN
    ]:
      parentNode= contextArg
      nextSibling= None

    if action==LSParser.ACTION_REPLACE:
      parentNode.removeChild(contextArg)
    elif action==LSParser.ACTION_REPLACE_CHILDREN:
      while contextArg.childNodes.length>0:
        contextArg.removeChild(contextArg.childNodes.item(0))

    if nextSibling is None:
      previousSibling= parentNode.lastChild
    else:
      previousSibling= nextSibling.previousSibling

    # Mysteriously, according to spec, whitespace removal shouldn't work in
    # parseWithContext.
    #
    ws= self._domConfig.getParameter('element-content-whitespace')
    self._domConfig.setParameter('element-content-whitespace', True)
    try:
      self.pxdomParseBefore(input, parentNode, nextSibling)
    finally:
      self._domConfig.setParameter('element-content-whitespace', ws)

    # Return the first generated node (if there was one)
    #
    if previousSibling is None:
      refChild= parentNode.firstChild
    else:
      refChild= previousSibling.nextSibling
    if refChild not in [None, nextSibling]:
      return refChild
    return None


  def pxdomParseBefore(self, input, parentNode, refChild):
    """ Main parse entry point, allowing content to be parsed into a node
        specified in the same way as with node.insertBefore. (A slightly saner
        interface than the parseWithContext call uses.)
    """
    p= self._domConfig.getParameter

    # Entity state: lookups for parameter and general entities, pointing to
    # InputBuffers for each; list of entity nesting depth to detect circular
    # entity definitions.
    #
    self._parameterEntities= self._generalEntities= {}
    self._entityNest= []

    # If the input source is certified, ignore normalisation options
    #
    if input.certifiedText:
      nc= p('normalize-characters')
      ccn= p('check-character-normalization')
      self._domConfig.setParameter('normalize-characters', False)
      self._domConfig.setParameter('check-character-normalization', False)
    try:

      # Dispatch into internal node parsing interfaces
      #
      namespaces= parentNode._getNamespaces(FIXEDNS.copy())
      self._queue= ''
      try:
        self._buffer= InputBuffer(input, (1, 1), self._domConfig, True)
        self._inEntity= False
        self._Declaration(parentNode)
        self._Content(parentNode, refChild, namespaces)
        self._end()

      except LSFilterInterrupt:
        pass
    finally:
      self._buffer= None
      del self._parameterEntities
      del self._generalEntities
      del self._entityNest
      if input.certifiedText:
        self._domConfig.setParameter('normalize-characters', nc)
        self._domConfig.setParameter('check-character-normalization', ccn)


  # Parsing utility functions
  #
  def _push(self, text):
    self._queue= self._queue+text

  def _flush(self, parentNode, refChild):
    """ Write any text that has been read and queued into a new Text node.
    """
    if self._queue=='':
      return None
    text= self._domConfig._cnorm(self._queue, parentNode, True)
    self._queue= ''
    node= parentNode._ownerDocument.createTextNode(text)
    node._setLocation(self._buffer.getLocation())

    # If whitespace removal is required, must put the node in place to test
    # whether it is element content whitespace.
    #
    if not self._domConfig.getParameter('element-content-whitespace'):
      node._containerNode= parentNode
      if node._get_isElementContentWhitespace(self._domConfig):
        return
      node._containerNode= None

    self._insert(node, parentNode, refChild)

  def _insert(self, newNode, parentNode, refChild, preserve= False):
    """ Utility method to insert a node into a specific place in the document
        and then find out the filter's point of view if any, possibly removing
        or skipping it afterwards. If skipping, optionally try to preserve
        the base URI. If the node is already in the parent we assume it's in
        the right place and don't try to re-insert it, for performance.
    """
    if newNode._containerNode is not parentNode:
      parentNode.insertBefore(newNode, refChild)
    accepted= _acceptNode(self._filter, newNode)
    if accepted==NodeFilter.FILTER_REJECT:
      parentNode.removeChild(newNode)
    elif accepted==NodeFilter.FILTER_SKIP:
      for grandchild in newNode.childNodes._list[:]:
        baseURI= grandchild.baseURI
        parentNode.insertBefore(grandchild, newNode)
        if grandchild.baseURI!=baseURI and preserve:
          if grandchild.nodeType==Node.ELEMENT_NODE:
            baseAttr= self._ownerDocument.createAttributeNS(XMNS, 'xml:base')
            baseAttr.value= baseURI
            specified= grandchild.hasAttributeNS(XMNS, 'xml:base')
            grandchild.setAttributeNodeNS(baseAttr)
            baseAttr._specified= specified
          else:
            self._domConfig._handleError(PIBaseURILostErr(grandchild, True))
      parentNode.removeChild(newNode)

  def _error(self, message):
    self._domConfig._handleError(ParseErr(self._buffer, message))


  # Low-level parsing
  #
  def _match(self, chars, stepPast= True):
    """ Check if a string is the next thing in the queue. Optionally and by
        default step over it if it is.
    """
    index= self._buffer.index
    matches= self._buffer.chars[index:index+len(chars)]==chars
    if stepPast and matches:
      self._buffer.index= index+len(chars)
    return matches

  def _upto(self, chars):
    """ Read text up until the next occurance of one of a range of characters
        or strings.
    """
    end= len(self._buffer.chars)
    for s in chars:
      index= string.find(self._buffer.chars, s, self._buffer.index, end)
      if index!=-1 and index<end:
        end= index
    try:
      return self._buffer.chars[self._buffer.index:end]
    finally:
      self._buffer.index= end

  def _white(self, required= True):
    """ Parse white space.
    """
    start= self._buffer.index
    l= len(self._buffer.chars)
    while True:
      index= self._buffer.index
      if index>=l:
        break
      c= self._buffer.chars[index]
      if not (c in WHITE or isinstance(c, Unicode) and c in WHITEU):
        break
      self._buffer.index= index+1
    if required and index<=start:
      self._error('Expected whitespace')

  def _quote(self):
    """ Parse and return a quote character.
    """
    for quote in '"\'':
      if self._match(quote):
        return quote
    self._error('Expected open-quote')

  def _equal(self):
    """ Parse an equals sign with possible white space.
    """
    self._white(False)
    if not self._match('='):
      self._error('Expected equals sign')
    self._white(False)

  def _literal(self):
    """ Parse and return a quoted literal value.
    """
    quote= self._quote()
    value= self._upto(quote)
    if not self._match(quote):
      self._error('Quoted literal left open')
    return self._domConfig._cnorm(value, None, True)

  def _hex(self):
    """ Parse and return a hexadecimal number.
    """
    start= self._buffer.index
    l= len(self._buffer.chars)
    while True:
      index= self._buffer.index
      if index>=l or self._buffer.chars[index] not in HEX:
        break
      self._buffer.index= index+1
    if index==start:
      self._error('Expected hex number')
    return eval('0x'+str(self._buffer.chars[start:self._buffer.index]))

  def _dec(self):
    """ Parse and return a decimal number.
    """
    start= self._buffer.index
    l= len(self._buffer.chars)
    while True:
      index= self._buffer.index
      if index>=l or self._buffer.chars[index] not in HEX:
        break
      self._buffer.index= index+1
    if index==start:
      self._error('Expected decimal number')
    return int(self._buffer.chars[start:self._buffer.index])

  def _name(self):
    """ Parse and return an XML name.
    """
    index= self._buffer.index
    if index>=len(self._buffer.chars):
      self._error('Expected name')
    char= self._buffer.chars[index]
    if char in NOTFIRST:
      self._error('Expected name')
    if isinstance(char, Unicode):
      for c0, c1 in NOTFIRSTU:
        if ord(char)>=c0 and ord(char)<c1:
          self._error('Expected name')
    return self._nmtokens()
  def _nmtokens(self):
    start= self._buffer.index
    l= len(self._buffer.chars)
    while True:
      index= self._buffer.index
      if index>=l:
        break
      char= self._buffer.chars[index]
      if char in NOTNAME or char in NOTCHAR:
        break
      if isinstance(char, Unicode):
        if char in NOTCHARU:
          break
        bad= False
        for c0, c1 in NOTNAMEU:
          if ord(char)>=c0 and ord(char)<c1:
            bad= True
        if bad:
          break
      self._buffer.index= index+1
    if index==start:
      self._error('Expected name tokens')
    return self._domConfig._cnorm(self._buffer.chars[start:index], None, True)

  def _end(self):
    """ Check there is no more input to come.
    """
    if self._buffer.index<len(self._buffer.chars):
      self._error('Expected end of input')


  # Main structure-parsing methods
  #
  def _Declaration(self, parentNode):
    """ Parse the XML/text declaration, if present.
    """
    xmlVersion= None
    xmlEncoding= None
    xmlStandalone= None

    if self._match('<?xml'):
      self._white()
      if not self._match('version'):
        self._error('Expected version declaration')
      self._equal()
      xmlVersion= self._literal()
      self._white(False)
      if self._match('encoding'):
        self._equal()
        xmlEncoding= self._literal()
        self._white(False)
      if self._match('standalone'):
        self._equal()
        standalone= self._literal()
        if standalone not in ('no', 'yes'):
          self._error('Expected yes or no')
        xmlStandalone= (standalone=='yes')
        self._white(False)
      if not self._match('?>'):
        self._error('Expected ?> to close XML/text declaration')

    # Let the buffer know we are now sure about the encoding. This might
    # change the encoding used to read the file.
    #
    self._buffer.setEncoding(xmlEncoding)

    # If the parentNode is a document or external parsed entity, can record
    # the above details.
    #
    if parentNode is not None:
      if parentNode.nodeType in (Node.DOCUMENT_NODE, Node.ENTITY_NODE):
        parentNode._xmlVersion= xmlVersion or '1.0'
        parentNode._xmlEncoding= xmlEncoding
        parentNode._inputEncoding= self._buffer.encoding
        parentNode._documentURI= self._buffer.uri
      if parentNode.nodeType==Node.DOCUMENT_NODE:
        parentNode._xmlStandalone= xmlStandalone


  def _Content(self, parentNode, refChild, namespaces,
    inheritURI= None, flush= True
  ):
    """ Parse general content. Optionally, fix up base URI (for when entity
        references are off)
    """
    isDoc= parentNode.nodeType==Node.DOCUMENT_NODE
    while True:

      # Get text up until next markup character and push it onto the text
      # queue.
      #
      text= self._upto('<&')
      if text!='':
        if isDoc:
          for c in text:
            if not (c in WHITE or isinstance(c, Unicode) and c in WHITEU):
              self._error('Text not allowed at document level')
        else:
          self._push(text)
      if self._match('</', stepPast= False):
        break

      # Work out what kind of markup it is and dispatch to relevant parser.
      #
      if self._match('<'): 
        if self._match('?'):
          self._PI(parentNode, refChild, namespaces, inheritURI)
        elif self._match('!'):
          if self._match('['):
            if self._match('CDATA['):
              if isDoc:
                self._error('CDATA not allowed at document level')
              self._CDATA(parentNode, refChild, namespaces)
            else:
              self._error('Expected \'CDATA[...]\'')
          elif self._match('DOCTYPE'):
            if (not isDoc or
              parentNode.documentElement is not None or
              parentNode._ownerDocument.doctype is not None
            ):
              self._error('Doctype in unexpected position')
            if self._domConfig.getParameter('disallow-doctype'):
              self._domConfig._handleError(DoctypeNotAllowedErr(None))
            self._Doctype(parentNode, refChild, namespaces)
          elif self._match('--'):
            self._Comment(parentNode, refChild, namespaces)
          else:
            self._error('Expected comment, doctype or CDATA')
        else:
          if isDoc and parentNode.documentElement is not None:
            self._error('Only one root element is allowed')
          self._Element(parentNode, refChild, namespaces, inheritURI)

      elif self._match('&'):
        if isDoc:
          self._error('References are not allowed at document level')
        if self._match('#'):
          self._Charref(parentNode, refChild, namespaces)
        else:
          self._Entref(parentNode, refChild, namespaces)

      else:
        break
    if flush:
      self._flush(parentNode, refChild)


  def _Element(self, parentNode, refChild, namespaces, baseURI= None):
    """ Parse complete element.
    """
    self._flush(parentNode, refChild)
    doc= parentNode._ownerDocument
    newspaces= namespaces.copy()
    ns= self._domConfig.getParameter('namespaces')

    # Create element. Check for any default attributes that might introduce
    # namespaces into scope.
    #
    element= doc.createElement(self._name())
    element._setLocation(self._buffer.getLocation())
    if ns:
      for attr in element.attributes:
        if attr.namespaceURI==NSNS:
          newspaces[
            [attr.localName, None][attr.prefix is None]
          ]= attr.value or None

    # First pass (parse) over attributes.
    #
    empty= False
    while True:
      if self._match('>'):
        break
      if self._match('/>'):
        empty= True
        break
      self._white()
      if self._match('>'):
        break
      if self._match('/>'):
        empty= True
        break

      name= self._name()
      attr= element.getAttributeNode(name)
      if attr is not None and attr.specified:
        self._error('Duplicate attribute %s' % name)

      # Add attribute node with parsed value. Take note of added namespace
      # declarations for next pass.
      #
      attr= doc.createAttribute(name)
      attr._setLocation(self._buffer.getLocation())
      self._equal()
      self._Attr(attr, None, namespaces)

      prefix, localName= _splitName(name)
      if ns and 'xmlns' in (name, prefix):
        newspaces[[localName, None][prefix is None]]= attr.value or None
      if not ns or self._domConfig.getParameter('namespace-declarations'):
        element.setAttributeNode(attr)

      if attr.schemaTypeInfo.typeName=='ID':
        element.setIdAttributeNode(attr, True)

    # If namespace parsing, use the new in-scope namespaces to work out the
    # namespaceURIs of the element and its attributes, converting them up to
    # level 2 nodes.
    #
    if ns:
      prefix, localName= _splitName(element.nodeName)
      if localName is None:
        self._error('Element %s not namespace-well-formed' % element.nodeName)
      element._prefix= prefix
      element._localName= localName
      if newspaces.has_key(prefix):
        element._namespaceURI= newspaces[prefix]
      else:
        element._namespaceURI= None
        if prefix is not None:
          self._domConfig._handleError(UnboundNSErr(element, self._inEntity))

      for attr in element.attributes:
        prefix, localName= _splitName(attr.nodeName)
        if localName is None:
          self._error('Attr %s not namespace-well-formed' % attr.nodeName)
        attr._prefix= prefix
        attr._localName= localName
        if prefix is None and localName=='xmlns':
          attr._namespaceURI= NSNS
        elif prefix is None:
          attr._namespaceURI= None
        elif newspaces.has_key(prefix):
          attr._namespaceURI= newspaces[prefix]
        else:
          attr._namespaceURI= None
          self._domConfig._handleError(UnboundNSErr(element, self._inEntity))

    # Add element to document. If we are inheriting a skipped baseURI and the
    # element doesn't completely override it with an absolute URI, fix it up
    #
    parentNode.insertBefore(element, refChild)
    if baseURI is not None:
      if element.hasAttributeNS(XMNS, 'base'):
        baseURI= urlparse.urljoin(baseURI,element.getAttributeNS(XMNS,'base'))
      if element.baseURI!=baseURI:
        baseAttr=parentNode._ownerDocument.createAttributeNS(XMNS, 'xml:base')
        baseAttr.value= baseURI
        specified= element.hasAttributeNS(XMNS, 'xml:base')
        element.setAttributeNodeNS(baseAttr)
        baseAttr._specified= specified

    # Check the filter's initial opinion of whether it wants the element.
    # Always accept the document root element
    #
    if parentNode.nodeType==Node.DOCUMENT_NODE:
      accepted= NodeFilter.FILTER_ACCEPT
    else:
      accepted= _acceptNode(self._filter, element, startElement= True)
    if accepted!=NodeFilter.FILTER_ACCEPT:
        parentNode.removeChild(element)
    if not empty:

      # If the filter doesn't want it at all, must parse the contents without
      # informing the filter and throw the lot away. Otherwise parse content
      # as either child or replacement. Note! If a NodeFilter rejects or skips
      # an element node, it is possible that the DOM tree could become
      # un-normalised - that is, there may be two text nodes next to each
      # other. Unfortunately there is no logical way to avoid this without
      # altering previous text nodes that have already been sent to the
      # NodeFilter, which is probably a worse thing.
      #
      if accepted==NodeFilter.FILTER_REJECT:
        filter= self._filter
        self._filter= None
        try:
          self._Content(element, None, newspaces)
        finally:
          self._filter= filter
      elif accepted==NodeFilter.FILTER_SKIP:
        self._Content(parentNode, refChild, newspaces, baseURI, flush= False)
      elif accepted==NodeFilter.FILTER_ACCEPT:
        self._Content(element, None, newspaces)

    # Parse end-tag
    #
    if not empty:
      if not self._match('</'+element.tagName):
        self._error('Expected %s end-tag' % element.tagName)
      self._white(False)
      if not self._match('>'):
        self._error('Expected close angle bracket')

    # After parsing all the content into the element, ask the filter again
    # what to do with it. _insert is used; it doesn't matter that the node is
    # already inserted as the second insert will have no effect.
    #
    if accepted==NodeFilter.FILTER_ACCEPT:
      if parentNode.nodeType==Node.DOCUMENT_NODE:
        parentNode.insertBefore(element, refChild)
      else:
        self._insert(element, parentNode, refChild,
          self._domConfig.getParameter('pxdom-preserve-base-uri')
        )


  def _Attr(self, parentNode, refChild, namespaces):
    """ Parse quoted attribute value. Turn non-escaped whitespace characters
        into actual spaces as XML mysteriously requires.
    """
    # Attr children are never passed to filter.
    #
    filter= self._filter
    self._filter= None
    quote= self._quote()

    while True:
      text= self._upto(quote+'<&')
      if text!='':
        for white in WHITE:
          text= r(text, white, ' ')
        if isinstance(text, Unicode):
          for white in WHITEU:
            text= r(text, white, ' ')
        self._push(text)
      if self._match('&'):
        if self._match('#'):
          self._Charref(parentNode, refChild, namespaces)
        else:
          self._Entref(parentNode, refChild, namespaces)
      elif self._match('<'):
        self._error('Expected close quote, found < in attribute value')
      else:
        break
    if not self._match(quote):
      self._error('Attr value left open, expected close quote')
    self._flush(parentNode, refChild)
    self._filter= filter


  def _Charref(self, parentNode, refChild, namespaces, textonly= False):
    """ Parse character references.
    """
    # Read character number from hex or decimal.
    #
    if self._match('x'):
      value= self._hex()
    else:
      value= self._dec()
    if not self._match(';'):
      self._error('Expected semicolon after character reference')
    if value in (0, 0xFFFE, 0xFFFF) or 0xD800<=value<0xE000:
      self._error('Invalid character referenced')
    elif parentNode.ownerDocument.xmlVersion=='1.0':
      if (value<256 and chr(value) in NOTCHAR) or (
        unicode is not None and unichr(value) in NOTCHARU
      ):
        self._error('Invalid character reference for XML 1.0 character model')

    # On pre-Unicode Pythons, store non-ASCII character references as fake
    # unbound entity references, unless we're parsing an EntityValue, in which
    # case we can only pass through an escaped &#...; as a last attempt
    #
    if unicode is None:
      if value>=128:
        if textonly:
          self._push('&#%d;' % value)
        else:
          self._flush(parentNode, refChild)
          ent= EntityReference(parentNode._ownerDocument, 'x')
          ent._nodeName= '#x%x' % value
          ent._setLocation(self._buffer.getLocation())
          ent._recurse(True, readonly= True)
          self._insert(ent, parentNode, refChild)

      # Otherwise add as text to the queue. On 'narrow' Python builds
      # character references outside the BMP will cause unichr to not work,
      # convert to two surrogate UTF-16 characters manually.
      #
      else:
        self._push(chr(value))
    else:
      try:
        unichr(value)
      except ValueError:
        self._push(unichr( 0xD800+((value-0x10000 >>10)&0x3FF) ))
        self._push(unichr( 0xDC00+((value-0x10000)&0x3FF) ))
      else:
        if unichr(value) in NOTCHARU:
          self._error('Invalid character referenced')
        if value>=0xD800 and value<0xE000:
          self._error('Invalid surrogate character reference')
        self._push(unichr(value))


  def _Entref(self, parentNode, refChild, namespaces):
    name= self._name()
    if not self._match(';'):
      self._error('Expected semicolon after entity reference')

    # Replace built-in entity references with plain text
    #
    char= {'amp':'&','lt':'<','gt':'>','quot':'"','apos':"'"}.get(name, None)
    if char is not None:
      self._push(char)
      return

    # Check for unparsed and circular entities
    #
    doctype= parentNode._ownerDocument.doctype
    if doctype is not None:
      ent= doctype.entities.getNamedItem(name)
      if ent is not None and ent.notationName is not None:
        self._error('Reference to unparsed entity')
    isCircular= name in self._entityNest
    self._entityNest.append(name)
    if isCircular:
      self._error('Circular entref: '+string.join(self._entityNest,'>'))

    # Look for the InputBuffer for this general entity
    #
    buffer= None
    if not self._generalEntities.has_key(name):
      self._domConfig._handleError(UnboundEntityErr())
    else:
      buffer= self._generalEntities[name]

    # If entities is on, create an EntityReference node and parse the
    # replacement text into it. If there is no replacement text available
    # create an empty EntityReference regardless of the state of entities.
    #
    if buffer is None or self._domConfig.getParameter('entities'):
      self._flush(parentNode, refChild)
      ent= EntityReference(parentNode.ownerDocument, name)
      if buffer is not None:
        parentNode.insertBefore(ent, refChild)
        oldbuffer= self._buffer
        self._buffer= buffer
        self._Content(ent, None, namespaces)
        self._buffer= oldbuffer
        buffer.reset()
      ent._recurse(True, readonly= True)
      self._insert(ent, parentNode, refChild,
        self._domConfig.getParameter('pxdom-preserve-base-uri')
      )

    # If entities is off, parse the replacement text from the InputBuffer
    # directly into the current node
    #
    else:
      if self._domConfig.getParameter('pxdom-preserve-base-uri'):
        inheritURI= None
        if buffer.uri!=parentNode.baseURI:
          inheritURI= buffer.uri
        oldbuffer= self._buffer
        self._buffer= buffer
        self._Content(parentNode, refChild, namespaces, inheritURI, flush= False)
        self._buffer= oldbuffer
        buffer.reset()

    del self._entityNest[-1]


  def _Comment(self, parentNode, refChild, namespaces):
    data= self._upto(['--'])
    if not self._match('-->'):
      self._error('Expected --> to close comment')
    if self._domConfig.getParameter('comments'):
      self._flush(parentNode, refChild)
      comment= parentNode._ownerDocument.createComment(data)
      comment._setLocation(self._buffer.getLocation())
      self._insert(comment, parentNode, refChild)


  def _PI(self, parentNode, refChild, namespaces, inheritURI= None):
    target= self._name()
    data= ''
    if not self._match('?>'):
      self._white()
      data= self._upto(['?>'])
      if not self._match('?>'):
        self._error('Expected ?> to close processing instruction')
    pi= parentNode._ownerDocument.createProcessingInstruction(target, data)
    pi._setLocation(self._buffer.getLocation())
    self._flush(parentNode, refChild)
    self._insert(pi, parentNode, refChild)
    if inheritURI is not None:
      self._domConfig._handleError(PIBaseURILostErr(pi, True))


  def _CDATA(self, parentNode, refChild, namespaces):
    data= self._upto([']]>'])
    if not self._match(']]>'):
      self._error('CDATA left open, expected ]]> to close')
    if not self._domConfig.getParameter('cdata-sections'):
      self._push(data)
    else:
      cdata= parentNode._ownerDocument.createCDATASection(data)
      cdata._setLocation(self._buffer.getLocation())

      # Depending on configuration parameter, possibly throw away CDATA
      # sections in element content that contain only whitespace. It is
      # currently unclear from spec whether this is the right thing.
      #
      if not self._domConfig.getParameter('element-content-whitespace'):
        cdata._containerNode= parentNode
        if cdata._get_isElementContentWhitespace(self._domConfig):
          cdata= None
        else:
          cdata._containerNode= None

      if cdata is not None:
        self._flush(parentNode, refChild)
        self._insert(cdata, parentNode, refChild)


  def _Doctype(self, parentNode, refChild, namespaces):
    self._white()
    name= self._name()
    if not self._match('>', False):
      self._white()
    publicId, systemId= self._externalId(None)

    # Create and insert doctype node. Make it temporarily not readonly.
    #
    imp= parentNode._ownerDocument.implementation
    p= self._domConfig.getParameter
    doctype= imp.createDocumentType(name, publicId, systemId)
    doctype._recurse(True, readonly= False)
    parentNode.insertBefore(doctype, refChild)

    # Parse internal subset if given
    #
    self._white(False)
    if self._match('['):
      start= self._buffer.index
      self._DTD(doctype, False)
      if start<self._buffer.index:
        doctype.internalSubset= self._buffer.chars[start:self._buffer.index]
      if not self._match(']'):
        self._error('Internal subset left open, expected ]')
      self._white(False)
    if not self._match('>'):
      self._error('Doctype left open, expected >')

    # Resolve and parse external DTD subset
    #
    if systemId is not None:
      baseURI= parentNode.documentURI
      buffer= self._buffer
      self._buffer=self._domConfig._resolveResource(publicId,systemId,baseURI)
      if self._buffer is None:
        doctype._processed= False
      else:
        self._Declaration(None)
        self._DTD(doctype, True)
        self._end()
      self._buffer= buffer

    # Fill in the children of available parsed general entities from the
    # replacement text in the InputBuffer we made at <!ENTITY> stage.
    #
    oldbuffer= self._buffer
    self._inEntity= True
    for ent in doctype.entities._list:
      if ent.notationName is None:
        buffer= self._generalEntities.get(ent.nodeName, None)
        if buffer is not None:
          self._buffer= buffer
          self._entityNest.append(ent.nodeName)
          self._Content(ent, None, namespaces)
          del self._entityNest[-1]
          ent._available= True
          buffer.reset()
          self._buffer= oldbuffer
    self._inEntity= False

    # Finished, make doctype read-only as per DOM spec
    #
    doctype._recurse(True, readonly= True)


  # Parameter entity handling for DTD parsing.
  #
  def _checkPE(self, doctype, white= True, ignorePercent= False):
    """ Check whether the buffer contains a parameter entity reference, or
        whether the buffer is coming to an end inside a parameter entity. In
        either case return a different buffer object to the caller to carry on
        parsing. Optionally skip white spaces at the edges of references and
        replacements. Optionally allow and ignore a % followed by whitespace,
        for the construct <!ENTITY % ...> which is the only place this can
        occur.
    """
    while True:
      if white:
        self._white(False)

      # Step into PE
      #
      if self._match('%'):
        if ignorePercent:
          index= self._buffer.index
          if self._buffer.chars[index:index+1] in WHITE+'%':
            self._buffer.index= index-1
            return

        name= self._name()
        if not self._match(';'):
          self._error('Expected ; to end parameter reference')
        if doctype is not None and doctype._processed:
          if not self._parameterEntities.has_key(name):
            self._error(self._buffer, 'Undefined parameter entity referenced')
          par= self._parameterEntities[name]
          if par is None:
            doctype._processed= False
          else:
            if par.parent is not None:
              self._error('Circular reference in parameter '+name)
            par.parent= self._buffer
            self._buffer= par
        continue

      # Step out of PE
      #
      l= len(self._buffer.chars)
      if self._buffer.index>=l and self._buffer.parent is not None:
        par= self._buffer.parent
        self._buffer.parent= None
        self._buffer.index= 0
        self._buffer= par
        continue
      break


  def _externalId(self, doctype, isNotation= False):
    """ Parse optional PUBLIC/SYSTEM ID as used by external entity/DTD subset.
        For notation declarations, allow a PUBLIC ID on its own.
    """
    if self._match('PUBLIC'):
      self._checkPE(doctype)
      publicId= self._literal()
      self._checkPE(doctype)
      systemId= None
      if not isNotation or not self._match('>', stepPast= False):
        systemId= self._literal()
      return (publicId, systemId)
    elif self._match('SYSTEM'):
      self._checkPE(doctype)
      return (None, self._literal())
    return (None, None)


  # DTD structure-parsing methods
  #
  def _DTD(self, doctype, external):
    """ Parse DTD declarations from internal or external subset or a DeclSep
        parameter entity reference.
    """
    while True:
      self._checkPE(doctype)
      if (
        self._buffer.index==len(self._buffer.chars) or
        self._match(']', stepPast=False)
      ):
        break

      # Dispatch declarations to appropriate parsing method. Ignore PIs and
      # comments; they do not appear in the DOM as DocumentType never has
      # any children. For some reason.
      #
      if self._match('<'):
        if self._match('?'):
          self._upto(['?>'])
          if not self._match('?>'):
            self._error('Expected ?> to close PI')
          continue

        if self._match('!'):
          if self._match('--'):
            self._upto(['--'])
            if not self._match('-->'):
              self._error('Expected --> to close comment')
            continue

          if self._match('['):
            self._checkPE(doctype)
            if not external:
              self._error('Cannot use conditionals in doctype')
            if self._match('INCLUDE'):
              self._checkPE(doctype)
              if not self._match('['):
                self._error('Expected open square bracket')
              self._DTD(doctype, external)
              if not self._match(']]>'):
                self._error('Expected ]]> to close conditional')
              continue
            if self._match('IGNORE'):
              self._checkPE(doctype)
              if not self._match('['):
                self._error('Expected open square bracket')
              nest= 1
              while nest>0:
                self._upto([']]>', '<!['])
                if self._match(']]>'):
                  nest= nest-1
                elif self._match('<!['):
                  nest= nest+1
                else:
                  self._error('Expected ]]> to close conditional')
              continue

          decl= None
          if self._match('NOTATION'):
            decl= self._NotationD
          elif self._match('ENTITY'):
            decl= self._EntityD
          elif self._match('ATTLIST'):
            decl= self._AttlistD
          elif self._match('ELEMENT'):
            decl= self._ElementD
          if decl is not None:
            decl(doctype)
            self._checkPE(doctype)
            if not self._match('>'):
              self._error('Expected close angle bracket')
            continue
      self._error('Expected markup declaration')


  def _NotationD(self, doctype):
    """ Parse notation declaration.
    """
    self._checkPE(doctype)
    name= self._name()
    self._checkPE(doctype)
    publicId, systemId= self._externalId(doctype, True)
    if doctype._processed and doctype._notations.getNamedItem(name) is None:
      doctype.notations.setNamedItem(Notation(
        doctype._ownerDocument, name, publicId, systemId, self._buffer.uri
      ))


  def _EntityD(self, doctype):
    """ Parse entity declaration.
    """
    self._checkPE(doctype, ignorePercent= True)
    isParameter= self._match('%')
    self._checkPE(doctype)
    name= self._name()
    self._checkPE(doctype)
    publicId, systemId= self._externalId(doctype)
    self._checkPE(doctype)

    # Internal entities: read the literal entity value into a temporary input
    # buffer and parse only character references and parameter entity
    # references from it - *not* any other type of entity reference, even the
    # built-ins. The queued text from this parse will be the replacement text
    # to be stored in another InputBuffer for later use.
    #
    if systemId is None:
      quote= self._quote()
      location= self._buffer.getLocation()
      literal= self._upto(quote)
      if not self._match(quote):
        self._error('EntityValue left open')
      realbuf= self._buffer

      input= LSInput()
      input.stringData= (literal,) # hack to allow empty string
      input.systemId= self._buffer.uri
      self._buffer= InputBuffer(input, location, self._domConfig, False)

      while True:
        self._push(self._upto(('&#', '%')))
        if self._match('&#'):
          self._Charref(doctype, None, None, textonly= True)
        else:
          self._checkPE(doctype, white= False)
          if self._buffer.index==len(self._buffer.chars):
            break

      replacement= self._queue
      self._queue= ''
      self._buffer=realbuf

      input= LSInput()
      input.stringData= (replacement,)
      input.systemId= self._buffer.uri
      extbuf= InputBuffer(input, location, self._domConfig, False)
      entity= Entity(
        doctype._ownerDocument, name, None, None, None, self._buffer.uri
      )

    # External entities: check for notation (which makes it an unparsed
    # entity) otherwise create LSInput representing external resource and
    # pass it through any LSResourceResolver in use, then make a buffer and
    # read then remove any text-declaration from it.
    #
    else:
      notation= None
      if not self._match('>', stepPast= False):
        self._checkPE(doctype)
      if self._match('NDATA'):
        self._checkPE(doctype)
        notation= self._name()
      entity= Entity(
        doctype._ownerDocument,name,
        publicId,systemId,notation,self._buffer.uri
      )

      extbuf= None
      if notation is None:
        extbuf= self._domConfig._resolveResource(
          publicId, systemId, self._buffer.uri
        )
      if extbuf is not None:
        buffer= self._buffer
        self._buffer= extbuf
        self._Declaration(entity)
        self._buffer= buffer
        extbuf.swallow()

    # Store the InputBuffer in one of the parser's maps (general or parameter
    # depending on type). For general entities store the Entity object in the
    # doctype NamedNodeMap, but do not parse it and fill in its children yet;
    # that doesn't happen until the doctype is complete.
    #
    if isParameter:
      if entity.notationName is not None:
        self._error('Parameter entities must be parsed entities')
      if doctype._processed and not self._parameterEntities.has_key(name):
        self._parameterEntities[name]= extbuf
    else:
      if doctype._processed and not self._generalEntities.has_key(name):
        doctype._entities.setNamedItem(entity)
        self._generalEntities[name]= extbuf


  def _AttlistD(self, doctype):
    """ Parse attribute list declaration.
    """
    # Get attlist object to write attributes to. Can re-use an existing one
    # to add attributes to a previously-declared attlist. If some declarations
    # have not been processed must ignore this, so write to a dummy attlist
    # we won't do anything with.
    #
    self._checkPE(doctype)
    name= self._name()
    if doctype._processed:
      attlist= doctype._attlists.getNamedItem(name)
      if attlist is None:
        attlist= AttributeListDeclaration(doctype._ownerDocument, name)
        doctype._attlists.setNamedItem(attlist)
    else:
      attlist= AttributeListDeclaration(doctype._ownerDocument, name)

    # Loop over declared attributes
    #
    while True:
      self._checkPE(doctype)
      if self._match('>', stepPast= False):
        break
      name= self._name()
      self._checkPE(doctype)
      typeValues= None

      # Look for known attribute value type names (CDATA etc.) but do it in
      # reverse order as a nasty hack to ensure 'NMTOKENS' is detected before
      # the substring 'NMTOKEN' (and similarly for ID[REF[S]]). If no name
      # found, must be an enum type.
      #
      for ix in range(len(AttributeDeclaration.ATTR_NAMES)-1, 0, -1):
        if self._match(AttributeDeclaration.ATTR_NAMES[ix]):
          attributeType= ix
          self._checkPE(doctype)
          break
      else:
        attributeType= AttributeDeclaration.ENUMERATION_ATTR

      # For enumeration types, parse list of names. For notation enums, must
      # be proper names, not just nmtokens
      #
      if attributeType in (
        AttributeDeclaration.NOTATION_ATTR,
        AttributeDeclaration.ENUMERATION_ATTR
      ):
        if not self._match('('):
          self._error(self._buffer,'Expected open bracket to start values')
        typeValues= []
        while True:
          self._checkPE(doctype)
          typeValues.append([self._nmtokens, self._name][
            attributeType==AttributeDeclaration.NOTATION_ATTR
          ]())
          self._checkPE(doctype)
          if not self._match('|'):
            break
        if not self._match(')'):
          self._error('Expected close bracket to end values')
        self._checkPE(doctype)

      # Read defaulting type.
      #
      if self._match('#REQUIRED'):
        defaultType= AttributeDeclaration.REQUIRED_VALUE
      elif self._match('#IMPLIED'):
        defaultType= AttributeDeclaration.IMPLIED_VALUE
      elif self._match('#FIXED'):
        defaultType= AttributeDeclaration.FIXED_VALUE
        self._checkPE(doctype)
      else:
        defaultType= AttributeDeclaration.DEFAULT_VALUE

      # Create attribute declaration object. Add to attlist if not already
      # declared. For attributes with default values, parse the attribute
      # value into the childNodes.
      #
      attdef= AttributeDeclaration(
        doctype._ownerDocument, name, attributeType, typeValues, defaultType
      )

      if attlist.declarations.getNamedItem(name) is None:
        attlist.declarations.setNamedItem(attdef)
      if defaultType in (
        AttributeDeclaration.FIXED_VALUE, AttributeDeclaration.DEFAULT_VALUE
      ):
        self._Attr(attdef, None, FIXEDNS.copy())


  def _ElementD(self, doctype):
    """ Parse element content declaration.
    """
    self._checkPE(doctype)
    name= self._name()
    self._checkPE(doctype)
    elements= None
    if self._match('EMPTY'):
      contentType= ElementDeclaration.EMPTY_CONTENT
    elif self._match('ANY'):
      contentType= ElementDeclaration.ANY_CONTENT
    else:
      if not self._match('('):
        self._error('Expected open bracket start content model')
      self._checkPE(doctype)
      if not self._match('#PCDATA'):
        contentType= ElementDeclaration.ELEMENT_CONTENT
        elements= self._ContentD(doctype)

      else:
        contentType= ElementDeclaration.MIXED_CONTENT
        elements= ContentDeclaration()
        self._checkPE(doctype)
        while True:
          if not self._match('|'):
            break
          self._checkPE(doctype)
          elements._append(self._name())
          self._checkPE(doctype)
        if not self._match(')'):
          self._error('Expected close bracket end content model')
        if not self._match('*') and elements.length!=0:
          self._error('Expected asterisk ending mixed content')

    if doctype._processed and doctype._elements.getNamedItem(name) is None:
      doctype._elements.setNamedItem(ElementDeclaration(
        doctype._ownerDocument, name, contentType,elements
      ))


  def _ContentD(self, doctype):
    """ Parse (recursively) the content model in an element declaration, minus
        the leading open bracket. Return a ContentDeclaration object.
    """
    elements= ContentDeclaration()
    elements.isSequence= None

    while True:
      if self._match('('):
        self._checkPE(doctype)
        element= self._ContentD(doctype)
      else:
        element= self._name()
        element= self._SuffixD(element)
      elements._append(element)

      self._checkPE(doctype)
      if self._match(')'):
        break
      if self._match('|'):
        sequence= False
      elif self._match(','):
        sequence= True
      else:
        self._error('Expected comma or pipe separator')
      if elements.isSequence not in (None, sequence):
        self._error('Cannot mix comma and pipe separators')
      elements.isSequence= sequence
      self._checkPE(doctype)
    if elements.isSequence is None:
      elements.isSequence= False
    return self._SuffixD(elements)

  def _SuffixD(self, cp):
    """ Parse suffix that appears on content particles in element content
         declarations. Return altered version of cp.
    """
    isOptional= False
    isMultiple= False
    if self._match('*'):
      isOptional= True
      isMultiple= True
    elif self._match('+'):
      isMultiple= True
    elif self._match('?'):
      isOptional= True
    if not isinstance(cp, ContentDeclaration) and (isOptional or isMultiple):
      c= ContentDeclaration()
      c._append(cp)
      cp= c
    if isOptional:
      cp.isOptional= True
    if isMultiple:
      cp.isMultiple= True
    return cp


# Convenience parsing functions. The default parameters for these functions
# are slightly different than those of a standard LSParser, to emulate the
# minidom functions of the same name. Other DOMConfiguration parameters may be
# passed in an optional mapping.
#
def parse(fileorpath, parameters= {}):
  """ Get a Document object from a file.
  """
  parser= LSParser()
  parser.domConfig.setParameter('cdata-sections', True)
  parser.domConfig.setParameter('pxdom-resolve-resources', False)
  for (key, value) in parameters.items():
    parser.domConfig.setParameter(key, value)
  src= _implementation.createLSInput()
  if hasattr(fileorpath, 'read'):
    src.byteStream= fileorpath
  else:
    src.systemId= 'file:'+urllib.pathname2url(os.path.abspath(fileorpath))
  doc= parser.parse(src)
  return doc

def parseString(content, parameters= {}):
  """ Get a Document object from a string.
  """
  parser= LSParser()
  parser.domConfig.setParameter('cdata-sections', True)
  parser.domConfig.setParameter('pxdom-resolve-resources', False)
  for (key, value) in parameters.items():
    parser.domConfig.setParameter(key, value)
  src= _implementation.createLSInput()
  src.stringData= content
  return parser.parse(src)


# DOM 3 LS Save features
# ============================================================================

def _DOMImplementation__createLSOutput(self):
  return LSOutput()
def _DOMImplementation__createLSSerializer(self):
  return LSSerializer()

# Markup content as a property, a convenience interface that was in the June
# WD as ElementLS.markupContent. It is no longer in the standard, but is
# included in pxdom for its convenience, extended to appear on all node types
# (though it is not always writable).
#
def _Node___get_pxdomContent(self):
  config= DOMConfiguration(self._ownerDocument.domConfig)
  s= LSSerializer(config)
  s.newLine= '\n'
  return s.writeToString(self)

def _Node___set_pxdomContent(self, value):
  input= LSInput()
  input.stringData= value
  parser= LSParser(self._ownerDocument.domConfig)
  parser.parseWithContext(input, self, LSParser.ACTION_REPLACE)


class LSOutput(DOMObject):
  """ Abstraction for the output destination of an LSSerializer. As well as
      the standard-defined options, we use characterStream= True internally to
      mean 'return data as string'.
  """
  def __init__(self):
    DOMObject.__init__(self)
    self._characterStream= None
    self._byteStream= None
    self._systemId= None
    self._encoding= None

  def _get_characterStream(self): return self._characterStream
  def _get_byteStream(self): return self._byteStream
  def _get_systemId(self): return self._systemId
  def _get_encoding(self): return self._encoding

  def _set_characterStream(self, value): self._characterStream= value
  def _set_byteStream(self, value): self._byteStream= value
  def _set_systemId(self, value): self._systemId= value
  def _set_encoding(self, value): self._encoding= value


class OutputBuffer:
  def __init__(self, output, document):
    self._output= output
    self._buffer= StringIO.StringIO()
    self._separator= None
    if (
      output.characterStream is None and output.byteStream is None
      and output.systemId is None
    ):
      raise NoOutputErr()

    # Work out which charsets to use (a) for detecting unencodable characters
    # and escaping them (and also putting in the XML declaration if there is
    # one) and (b) encoding the final output.
    #
    if output.characterStream is None:
      self.encoding=self.outputEncoding= (
        output.encoding or document.inputEncoding or document.xmlEncoding
        or 'utf-8'
      )
    else:
      if output.encoding is not None:
        self.encoding= output.encoding
      elif unicode is not None:
        self.encoding= 'utf-16'
      else:
        self.encoding= 'utf-8'
      self.outputEncoding= None

    # Ignore endianness in the declared version of the encoding, and check it
    # actually exists.
    #
    if self.encoding is not None:
      if (
        string.lower(self.encoding)[:6] in ('utf-16', 'utf-32') and
        self.encoding[6:-2] in ('', '-', '_') and
        string.lower(self.encoding)[-2:] in ('le', 'be')
      ):
        self.encoding= self.encoding[:6]
      if unicode is not None:
        try:
          unicode('').encode(self.encoding)
        except LookupError:
          document.domConfig._handleError(UnsupportedEncodingErr())


  def flush(self):
    """ Finish output, sending buffer contents to the nominated destination
        (optionally encoding it). In the special case where characterStream
        was 'True' return the buffer as a string, else return a success flag,
        which is always True since we raise an exception when there is an
        fatal error and don't attempt to carry on.
    """
    data= self._buffer.getvalue()
    self._buffer= None
    bs, cs= self._output.byteStream, self._output.characterStream
    try:

      # Unless outputting to byte-based destination with no outputEncoding,
      # try to coerce collected string to unicode. Leave the string narrow if
      # it contains characters than cannot be coerced into unicode.
      #
      if unicode is not None and not isinstance(data, Unicode) and not (
        cs is None and self.outputEncoding is None
      ):
        try:
          data= unicode(data, self.outputEncoding or 'us-ascii')
        except UnicodeError:
          pass

      # If outputting character string or stream, return the probably-unicode
      # data
      #
      if cs is True:
        return data
      elif cs is not None:
        cs.write(data)
        return True

      # If outputting to byte stream/URI, encode if necessary. May fail if
      # data still contains non-ascii byte character.
      #
      if unicode is not None and self.outputEncoding is not None:
        try:
          data= data.encode(self.outputEncoding)
        except UnicodeError:
          pass

      if bs is True:
        return data
      if self._output.byteStream is not None:
        self._output.byteStream.write(data)
        return True

      if self._output.systemId is not None:
        urlparts= urlparse.urlparse(self._output.systemId, 'file')
        scheme= string.lower(urlparts[0])
        if scheme=='file':
          stream= open(urllib.url2pathname(urlparts[2]), 'wb')
          stream.write(data)
          stream.close()
          return True
        elif scheme in ('http', 'https'):
          if scheme=='https':
            conn= httplib.HTTPSConnection(urlparts[1])
          else:
            conn= httplib.HTTPConnection(urlparts[1])
          conn.request('PUT', urlparts[2], data, {
            'Content-Type': 'text/xml', 'Content-Length': str(len(data))
          })
          response= conn.getresponse()
          conn.close()
          if not (response.status>=200 and response.status<300):
            raise IOErrorErr(IOError(
              'HTTP response %d %s' % (response.status, response.reason)
            ))
          return True
        else:
          raise IOErrorErr(
            ValueError('Can\'t write to URI type %s' % urlparts[0])
          )
    except IOError, e:
      raise IOErrorErr(e)

  def setSeparator(self, separator):
    """ A separator can be set (or cleared by passing None) on the output,
        causing that string to be written the next time write() is called with
        a non-empty string. This is useful for eg. attributes, where the
        serializer won't know if a whitespace character is needed until the
        attribute markup arrives.
    """
    self._separator= separator

  def write(self, data, escaper= None):
    """ Accumulate string parts, calling an escaper function back for any
        characters that cannot be output in the desired encoding. Note that
        even though we do an encode step here, it is only to detect tricky
        characters - it is the plain, unencoded versions that are sent to the
        output buffer, they will be encoded in the final output encoding in
        the flush() step.
    """
    if self._separator is not None:
      self._buffer.write(self._separator)
      self._separator= None

    # Call the escaper for any restrictedChars in the string.
    #
    if escaper is not None:
      for ch in NOTCHAR:
        if ch in data:
          data= r(data, ch, escaper.escape(ord(ch)))
      if isinstance(data, Unicode):
        for ch in NOTCHARU:
          if ch in data:
            data= r(data, ch, escaper.escape(ord(ch)))

    # Try to unicode-encode if we will need to and the result isn't going to
    # be a UTF encoding - by definition, all possible characters are encodable
    # in a UTF form.
    #
    if not isinstance(data,Unicode) or string.lower(self.encoding[:3])=='utf':
      self._buffer.write(data)
    else:
      chars= unicode(data)

      # See if there are any characters that we can't encode in the string. If
      # not, just slap it into the buffer as-is, otherwise we'll need to
      # handle the string character-by-character, because up until Python 2.3
      # and UnicodeEncodeError it's impossible to tell where the error was.
      #
      try:
        chars.encode(self.encoding, 'strict')
      except UnicodeError:

        # Iterate over characters. If Python is not compiled in wide-mode
        # (UTF-32), there may be surrogates in there; detect and deal with
        # two characters at a time in this case.
        #
        ix= 0
        while ix<len(chars):
          isSurrogate= 0xD800<=ord(chars[ix])<0xDC00 and (
            ix<len(chars)-1 and 0xDC00<=ord(chars[ix+1])<0xE000
          )
          try:
            chars[ix:ix+1+isSurrogate].encode(self.encoding, 'strict')
          except UnicodeError:
            if escaper is not None:
              if isSurrogate:
                c= 0x10000+(
                  (ord(chars[ix])&0x3FF)<<10)+(
                  ord(chars[ix+1])&0x3FF
                )
              else:
                c= ord(chars[ix])
              self._buffer.write(escaper.escape(c))
          else:
            self._buffer.write(chars[ix:ix+1+isSurrogate])
          ix= ix+1+isSurrogate

      else:
        self._buffer.write(chars)


# OuputBuffer escapers
#
class _Complainer:
  """ Holds an escaper method for OutputBuffer that just raises a given kind
      of DOMError when called back.
  """
  def __init__(self, config, node, isName= False):
    if isName:
      self._exn= WfInvalidCharacterErr
    else:
      self._exn= InvalidCharacterInNodeNameErr
    self._node= node
    self._domConfig= config
  def escape(self, c):
    self._domConfig._handleError(self._exn(self._node))
    return ''

class _Charreffer:
  """ Holds an escaper method that outputs a character reference, optionally
      in hex for canonical-form.
  """
  def __init__(self, hexref= False):
    self._hexref= hexref
  def escape(self, c):
    return ('&#%d;', '&#x%x;')[self._hexref] % c

class _CdataSplitter:
  """ Holds an escaper method that outputs a CDATA-end-section then a charref,
      then re-opens CDATA, as long as the DOMConfiguration allows it. Config
      is only called back once per node, after that we null the reference. No
      hex option, as canonical-form allows no CDATASections.
  """
  def __init__(self, config, node):
    self._domConfig= config
    self._node= node
  def escape(self, c):
    config= self._domConfig
    if config is not None:
      if config.getParameter('split-cdata-sections'):
        config._handleError(CdataSectionsSplittedErr(self._node))
      else:
        config._handleError(WfInvalidCharacterErr(self._node))
      self._domConfig= None
    return ']]>&#%d;<![CDATA[' % c


class LSSerializer(DOMObject):
  def __init__(self, config= None):
    DOMObject.__init__(self)
    if config is None:
      config= DOMConfiguration()
      if CNORM:
        config.setParameter('normalize-characters', True)
    self._domConfig= config
    self._newLine= os.linesep
    self._filter= None

  def _get_domConfig(self): return self._domConfig
  def _get_filter(self): return self._filter
  def _get_newLine(self): return self._newLine

  def _set_filter(self, value): self._filter= value
  def _set_newLine(self, value):
    if value is None:
      self._newLine= os.linesep
    else:
      self._newLine= value

  def write(self, node, destination):
    try:
      buffer= OutputBuffer(destination, node._ownerDocument)
    except DOMException, e:
      self._domConfig._handleError(e)
    if node.parentNode is not None:
      namespaces= node.parentNode._getNamespaces(FIXEDNS.copy())
    else:
      namespaces= FIXEDNS.copy()
    node._writeTo(
      buffer, self._domConfig, self._filter, self._newLine, namespaces
    )
    return buffer.flush()

  def writeToString(self, node):
    destination= LSOutput()
    destination.characterStream= True
    return self.write(node, destination)

  def writeToURI(self, node, uri):
    destination= LSOutput()
    destination.systemId= uri
    return self.write(node, destination)


def _Node___writeTo(self, dest, config, filter, newLine, namespaces):
  """ Markup production, for various node types. The default node behaviour is
      just to recurse to all children.
  """
  for child in self._childNodes:
    child._writeTo(dest, config, filter, newLine, namespaces)


def _Document___writeTo(self,dest,config,filter,newLine,namespaces):
  if config.getParameter('canonical-form') and self._xmlVersion=='1.1':
    config._handleError(CanonicalXmlErr(self))

  # Output XML preamble
  #
  if config.getParameter('xml-declaration'):
    dest.write('<?xml version="')
    dest.write(self._xmlVersion or '1.0', _Complainer(config, self))
    if dest.encoding is not None:
      dest.write('" encoding="')
      dest.write(dest.encoding)
    if self._xmlStandalone:
      dest.write('" standalone="yes')
    dest.write('"?>'+newLine)
  elif (self._xmlVersion not in ('1.0', None, '') or self._xmlStandalone):
    config._handleError(XmlDeclarationNeededErr(self))

  # Put a single newline between each document-level child, as there are no
  # whitespace nodes
  #
  for child in self._childNodes:
    child._writeTo(dest, config, filter, newLine, namespaces)
    dest.setSeparator(newLine)


def _Element___writeTo(self, dest, config, filter, newLine, namespaces):
  accepted= _acceptNode(filter, self)
  if accepted==NodeFilter.FILTER_SKIP:
    NamedNodeNS._writeTo(self, dest, config, filter, newLine, namespaces)
  if accepted!=NodeFilter.FILTER_ACCEPT:
    return

  # Get list of attributes. If doing namespace fixup at output stage, update
  # the namespaces lookup table from namespace declaration attributes then
  # from fixups.
  #
  attrs= self._attributes._list[:]
  newspaces= namespaces.copy()
  reprefix= []
  if config.getParameter('namespaces'):
    for attr in attrs:
      if attr.namespaceURI==NSNS:
        prefix= [attr.localName, None][attr.prefix is None]
        newspaces[prefix]= attr.value or None
    create, reprefix= self._getFixups(newspaces)

    for prefix, namespaceURI in create:
      name= 'xmlns'
      if prefix is not None:
        name= name+':'+prefix
      for attr in attrs:
        if attr.nodeName==name:
          attrs.remove(attr)
          break
      attr= self._ownerDocument.createAttributeNS(NSNS, name)
      attr.value= namespaceURI or ''
      attrs.append(attr)
      newspaces[prefix]= namespaceURI

  # If outputting canonically, put the attribute list in order.
  #
  if config.getParameter('canonical-form'):
    attrs= attrs._list[:]
    attrs.sort(_canonicalAttrSort)

  # Write beginning of start-tag.
  #
  escaper= _Complainer(config, self, True)
  dest.write('<')
  dest.write(config._cnorm(self.tagName, self), escaper)
  dest.setSeparator(' ')

  # Write attributes. Where we remembered that a changed prefix would be
  # required, ask Attr._writeTo to override the actual prefix.
  #
  for attr in attrs:
    for pattr, prefix in reprefix:
      if attr is pattr:
        attr._writeTo(dest,config,filter,newLine,namespaces,prefix)
        break
    else:
      attr._writeTo(dest, config, filter, newLine, namespaces)
    dest.setSeparator(' ')
  dest.setSeparator(None)

  if config.getParameter('canonical-form'):
    empty= False
  else:
    empty= self._childNodes.length==0
    if config.getParameter('pxdom-html-compatible'):
      empty= empty and (
        self.namespaceURI in (HTNS, None) and self.localName in HTMLEMPTY
      )

  if empty:
    if config.getParameter('pxdom-html-compatible'):
      dest.write(' ')
    dest.write('/>')
  else:
    dest.write('>')
    if self._childNodes.length!=0:

      # Write children, reformatting them in pretty-print mode
      #
      if not config.getParameter('format-pretty-print') or (
        self._childNodes.length==1 and
        self._childNodes[0].nodeType==Node.TEXT_NODE and
        '\n' not in self._childNodes[0].data
      ):
        NamedNodeNS._writeTo(
          self, dest, config, filter, newLine, newspaces
        )
      else:
        dest.write(newLine+'  ')
        NamedNodeNS._writeTo(
          self, dest, config, filter, newLine+'  ', newspaces
        )
        dest.write(newLine)

    dest.write('</')
    dest.write(self.tagName, escaper)
    dest.write('>')


def _Attr___writeTo(
  self, dest, config, filter, newLine, namespaces, prefix= NONS
):
  # Apply LSSerializerFiltering to non-namespace-declaring attributes only
  #
  isNsDecl= self.namespaceURI==NSNS and config.getParameter('namespaces')
  if (isNsDecl and not config.getParameter('namespace-declarations')):
    return
  if not isNsDecl and _acceptNode(filter, self)!=NodeFilter.FILTER_ACCEPT:
    return

  # Possibly discard default and redundant attributes depending on config
  #
  if not self._specified and config.getParameter('discard-default-content'):
    return
  if self.namespaceURI==NSNS and config.getParameter('canonical-form'):
    prefix= [self.localName, None][self.prefix is None]
    value= None
    if self._containerNode is not None:
      if self._containerNode.parentNode is not None:
        value= self._containerNode.parentNode._lookupNamespaceURI(prefix)
    if self.value==(value or ''):
      return

  # Output attribute name, with possible overridden prefix
  #
  name= self.nodeName
  if prefix is not NONS:
    name= self.localName
    if prefix is not None:
      name= prefix+':'+name
  dest.write(config._cnorm(name, self),_Complainer(config, self, True))

  # In canonical form mode, output actual attribute value (suitably encoded)
  # no entrefs
  #
  dest.write('="')
  if config.getParameter('canonical-form'):
    s= r(r(r(r(r(r(self.value, '&', '&amp;'), '<','&lt;'),'"','&quot;'),
      '\x0D','&#xD;'),'\n','&#xA'),'\t','&#x9;')
    if isinstance(m, Unicode):
      m= r(r(m, unichr(0x85), '&#x85;'), unichr(0x2028), unichr(0x2028))
    dest.write(s, _Charreffer(True))

  # Otherwise, iterate into children, but replacing " marks. Don't filter
  # children.
  #
  else:
    for child in self._childNodes:
      child._writeTo(dest, config, None,'&#10;', namespaces, attr=True)
  dest.write('"')


def _Comment___writeTo(self,dest,config,filter,newLine,namespaces):
  if (not config.getParameter('comments') or
    _acceptNode(filter, self)!=NodeFilter.FILTER_ACCEPT
  ):
    return
  if self.data[-1:]=='-' or string.find(self.data, '--')!=-1:
    config._handleError(WfInvalidCharacterErr(self))
  dest.write('<!--')
  pretty= config.getParameter('format-pretty-print')
  if pretty and '\n' in string.strip(self.data):
    for line in string.split(self.data, '\n'):
      line= string.strip(line)
      if line!='':
        dest.write(newLine+'  ')
        dest.write(line, _Complainer(config, self))
    dest.write(newLine)
  else:
    dest.write(r(self.data, '\n', newLine), _Complainer(config, self))
  dest.write('-->')

def _Text___writeTo(
  self, dest, config, filter, newLine, namespaces, attr= False
):
  if (
    not config.getParameter('element-content-whitespace')
    and self._get_isElementContentWhitespace(config)
  ) or _acceptNode(filter, self)!=NodeFilter.FILTER_ACCEPT:
    return

  m= r(r(config._cnorm(self.data, self), '&', '&amp;'), '<', '&lt;')
  if config.getParameter('canonical-form'): # attr always false here
    dest.write(r(r(r(m, '>', '&gt;'), '\r', '&#xD;'), '\n', newLine),
      _Charreffer(True)
    )
  else:
    if attr:
      m= r(r(m, '"', '&quot;'), '\t', '&#9;')
    m= r(r(m, ']]>', ']]&gt;'), '\r', '&#13;')
    if isinstance(m, Unicode):
      m= r(r(m, unichr(0x85), '&#133;'), unichr(0x2028), '&#8232;')
    if config.getParameter('format-pretty-print'):
      m= string.join(map(string.strip, string.split(m, '\n')), newLine)
    else:
      m= r(m, '\n', newLine)
    dest.write(m, _Charreffer())

def _CDATASection___writeTo(
  self, dest, config, filter, newLine, namespaces
):
  if not config.getParameter('cdata-sections'):
    return Text._writeTo(self,dest,config,filter,newLine,namespaces)
  if (
    not config.getParameter('element-content-whitespace')
    and self.isElementContentWhitespace(config)
  ) or _acceptNode(filter, self)!=NodeFilter.FILTER_ACCEPT:
    return

  m= config._cnorm(self.data, self)
  escaper= _CdataSplitter(config, self)
  dest.write('<![CDATA[')
  if string.find(m, ']]>')!=-1 or string.find(m, '\r')!=-1:
    escaper.escape(32)
    dest.write(r(r(r(m,
      ']]>',']]]]><![CDATA[>'), '\r',']]>&#13;<![CDATA['), '\n', newLine),
      escaper
    )
  else:
    dest.write(r(m, '\n', newLine), escaper)
  dest.write(']]>')

def _ProcessingInstruction___writeTo(
  self, dest, config, filter, newLine, namespaces
):
  if _acceptNode(filter, self)!=NodeFilter.FILTER_ACCEPT:
    return
  dest.write('<?')
  dest.write(self._nodeName, _Complainer(config, self, True))
  if self._data!='':
    dest.write(' ')
    if string.find(self._data, '?>')!=-1 or string.find(self._data, '\r')!=-1:
      config._handleError(WfInvalidCharacterErr(self))
    dest.write(r(config._cnorm(self._data, self), '\n', newLine),
      _Complainer(config, self)
    )
  dest.write('?>')

def _EntityReference___writeTo(self,
  dest, config, filter, newLine, namespaces, attr= False
):
  # If entities parameter is false, skip all bound available entity references
  # otherwise pass to filter as normal
  #
  doctype= self._ownerDocument.doctype
  entity= None
  if doctype is not None:
    entity= doctype.entities.getNamedItem(self.nodeName)
  accepted= NodeFilter.FILTER_ACCEPT
  if not config.getParameter('entities'):
      if entity is not None and entity.pxdomAvailable:
        accepted= NodeFilter.FILTER_SKIP
  if accepted==NodeFilter.FILTER_ACCEPT:
    accepted= _acceptNode(filter, self)

  if accepted==NodeFilter.FILTER_ACCEPT:
    dest.write('&')
    dest.write(config._cnorm(self._nodeName, self),
      _Complainer(config, self, True)
    )
    dest.write(';')

  elif accepted==NodeFilter.FILTER_SKIP:
    for child in entity._childNodes:
      if attr:
        if child.nodeType not in Attr._childTypes:
          config._handleError(InvalidEntityForAttrErr(self))
        child._writeTo(dest, config, filter, newLine, namespaces, True)
      else:
        child._writeTo(dest, config, filter, newLine, namespaces)


def _DocumentType___writeTo(
  self, dest, config, filter, newLine, namespaces
):
  dest.write('<!DOCTYPE ')
  dest.write(
    config._cnorm(self._nodeName, self),
    _Complainer(config, self, True)
  )
  escaper= _Complainer(config, self)
  if self._publicId is not None:
    dest.write(' PUBLIC "')
    dest.write(config._cnorm(self._publicId, self), escaper)
    dest.write('"')
    if self._systemId is not None:
      dest.write(' "')
      dest.write(config._cnorm(self._systemId, self), escaper)
      dest.write('"')
  elif self._systemId is not None:
    dest.write(' SYSTEM "')
    dest.write(config._cnorm(self._systemId, self), escaper)
    dest.write('"')
  if self._internalSubset is not None:
    dest.write(' [')
    dest.write(config._cnorm(self._internalSubset, self), escaper)
    dest.write(']')
  dest.write('>')


# Exceptions
# ============================================================================

class DOMException(Exception):
  """ The pxdom DOMException implements the interfaces DOMException, DOMError
      and LSException. There are _get methods, but the properties are read
      directly and aren't read-only, as Exception behaves oddly when its
      getter/setter is overridden.
  """
  [INDEX_SIZE_ERR,DOMSTRING_SIZE_ERR,HIERARCHY_REQUEST_ERR,WRONG_DOCUMENT_ERR,
  INVALID_CHARACTER_ERR,NO_DATA_ALLOWED_ERR,NO_MODIFICATION_ALLOWED_ERR,
  NOT_FOUND_ERR,NOT_SUPPORTED_ERR,INUSE_ATTRIBUTE_ERR,INVALID_STATE_ERR,
  SYNTAX_ERR,INVALID_MODIFICATION_ERR,NAMESPACE_ERR,INVALID_ACCESS_ERR,
  VALIDATION_ERR, TYPE_MISMATCH_ERR
  ]= range(1, 18)
  [PARSE_ERR, SERIALIZE_ERR
  ]= range(81, 83)
  [SEVERITY_WARNING,SEVERITY_ERROR,SEVERITY_FATAL_ERROR
  ]= range(1, 4)
  SEVERITY_NAMES= ('', 'Warning', 'Error', 'Fatal error')

  code= 0
  type= 'pxdom-exception'
  severity= SEVERITY_FATAL_ERROR
  message= 'pxdom exception'
  relatedData= None
  location= None

  def __init__(self, related= None):
    if related is not None:
      self.relatedData= related
      self.location= related.pxdomLocation
    self.relatedException= self
    self.message= '%s \'%s\'' %(self.SEVERITY_NAMES[self.severity], self.type)
  def __str__(self):
    return self.message
  def __repr__(self):
    return self.message

  def _get_code(self):
    return self.code
  def _get_relatedData(self):
    return self.relatedData
  def _get_location(self):
    return self.location

  def allowContinue(self, cont):
    if self.severity==DOMException.SEVERITY_WARNING:
      return [cont, True][cont is None]
    elif self.severity==DOMException.SEVERITY_ERROR:
      return [cont, False][cont is None]
    else:
      return False


# Traditional DOMExceptions
#
class IndexSizeErr(DOMException):
  code= DOMException.INDEX_SIZE_ERR
  def __init__(self, data, index):
    DOMException.__init__(self)
    self.message= 'index %s in data of length %s' % (index, len(data))

class HierarchyRequestErr(DOMException):
  code= DOMException.HIERARCHY_REQUEST_ERR
  def __init__(self, child, parent):
    DOMException.__init__(self)
    if child.nodeType not in parent._childTypes:
      self.message= 'putting %s inside %s' % (
        child.__class__.__name__, parent.__class__.__name__
      )
    elif parent.nodeType==Node.DOCUMENT_NODE:
      self.message= 'putting extra %s in Document' % child.__class__.__name__
    else:
      self.message= 'putting %s inside itself' % parent.__class__.__name__

class WrongDocumentErr(DOMException):
  code= DOMException.WRONG_DOCUMENT_ERR
  def __init__(self, child, document):
    DOMException.__init__(self)
    self.message= '%s from foreign Document' % child.__class__.__name__

class InvalidCharacterErr(DOMException):
  code= DOMException.INVALID_CHARACTER_ERR
  def __init__(self, name, char):
    DOMException.__init__(self)
    self.message= '%s in %s' % (repr(char), repr(name))

class NoModificationAllowedErr(DOMException):
  code= DOMException.NO_MODIFICATION_ALLOWED_ERR
  def __init__(self, obj, key):
    DOMException.__init__(self)
    self.message= '%s.%s read-only' % (obj.__class__.__name__, key)

class NamespaceErr(DOMException):
  code= DOMException.NAMESPACE_ERR
  def __init__(self, qualifiedName, namespaceURI):
    DOMException.__init__(self)
    if _splitName(qualifiedName)[1] is None:
      self.message= '%s is not a qualifiedName' % repr(qualifiedName)
    else:
      self.message= '%s can\'t be in namespace %s' % (
      repr(qualifiedName), repr(namespaceURI)
    )

class NotFoundErr(DOMException):
  code= DOMException.NOT_FOUND_ERR
  def __init__(self, obj, namespaceURI, localName):
    DOMException.__init__(self)
    if namespaceURI not in (None, NONS):
      self.message= '%s in %s' % (repr(localName), obj.__class__.__name__)
    else:
      self.message= '%s (ns: %s) in %s' % (
        repr(localName), repr(namespaceURI), obj.__class__.__name__
      )

class NotSupportedErr(DOMException):
  code= DOMException.NOT_SUPPORTED_ERR
  def __init__(self, obj, name):
    DOMException.__init__(self)
    self.message= '%s.%s' % (obj.__class__.__name__, name)

class InuseAttributeErr(DOMException):
  code= DOMException.INUSE_ATTRIBUTE_ERR
  def __init__(self, attr):
    DOMException.__init__(self)
    self.message= 'attr %s in use' % repr(attr.name)


# Serious parsing problems
#
class IOErrorErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'pxdom-uri-unreadable'
  def __init__(self, e):
    DOMException.__init__(self)
    self.message= 'pxdom could not read resource: '+str(e)

class ParseErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'pxdom-parse-error'
  def __init__(self, buffer, message):
    DOMException.__init__(self)
    self.message= message
    self.buffer= buffer
    line, column= buffer.getLocation()
    self.location= DOMLocator(None, line, column, buffer.uri)
  def __str__(self):
    LEE= 30
    ch= self.buffer.chars
    ix= self.buffer.index
    pre= string.split(ch[max(ix-LEE, 0):ix], '\n')[-1]
    post= string.split(ch[ix:min(ix+LEE, len(ch))], '\n')[0]
    pre= string.join(filter(lambda c: ord(c)<127, pre), '')
    post= string.join(filter(lambda c: ord(c)<127, post), '')
    line, column= self.location.lineNumber, self.location.columnNumber
    s= '%s\naround line %s char %s' % (self.message, line, column)
    if self.buffer.uri is not None:
      s= s+' of '+self.buffer.uri
    return  '%s:\n%s%s\n%s^'%(s, pre, post, ' '*len(pre))

# Simple errors
#
class UnsupportedMediaTypeErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'unsupported-media-type'
class UnsupportedEncodingErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'unsupported-encoding'
class DoctypeNotAllowedErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'doctype-not-allowed'
class NoInputErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'no-input-specified'
class NoOutputErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'no-output-specified'
class InvalidCharacterInNodeNameErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'wf-invalid-character-in-node-name'
class CanonicalXmlErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'pxdom-xml-1.1-cannot-be-canonicalised'

# Simple recoverable errors
#
class WfInvalidCharacterErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'wf-invalid-character'
  severity= DOMException.SEVERITY_ERROR
class XmlDeclarationNeededErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'xml-declaration-needed'
  severity= DOMException.SEVERITY_WARNING
class CdataSectionsSplittedErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'cdata-sections-splitted'
  severity= DOMException.SEVERITY_WARNING
class InvalidEntityForAttrErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'pxdom-invalid-entity-for-attr'
  severity= DOMException.SEVERITY_ERROR
class UnboundEntityErr(DOMException):
  code= DOMException.PARSE_ERR
  type= 'pxdom-unbound-entity'
  severity= DOMException.SEVERITY_WARNING

# A few DOMErrors can happen at both serialise and parse time
#
class DOMEitherException(DOMException):
  def __init__(self, node, isParse):
    DOMException.__init__(self, node)
    self.code= [DOMException.SERIALIZE_ERR, DOMException.PARSE_ERR][isParse]
class CheckNormErr(DOMEitherException):
  type= 'check-character-normalization-failure'
  severity= DOMException.SEVERITY_ERROR
class PIBaseURILostErr(DOMEitherException):
  type= 'pi-base-uri-not-preserved'
  severity= DOMException.SEVERITY_WARNING

# Unbound namespace warnings are only official W3 ones when in entity
# declarations. Otherwise use a pxdom-specific warning; perhaps officially
# should be an error instead?
#
class UnboundNSErr(DOMException):
  code= DOMException.PARSE_ERR
  severity= DOMException.SEVERITY_WARNING
  def __init__(self, node, isEntity):
    self.type= [
      'pxdom-unbound-namespace', 'unbound-namespace-in-entity'
    ][isEntity]
    DOMException.__init__(self, node)

# Spec requires that this DOMError is severity ERROR, however it makes no
# sense to stop processing due to Level 1 node, so treat it as if it were a
# WARNING.
#
class Level1NodeErr(DOMException):
  code= DOMException.SERIALIZE_ERR
  type= 'pxdom-non-namespace-node-encountered'
  severity= DOMException.SEVERITY_ERROR
  def allowContinue(self, cont):
    return [cont, True][cont is None]


# END. Fix up classes.
#
_insertMethods()
