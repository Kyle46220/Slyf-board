from PIL import Image
# Create a dummy animated gif to test
im1 = Image.new('RGB', (10, 10), 'red')
im2 = Image.new('RGB', (10, 10), 'blue')
im1.save('test.gif', save_all=True, append_images=[im2], duration=100, loop=0)

img = Image.open('test.gif')
if getattr(img, 'is_animated', False):
    img.save('test.webp', 'WEBP', save_all=True)
    print("Saved animated webp")
