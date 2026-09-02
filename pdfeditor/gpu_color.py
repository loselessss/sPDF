"""Small, lazily built color-conversion tables for GPU mask composition."""

from functools import lru_cache

import pymupdf


LUMINOSITY_LUT_EDGE = 65


def softmask_gray_samples(source):
    mupdf = pymupdf.mupdf
    params = mupdf.FzColorParams()
    params.ri |= mupdf.FZ_RI_IN_SOFTMASK
    gray = mupdf.fz_device_gray()
    gray.thisown = False
    converted = pymupdf.Pixmap(mupdf.fz_convert_pixmap(
        source.this, gray, mupdf.FzColorspace(), mupdf.FzDefaultColorspaces(), params, 0))
    return converted.samples[::converted.n]


@lru_cache(maxsize=1)
def _luminosity_lut(profile_signature):
    # D2D indexes blue fastest, then green, then red. MuPDF performs only this
    # bounded setup conversion; actual mask pixels are converted by the GPU.
    edge = LUMINOSITY_LUT_EDGE
    levels = [round(index * 255 / (edge - 1)) for index in range(edge)]
    rgb = bytes(channel for red in levels for green in levels for blue in levels
                for channel in (red, green, blue))
    source = pymupdf.Pixmap(pymupdf.csRGB, edge, edge * edge, rgb, False)
    gray = softmask_gray_samples(source)
    rgba = bytearray(len(gray) * 4)
    rgba[0::4] = gray
    rgba[1::4] = gray
    rgba[2::4] = gray
    rgba[3::4] = b"\xff" * len(gray)
    return bytes(rgba)


def luminosity_lut():
    # Invalidate the cache if the host changes MuPDF's default ICC conversion.
    probe = pymupdf.Pixmap(pymupdf.csRGB, 3, 1,
                          bytes((255, 0, 0, 0, 255, 0, 0, 0, 255)), False)
    signature = softmask_gray_samples(probe)
    return signature, LUMINOSITY_LUT_EDGE, _luminosity_lut(signature)
