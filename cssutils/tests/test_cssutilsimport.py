"""testcase for cssutils imports
"""
__all__ = ['CSSutilsImportTestCase']
__author__ = '$LastChangedBy: cthedot $'
__date__ = '$LastChangedDate: 2007-09-26 17:00:37 +0200 (Mi, 26 Sep 2007) $'
__version__ = '$LastChangedRevision: 468 $'

before = len(locals()) # to check is only exp amount is imported
from cssutils import *
after = len(locals()) # to check is only exp amount is imported

import unittest

class CSSutilsImportTestCase(unittest.TestCase):

    def test_import_all(self):
        "from cssutils import *"
        import cssutils

        act = globals()
        exp = {'CSSParser': CSSParser,
               'CSSSerializer': CSSSerializer,
               'css': cssutils.css,
               'stylesheets': cssutils.stylesheets,
        }
        exptotal = before + len(exp) + 1
        # imports before + * + "after"
        self.assert_(after == exptotal, 'too many imported')

        found = 0
        for e in exp:
            self.assert_(e in act, '%s not found' %e)
            self.assert_(act[e] == exp[e], '%s not the same' %e)
            found += 1
        self.assert_(found == len(exp))

if __name__ == '__main__':
    import unittest
    unittest.main()
