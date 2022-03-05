# This is a midi controller using Raspberry Pi

Written in python. Used to be pedal looper project but removed all the looper / switcher parts and only use midi now.

## to take picture with pi cam and display on oled screen

```shell
raspistill -o image.jpg
python
```

Then

```python
from PIL import Image
image = Image.open('image.jpg')
new_image = image.resize((128, 64))
new_image.save('new_image.ppm')
```

Then

```shell
python /home/pi/Adafruit_Python_SSD1306/examples/image.py
```
