#define SPDF_D2D_EXPORTS
#include "spdf_d2d.h"

#include <algorithm>
#include <cstring>
#include <iterator>
#include <new>

#include <d2d1_1.h>
#include <d3d11_1.h>
#include <dwrite.h>
#include <dxgi1_2.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

namespace {

HRESULT create_d3d_device(
    D3D_DRIVER_TYPE driver_type,
    ComPtr<ID3D11Device>& device,
    D3D_FEATURE_LEVEL& selected_level) noexcept {
    constexpr D3D_FEATURE_LEVEL levels[] = {
        D3D_FEATURE_LEVEL_11_1,
        D3D_FEATURE_LEVEL_11_0,
        D3D_FEATURE_LEVEL_10_1,
        D3D_FEATURE_LEVEL_10_0,
    };
    ComPtr<ID3D11DeviceContext> immediate_context;
    auto result = D3D11CreateDevice(
        nullptr,
        driver_type,
        nullptr,
        D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        levels,
        static_cast<UINT>(std::size(levels)),
        D3D11_SDK_VERSION,
        &device,
        &selected_level,
        &immediate_context);
    if (result == E_INVALIDARG) {
        // Windows 7 without the 11.1 runtime rejects 11_1 in the list.
        result = D3D11CreateDevice(
            nullptr,
            driver_type,
            nullptr,
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            levels + 1,
            static_cast<UINT>(std::size(levels) - 1),
            D3D11_SDK_VERSION,
            &device,
            &selected_level,
            &immediate_context);
    }
    return result;
}

void reset_info(SpdfD2DInfo* info) noexcept {
    if (info == nullptr) {
        return;
    }
    const auto caller_size = info->struct_size;
    std::memset(info, 0, std::min<std::size_t>(caller_size, sizeof(SpdfD2DInfo)));
    info->struct_size = sizeof(SpdfD2DInfo);
    info->abi_version = SPDF_D2D_ABI_VERSION;
}

void set_adapter_name(ID3D11Device* device, SpdfD2DInfo* info) noexcept {
    if (device == nullptr || info == nullptr) {
        return;
    }
    ComPtr<IDXGIDevice> dxgi_device;
    if (FAILED(device->QueryInterface(IID_PPV_ARGS(&dxgi_device)))) {
        return;
    }
    ComPtr<IDXGIAdapter> adapter;
    if (FAILED(dxgi_device->GetAdapter(&adapter))) {
        return;
    }
    DXGI_ADAPTER_DESC description{};
    if (FAILED(adapter->GetDesc(&description))) {
        return;
    }
    wcsncpy_s(
        info->adapter_name,
        SPDF_D2D_ADAPTER_NAME_LENGTH,
        description.Description,
        _TRUNCATE);
}

class Surface {
public:
    struct Bitmap {
        Surface* owner;
        ComPtr<ID2D1Bitmap1> resource;
    };

    HRESULT initialize(
        HWND hwnd,
        std::uint32_t width,
        std::uint32_t height,
        float dpi,
        SpdfD2DInfo* info) noexcept {
        D3D_FEATURE_LEVEL feature_level = D3D_FEATURE_LEVEL_10_0;
        auto result = create_d3d_device(
            D3D_DRIVER_TYPE_HARDWARE, d3d_device_, feature_level);
        if (SUCCEEDED(result)) {
            driver_ = SPDF_D2D_DRIVER_HARDWARE;
        } else {
            result = create_d3d_device(D3D_DRIVER_TYPE_WARP, d3d_device_, feature_level);
            if (FAILED(result)) {
                return result;
            }
            driver_ = SPDF_D2D_DRIVER_WARP;
        }
        feature_level_ = feature_level;

        result = d3d_device_.As(&dxgi_device_);
        if (FAILED(result)) {
            return result;
        }
        ComPtr<IDXGIAdapter> adapter;
        result = dxgi_device_->GetAdapter(&adapter);
        if (FAILED(result)) {
            return result;
        }
        result = adapter->GetParent(IID_PPV_ARGS(&dxgi_factory_));
        if (FAILED(result)) {
            return result;
        }

        D2D1_FACTORY_OPTIONS options{};
        result = D2D1CreateFactory(
            D2D1_FACTORY_TYPE_SINGLE_THREADED,
            __uuidof(ID2D1Factory1),
            &options,
            reinterpret_cast<void**>(d2d_factory_.GetAddressOf()));
        if (FAILED(result)) {
            return result;
        }
        result = d2d_factory_->CreateDevice(dxgi_device_.Get(), &d2d_device_);
        if (FAILED(result)) {
            return result;
        }
        result = d2d_device_->CreateDeviceContext(
            D2D1_DEVICE_CONTEXT_OPTIONS_NONE, &d2d_context_);
        if (FAILED(result)) {
            return result;
        }
        result = DWriteCreateFactory(
            DWRITE_FACTORY_TYPE_SHARED,
            __uuidof(IDWriteFactory),
            reinterpret_cast<IUnknown**>(dwrite_factory_.GetAddressOf()));
        if (FAILED(result)) {
            return result;
        }

        DXGI_SWAP_CHAIN_DESC1 description{};
        description.Width = std::max<std::uint32_t>(1, width);
        description.Height = std::max<std::uint32_t>(1, height);
        description.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
        description.SampleDesc.Count = 1;
        description.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
        description.BufferCount = 2;
        description.Scaling = DXGI_SCALING_STRETCH;
        description.SwapEffect = DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL;
        description.AlphaMode = DXGI_ALPHA_MODE_IGNORE;
        result = dxgi_factory_->CreateSwapChainForHwnd(
            d3d_device_.Get(), hwnd, &description, nullptr, nullptr, &swap_chain_);
        if (FAILED(result)) {
            return result;
        }
        dxgi_factory_->MakeWindowAssociation(hwnd, DXGI_MWA_NO_ALT_ENTER);
        dpi_ = dpi > 0 ? dpi : 96.0f;
        result = create_target();
        if (SUCCEEDED(result) && info != nullptr) {
            info->driver = driver_;
            info->feature_level = static_cast<std::uint32_t>(feature_level_);
            set_adapter_name(d3d_device_.Get(), info);
        }
        return result;
    }

    HRESULT resize(std::uint32_t width, std::uint32_t height, float dpi) noexcept {
        if (!swap_chain_ || width == 0 || height == 0) {
            return E_INVALIDARG;
        }
        d2d_context_->SetTarget(nullptr);
        target_.Reset();
        const auto result = swap_chain_->ResizeBuffers(
            0, width, height, DXGI_FORMAT_UNKNOWN, 0);
        if (FAILED(result)) {
            return result;
        }
        dpi_ = dpi > 0 ? dpi : dpi_;
        return create_target();
    }

    HRESULT clear(std::uint32_t argb) noexcept {
        if (!d2d_context_ || !target_ || !swap_chain_) {
            return E_UNEXPECTED;
        }
        auto result = begin_frame(argb);
        if (FAILED(result)) {
            return result;
        }
        return end_frame();
    }

    HRESULT begin_frame(std::uint32_t argb) noexcept {
        if (!d2d_context_ || !target_ || drawing_) {
            return E_UNEXPECTED;
        }
        const auto alpha = static_cast<float>((argb >> 24) & 0xff) / 255.0f;
        const auto red = static_cast<float>((argb >> 16) & 0xff) / 255.0f;
        const auto green = static_cast<float>((argb >> 8) & 0xff) / 255.0f;
        const auto blue = static_cast<float>(argb & 0xff) / 255.0f;
        d2d_context_->BeginDraw();
        drawing_ = true;
        d2d_context_->SetTransform(D2D1::Matrix3x2F::Identity());
        d2d_context_->Clear(D2D1::ColorF(red, green, blue, alpha));
        return S_OK;
    }

    HRESULT create_bitmap(
        const void* pixels,
        std::uint32_t width,
        std::uint32_t height,
        std::uint32_t stride,
        Bitmap** bitmap) noexcept {
        if (!d2d_context_ || pixels == nullptr || width == 0 || height == 0 ||
                stride < width * 4 || bitmap == nullptr) {
            return E_INVALIDARG;
        }
        *bitmap = nullptr;
        auto result_bitmap = new (std::nothrow) Bitmap{this, nullptr};
        if (result_bitmap == nullptr) {
            return E_OUTOFMEMORY;
        }
        const auto properties = D2D1::BitmapProperties1(
            D2D1_BITMAP_OPTIONS_NONE,
            D2D1::PixelFormat(
                DXGI_FORMAT_B8G8R8A8_UNORM,
                D2D1_ALPHA_MODE_PREMULTIPLIED),
            96.0f,
            96.0f);
        const auto result = d2d_context_->CreateBitmap(
            D2D1::SizeU(width, height),
            pixels,
            stride,
            &properties,
            &result_bitmap->resource);
        if (FAILED(result)) {
            delete result_bitmap;
            return result;
        }
        *bitmap = result_bitmap;
        return S_OK;
    }

    HRESULT draw_bitmap(
        Bitmap* bitmap,
        float left,
        float top,
        float right,
        float bottom,
        float opacity) noexcept {
        if (!drawing_ || bitmap == nullptr || bitmap->owner != this ||
                !bitmap->resource || right <= left || bottom <= top) {
            return E_INVALIDARG;
        }
        const auto destination = D2D1::RectF(left, top, right, bottom);
        d2d_context_->DrawBitmap(
            bitmap->resource.Get(),
            &destination,
            std::clamp(opacity, 0.0f, 1.0f),
            D2D1_INTERPOLATION_MODE_LINEAR,
            nullptr);
        return S_OK;
    }

    HRESULT end_frame() noexcept {
        if (!d2d_context_ || !swap_chain_ || !drawing_) {
            return E_UNEXPECTED;
        }
        drawing_ = false;
        auto result = d2d_context_->EndDraw();
        if (result == D2DERR_RECREATE_TARGET) {
            d2d_context_->SetTarget(nullptr);
            target_.Reset();
            result = create_target();
            if (FAILED(result)) {
                return result;
            }
            return S_FALSE;
        }
        if (FAILED(result)) {
            return result;
        }
        return swap_chain_->Present(1, 0);
    }

private:
    HRESULT create_target() noexcept {
        ComPtr<IDXGISurface> back_buffer;
        auto result = swap_chain_->GetBuffer(0, IID_PPV_ARGS(&back_buffer));
        if (FAILED(result)) {
            return result;
        }
        const auto properties = D2D1::BitmapProperties1(
            D2D1_BITMAP_OPTIONS_TARGET | D2D1_BITMAP_OPTIONS_CANNOT_DRAW,
            D2D1::PixelFormat(
                DXGI_FORMAT_B8G8R8A8_UNORM,
                D2D1_ALPHA_MODE_PREMULTIPLIED),
            dpi_,
            dpi_);
        result = d2d_context_->CreateBitmapFromDxgiSurface(
            back_buffer.Get(), &properties, &target_);
        if (SUCCEEDED(result)) {
            d2d_context_->SetTarget(target_.Get());
            d2d_context_->SetDpi(dpi_, dpi_);
        }
        return result;
    }

    SpdfD2DDriver driver_ = SPDF_D2D_DRIVER_NONE;
    D3D_FEATURE_LEVEL feature_level_ = D3D_FEATURE_LEVEL_10_0;
    float dpi_ = 96.0f;
    ComPtr<ID3D11Device> d3d_device_;
    ComPtr<IDXGIDevice> dxgi_device_;
    ComPtr<IDXGIFactory2> dxgi_factory_;
    ComPtr<IDXGISwapChain1> swap_chain_;
    ComPtr<ID2D1Factory1> d2d_factory_;
    ComPtr<ID2D1Device> d2d_device_;
    ComPtr<ID2D1DeviceContext> d2d_context_;
    ComPtr<ID2D1Bitmap1> target_;
    ComPtr<IDWriteFactory> dwrite_factory_;
    bool drawing_ = false;
};

}  // namespace

std::uint32_t spdf_d2d_abi_version() noexcept {
    return SPDF_D2D_ABI_VERSION;
}

std::int32_t spdf_d2d_probe(SpdfD2DInfo* info) noexcept {
    if (info == nullptr || info->struct_size < sizeof(SpdfD2DInfo)) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    reset_info(info);

    ComPtr<ID3D11Device> d3d_device;
    D3D_FEATURE_LEVEL feature_level = D3D_FEATURE_LEVEL_10_0;
    auto result = create_d3d_device(D3D_DRIVER_TYPE_HARDWARE, d3d_device, feature_level);
    if (SUCCEEDED(result)) {
        info->driver = SPDF_D2D_DRIVER_HARDWARE;
    } else {
        result = create_d3d_device(D3D_DRIVER_TYPE_WARP, d3d_device, feature_level);
        if (FAILED(result)) {
            info->last_hresult = static_cast<std::int32_t>(result);
            return static_cast<std::int32_t>(result);
        }
        info->driver = SPDF_D2D_DRIVER_WARP;
    }
    info->feature_level = static_cast<std::uint32_t>(feature_level);
    set_adapter_name(d3d_device.Get(), info);

    ComPtr<IDXGIDevice> dxgi_device;
    result = d3d_device.As(&dxgi_device);
    if (FAILED(result)) {
        info->last_hresult = static_cast<std::int32_t>(result);
        return static_cast<std::int32_t>(result);
    }

    D2D1_FACTORY_OPTIONS options{};
    ComPtr<ID2D1Factory1> d2d_factory;
    result = D2D1CreateFactory(
        D2D1_FACTORY_TYPE_SINGLE_THREADED,
        __uuidof(ID2D1Factory1),
        &options,
        reinterpret_cast<void**>(d2d_factory.GetAddressOf()));
    if (FAILED(result)) {
        info->last_hresult = static_cast<std::int32_t>(result);
        return static_cast<std::int32_t>(result);
    }

    ComPtr<ID2D1Device> d2d_device;
    result = d2d_factory->CreateDevice(dxgi_device.Get(), &d2d_device);
    if (FAILED(result)) {
        info->last_hresult = static_cast<std::int32_t>(result);
        return static_cast<std::int32_t>(result);
    }

    ComPtr<ID2D1DeviceContext> d2d_context;
    result = d2d_device->CreateDeviceContext(
        D2D1_DEVICE_CONTEXT_OPTIONS_NONE,
        &d2d_context);
    if (FAILED(result)) {
        info->last_hresult = static_cast<std::int32_t>(result);
        return static_cast<std::int32_t>(result);
    }

    ComPtr<IDWriteFactory> dwrite_factory;
    result = DWriteCreateFactory(
        DWRITE_FACTORY_TYPE_SHARED,
        __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown**>(dwrite_factory.GetAddressOf()));
    info->last_hresult = static_cast<std::int32_t>(result);
    return static_cast<std::int32_t>(result);
}

std::int32_t spdf_d2d_create_surface(
    std::uintptr_t hwnd,
    std::uint32_t width,
    std::uint32_t height,
    float dpi,
    SpdfD2DInfo* info,
    void** surface) noexcept {
    if (hwnd == 0 || info == nullptr || info->struct_size < sizeof(SpdfD2DInfo) ||
            surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    *surface = nullptr;
    reset_info(info);
    auto context = new (std::nothrow) Surface();
    if (context == nullptr) {
        info->last_hresult = static_cast<std::int32_t>(E_OUTOFMEMORY);
        return static_cast<std::int32_t>(E_OUTOFMEMORY);
    }
    const auto result = context->initialize(
        reinterpret_cast<HWND>(hwnd), width, height, dpi, info);
    info->last_hresult = static_cast<std::int32_t>(result);
    if (FAILED(result)) {
        delete context;
        return static_cast<std::int32_t>(result);
    }
    *surface = context;
    return static_cast<std::int32_t>(S_OK);
}

std::int32_t spdf_d2d_resize_surface(
    void* surface,
    std::uint32_t width,
    std::uint32_t height,
    float dpi) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(
        static_cast<Surface*>(surface)->resize(width, height, dpi));
}

std::int32_t spdf_d2d_clear_surface(void* surface, std::uint32_t argb) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->clear(argb));
}

std::int32_t spdf_d2d_begin_frame(void* surface, std::uint32_t argb) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(
        static_cast<Surface*>(surface)->begin_frame(argb));
}

std::int32_t spdf_d2d_create_bitmap(
    void* surface,
    const void* bgra_pixels,
    std::uint32_t width,
    std::uint32_t height,
    std::uint32_t stride,
    void** bitmap) noexcept {
    if (surface == nullptr || bitmap == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->create_bitmap(
        bgra_pixels,
        width,
        height,
        stride,
        reinterpret_cast<Surface::Bitmap**>(bitmap)));
}

std::int32_t spdf_d2d_draw_bitmap(
    void* surface,
    void* bitmap,
    float left,
    float top,
    float right,
    float bottom,
    float opacity) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->draw_bitmap(
        static_cast<Surface::Bitmap*>(bitmap),
        left,
        top,
        right,
        bottom,
        opacity));
}

std::int32_t spdf_d2d_end_frame(void* surface) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->end_frame());
}

void spdf_d2d_destroy_bitmap(void* bitmap) noexcept {
    delete static_cast<Surface::Bitmap*>(bitmap);
}

void spdf_d2d_destroy_surface(void* surface) noexcept {
    delete static_cast<Surface*>(surface);
}
