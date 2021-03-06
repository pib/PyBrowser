"""CSSCharsetRule implements DOM Level 2 CSS CSSCharsetRule.

TODO:
    - check specific allowed syntaxes
    - check encoding syntax and not codecs.lookup?
"""
__all__ = ['CSSCharsetRule']
__docformat__ = 'restructuredtext'
__author__ = '$LastChangedBy: cthedot $'
__date__ = '$LastChangedDate: 2007-10-20 20:05:47 +0200 (Sa, 20 Okt 2007) $'
__version__ = '$LastChangedRevision: 541 $'

import codecs
import xml.dom
import cssrule
import cssutils

class CSSCharsetRule(cssrule.CSSRule):
    """
    The CSSCharsetRule interface represents an @charset rule in a CSS style
    sheet. The value of the encoding attribute does not affect the encoding
    of text data in the DOM objects; this encoding is always UTF-16
    (also in Python?). After a stylesheet is loaded, the value of the
    encoding attribute is the value found in the @charset rule. If there
    was no @charset in the original document, then no CSSCharsetRule is
    created. The value of the encoding attribute may also be used as a hint
    for the encoding used on serialization of the style sheet.

    The value of the @charset rule (and therefore of the CSSCharsetRule)
    may not correspond to the encoding the document actually came in;
    character encoding information e.g. in an HTTP header, has priority
    (see CSS document representation) but this is not reflected in the
    CSSCharsetRule.

    Properties
    ==========
    cssText: of type DOMString
        The parsable textual representation of this rule
    encoding: of type DOMString
        The encoding information used in this @charset rule.

    Inherits properties from CSSRule

    Format
    ======
    charsetrule:
        CHARSET_SYM S* STRING S* ';'

    BUT: Only valid format is:
        @charset "ENCODING";
    """
    type = cssrule.CSSRule.CHARSET_RULE

    def __init__(self, encoding=None, readonly=False):
        """
        encoding:
            a valid character encoding
        readonly:
            defaults to False, not used yet

        if readonly allows setting of properties in constructor only
        """
        super(CSSCharsetRule, self).__init__()

        self._encoding = None
        if encoding:
            self.encoding = encoding

        self._readonly = readonly

    def _getEncoding(self):
        """ returns encoding as a string """
        return self._encoding

    def _setEncoding(self, encoding):
        """
        DOMException on setting

        - NO_MODIFICATION_ALLOWED_ERR: (CSSRule)
          Raised if this encoding rule is readonly.
        - SYNTAX_ERR: (self)
          Raised if the specified encoding value has a syntax error and
          is unparsable.
          Currently only valid Python encodings are allowed.
        """
        self._checkReadonly()
        tokenizer = self._tokenize2(encoding)
        encodingtoken = self._nexttoken(tokenizer)
        unexpected = self._nexttoken(tokenizer)

        valid = True
        if not encodingtoken or unexpected or\
           self._prods.IDENT != self._type(encodingtoken):
            valid = False
            self._log.error(
                'CSSCharsetRule: Syntax Error in encoding value %r.' %
                      encoding)
        else:
            try:
                codecs.lookup(encoding)
            except LookupError:
                valid = False
                self._log.error('CSSCharsetRule: Unknown (Python) encoding %r.' %
                          encoding)
            else:
                self._encoding = encoding.lower()
        self.valid = valid

    encoding = property(_getEncoding, _setEncoding,
        doc="(DOM)The encoding information used in this @charset rule.")


    def _getCssText(self):
        """returns serialized property cssText"""
        return cssutils.ser.do_CSSCharsetRule(self)

    def _setCssText(self, cssText):
        """
        DOMException on setting

        - SYNTAX_ERR: (self)
          Raised if the specified CSS string value has a syntax error and
          is unparsable.
        - INVALID_MODIFICATION_ERR: (self)
          Raised if the specified CSS string value represents a different
          type of rule than the current one.
        - HIERARCHY_REQUEST_ERR: (CSSStylesheet)
          Raised if the rule cannot be inserted at this point in the
          style sheet.
        - NO_MODIFICATION_ALLOWED_ERR: (CSSRule)
          Raised if the rule is readonly.
        """
        super(CSSCharsetRule, self)._setCssText(cssText)

        valid = True
        tokenizer = self._tokenize2(cssText)
        
        atkeyword = self._tokenvalue(self._nexttoken(tokenizer))        
        if u'@charset ' != atkeyword: 
            valid = False
            self._log.error(u'CSSCharsetRule must start with "@charset "',
                            error=xml.dom.InvalidModificationErr)
        
        encodingtoken = self._nexttoken(tokenizer)
        encodingtype, encoding = self._type(encodingtoken), self._tokenvalue(
                                                            encodingtoken)
        if 'STRING' != encodingtype or len(encoding) < 3:
            valid = False
            self._log.error(u'CSSCharsetRule: no encoding found.')
        else:
            encoding = encoding[1:-1] # remove "..." or '...'
            
        semicolon = self._tokenvalue(self._nexttoken(tokenizer))
        EOFtype = self._type(self._nexttoken(tokenizer))
        if u';' != semicolon or (EOFtype and 'EOF' != EOFtype):
            valid = False
            self._log.error(u'CSSCharsetRule: Syntax Error: %r.' % 
                            self._valuestr(cssText))
        
        self.valid = valid
        if valid:
            self.encoding = encoding
            
    cssText = property(fget=_getCssText, fset=_setCssText,
        doc="(DOM) The parsable textual representation.")

    def __repr__(self):
        return "cssutils.css.%s(encoding=%r)" % (
                self.__class__.__name__, self.encoding)

    def __str__(self):
        return "<cssutils.css.%s object encoding=%r at 0x%x>" % (
                self.__class__.__name__, self.encoding, id(self))
