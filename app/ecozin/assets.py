"""업로드 자산 저장. 쇼츠 렌더링에 필요한 크기(긴 변 1920px)로 줄여 저장해 렌더링 시간을 줄인다."""

from __future__ import annotations

import os
from typing import IO, Union

from PIL import Image, ImageOps

MAX_SIDE = 1920
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def save_upload(dest_dir: str, filename: str, data: Union[bytes, IO[bytes]]) -> str:
    """파일을 dest_dir 에 저장한다. 이미지는 EXIF 회전을 적용하고 긴 변 1920px 로 줄인다. 동영상은 그대로 둔다."""
    name = os.path.basename(filename)
    path = os.path.join(dest_dir, name)
    raw = data if isinstance(data, (bytes, bytearray)) else data.read()
    ext = os.path.splitext(name)[1].lower()
    if ext in _IMAGE_EXT:
        from io import BytesIO
        im = ImageOps.exif_transpose(Image.open(BytesIO(raw)))
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        if ext in (".jpg", ".jpeg"):
            im.convert("RGB").save(path, quality=90, optimize=True)
        else:
            im.save(path)
    else:
        with open(path, "wb") as f:
            f.write(raw)
    return path
