import urlparse
import fetchers.urllib2Wrapper as urllib2Wrapper

# This file will contain all the parts needed for getting documents and interfacing with the filesystem and Internet

class Browser (object):
    """
    The Browser class holds all the data and handles all the
    functionality related to a single browser instance
    This includes (but probably isn't limited to):
    - Fetching resources from URIs
    - Getting/Setting/handling cookies
    - Managing History (allowing forward/back functionality)
    - Managing multiple "contexts", each which has its own histories, but
    shares things like cookies. Think tabs or windows within the same
    browser instance
    """

    def __init__(self):
        self.fetchers = {'http': urllib2Wrapper.open,
                         'file': urllib2Wrapper.open}
        
    def open(self, uri):
        """ Gets the resource at the specified URI """

        # Where are we looking?
        url_parts = urlparse.urlparse(uri, 'http')

        f = self.fetchers[url_parts.scheme](uri)

        return f


        
            
