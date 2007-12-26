import urllib2

def protocols():
    """ returns a list of the protocols supported by this module """
    return ('http', 'file')

def open(url):
    return urllib2.urlopen(url)
