""" Fully compliant (I think) DOM 2 HTML implementation.
Currently requires pxdom (http://doxdesk.com/software/py/pxdom.html)

Licence (new-BSD-style)

Copyright (C) 2008, Paul Bonser. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions must reproduce the above copyright notice, this list
  of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* The name of the copyright holder may not be used to endorse or
  promote products derived from this software without specific prior
  written permission.

This software is provided by the copyright holder and contributors "as
is" and any express or implied warranties, including, but not limited
to, the implied warranties of merchantability and fitness for a
particular purpose are disclaimed. In no event shall the copyright
owner or contributors be liable for any direct, indirect, incidental,
special, exemplary, or consequential damages (including, but not
limited to, procurement of substitute goods or services; loss of use,
data, or profits; or business interruption) however caused and on any
theory of liability, whether in contract, strict liability, or tort
(including negligence or otherwise) arising in any way out of the use
of this software, even if advised of the possibility of such damage.
"""

# Extend the DOM with DOM 2 HTML, DOM 2 View, and DOM 2 CSS/Style support

#TODO get rid of as much dependence on pxdom as possible for portability between
# DOM implementations in the future
import pxdom as dom

from cssutils import css

import urlparse, string, re

def parseString(str, uri=''):
    di = getDOMImplementation()
    parser = di.createLSParser(di.MODE_SYNCHRONOUS, None)
    input = di.createLSInput()

    input.stringData = str
    input.systemId= uri
  
    document = HTMLDocument()
    parser.parseWithContext(input, document,
                            parser.ACTION_REPLACE_CHILDREN)


class HTMLDOMImplementation(dom.DOMImplementation):
    """ Add the View, HTML, and CSS/Style (not yet implemented) features """
    def __init__(self):
        self._features['views']       = ['2.0']
        self._features['html']        = ['2.0']
        self._features['stylesheets'] = ['2.0']

    def createDocument(self, namespaceURI, qualifiedName, doctype):
        if namespaceURI=='':
            namespaceURI= None
        document = HTMLDocument()
        if doctype is not None:
            document.appendChild(doctype)
        if qualifiedName is not None:
            root = document.createElementNS(namespaceURI, qualifiedName)
            document.appendChild(root)
        return document

_html_implementation = HTMLDOMImplementation()
                 
def getDOMImplementation(features= ''):
    """ DOM 3 Core hook to get the Implementation object. If features is
    supplied, only return the implementation if all features are satisfied.
    """
    fv = string.split(features, ' ')
    for index in range(0, len(fv)-1, 2):
        if not _html_implementation.hasFeature(fv[index], fv[index+1]):
            return None
    return _html_implementation

def getDOMImplementationList(features= ''):
    """ DOM 3 Core method to get implementations in a list.
    This will be either pxdom's implementation or this extended one
    """
    domimplementation = dom.getDOMImplementation(features)
    htmldomimplementation = getDOMImplementation(features)

    implementationList = DOMImplementationList()
    if domimplementation is not None:
        implementationList._append(domimplementation)
    if htmldomimplementation is not None:
        implementationList._append(htmldomimplementation)
    implementationList.readonly= True
    return implementationList

# Some constants for use below
_KEY  = 0
_TYPE = 1
_PERMISSIONS = 2
class DOMObject:
    def __init__(self, readonly= False):
        self.__dict__['_attr'] = {
            'id':        ['id', 'string', 'rw'],
            'title':     ['title', 'string', 'rw'],
            'lang':      ['lang', 'string', 'rw'],
            'dir':       ['dir', 'string', 'rw'],
            'className': ['class', 'string', 'rw']
        }
        self._readonly= readonly
        self._sub_element = None

    def _get_readonly(self):
        return self._readonly
    def _set_readonly(self, value):
        self._readonly= value
    
    def __getattr__(self, key):
        attr = self._attr.get(key)
        if attr and 'r' in attr[_PERMISSIONS]:
            if attr[_TYPE] == 'string':
                return self.getAttribute(attr[_KEY])
            elif attr[_TYPE] == 'bool':
                return self.hasAttribute(attr[_KEY])
            elif attr[_TYPE] == 'long':
                try:
                    return int(self.getAttribute(attr[_KEY]))
                except ValueError:
                    return 0
            elif attr[_TYPE] == 'local_string':
                return self.__dict__[attr[_KEY]]
            elif attr[_TYPE] == 'local_bool':
                return self.__dict__[attr[_KEY]]
            elif attr[_TYPE] == 'local_long':
                try:
                    return int(self.__dict__[attr[_KEY]])
                except ValueError:
                    return 0
            else:
                return self.getAttribute(attr[_KEY])
        
        if key[:1]=='_':
            raise AttributeError, key
        try:
            getter= getattr(self, '_get_'+key)
        except AttributeError:
            if self._sub_element:
                return getattr(self._sub_element, key)
            raise AttributeError, key
        return getter()

    def __setattr__(self, key, value):
        attr = self._attr.get(key)
        if attr:
            if 'w' in attr[_PERMISSIONS]:
                if attr[_TYPE] == 'string':
                    self.setAttribute(attr[_KEY], value)
                elif attr[_TYPE] == 'bool':
                    if value:
                        self.setAttribute(attr[_KEY], '')
                    else:
                        self.removeAttribute(attr[_KEY])
                elif attr[_TYPE] == 'long':
                    try:
                        val = int(value)
                    except ValueError:
                        val = 0
                    self.setAttribute(attr[_KEY], val)
                elif attr[_TYPE] == 'local_string':
                    self.__dict__[attr[_KEY]] = value
                elif attr[_TYPE] == 'local_bool':
                    if value:
                        self.__dict__[attr[_KEY]] = True
                    else:
                        self.__dict__[attr[_KEY]] = False
                elif attr[_TYPE] == 'local_long':
                    try:
                        val = int(value)
                    except ValueError:
                        val = 0
                    self.__dict__[attr[_KEY]] = val
                else:
                    self.setAttribute(attr[_KEY], value)
            else:
                raise NoModificationAllowedErr(self, key)
            
        if key[:1]=='_' or hasattr(self, key):
            self.__dict__[key]= value
            return
    
        if self._readonly and key not in ('readonly', 'nodeValue',
                                          'textContent'):
            raise NoModificationAllowedErr(self, key)
        try:
            setter= getattr(self, '_set_'+key)
        except AttributeError:
            if hasattr(self, '_get_'+key):
                raise NoModificationAllowedErr(self, key)
            if self._sub_element:
                setattr(self._sub_element, key, value)
            raise AttributeError, key
        setter(value)        

class FilterCollection(dom.NodeListByTagName):
    """ Works just like NodeListByTagName, but rather than just filtering by
    tagName, it takes a list of functions to run the check each node against
    """
    def __init__(self, ownerNode, namespaceURI, *checks):
        dom.NodeListByTagName.__init__(self, ownerNode, namespaceURI, '')
        self._checks = checks

    def _walk(self, element):
        """ Recursively add a node's child elements to the internal node list
        when they match the conditions passed to the constructor
        """
        for childNode in element.childNodes:
            if childNode.nodeType==dom.Node.ELEMENT_NODE:
                passed = True
                for check in self._checks:
                    check_passed = check(childNode)
                    if not check_passed:
                        passed = False
                if passed:
                    self._list.append(childNode)
            if childNode.nodeType in (dom.Node.ELEMENT_NODE,
                                      dom.Node.ENTITY_REFERENCE_NODE):
                self._walk(childNode)

class TableRowCollection(dom.NodeListByTagName):
    """ Works like NodeListByTagName, but gets the rows of a table in
    logical order
    """
    def __init__(self, ownerNode):
        dom.NodeListByTagName.__init__(self, ownerNode, dom.NONS, '')
        self._checks = checks
        
    def _walk(self, element):
        th = element.tHead
        if th:
            self._list.extend(th.rows)
        tbs = element.tBodies
        if tbs.length:
            for tb in tbs:
                self._list.extend(tb.rows)
        tf = element.tFoot
        if tf:
            self._list.extend(tf.rows)

# DOM 2 Views
# -----------
class AbstractView(DOMObject):
    """ Implements the DOM View interface """
    def __init__(self, document):
        DOMObject.__init__(self)
        self._document = document
        self._readonly = True
    def _get_document(self):
        return self._document

# DOM 2 HTML
# ----------

class HTMLCollection(DOMObject):
    def __init__(self, nodelist, html_mode=False):
        DOMObject.__init__(self)
        self._nodelist = nodelist

    def _get_length(self):
        return self._nodelist.length

    def item(self, index):
        return self._nodelist.item(index)

    def namedItem(self, name):
        for elem in self._nodelist:
            if elem.id == name:
                return elem
            if html_mode and elem.getAttribute('name') == name:
                return elem
    # Python-style methods
    #
    def __len__(self):
        return len(self._nodelist)
    
    def __getitem__(self, index):
        return self._nodelist[index]
    
    def __setitem__(self, index, value):
        raise dom.NoModificationAllowedErr(self, 'item(%s)' % str(index))
    
    def __delitem__(self, index):
        raise dom.NoModificationAllowedErr(self, 'item(%s)' % str(index))


class HTMLElement(DOMObject, dom.Element):
    def __init__(self, *args, **kwargs):
        DOMObject.__init__(self)
        dom.Element.__init__(self, *args, **kwargs)
        
    def isSupported(self, feature, version):
        return _html_implementation.hasFeature(feature, version)

    def getFeature(self, feature, version):
        if _html_implementation.hasFeature(feature, version):
            return self
        return None

class _HTMLDisabledElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._disabled = False
    def _get_disabled(self):
        return self._disabled
    def _set_disabled(self, disabled):
        self._disabled = disabled

class _HTMLTextElement(HTMLElement):
    def _get_text(self):
        return self.textContent
    def _set_text(self, text):
        self.textContent = text

class _HTMLFocusBlurElement(HTMLElement):
    def blur(self):
        if self.ownerDocument:
            self.ownerDocument._handler.element_blur(self)

    def focus(self): 
        if self.ownerDocument:
            self.ownerDocument._handler.element_focus(self)

class _HTMLClickElement(HTMLElement):
    def click(self):
        if self.ownerDocument:
            self.ownerDocument._handler.element_click(self)

class _HTMLSelectElement(HTMLElement):
    def select(self): 
        if self.ownerDocument:
            self.ownerDocument._handler.element_select(self)
            

class _HTMLBaseFormElement(HTMLElement):
    def _get_form(self):
        """ Returns the FORM element containing this control. Returns null if
        this control is not within the context of a form. """
        parent = self.parentNode
        while parent and parent.tagName != 'form':
            parent = parent.parentNode
        return parent
           
    def _reset(self):
        pass

class _HTMLFormControlElement(_HTMLBaseFormElement,_HTMLFocusBlurElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)

class _HTMLFormValueElement(_HTMLFormControlElement):
    """ Base class for form controls where value and defaultValue are attributes
    """
    def __init__(self, *args, **kwargs):
        _HTMLFormControlElement.__init__(self,  *args, **kwargs)

    def setAttributeNode(self, attr):
        if attr.name == 'value':
            self.__dict__['defaultValue'] = attr.value
        _HTMLFormControlElement.setAttributeNode(self, attr)
    
    def _reset(self):
        """ Basic function to reset form value """
        self.value = self.defaultValue
        
class HTMLHtmlElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'version': ['version', 'string', 'rw']})

class HTMLHeadElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'profile': ['profile', 'string', 'rw']})

class HTMLLinkElement(_HTMLDisabledElement):
    def __init__(self, *args, **kwargs):
        _HTMLDisabledElement.__init__(self, *args, **kwargs)
        self._attr.update({
            # DOM HTML Attributes
            'charset':  ['charset', 'string', 'rw'],
            'href':     ['href', 'string', 'rw'],
            'hreflang': ['hreflang', 'string', 'rw'],
            'media':    ['media', 'string', 'rw'],
            'rel':      ['rel', 'string', 'rw'],
            'rev':      ['rev', 'string', 'rw'],
            'target':   ['target', 'string', 'rw'],
            'type':     ['type', 'string', 'rw']
            })
        if self.getAttribute('rel') == 'stylesheet':
            self._attr.update({'sheet':     ['_sheet', 'local_string', 'r']})

            if self.getAttribute('type') == 'text/css':
                self._sheet = CSSStyleSheet(self)
            else:
                self._sheet = StyleSheet(self)

class HTMLTitleElement(_HTMLTextElement):
    pass

class HTMLMetaElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'content':   ['content', 'string', 'rw'],
            'httpEquiv': ['http-equiv', 'string', 'rw'],
            'name':      ['name', 'string', 'rw'],
            'scheme':    ['scheme', 'string', 'rw']
            })
    
class HTMLBaseElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'href':     ['href', 'string', 'rw'],
            'target':   ['target', 'string', 'rw'],
            })

class HTMLIsIndexElement(_HTMLBaseFormElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self._attr.update({'prompt': ['prompt', 'string', 'rw']})
    
class HTMLStyleElement(_HTMLDisabledElement):
    def __init__(self, *args, **kwargs):
        _HTMLDisabledElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'media':    ['media', 'string', 'rw'],
            'type':     ['type', 'string', 'rw'],
            # DOM StyleSheet Attributes
            'sheet':     ['_sheet', 'local_string', 'r']
            })
        self._sheet = StyleSheet(self)

class HTMLBodyElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'aLink':         ['alink', 'string', 'rw'],
            'background':    ['background', 'string', 'rw'],
            'bgColor':       ['bgcolor', 'string', 'rw'],
            'link':          ['link', 'string', 'rw'],
            'text':          ['text', 'string', 'rw'],
            'vLink':         ['vlink', 'string', 'rw'],
            })
    
class HTMLFormElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'name':          ['name', 'string', 'rw'],
            'acceptCharset': ['accept-charset', 'string', 'rw'],
            'action':        ['action', 'string', 'rw'],
            'enctype':       ['enctype', 'string', 'rw'],
            'method':        ['method', 'string', 'rw'],
            'target':        ['target', 'string', 'rw']
            })
        
    def _get_elements(self):
        """ Returns a collection of all form control elements in the form. """
        return HTMLCollection(
            FilterCollection(self, dom.NONS,
                             lambda node: node.tagName in
                             ('input', 'button', 'select', 'optgroup',
                              'option', 'textarea', 'isindex', 'fieldset'))
            )
    
    def _get_length(self):
        return self.elements.length

    def submit(self):
        if self.ownerDocument:
            self.ownerDocument._event.form_submit(self)

    def reset(self):
        for element in self.elements:
            element._reset()
        
class HTMLSelectElement(_HTMLFormControlElement):
    def __init__(self, *args, **kwargs):
        _HTMLFormControlElement.__init__(self, *args, **kwargs)        
        self._attr.update({
            'name':     ['name', 'string', 'rw'],
            'disabled': ['disabled', 'bool', 'rw'],
            'multiple': ['multiple', 'bool', 'rw'], 
            'size':     ['size', 'long', 'rw'],
            'tabIndex': ['tabindex', 'long', 'rw']
            })

    def _get_type(self):
        if self.muliple:
            return 'select-multiple'
        return 'select-one'

    def _get_selectedIndex(self):
        options = self.options
        for i in range(0, self.options.length):
            if options[i].selected: return i
        return -1
    def _set_selectedIndex(self, index):
        options = self.options
        for option in options:
            option.selected = False
        options[index].selected = True

    def _get_value(self):
        si = self.selectedIndex
        if si != -1:
            return self.options[si].value
        else: return ''
    def _set_value(self, value):
        pass

    def _get_length(self):
        return self.options.length

    def _get_options(self):
        return self.getElementsByTagName('option')

    def _get_multiple(self):
        return self.hasAttribute('multiple')
    def _set_multiple(self, multiple):
        if multiple:
            self.setAttribute('multiple', '')
        else:
            self.removeAttribute('multiple')

    def add(self, element, before):
        if element.tagName not in ('option', 'optgroup'):
            return
        if before:
            self.insertBefore(element, before)
        else:
            self.appendChild(element)

    def remove(self, index):
        option = self.options.item(index)
        if option:
            self.removeChild(option)

class HTMLOptGroupElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'disabled': ['disabled', 'bool', 'rw'],        
            'label':    ['label', 'string', 'rw'],        
            })

class HTMLOptionElement(_HTMLBaseFormElement,_HTMLTextElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self.defaultSelected = self.hasAttribute('selected')
        self._selected = self.defaultSelected
        self._attr.update({
            'disabled': ['disabled', 'bool', 'rw'],        
            'label':    ['label', 'string', 'rw'],        
            })

    def _reset(self):
        self.selected = self.defaultSelected
        
    def _set_text(self, text):
        raise NoModificationAllowedErr(self, 'text')

    def _get_index(self):
        parent = self.parentNode
        while parent and parent.tagName != 'select':
            parent = parent.parentNode
        if parent:
            options = parent.options
            for i in range(parent.length):
                if options[i] is self:
                    return i
        return None

    def _get_selected(self):
        return self._selected
    def _set_selected(self, selected):
        if selected:
            self._selected = True
        else:
            self._selected = False

    def _get_value(self):
        val = self.getAttributeNode('value')
        if val:
            return val.value
        return self.text
    def _set_value(self, value):
        self.setAttributeNode('value', value)

class HTMLInputElement(_HTMLFormValueElement,_HTMLFocusBlurElement,
                       _HTMLClickElement,_HTMLSelectElement):
    def __init__(self, *args, **kwargs):
        _HTMLFormValueElement.__init__(self, *args, **kwargs)

        self._attr.update({
            'accept':   ['accept', 'string', 'rw'],        
            'accessKey': ['accesskey', 'string', 'rw'],        
            'align':    ['align', 'string', 'rw'],        
            'alt':      ['alt', 'string', 'rw'],
            'checked':  ['_checked', 'local_bool', 'rw'],            
            'disabled': ['disabled', 'bool', 'rw'],
            'maxLength': ['maxlength', 'long', 'rw'],            
            'name':      ['name', 'string', 'rw'],        
            'readOnly':  ['readonly', 'boolean', 'rw'],        
            'size':      ['size', 'long', 'rw'],        
            'src':       ['src', 'string', 'rw'],        
            'tabIndex':  ['tabindex', 'long', 'rw'],        
            'type':      ['type', 'string', 'rw'],        
            'useMap':    ['usemap', 'string', 'rw'],        
            'value':     ['_value', 'local_string', 'rw']
            })
        self.__dict__['defaultChecked'] = False
        self.__dict__['_checked'] = False

    def _reset(self):
        _HTMLFormValueElement._reset(self)
        self.checked = self.defaultChecked

    _attrs_to_catch = {
        'value': ('_value',),
        'checked': ('_checked', 'defaultChecked')
        }
    def setAttributeNode(self, attr):
        tc = self._attrs_to_catch.get(attr.name, None)
        if tc:
            for item in tc:
                self.__dict__[item] = attr.value
            
        _HTMLFormValueElement.setAttributeNode(self, attr)

class HTMLTextAreaElement(_HTMLFormControlElement,_HTMLFocusBlurElement,
                          _HTMLSelectElement):
    def __init__(self, *args, **kwargs):
        _HTMLFormControlElement.__init__(self, *args, **kwargs)
        self.defaultValue = self.textContent
        self.value = self.defaultValue

        self._attr.update({
            'accessKey': ['accesskey', 'string', 'rw'],        
            'cols':     ['cols', 'long', 'rw'],        
            'disabled': ['disabled', 'bool', 'rw'],
            'name':      ['name', 'string', 'rw'],        
            'readOnly':  ['readonly', 'boolean', 'rw'],        
            'rows':      ['rows', 'long', 'rw'],        
            'tabIndex':  ['tabindex', 'long', 'rw'],        
            'type':      ['type', 'string', 'rw'],        
            })
        
    def _reset(self):
        """ Basic function to reset form value """
        self.value = self.defaultValue
        
    def _get_type(self):
        return 'textarea'

class HTMLButtonElement(_HTMLBaseFormElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'accessKey': ['accesskey', 'string', 'rw'],        
            'disabled': ['disabled', 'bool', 'rw'],
            'name':     ['name', 'string', 'rw'],        
            'tabIndex': ['tabindex', 'long', 'rw'],        
            'type':     ['type', 'string', 'r'],
            'value':    ['value', 'string', 'rw']
            })
    
class HTMLLabelElement(_HTMLBaseFormElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'accessKey': ['accesskey', 'string', 'rw'],        
            'htmlFor':  ['for', 'string', 'rw']
            })

class HTMLFieldSetElement(_HTMLBaseFormElement):pass

class HTMLLegendElement(_HTMLBaseFormElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'accessKey': ['accesskey', 'string', 'rw'],        
            'align':    ['align', 'string', 'rw']
            })    

class HTMLULstElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'compact': ['compact', 'bool', 'rw'],        
            'type':    ['type', 'string', 'rw']
            })

class HTMLOLstElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'compact': ['compact', 'bool', 'rw'],
            'start':   ['start', 'long', 'rw'],
            'type':    ['type', 'string', 'rw']
            })
        
class HTMLDListElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'compact': ['compact', 'bool', 'rw']})

class HTMLDirectoryElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'compact': ['compact', 'bool', 'rw']})

class HTMLMenuElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'compact': ['compact', 'bool', 'rw']})

class HTMLLIElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'type':  ['type', 'string', 'rw'],
            'value': ['value', 'long', 'rw']
            })

class HTMLDivElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'align': ['align', 'string', 'rw']})

class HTMLParagraphElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'align': ['align', 'string', 'rw']})

class HTMLHeadingElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'align': ['align', 'string', 'rw']})

class HTMLQuoteElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'cite': ['cite', 'string', 'rw']})
        
class HTMLPreElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'width': ['width', 'long', 'rw']})

class HTMLBRElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'clear': ['clear', 'string', 'rw']})
        
class HTMLBaseFontElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'color':  ['color', 'string', 'rw'],
            'face':   ['face', 'string', 'rw'],
            'size':   ['size', 'long', 'rw']
            })
        
class HTMLFontElement(HTMLBaseFontElement):pass

class HTMLHRElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'align':   ['align', 'string', 'rw'],
            'noShade': ['noshade', 'boolean', 'rw'],
            'size':    ['size', 'string', 'rw'],
            'width':   ['width', 'string', 'rw']
            })
        
class HTMLModElement(HTMLElement):
   def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'cite':     ['cite', 'string', 'rw'],
            'dateTime': ['datetime', 'string', 'rw']
            })
        
class HTMLAnchorElement(_HTMLFocusBlurElement):
    def __init__(self, *args, **kwargs):
        _HTMLFocusBlurElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'accessKey': ['accesskey', 'string', 'rw'],
            'charset':   ['charset', 'string', 'rw'],
            'coords':    ['coords', 'string', 'rw'],
            'href':      ['href', 'string', 'rw'],
            'hreflang':  ['hreflang', 'string', 'rw'],
            'name':      ['name', 'string', 'rw'],
            'rel':       ['rel', 'string', 'rw'],
            'rev':       ['rev', 'string', 'rw'],
            'shape':     ['shape', 'string', 'rw'],
            'tabIndex':  ['tabindex', 'long', 'rw'],
            'target':    ['target', 'string', 'rw'],
            'type':      ['type', 'string', 'rw']
            })
        
class HTMLImageElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'name':     ['name', 'string', 'rw'],
            'align':    ['align', 'string', 'rw'],
            'alt':      ['alt', 'string', 'rw'],
            'border':   ['border', 'string', 'rw'],
            'height':   ['height', 'long', 'rw'],
            'hspace':   ['hspace', 'long', 'rw'],
            'isMap':    ['ismap', 'bool', 'rw'],
            'longDesc': ['longdesc', 'string', 'rw'],
            'src':      ['src', 'string', 'rw'],
            'useMap':   ['usemap', 'string', 'rw'],
            'vspace':   ['vspace', 'long', 'rw'],
            'width':    ['width', 'long', 'rw']
            })
        
class HTMLObjectElement(_HTMLBaseFormElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'code':     ['code', 'string', 'rw'],
            'align':    ['align', 'string', 'rw'],
            'archive':  ['archive', 'string', 'rw'],
            'border':   ['border', 'string', 'rw'],
            'codeBase': ['codebase', 'string', 'rw'],
            'codeType': ['codetype', 'string', 'rw'],
            'data':     ['data', 'string', 'rw'],
            'declare':  ['declare', 'bool', 'rw'],
            'height':   ['height', 'string', 'rw'],
            'hspace':   ['hspace', 'long', 'rw'],
            'name':     ['name', 'string', 'rw'],
            'standby':  ['standby', 'string', 'rw'],
            'tabIndex': ['tabindex', 'long', 'rw'],
            'type':     ['type', 'string', 'rw'],
            'useMap':   ['usemap', 'string', 'rw'],
            'vspace':   ['vspace', 'long', 'rw'],
            'width':    ['width', 'long', 'rw']
            })
        self._contentDocument = None
        
    def _get_contentDocument(self):
        return self._contentDocument
        
class HTMLParamElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'name':      ['name', 'string', 'rw'],
            'type':      ['type', 'string', 'rw'],
            'value':     ['value', 'string', 'rw'],
            'valueType': ['valuetype', 'string', 'rw']
            })
        
class HTMLAppletElement         (HTMLElement):
    def __init__(self, *args, **kwargs):
        _HTMLBaseFormElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'align':    ['align', 'string', 'rw'],
            'alt':      ['alt', 'string', 'rw'],
            'archive':  ['archive', 'string', 'rw'],
            'code':     ['code', 'string', 'rw'],
            'codeBase': ['codebase', 'string', 'rw'],
            'height':   ['height', 'string', 'rw'],
            'hspace':   ['hspace', 'long', 'rw'],
            'name':     ['name', 'string', 'rw'],
            'object':   ['object', 'string', 'rw'],
            'vspace':   ['vspace', 'long', 'rw'],
            'width':    ['width', 'long', 'rw']
            })

class HTMLMapElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'name': ['name', 'string', 'rw']})

    def _get_areas(self):
        return self.getElementsByTagName('area')
        
class HTMLAreaElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'accessKey': ['accesskey', 'string', 'rw'],
            'alt':       ['alt', 'string', 'rw'],
            'coords':    ['coords', 'string', 'rw'],
            'href':      ['href', 'string', 'rw'],
            'noHref':    ['nohref', 'bool', 'rw'],
            'shape':     ['shape', 'string', 'rw'],
            'tabIndex':  ['tabindex', 'long', 'rw'],
            'target':    ['target', 'string', 'rw']
            })
        
class HTMLScriptElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'text':    ['text', 'string', 'rw'],
            'htmlFor': ['for', 'string', 'rw'],
            'event':   ['event', 'string', 'rw'],
            'charset': ['charset', 'string', 'rw'],
            'defer':   ['defer', 'bool', 'rw'],
            'src':     ['src', 'string', 'rw'],
            'type':    ['type', 'string', 'rw']
            })
        
class HTMLTableElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'align':       ['align', 'string', 'rw'],
            'bgColor':     ['bgcolor', 'string', 'rw'],
            'border':      ['border', 'string', 'rw'],
            'cellPadding': ['cellpadding', 'string', 'rw'],
            'cellSpacing': ['cellspacing', 'bool', 'rw'],
            'frame':       ['frame', 'string', 'rw'],
            'rules':       ['rules', 'string', 'rw'],
            'summary':     ['summary', 'string', 'rw'],
            'width':       ['width', 'string', 'rw']
            })

    def _get_caption(self):
        caps = self.getElementsByTagName('caption')
        if caps.length > 0:
            return caps[0]
        return None
    def _set_caption(self, cap):
        if cap.tagName != 'caption':
            raise HierarchyRequestErr(self, cap)

        oldcap = self.caption
        if oldcap:
            self.replaceChild(cap, oldcap)
        else:
            self.appendChild(cap)

    def _get_tHead(self):
        ths = self.getElementsByTagName('thead')
        if ths.length > 0:
            return ths[0]
        return None
    def _set_tHead(self, th):
        if th.tagName != 'thead':
            raise HierarchyRequestErr(self, th)

        oldth = self.tHead
        if oldth:
            self.replaceChild(th, oldth)
        else:
            self.appendChild(th)        

    def _get_tFoot(self):
        tfs = self.getElementsByTagName('tfoot')
        if tfs.length > 0:
            return tfs[0]
        return None
    def _set_tFoot(self, tf):
        if tf.tagName != 'tfoot':
            raise HierarchyRequestErr(self, tf)

        oldtf = self.tFoot
        if oldtf:
            self.replaceChild(tf, oldtf)
        else:
            self.appendChild(tf)

    def _get_rows(self):
        return HTMLCollection(TableRowCollection(self))

    def _get_tBodies(self):
        return self.getElementsByTagName('tbody')

    def createTHead(self):
        th = self.tHead
        if th:
            return th
        th = self.ownerDocument.createElement('thead')
        self.insertBefore(th, self.firstChild)
        return th
    def deleteTHead(self):
        th = self.tHead
        if th:
            self.removeChild(th)

    def createTFoot(self):
        tf = self.tFoot
        if tf:
            return tf
        tf = self.ownerDocument.createElement('tfoot')
        self.appendChild(tf)
        return tf
    def deleteTFoot(self):
        tf = self.tFoot
        if tf:
            self.removeChild(tf)

    def createCaption(self):
        cap = self.caption
        if cap:
            return cap
        cap = self.ownerDocument.createElement('caption')
        self.appendChild(cap)
        return cap
    def deleteCaption(self):
        cap = self.caption
        if cap:
            self.removeChild(cap)

    def insertRow(self, index):
        rows = self.rows
        if index > rows.length:
            raise dom.IndexSizeErr(rows, index)
        oldrow = rows.item(index)
        newrow = self.ownerDocument.createElement('tr')
        self.insertBefore(newrow, oldrow)
        return newrow

    def deleteRow(self, index):
        oldrow = self.rows.item(index)
        if not oldrow:
            raise dom.IndexSizeErr(self.rows, index)
        self.removeChild(oldrow)
            
class HTMLTableCaptionElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({'align': ['align', 'string', 'rw']})
        
class HTMLTableColElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'align':  ['align', 'string', 'rw'],
            'ch':     ['char', 'string', 'rw'],
            'chOff':  ['charoff', 'string', 'rw'],
            'span':   ['span', 'long', 'rw'],
            'vAlign': ['valign', 'string', 'rw'],
            'width':  ['width', 'string', 'rw']
            })
        
class HTMLTableSectionElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'align':  ['align', 'string', 'rw'],
            'ch':     ['char', 'string', 'rw'],
            'chOff':  ['charoff', 'string', 'rw'],
            'vAlign': ['valign', 'string', 'rw']
            })

    def _get_rows(self):
        return self.getElementsByTagName('tr')

    def insertRow(self, index):
        rows = self.rows
        if index > rows.length:
            raise dom.IndexSizeErr(rows, index)
        oldrow = rows.item(index)
        newrow = self.ownerDocument.createElement('tr')
        self.insertBefore(newrow, oldrow)
        return newrow

    def deleteRow(self, index):
        oldrow = self.rows.item(index)
        if not oldrow:
            raise dom.IndexSizeErr(self.rows, index)
        self.removeChild(oldrow)


def _up_to(self, elements):
    """ Goes up the document tree until it finds one of the elements in
    elements and returns that element
    """
    parent = self.parentNode
    while parent and parent.tagName not in elements:
        parent = parent.parentNode
    return parent
def _find_self(self, list):
    """ Find ourselves in a list, returns our index"""
    for i in range(list.length):
        if list[i] is self:
            return i

class HTMLTableRowElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'align':   ['align', 'string', 'rw'],
            'bgColor': ['bgcolor', 'string', 'rw'],
            'ch':      ['char', 'string', 'rw'],
            'chOff':   ['charoff', 'string', 'rw'],
            'vAlign':  ['valign', 'string', 'rw'],
            })

    def _get_rowIndex(self):
        table = _up_to(self, ('table',))
        index = _find_self(self, table.rows)
        return index

    def _get_sectionRowIndex(self):
        section = _up_to(self, ('thead', 'tbody', 'tfoot'))
        index = _find_self(self, section.rows)
        return index

    def _get_cells(self):
        return HTMLCollection(FilterCollection(self, dom.NONS,
                                               lambda node:
                                               node.tagName in ('th', 'td')))

    def insertCell(self, index):
        cells = self.cells
        if index > cells.length or index < -1:
            raise dom.IndexSizeErr(cells, index)
        oldcell = cells.item(index)
        newcell = self.ownerDocument.createElement('td')
        self.insertBefore(newcell, oldcell)
        return newcell
          
    def deleteCell(self, index):
        oldcell = self.cells.item(index)
        if not oldcell:
            raise dom.IndexSizeErr(self.cells, index)
        self.removeChild(oldcell)      
        
class HTMLTableCellElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'abbr':    ['abbr', 'string', 'rw'],
            'align':   ['align', 'string', 'rw'],
            'axis':    ['axis', 'string', 'rw'],
            'bgColor': ['bgcolor', 'string', 'rw'],
            'ch':      ['char', 'string', 'rw'],
            'chOff':   ['charoff', 'string', 'rw'],
            'colSpan': ['colspan', 'long', 'rw'],
            'headers': ['headers', 'string', 'rw'],
            'height':  ['height', 'string', 'rw'],
            'noWrap':  ['nowrap', 'bool', 'rw'],
            'rowSpan': ['rowspan', 'long', 'rw'],
            'scope':   ['scope', 'string', 'rw'],
            'vAlign':  ['valign', 'string', 'rw'],
            'width':   ['width', 'string', 'rw']
            })
        
    def _get_cellIndex(self):
        row = _up_to(self, ('tr'))
        index = _find_self(self, row.cells)
        return index
        
class HTMLFrameSetElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'cols': ['cols', 'string', 'rw'],
            'rows': ['rows', 'string', 'rw']
            })
        
class HTMLFrameElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'contentDocument':  ['_contentDocument', 'local_string', 'r'],
            'frameBorder':      ['frameborder', 'string', 'rw'],
            'longDesc':         ['longdesc', 'string', 'rw'],
            'marginHeight':     ['marginheight', 'string', 'rw'],
            'marginWidth':      ['marginwidth', 'string', 'rw'],
            'name':             ['name', 'string', 'rw'],
            'noResize':         ['noresize', 'bool', 'rw'],
            'scrolling':        ['scrolling', 'string', 'rw'],
            'src':              ['src', 'string', 'rw']
            })
        self._contentDocument = None

class HTMLIFrameElement(HTMLElement):
    def __init__(self, *args, **kwargs):
        HTMLElement.__init__(self, *args, **kwargs)
        self._attr.update({
            'contentDocument':  ['_contentDocument', 'local_string', 'r'],
            'align':            ['align', 'string', 'rw'],
            'frameBorder':      ['frameborder', 'string', 'rw'],
            'height':           ['height', 'string', 'rw'],
            'longDesc':         ['longdesc', 'string', 'rw'],
            'marginHeight':     ['marginheight', 'string', 'rw'],
            'marginWidth':      ['marginwidth', 'string', 'rw'],
            'name':             ['name', 'string', 'rw'],
            'scrolling':        ['scrolling', 'string', 'rw'],
            'src':              ['src', 'string', 'rw'],
            'width':            ['width', 'string', 'rw']
            })
        self._contentDocument = None


# These elements are implemented with the base HTMLElement class
BASE_HTML_ELEMENTS = set([
    'sub', 'sup', 'span', 'bdo', 'tt', 'i', 'b', 'u', 's', 'strike', 'big',
    'small', 'em', 'strong', 'dfn', 'code', 'samp', 'kbd', 'var', 'cite',
    'acronym', 'abbr', 'dd', 'dt', 'noframes', 'noscript', 'address', 'center'
    ])
# These elements are specialized subclasses of HTMLElement
EXTENDED_HTML_ELEMENTS = {
    'html': HTMLHtmlElement, 'head': HTMLHeadElement, 'link': HTMLLinkElement,
    'title': HTMLTitleElement, 'meta': HTMLMetaElement, 'base': HTMLBaseElement,
    'isindex': HTMLIsIndexElement, 'style': HTMLStyleElement,
    'body': HTMLBodyElement, 'form': HTMLFormElement,
    'select': HTMLSelectElement, 'optgroup': HTMLOptGroupElement,
    'option': HTMLOptionElement, 'input': HTMLInputElement,
    'textarea': HTMLTextAreaElement, 'button': HTMLButtonElement,
    'label': HTMLLabelElement, 'fieldset': HTMLFieldSetElement,
    'legend': HTMLLegendElement, 'ul': HTMLULstElement,
    'ol': HTMLOLstElement, 'dl': HTMLDListElement,
    'dir': HTMLDirectoryElement, 'menu': HTMLMenuElement, 'li': HTMLLIElement,
    'div': HTMLDivElement, 'p': HTMLParagraphElement,
    # headers
    'h1': HTMLHeadingElement, 'h2': HTMLHeadingElement,
    'h3': HTMLHeadingElement, 'h4': HTMLHeadingElement,
    'h5': HTMLHeadingElement, 'h6': HTMLHeadingElement,
    'q': HTMLQuoteElement, 'blockquote':HTMLQuoteElement, 'pre': HTMLPreElement,
    'br': HTMLBRElement, 'basefont': HTMLBaseFontElement,
    'font': HTMLFontElement, 'hr': HTMLHRElement,
    'ins': HTMLModElement, 'del': HTMLModElement,
    'a': HTMLAnchorElement, 'img': HTMLImageElement,
    'object': HTMLObjectElement, 'param': HTMLParamElement,
    'applet': HTMLAppletElement, 'map': HTMLMapElement, 'area': HTMLAreaElement,
    'script': HTMLScriptElement,
    # table stuff
    'table': HTMLTableElement,'caption': HTMLTableCaptionElement,
    'col': HTMLTableColElement, 'thead': HTMLTableSectionElement,
    'tfoot': HTMLTableSectionElement, 'tbody': HTMLTableSectionElement,
    'tr': HTMLTableRowElement, 'td': HTMLTableCellElement,
    #frame stuff
    'frameset': HTMLFrameSetElement, 'frame': HTMLFrameElement,
    'iframe': HTMLIFrameElement
    }

def _lookup_html_element(tagName):
    if tagName in BASE_HTML_ELEMENTS:
        return HTMLElement
    if tagName in EXTENDED_HTML_ELEMENTS:
        return EXTENDED_HTML_ELEMENTS[tagName]
    return HTMLElement


def _copy_and_extend(source_node, dest_node, owner_document):
    """ Walk through the DOM tree of the provided source_node and copy the whole
    structure into the dest_node. Also take any HTML-specific elements found and
    extend them into their HTML-specific version before copying
    """
    for childNode in source_node.childNodes:
        newChildNode = owner_document.createElement(childNode.tagName)
        dest_node.appendChild(newChildNode)
        _copy_and_extend(childNode, newChildNode, owner_document)

#        if self._current_node.childNodes:
#            self._current_node = self._current_node.firstChild
#        else:
#            old_node = self._current_node # backup in case there's no next
#            
#            while (not self._current_node.nextSibling and
#                   self._current_node.parentNode):
#                self._current_node = self._current_node.parentNode
#            if not self._current_node.nextSibling:
#                self._current_node = old_node
#                return None
#            self._current_node = self._current_node.nextSibling
#        elem = self._current_node
#        elem._computed_style = self._document.defaultView.getComputedStyle(
#            elem, None)
#        return elem

class _HTMLEventHandler:
    def __init__(self):
        self._handlers = {}
    def __getattr__(self, key):
        return self._handlers.get(key, lambda x: None)
   
class HTMLDocument(dom.Document):
    """ Implements the DOM HTMLDocument interface
    and the DOM DocumentStyle interface
    """
    
    def __init__(self, document=None, uri='', referrer=''):
        """ Initialize the HTMLDocument from an existing Document """
        dom.Document.__init__(self)

        self._handler = _HTMLEventHandler()

        self._styleSheets = StyleSheetList(self)

        self._referrer = referrer

        if document:
            # copy the original document
            document._cloneTo(self)
            self._documentURI = self._documentURI or uri

            # Convert the DOM over to HTML and copy children over
            _copy_and_extend(document, self, self)

    def _get_defaultView(self):
        return ViewCSS(self)

    def _get_styleSheets(self):
        return self._styleSheets

    def _get_implementation(self):
        return _html_implementation

    def isSupported(self, feature, version):
        return _html_implementation.hasFeature(feature, version)

    def getFeature(self, feature, version):
        if _html_implementation.hasFeature(feature, version):
            return self
        return None

    def createElement(self, tagName):
        element = _lookup_html_element(tagName)(self, dom.NONS, tagName, None)
        element._setDefaultAttributes()
        return element
    
    def createElementNS(self, namespaceURI, qualifiedName):
        if namespaceURI=='':
            namespaceURI= None
        dom._checkName(qualifiedName)
        prefix, localName= dom._splitName(qualifiedName)
        if (
            localName is None or
            namespaceURI is None and prefix is not None or
            prefix=='xml' and namespaceURI!=dom.XMNS or
            (namespaceURI==dom.NSNS) != ('xmlns' in (prefix, qualifiedName))
        ):
            raise NamespaceErr(qualifiedName, namespaceURI)
        element = _lookup_html_element(localName)(self, namespaceURI,
                                                  localName, prefix)
        element._setDefaultAttributes()
        return element

    def _get_title(self):
        title_elem = self.getElementsByTagName('title')
        if title_elem.length == 0: return ''
        return title_elem[0].text
    def _set_title(self, text):
        title_elem = self.getElementsByTagName('title')
        if title_elem.length == 0: return
        title_elem[0].text = text

    def _get_referrer(self):
        return self._referrer

    def _get_domain(self):
        return urlparse.urlsplit(self._documentURI).hostname

    def _get_URL(self):
        return self._documentURI

    def _get_body(self):
        e = self.getElementsByTagName('body')
        if e.length is 0:
            e = self.getElementsByTagName('frameset')
        return e[0]
    def _set_body(self, new_body):
        old_body = self._get_body()
        self.replaceChild(new_body, old_body)

    def _get_images(self):
        return HTMLCollection(self.getElementsByTagName('img'))

    def _get_applets(self):
        """ A collection of all the OBJECT elements that include applets and
        APPLET (depricated) elements in a document """
        return HTMLCollection(
            FilterCollection(self, dom.NONS,
                             lambda node:
                             node.tagName == 'applet' or
                             (node.tagName == 'object' and
                              node.getElementsByTagName.length > 0)
                             )
            )

    def _get_links(self):
        """ A collection of all AREA elements and anchor (A) elements in a
        document with a value for the href attribute. """
        return HTMLCollection(
            FilterCollection(self, dom.NONS,
                             lambda node:
                             (node.tagName == 'area' or
                              node.tagName == 'a') and
                             node.href != ''
                             )
            )

    def _get_forms(self):
        return HTMLCollection(self.getElementsByTagName('form'))

    def _get_anchors(self):
        return HTMLCollection(
            FilterCollection(self, dom.NONS,
                             lambda node:
                             node.tagName == 'a' and
                             node.name != ''
                             )
            )

    def set_handler(self, key, handler):
        self._handler._handlers[key] = handler

    def _get_cookie(self):
        return self._handler.cookie_read(None) or ''
    def _set_cookie(self, cookie):
        return self._handler.cookie_write(cookie)

    def open(self):
        self._open = True
        self._write_document = ''

    def close(self):
        self._open = False
        self.pxdomContent = self._write_document

    def write(self, text):
        if self._open:
            self._write_document += text

    def writeln(self, text):
        if self._open:
            self._write_document += text + "\n"

    def getElementsByTagNameNS(self, ns, name):
        """ Wrap the Document's implementation to add the namedItem function """
        return HTMLCollection(
            dom.Document.getElementsByTagNameNS(self, ns, name))

    def getElementsByName(self, name):
        return HTMLCollection(
            FilterCollection(self, dom.NONS,
                             lambda node:
                             hasattr(node, 'name') and node.name == name)
            )

# DOM 2 Style Sheets
# ------------------

class StyleSheet(DOMObject):
    def __init__(self, ownerNode, parentSheet=None):
        DOMObject.__init__(self)

        self._ownerNode = ownerNode
        self._parentStyleSheet = parentSheet
        self._disabled = False
        
        self._attr.update({
            'disabled':         ['_disabled', 'local_bool', 'rw'],
            'ownerNode':        ['ownerNode', 'local_string', 'r'],
            'parentStyleSheet': ['parentStypeSheet', 'local_string', 'r'],

            'media':             ['_media', 'local_string', 'r']
            })
        # We only ever need a single instance of this MediaList
        if self._ownerNode:
            media = self._ownerNode.media
        else:
            media = self._parentStyleSheet.media
        self._media = MediaList(media)
        
    def _get_type(self):
        if self._ownerNode:
            return self._ownerNode.type
        return self._parentStyleSheet.type

    def _get_href(self):
        if self._ownerNode and self._ownerNode.tagName != 'style':
            return self._ownerNode.href
        return None

    def _get_title(self):
        if self._ownerNode:
            return self._ownerNode.title
        return None

class StyleSheetList(DOMObject):
    def __init__(self, document):
        DOMObject.__init__(self)
        self._document = document
        self._sequence = None

    # The following two methods make sure the list is always accurate
    def _check(self):
        if self._sequence != self._document._sequence:
            self._regen_list()
            self._sequence = self._document._sequence

    def _regen_list(self):
        elems = FilterCollection(self._document, dom.NONS,
                                 lambda node:
                                 node.tagName in ('link', 'style'))
        self._list = []
        for elem in elems:
            self._list.append(elem.sheet)

    def _get_length(self):
        self._check()
        return self._list.length

    def item(self, index):
        self._check()
        return self._list.get(index)

class MediaList(DOMObject):
    _allowed_media = ['screen', 'tty', 'tv', 'projection', 'handheld', 'print',
                      'braile', 'aural', 'all']
    def __init__(self, mediastring):
        """ Take mediastring and set the internal media list according to the
        rules at http://www.w3.org/TR/1998/REC-html40-19980424/types.html#h-6.13
        """
        DOMObject.__init__(self)
        self._mediaText = mediastring
        self._parse()

    def _parse(self):
        medialist = self._mediaText.split(',')
        regex = re.compile('^[^-a-zA-Z0-9]')
        for i in range(len(medialist)):
            value = medialist[i].strip()
            mo = regex.match(value)
            if mo:
                medialist[i] = mo.group()
            else:
                medialist[i] = None
        self._medialist = filter(lambda item:
                                 item in self._allowed_media, medialist)
        self._mediaText = ', '.join(self._medialist)

    def _get_length(self):
        return self._medialist.length

    def item(self, index):
        return self._medialist.get(index)

    def deleteMedium(self, oldmedium):
        if self._readonly:
            raise dom.NoModificationAllowedErr(self, 'list')
        if not oldmedium in self._medialist:
            raise dom.NotFoundErr(self, None, oldmedium)

        self._medialist.remove(oldmedium)

    def appendMedium(self, newmedium):
        if self._readonly:
            raise dom.NoModificationAllowedErr(self, 'list')
        if newmedium not in self._allowed_media:
            return
        if newmedium in self._medialist:
            self.deleteMedium(newmedium)
        self._medialist.append(newmedium)

        
# DOM 2 CSS
# ---------

#class CSSStyleSheet(StyleSheet):
#    """ Wrapper around cssutils.css.StyleSheet """
#    def __init__(self, ownerNode, parentSheet):
#        StyleSheet.__init__(self, ownerNode, parentSheet)
#        self._sub_element = css.CSSStyleSheet(

class ViewCSS(AbstractView):
    def getComputedStyle(elt, psuedoElt):
        """ Return a CSSStyleDeclaration with the computed style of the element
        (or psuedo element if psuedoElt is not None)

        This is just a dummy version for now which returns the very minimum
        basic styles.
        """
        return css.CSSStyleDeclaration(cssText =
                                       """
                                       position: static;
                                       display: inline;
                                       visibility: visible;
                                       z-index: auto;
                                       overflow: visible;
                                       white-space: normal;
                                       clip: auto;
                                       float: none;
                                       clear: none;

                                       width: auto;
                                       height: auto;
                                       top: auto;
                                       right: auto;
                                       bottom: auto;
                                       left: auto;
                                       
                                       margin-top:    0px;
                                       margin-bottom: 0px;
                                       margin-right:  0px;
                                       margin-left:   0px;
                                       
                                       padding-top:    0px;
                                       padding-bottom: 0px;
                                       padding-right:  0px;
                                       padding-left:   0px;

                                       border-top-width:    0px;
                                       border-bottom-width: 0px;
                                       border-right-width:  0px;
                                       border-left-width:   0px;
                                       
                                       border-top-color:    #000000;
                                       border-bottom-color: #000000;
                                       border-right-color:  #000000;
                                       border-left-color:   #000000;
                                       
                                       border-top-style:    none;
                                       border-bottom-style: none;
                                       border-right-style:  none;
                                       border-left-style:   none;

                                       """
                                       )
