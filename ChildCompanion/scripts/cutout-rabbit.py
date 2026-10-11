"""把 5 张兔子状态图的米色背景抠成透明，输出同名 PNG。

难点：兔子本体（奶油白）与背景（255,249,235）极其接近，单纯按颜色阈值会把
耳朵、肚子、爪子一起啃掉。

算法（"反向洪水填充"）：
  1. 判定"疑似背景"的像素：局部纹理极低 AND 与背景色差小 AND 不比背景暗
     —— 三个条件同时满足才算背景，比"任一满足算前景"更严格
  2. 只保留与画布四边相连的背景连通块（真正的背景），其余一律算前景
     —— 这样兔子内部的浅色区（肚子、脸颊高光）不会被误删
  3. 去脚底投影阴影
  4. 逐行左右填充，补上仍缺失的缺口
  5. 轻微羽化边缘，抵消 JPEG 锯齿
"""
from PIL import Image, ImageFilter
import numpy as np
from scipy import ndimage
import os

SRC_DIR = 'public/characters/rabbit'
NAMES = ['welcome', 'idle', 'listening', 'thinking', 'speaking']

# 每张图的背景判定阈值（局部std / 色差 / 比背景暗多少）
# listening 的爪子抬手直接贴背景、光晕重，所以用更严格的判定把它和背景分开
PARAMS = {
    'welcome':   (1.6, 9, 4),
    'idle':      (2.0, 12, 5),
    'listening': (1.5, 9, 4),
    'thinking':  (1.8, 10, 4),
    'speaking':  (1.8, 10, 4),
}


def cut(path: str, t_std: float, t_col: float, t_lum: float) -> Image.Image:
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(np.float32)
    gray = a.mean(axis=2)

    lm = ndimage.uniform_filter(gray, 9)
    ls = ndimage.uniform_filter(gray ** 2, 9)
    lstd = np.sqrt(np.maximum(ls - lm ** 2, 0))          # 局部纹理

    border = np.concatenate([
        a[0:6].reshape(-1, 3), a[-6:].reshape(-1, 3),
        a[:, 0:6].reshape(-1, 3), a[:, -6:].reshape(-1, 3),
    ])
    bg = np.median(border, axis=0)
    cold = np.sqrt(((a - bg) ** 2).sum(axis=2))           # 与背景色差
    lum = bg.mean() - gray                                # 比背景暗多少

    # 1. 严格判定背景：三条件全满足
    bgmask = (lstd < t_std) & (cold < t_col) & (lum < t_lum)

    # 2. 只保留与画布边缘连通的背景
    lab, _ = ndimage.label(bgmask)
    edge = set(lab[0].tolist()) | set(lab[-1].tolist()) | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    edge.discard(0)
    outside = np.isin(lab, list(edge)) if edge else np.zeros_like(bgmask)

    fg = ~outside
    fg = ndimage.binary_fill_holes(fg)
    lab2, n2 = ndimage.label(fg)
    sz = ndimage.sum(fg, lab2, range(1, n2 + 1))
    fg = np.isin(lab2, (np.argsort(sz)[::-1][:1]) + 1)

    # 3. 去脚底投影阴影
    #    阴影特征：位于最下方、非常平滑（无纹理）、只略暗不偏色。
    #    但脚掌本身也在最下方且颜色浅，所以还要排除"有纹理"的脚掌边缘。
    ys, xs = np.where(fg)
    ymin, ymax = ys.min(), ys.max()
    low = np.zeros_like(fg)
    low[int(ymax - 0.09 * (ymax - ymin)):ymax + 2, :] = True
    sh = fg & low & (lstd < 5.0) & (cold < 28)
    sh = ndimage.binary_opening(sh, np.ones((3, 20)))
    fg = fg & ~sh

    # 3b. 再清一遍"几乎就是背景色"的残留（主要是不透明的淡阴影/光晕）
    #     只要色差极小且无纹理，即便在主体附近也删掉；用主体核心保护真正的本体
    core = cold > 26                      # 明显不是背景色 = 本体核心，永不删
    residue = (cold < 11) & (lstd < 3.2) & ~core
    fg = fg & ~residue
    fg = ndimage.binary_closing(fg, np.ones((5, 5)))
    fg = ndimage.binary_fill_holes(fg)

    # 4. 逐行左右填充
    ys, xs = np.where(fg)
    for y in range(ys.min(), ys.max() + 1):
        r = np.where(fg[y])[0]
        if len(r) > 1:
            fg[y, r.min():r.max() + 1] = True
    fg = ndimage.binary_fill_holes(fg)

    lab3, n3 = ndimage.label(fg)
    sz3 = ndimage.sum(fg, lab3, range(1, n3 + 1))
    fg = np.isin(lab3, (np.argsort(sz3)[::-1][:1]) + 1)

    # 5. 膨胀补轮廓外沿 + 羽化
    fg = ndimage.binary_dilation(fg, np.ones((3, 3)))
    alpha = (fg * 255).astype(np.uint8)
    out = Image.fromarray(np.dstack([np.asarray(im).astype(np.uint8), alpha]), 'RGBA')
    out.putalpha(out.getchannel('A').filter(ImageFilter.GaussianBlur(0.9)))
    return out


SIZE = 1024

if __name__ == '__main__':
    for name in NAMES:
        src = os.path.join(SRC_DIR, f'{name}.jpg')
        if not os.path.exists(src):
            print(f'跳过（无原图）: {src}')
            continue
        t_std, t_col, t_lum = PARAMS.get(name, (1.8, 10, 4))
        img = cut(src, t_std, t_col, t_lum)

        bbox = img.getchannel('A').getbbox()
        img = img.crop(bbox)
        w, h = img.size
        pad = int(max(w, h) * 0.02)
        canvas = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        canvas.paste(img, (pad, pad), img)
        canvas.thumbnail((SIZE, SIZE), Image.LANCZOS)

        dst = os.path.join(SRC_DIR, f'{name}.png')
        canvas.save(dst, 'PNG', optimize=True)
        print(f'{name}.png  {canvas.size}  {os.path.getsize(dst)/1024:.0f} KB')
