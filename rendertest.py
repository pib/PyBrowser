from pagenode import PageNode
import urllib2
from BeautifulSoup import BeautifulSoup

soup = BeautifulSoup(urllib2.urlopen("http://oregonstate.edu/~bonserp/blog"))
page = PageNode(soup, None)

page.makeBox()
img = page.makeImage(1000)
img.write_to_png("test.png")

