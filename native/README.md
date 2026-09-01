# sPDF Windows native renderer

This directory contains the experimental Windows rendering boundary. It is not
loaded by the application unless Python explicitly probes or creates it, so a
missing or failed DLL does not change the current CPU/OpenGL display path.

## Build

Install Visual Studio 2022 C++ Build Tools with the Desktop C++ workload and a
Windows SDK, then run:

```bat
native\build_d2d_renderer.bat
```

Generated objects, import libraries, PDBs, and `spdf_d2d_renderer.dll` are kept
under `native\bin` and are not committed.

## Current ABI

ABI version 1 can:

- probe a hardware D3D11 device and fall back to WARP;
- create Direct2D and DirectWrite devices on the same DXGI device;
- create a flip-model swap chain for an HWND;
- upload premultiplied BGRA bitmaps and draw them into a frame;
- clear/present, resize, and destroy the surface and bitmap resources.

The bitmap path is verified with synthetic pixels but is not yet connected to
PDF tiles. The live sPDF reader therefore remains on its existing display
backend until PDF cache lifetime, device-loss recovery, and Qt input/overlay
integration are verified.
