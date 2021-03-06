"""Selector is a single Selector of a CSSStyleRule SelectorList.

Partly implements
    http://www.w3.org/TR/css3-selectors/

TODO
    - .contains(selector)
    - .isSubselector(selector)

    - ??? CSS2 gives a special meaning to the comma (,) in selectors.
        However, since it is not known if the comma may acquire other
        meanings in future versions of CSS, the whole statement should be
        ignored if there is an error anywhere in the selector, even though
        the rest of the selector may look reasonable in CSS2.

        Illegal example(s):

        For example, since the "&" is not a valid token in a CSS2 selector,
        a CSS2 user agent must ignore the whole second line, and not set
        the color of H3 to red:
"""
__all__ = ['Selector']
__docformat__ = 'restructuredtext'
__author__ = '$LastChangedBy: cthedot $'
__date__ = '$LastChangedDate: 2007-12-25 21:53:11 +0100 (Di, 25 Dez 2007) $'
__version__ = '$LastChangedRevision: 723 $'

import xml.dom

import cssutils

class Selector(cssutils.util.Base):
    """
    (cssutils) a single selector in a SelectorList of a CSSStyleRule

    Properties
    ==========
    selectorText
        textual representation of this Selector
    prefixes
        a set which prefixes have been used in this selector
    seq
        sequence of Selector parts including comments
        
    wellformed
        if this selector is wellformed regarding the Selector spec

    Format
    ======
    ::

        # implemented in SelectorList
        selectors_group
          : selector [ COMMA S* selector ]*
          ;

        selector
          : simple_selector_sequence [ combinator simple_selector_sequence ]*
          ;

        combinator
          /* combinators can be surrounded by white space */
          : PLUS S* | GREATER S* | TILDE S* | S+
          ;

        simple_selector_sequence
          : [ type_selector | universal ]
            [ HASH | class | attrib | pseudo | negation ]*
          | [ HASH | class | attrib | pseudo | negation ]+
          ;

        type_selector
          : [ namespace_prefix ]? element_name
          ;

        namespace_prefix
          : [ IDENT | '*' ]? '|'
          ;

        element_name
          : IDENT
          ;

        universal
          : [ namespace_prefix ]? '*'
          ;

        class
          : '.' IDENT
          ;

        attrib
          : '[' S* [ namespace_prefix ]? IDENT S*
                [ [ PREFIXMATCH |
                    SUFFIXMATCH |
                    SUBSTRINGMATCH |
                    '=' |
                    INCLUDES |
                    DASHMATCH ] S* [ IDENT | STRING ] S*
                ]? ']'
          ;

        pseudo
          /* '::' starts a pseudo-element, ':' a pseudo-class */
          /* Exceptions: :first-line, :first-letter, :before and :after. */
          /* Note that pseudo-elements are restricted to one per selector and */
          /* occur only in the last simple_selector_sequence. */
          : ':' ':'? [ IDENT | functional_pseudo ]
          ;

        functional_pseudo
          : FUNCTION S* expression ')'
          ;

        expression
          /* In CSS3, the expressions are identifiers, strings, */
          /* or of the form "an+b" */
          : [ [ PLUS | '-' | DIMENSION | NUMBER | STRING | IDENT ] S* ]+
          ;

        negation
          : NOT S* negation_arg S* ')'
          ;

        negation_arg
          : type_selector | universal | HASH | class | attrib | pseudo
          ;

    """
    def __init__(self, selectorText=None, readonly=False):
        """
        selectorText
            initial value of this selector
        readonly
            default to False
        """
        super(Selector, self).__init__()

        #self.valid = False # not used anymore
        self.wellformed = False
        self.seq = self._newseq()
        self.prefixes = set()
        if selectorText:
            self.selectorText = selectorText
        self._readonly = readonly


    def _getSelectorText(self):
        """
        returns serialized format
        """
        return cssutils.ser.do_css_Selector(self)

    def _setSelectorText(self, selectorText):
        """
        sets this selectorText
        
        TODO:
        raises xml.dom.Exception
        """
        self._checkReadonly()
        tokenizer = self._tokenize2(selectorText)
        if not tokenizer:
            self._log.error(u'Selector: No selectorText given.')
        else:
            # prepare tokenlist:
            #     "*" -> type "universal"
            #     "*"|IDENT + "|" -> combined to "namespace_prefix"
            #     "|" -> type "namespace_prefix"
            #     "." + IDENT -> combined to "class"
            #     ":" + IDENT, ":" + FUNCTION -> pseudo-class
            #     FUNCTION "not(" -> negation
            #     "::" + IDENT, "::" + FUNCTION -> pseudo-element
            tokens = []
            for t in tokenizer:
                typ, val, lin, col = t
                if val == u':' and tokens and\
                   self._tokenvalue(tokens[-1]) == ':':
                    # combine ":" and ":"
                    tokens[-1] = (typ, u'::', lin, col)

                elif typ == 'IDENT' and tokens\
                     and self._tokenvalue(tokens[-1]) == u'.':
                    # class: combine to .IDENT
                    tokens[-1] = ('class', u'.'+val, lin, col)
                elif typ == 'IDENT' and tokens and \
                     self._tokenvalue(tokens[-1]).startswith(u':') and\
                     not self._tokenvalue(tokens[-1]).endswith(u'('):
                    # pseudo-X: combine to :IDENT or ::IDENT but not ":a(" + "b"
                    if self._tokenvalue(tokens[-1]).startswith(u'::'): 
                        t = 'pseudo-element'
                    else: 
                        t = 'pseudo-class'
                    tokens[-1] = (t, self._tokenvalue(tokens[-1])+val, lin, col)

                elif typ == 'FUNCTION' and val == u'not(' and tokens and \
                     u':' == self._tokenvalue(tokens[-1]):
                    tokens[-1] = ('negation', u':' + val, lin, tokens[-1][3])
                elif typ == 'FUNCTION' and tokens\
                     and self._tokenvalue(tokens[-1]).startswith(u':'):
                    # pseudo-X: combine to :FUNCTION( or ::FUNCTION(
                    if self._tokenvalue(tokens[-1]).startswith(u'::'): 
                        t = 'pseudo-element'
                    else: 
                        t = 'pseudo-class'
                    tokens[-1] = (t, self._tokenvalue(tokens[-1])+val, lin, col)

                elif val == u'*' and tokens and\
                     self._type(tokens[-1]) == 'namespace_prefix' and\
                     self._tokenvalue(tokens[-1]).endswith(u'|'):
                    # combine prefix|*
                    tokens[-1] = ('universal', self._tokenvalue(tokens[-1])+val, 
                                  lin, col)
                elif val == u'*':
                    # universal: "*"
                    tokens.append(('universal', val, lin, col))

                elif val == u'|' and tokens and\
                     self._type(tokens[-1]) in ('IDENT', 'universal') and\
                     self._tokenvalue(tokens[-1]).find(u'|') == -1:
                    # namespace_prefix: "IDENT|" or "*|"
                    tokens[-1] = ('namespace_prefix', 
                                  self._tokenvalue(tokens[-1])+u'|', lin, col)
                elif val == u'|':
                    # namespace_prefix: "|"
                    tokens.append(('namespace_prefix', val, lin, col))

                else:
                    tokens.append(t)

            # TODO: back to generator but not elegant at all!
            tokenizer = (t for t in tokens) 

            # for closures: must be a mutable
            new = {'wellformed': True,
                   'context': ['ROOT'], # stack of: 'attrib', 'negation', 'pseudo'
                   'prefixes': set()
                   }
            # used for equality checks and setting of a space combinator
            S = u' '

            def append(seq, val, typ=None):
                "appends to seq, may be expanded later"
                seq.append(val, typ)

            # expected constants
            simple_selector_sequence = 'type_selector universal HASH class attrib pseudo negation '
            simple_selector_sequence2 = 'HASH class attrib pseudo negation '

            element_name = 'element_name'

            negation_arg = 'type_selector universal HASH class attrib pseudo'
            negationend = ')'
            
            attname = 'prefix attribute'
            attname2 = 'attribute'
            attcombinator = 'combinator ]' # optional
            attvalue = 'value'       # optional
            attend = ']'
            
            expressionstart = 'PLUS - DIMENSION NUMBER STRING IDENT'
            expression = expressionstart + ' )' 
            
            combinator = ' combinator'

            def _COMMENT(expected, seq, token, tokenizer=None):
                "special implementation for comment token"
                append(seq, cssutils.css.CSSComment([token]))
                return expected

            def _S(expected, seq, token, tokenizer=None):
                # S
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if context.startswith('pseudo-'):
                    append(seq, S, 'combinator')
                    return expected
                
                elif context != 'attrib' and 'combinator' in expected:
                    append(seq, S, 'combinator')
                    return simple_selector_sequence + combinator
                
                else:
                    return expected
            
            def _universal(expected, seq, token, tokenizer=None):
                # *|* or prefix|*
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if 'universal' in expected:
                    append(seq, val, typ)
                    
                    newprefix = val.split(u'|')[0]
                    if newprefix and newprefix != u'*':
                        new['prefixes'].add(newprefix)
                    
                    if 'negation' == context:
                        return negationend
                    else:
                        return simple_selector_sequence2 + combinator

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected universal.', token=token)
                    return expected

            def _namespace_prefix(expected, seq, token, tokenizer=None):
                # prefix| => element_name
                # or prefix| => attribute_name if attrib
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if 'attrib' == context and 'prefix' in expected:
                    # [PREFIX|att]
                    append(seq, val, typ)
                    
                    newprefix = val.split(u'|')[0]
                    if newprefix and newprefix != u'*':
                        new['prefixes'].add(newprefix)
                        
                    return attname2
                elif 'type_selector' in expected:
                    # PREFIX|*
                    append(seq, val, typ)
                    
                    newprefix = val.split(u'|')[0]
                    if newprefix and newprefix != u'*':
                        new['prefixes'].add(newprefix)
                        
                    return element_name
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected namespace prefix.', token=token)
                    return expected

            def _pseudo(expected, seq, token, tokenizer=None):
                # pseudo-class or pseudo-element :a ::a :a( ::a(
                """
                /* '::' starts a pseudo-element, ':' a pseudo-class */
                /* Exceptions: :first-line, :first-letter, :before and :after. */
                /* Note that pseudo-elements are restricted to one per selector and */
                /* occur only in the last simple_selector_sequence. */
                """
                context = new['context'][-1]
                val, typ = self._tokenvalue(token, normalize=True), self._type(token)
                if 'pseudo' in expected:                    
                    if val in (':first-line', ':first-letter', ':before', ':after'):
                        # always pseudo-element ???
                        typ = 'pseudo-element'
                    append(seq, val, typ)
                    
                    if val.endswith(u'('):
                        # function
                        new['context'].append(typ) # "pseudo-" "class" or "element"
                        return expressionstart                 
                    elif 'negation' == context:
                        return negationend
                    elif 'pseudo-element' == typ:
                        # only one per element, check at ) also!
                        return combinator
                    else:
                        return simple_selector_sequence2 + combinator

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected start of pseudo.', token=token)
                    return expected

            def _expression(expected, seq, token, tokenizer=None):
                # [ [ PLUS | '-' | DIMENSION | NUMBER | STRING | IDENT ] S* ]+
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if context.startswith('pseudo-'):
                    append(seq, val, typ)
                    return expression
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected %s.' % typ, token=token)
                    return expected

            def _attcombinator(expected, seq, token, tokenizer=None):
                # context: attrib
                # PREFIXMATCH | SUFFIXMATCH | SUBSTRINGMATCH | INCLUDES | 
                # DASHMATCH
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if 'attrib' == context and 'combinator' in expected:
                    # combinator in attrib
                    append(seq, val)
                    return attvalue
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected %s.' % typ, token=token)
                    return expected

            def _string(expected, seq, token, tokenizer=None):
                # identifier
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                
                # context: attrib
                if 'attrib' == context and 'value' in expected:
                    # attrib: [...=VALUE]
                    append(seq, val, typ)
                    return attend

                # context: pseudo
                elif context.startswith('pseudo-'):
                    # :func(...)
                    append(seq, val, typ)
                    return expression

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected STRING.', token=token)
                    return expected

            def _ident(expected, seq, token, tokenizer=None):
                # identifier
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                
                # context: attrib
                if 'attrib' == context and 'attribute' in expected:
                    # attrib: [...|ATT...]
                    append(seq, val, typ)
                    return attcombinator

                elif 'attrib' == context and 'value' in expected:
                    # attrib: [...=VALUE]
                    append(seq, val, typ)
                    return attend

                # context: negation
                elif 'negation' == context:
                    # negation: (prefix|IDENT)
                    append(seq, val, typ)
                    return negationend

                # context: pseudo
                elif context.startswith('pseudo-'):
                    # :func(...)
                    append(seq, val, typ)
                    return expression

                elif 'type_selector' in expected or element_name == expected:
                    # element name after ns or complete type_selector
                    append(seq, val, typ)
                    return simple_selector_sequence2 + combinator

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected IDENT.', 
                        token=token)
                    return expected

            def _class(expected, seq, token, tokenizer=None):
                # .IDENT
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if 'class' in expected:
                    append(seq, val, typ)

                    if 'negation' == context:
                        return negationend
                    else:
                        return simple_selector_sequence2 + combinator

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected class.', token=token)
                    return expected

            def _hash(expected, seq, token, tokenizer=None):
                # #IDENT
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                if 'HASH' in expected:
                    append(seq, val, typ)
                    
                    if 'negation' == context:
                        return negationend
                    else:
                        return simple_selector_sequence2 + combinator

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected HASH.', token=token)
                    return expected

            def _char(expected, seq, token, tokenizer=None):
                # + > ~ S
                context = new['context'][-1]
                val, typ = self._tokenvalue(token), self._type(token)
                
                # context: attrib
                if u']' == val and 'attrib' == context and ']' in expected:
                    # end of attrib
                    append(seq, val)
                    context = new['context'].pop() # attrib is done
                    context = new['context'][-1]
                    if 'negation' == context:
                        return negationend
                    else:
                        return simple_selector_sequence2 + combinator

                elif u'=' == val and 'attrib' == context and 'combinator' in expected:
                    # combinator in attrib
                    append(seq, val)
                    return attvalue

                # context: negation
                elif u')' == val and 'negation' == context and u')' in expected:
                    # not(negation_arg)"
                    append(seq, val)
                    new['context'].pop() # negation is done
                    context = new['context'][-1]
                    return simple_selector_sequence + combinator                

                # context: pseudo (at least one expression)
                elif val in u'+-' and context.startswith('pseudo-'):
                    # :func(+ -)"
                    append(seq, val)
                    return expression                

                elif u')' == val and context.startswith('pseudo-') and\
                     expression == expected:
                    # :func(expression)"
                    append(seq, val)
                    new['context'].pop() # pseudo is done
                    if 'pseudo-element' == context:
                        return combinator
                    else:
                        return simple_selector_sequence + combinator                

                # context: ROOT                
                elif u'[' == val and 'attrib' in expected:
                    # start of [attrib]
                    new['context'].append('attrib')
                    append(seq, val)
                    return attname

                elif val in u'+>~' and 'combinator' in expected:
                    # no other combinator except S may be following
                    if seq and S == seq[-1]:
                        seq[-1] = (val, 'combinator')
                    else:
                        append(seq, val, 'combinator')
                    return simple_selector_sequence

                elif u',' == val:
                    # not a selectorlist
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Single selector only.', 
                        error=xml.dom.InvalidModificationErr, 
                        token=token)

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected CHAR.', token=token)
                    return expected

            def _negation(expected, seq, token, tokenizer=None):
                # not(
                val = self._tokenvalue(token, normalize=True)
                if 'negation' in expected:
                    new['context'].append('negation')
                    append(seq, val, 'negation')
                    return negation_arg
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'Selector: Unexpected negation.', token=token)
                    return expected

            # expected: only|not or mediatype, mediatype, feature, and
            newseq = self._newseq()
            wellformed, expected = self._parse(expected=simple_selector_sequence,
                seq=newseq, tokenizer=tokenizer,
                productions={'CHAR': _char,
                             'class': _class,
                             'HASH': _hash,
                             'STRING': _string,
                             'IDENT': _ident,
                             'namespace_prefix': _namespace_prefix,
                             'negation': _negation,
                             'pseudo-class': _pseudo,
                             'pseudo-element': _pseudo,
                             'universal': _universal,
                             # pseudo
                             'NUMBER': _expression,
                             'DIMENSION': _expression,
                             # attribute
                             'PREFIXMATCH': _attcombinator,
                             'SUFFIXMATCH': _attcombinator,
                             'SUBSTRINGMATCH': _attcombinator,
                             'DASHMATCH': _attcombinator,
                             'INCLUDES': _attcombinator,
                             
                             'S': _S,
                             'COMMENT': _COMMENT})
            wellformed = wellformed and new['wellformed']

            # post condition
            if len(new['context']) > 1:
                wellformed = False
                self._log.error(u'Selector: Incomplete selector: %s' %
                    self._valuestr(selectorText))
            
            if expected == 'element_name':
                wellformed = False
                self._log.error(u'Selector: No element name found: %s' %
                    self._valuestr(selectorText))

            if expected == simple_selector_sequence:
                wellformed = False
                self._log.error(u'Selector: Cannot end with combinator: %s' %
                    self._valuestr(selectorText))

            if newseq and hasattr(newseq[-1], 'strip') and newseq[-1].strip() == u'':
                del newseq[-1]

            # set
            if wellformed:
                self.wellformed = True
                self.seq = newseq
                self.prefixes = new['prefixes']

    selectorText = property(_getSelectorText, _setSelectorText,
        doc="(DOM) The parsable textual representation of the selector.")

    def __repr__(self):
        return "cssutils.css.%s(selectorText=%r)" % (
                self.__class__.__name__, self.selectorText)

    def __str__(self):
        return "<cssutils.css.%s object selectorText=%r at 0x%x>" % (
                self.__class__.__name__, self.selectorText, id(self))
