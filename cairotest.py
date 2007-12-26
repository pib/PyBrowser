import cairo

WIDTH,HEIGHT = 400,400

surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
ctx = cairo.Context(surface)

ctx.set_line_width(15)

for i in range(0,2400):
	ctx.arc(200,200, 10.0 + i/10.0, (i-1.0)/100.0, i/100.0 )
ctx.stroke()

ctx.set_source_rgb(1.0,1.0,1.0)
#ctx.select_font_face("courier", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
#ctx.set_font_size(12)
ctx.move_to(0,12)

ctx.show_text("this is a test, damnit!")

surface.write_to_png("triangle.png")
