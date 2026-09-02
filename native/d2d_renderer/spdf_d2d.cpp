#define SPDF_D2D_EXPORTS
#include "spdf_d2d.h"

#include <algorithm>
#include <cstring>
#include <iterator>
#include <new>
#include <unordered_map>
#include <vector>

#include <d2d1_1.h>
#include <d2d1_2.h>
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

    struct Path {
        Surface* owner;
        ComPtr<ID2D1Geometry> resource;
        ComPtr<ID2D1GeometryRealization> fill_realization;
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
        // Geometry realizations cache tessellation for repeated zoom/pan frames.
        // They are optional and FillGeometry remains the compatibility path.
        d2d_context_.As(&d2d_context1_);
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
        if (!swap_chain_ || drawing_ || width == 0 || height == 0) {
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
        if (!d2d_context_ || !target_ || drawing_ || clip_depth_ != 0) {
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

    HRESULT set_transform(
        float m11,
        float m12,
        float m21,
        float m22,
        float dx,
        float dy) noexcept {
        if (!d2d_context_ || !drawing_) {
            return E_UNEXPECTED;
        }
        d2d_context_->SetTransform(D2D1::Matrix3x2F(
            m11, m12, m21, m22, dx, dy));
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

    HRESULT create_path(
        const SpdfD2DPathCommand* commands,
        std::uint32_t command_count,
        bool even_odd,
        Path** path) noexcept {
        if (!d2d_factory_ || commands == nullptr || command_count == 0 || path == nullptr) {
            return E_INVALIDARG;
        }
        *path = nullptr;
        auto result_path = new (std::nothrow) Path{this, nullptr, nullptr};
        if (result_path == nullptr) {
            return E_OUTOFMEMORY;
        }
        ComPtr<ID2D1PathGeometry> geometry;
        auto result = d2d_factory_->CreatePathGeometry(&geometry);
        ComPtr<ID2D1GeometrySink> sink;
        if (SUCCEEDED(result)) {
            result = geometry->Open(&sink);
        }
        if (FAILED(result)) {
            delete result_path;
            return result;
        }
        sink->SetFillMode(even_odd ? D2D1_FILL_MODE_ALTERNATE : D2D1_FILL_MODE_WINDING);
        bool figure_open = false;
        for (std::uint32_t index = 0; index < command_count; ++index) {
            const auto& command = commands[index];
            switch (command.type) {
            case SPDF_D2D_PATH_MOVE:
                if (figure_open) {
                    sink->EndFigure(D2D1_FIGURE_END_OPEN);
                }
                sink->BeginFigure(
                    D2D1::Point2F(command.points[0], command.points[1]),
                    D2D1_FIGURE_BEGIN_FILLED);
                figure_open = true;
                break;
            case SPDF_D2D_PATH_LINE:
                if (!figure_open) {
                    result = E_INVALIDARG;
                    break;
                }
                sink->AddLine(D2D1::Point2F(command.points[0], command.points[1]));
                break;
            case SPDF_D2D_PATH_CUBIC:
                if (!figure_open) {
                    result = E_INVALIDARG;
                    break;
                }
                sink->AddBezier(D2D1::BezierSegment(
                    D2D1::Point2F(command.points[0], command.points[1]),
                    D2D1::Point2F(command.points[2], command.points[3]),
                    D2D1::Point2F(command.points[4], command.points[5])));
                break;
            case SPDF_D2D_PATH_CLOSE:
                if (!figure_open) {
                    result = E_INVALIDARG;
                    break;
                }
                sink->EndFigure(D2D1_FIGURE_END_CLOSED);
                figure_open = false;
                break;
            default:
                result = E_INVALIDARG;
                break;
            }
            if (FAILED(result)) {
                break;
            }
        }
        if (figure_open) {
            sink->EndFigure(D2D1_FIGURE_END_OPEN);
        }
        if (SUCCEEDED(result)) {
            result = sink->Close();
        }
        if (FAILED(result)) {
            delete result_path;
            return result;
        }
        result_path->resource = geometry;
        realize_path(result_path);
        *path = result_path;
        return S_OK;
    }

    HRESULT create_geometry_group(
        Path* const* paths,
        const SpdfD2DTransform* transforms,
        std::uint32_t path_count,
        bool even_odd,
        Path** group) noexcept {
        if (!d2d_factory_ || paths == nullptr || transforms == nullptr ||
                path_count == 0 || group == nullptr) {
            return E_INVALIDARG;
        }
        *group = nullptr;
        std::vector<ComPtr<ID2D1TransformedGeometry>> transformed;
        std::vector<ID2D1Geometry*> geometries;
        transformed.reserve(path_count);
        geometries.reserve(path_count);
        for (std::uint32_t index = 0; index < path_count; ++index) {
            const auto path = paths[index];
            if (path == nullptr || path->owner != this || !path->resource) {
                return E_INVALIDARG;
            }
            const auto& matrix = transforms[index];
            ComPtr<ID2D1TransformedGeometry> instance;
            const auto d2d_matrix = D2D1::Matrix3x2F(
                matrix.m11, matrix.m12, matrix.m21, matrix.m22,
                matrix.dx, matrix.dy);
            const auto result = d2d_factory_->CreateTransformedGeometry(
                path->resource.Get(),
                &d2d_matrix,
                &instance);
            if (FAILED(result)) {
                return result;
            }
            geometries.push_back(instance.Get());
            transformed.push_back(std::move(instance));
        }
        auto result_group = new (std::nothrow) Path{this, nullptr, nullptr};
        if (result_group == nullptr) {
            return E_OUTOFMEMORY;
        }
        ComPtr<ID2D1GeometryGroup> geometry_group;
        const auto result = d2d_factory_->CreateGeometryGroup(
            even_odd ? D2D1_FILL_MODE_ALTERNATE : D2D1_FILL_MODE_WINDING,
            geometries.data(), path_count, &geometry_group);
        if (FAILED(result)) {
            delete result_group;
            return result;
        }
        result_group->resource = geometry_group;
        realize_path(result_group);
        *group = result_group;
        return S_OK;
    }

    HRESULT push_clip_path(Path* path) noexcept {
        if (!drawing_ || path == nullptr || path->owner != this ||
                !path->resource) {
            return E_INVALIDARG;
        }
        const auto parameters = D2D1::LayerParameters1(
            D2D1::InfiniteRect(),
            path->resource.Get(),
            D2D1_ANTIALIAS_MODE_PER_PRIMITIVE,
            D2D1::Matrix3x2F::Identity(),
            1.0f,
            nullptr,
            D2D1_LAYER_OPTIONS1_NONE);
        d2d_context_->PushLayer(parameters, nullptr);
        ++clip_depth_;
        return S_OK;
    }

    HRESULT pop_clip() noexcept {
        if (!drawing_ || clip_depth_ == 0) {
            return E_UNEXPECTED;
        }
        d2d_context_->PopLayer();
        --clip_depth_;
        return S_OK;
    }

    HRESULT fill_rect(
        float left,
        float top,
        float right,
        float bottom,
        std::uint32_t argb) noexcept {
        if (!drawing_ || right <= left || bottom <= top) {
            return E_INVALIDARG;
        }
        ComPtr<ID2D1SolidColorBrush> brush;
        auto result = create_brush(argb, &brush);
        if (FAILED(result)) {
            return result;
        }
        d2d_context_->FillRectangle(D2D1::RectF(left, top, right, bottom), brush.Get());
        return S_OK;
    }

    HRESULT stroke_rect(
        float left,
        float top,
        float right,
        float bottom,
        std::uint32_t argb,
        float width) noexcept {
        if (!drawing_ || right <= left || bottom <= top || width <= 0.0f) {
            return E_INVALIDARG;
        }
        ComPtr<ID2D1SolidColorBrush> brush;
        auto result = create_brush(argb, &brush);
        if (FAILED(result)) {
            return result;
        }
        d2d_context_->DrawRectangle(
            D2D1::RectF(left, top, right, bottom), brush.Get(), width);
        return S_OK;
    }

    HRESULT fill_path(Path* path, std::uint32_t argb) noexcept {
        if (!drawing_ || path == nullptr || path->owner != this || !path->resource) {
            return E_INVALIDARG;
        }
        ComPtr<ID2D1SolidColorBrush> brush;
        auto result = create_brush(argb, &brush);
        if (FAILED(result)) {
            return result;
        }
        if (d2d_context1_ && path->fill_realization) {
            d2d_context1_->DrawGeometryRealization(
                path->fill_realization.Get(), brush.Get());
        } else {
            d2d_context_->FillGeometry(path->resource.Get(), brush.Get());
        }
        return S_OK;
    }

    HRESULT stroke_path(Path* path, std::uint32_t argb, float width) noexcept {
        if (!drawing_ || path == nullptr || path->owner != this ||
                !path->resource || width <= 0.0f) {
            return E_INVALIDARG;
        }
        ComPtr<ID2D1SolidColorBrush> brush;
        auto result = create_brush(argb, &brush);
        if (FAILED(result)) {
            return result;
        }
        d2d_context_->DrawGeometry(path->resource.Get(), brush.Get(), width);
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
        if (clip_depth_ != 0) {
            while (clip_depth_ != 0) {
                d2d_context_->PopLayer();
                --clip_depth_;
            }
            drawing_ = false;
            d2d_context_->EndDraw();
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
    void realize_path(Path* path) noexcept {
        if (d2d_context1_ && path != nullptr && path->resource) {
            // 0.05 PDF points stays below half a pixel at the 800% UI limit.
            d2d_context1_->CreateFilledGeometryRealization(
                path->resource.Get(), 0.05f, &path->fill_realization);
        }
    }

    HRESULT create_brush(
        std::uint32_t argb,
        ID2D1SolidColorBrush** brush) noexcept {
        const auto cached = brushes_.find(argb);
        if (cached != brushes_.end()) {
            return cached->second.CopyTo(brush);
        }
        const auto alpha = static_cast<float>((argb >> 24) & 0xff) / 255.0f;
        const auto red = static_cast<float>((argb >> 16) & 0xff) / 255.0f;
        const auto green = static_cast<float>((argb >> 8) & 0xff) / 255.0f;
        const auto blue = static_cast<float>(argb & 0xff) / 255.0f;
        ComPtr<ID2D1SolidColorBrush> created;
        const auto result = d2d_context_->CreateSolidColorBrush(
            D2D1::ColorF(red, green, blue, alpha), &created);
        if (FAILED(result)) {
            return result;
        }
        brushes_.emplace(argb, created);
        return created.CopyTo(brush);
    }

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
    ComPtr<ID2D1DeviceContext1> d2d_context1_;
    ComPtr<ID2D1Bitmap1> target_;
    ComPtr<IDWriteFactory> dwrite_factory_;
    std::unordered_map<std::uint32_t, ComPtr<ID2D1SolidColorBrush>> brushes_;
    std::uint32_t clip_depth_ = 0;
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

std::int32_t spdf_d2d_set_transform(
    void* surface,
    float m11,
    float m12,
    float m21,
    float m22,
    float dx,
    float dy) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->set_transform(
        m11, m12, m21, m22, dx, dy));
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

std::int32_t spdf_d2d_create_path(
    void* surface,
    const SpdfD2DPathCommand* commands,
    std::uint32_t command_count,
    std::uint32_t even_odd,
    void** path) noexcept {
    if (surface == nullptr || path == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->create_path(
        commands,
        command_count,
        even_odd != 0,
        reinterpret_cast<Surface::Path**>(path)));
}

std::int32_t spdf_d2d_create_geometry_group(
    void* surface,
    void* const* paths,
    const SpdfD2DTransform* transforms,
    std::uint32_t path_count,
    std::uint32_t even_odd,
    void** group) noexcept {
    if (surface == nullptr || paths == nullptr || transforms == nullptr ||
            group == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(
        static_cast<Surface*>(surface)->create_geometry_group(
            reinterpret_cast<Surface::Path* const*>(paths), transforms,
            path_count, even_odd != 0,
            reinterpret_cast<Surface::Path**>(group)));
}

std::int32_t spdf_d2d_push_clip_path(void* surface, void* path) noexcept {
    if (surface == nullptr || path == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(
        static_cast<Surface*>(surface)->push_clip_path(
            static_cast<Surface::Path*>(path)));
}

std::int32_t spdf_d2d_pop_clip(void* surface) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(
        static_cast<Surface*>(surface)->pop_clip());
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

std::int32_t spdf_d2d_fill_rect(
    void* surface,
    float left,
    float top,
    float right,
    float bottom,
    std::uint32_t argb) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->fill_rect(
        left, top, right, bottom, argb));
}

std::int32_t spdf_d2d_stroke_rect(
    void* surface,
    float left,
    float top,
    float right,
    float bottom,
    std::uint32_t argb,
    float width) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->stroke_rect(
        left, top, right, bottom, argb, width));
}

std::int32_t spdf_d2d_fill_path(
    void* surface,
    void* path,
    std::uint32_t argb) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->fill_path(
        static_cast<Surface::Path*>(path), argb));
}

std::int32_t spdf_d2d_stroke_path(
    void* surface,
    void* path,
    std::uint32_t argb,
    float width) noexcept {
    if (surface == nullptr) {
        return static_cast<std::int32_t>(E_INVALIDARG);
    }
    return static_cast<std::int32_t>(static_cast<Surface*>(surface)->stroke_path(
        static_cast<Surface::Path*>(path), argb, width));
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

void spdf_d2d_destroy_path(void* path) noexcept {
    delete static_cast<Surface::Path*>(path);
}

void spdf_d2d_destroy_surface(void* surface) noexcept {
    delete static_cast<Surface*>(surface);
}
