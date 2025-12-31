# 图标说明

请将 icon.svg 转换为以下尺寸的 PNG 文件：
- icon16.png (16x16)
- icon48.png (48x48)
- icon128.png (128x128)

可以使用在线工具如 https://cloudconvert.com/svg-to-png 进行转换。

或者使用 ImageMagick 命令：
```bash
convert -background none icon.svg -resize 16x16 icon16.png
convert -background none icon.svg -resize 48x48 icon48.png
convert -background none icon.svg -resize 128x128 icon128.png
```
