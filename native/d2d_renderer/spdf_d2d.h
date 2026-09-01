#pragma once

#include <cstddef>
#include <cstdint>

#ifdef SPDF_D2D_EXPORTS
#define SPDF_D2D_API extern "C" __declspec(dllexport)
#else
#define SPDF_D2D_API extern "C" __declspec(dllimport)
#endif

constexpr std::uint32_t SPDF_D2D_ABI_VERSION = 1;
constexpr std::uint32_t SPDF_D2D_ADAPTER_NAME_LENGTH = 128;

enum SpdfD2DDriver : std::uint32_t {
    SPDF_D2D_DRIVER_NONE = 0,
    SPDF_D2D_DRIVER_HARDWARE = 1,
    SPDF_D2D_DRIVER_WARP = 2,
};

struct SpdfD2DInfo {
    std::uint32_t struct_size;
    std::uint32_t abi_version;
    std::uint32_t driver;
    std::uint32_t feature_level;
    std::int32_t last_hresult;
    wchar_t adapter_name[SPDF_D2D_ADAPTER_NAME_LENGTH];
};

static_assert(sizeof(wchar_t) == 2, "The sPDF D2D ABI requires Windows wchar_t");
static_assert(offsetof(SpdfD2DInfo, adapter_name) == 20, "Unexpected D2D ABI layout");
static_assert(sizeof(SpdfD2DInfo) == 276, "Unexpected D2D ABI size");

SPDF_D2D_API std::uint32_t spdf_d2d_abi_version() noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_probe(SpdfD2DInfo* info) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_create_surface(
    std::uintptr_t hwnd,
    std::uint32_t width,
    std::uint32_t height,
    float dpi,
    SpdfD2DInfo* info,
    void** surface) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_resize_surface(
    void* surface,
    std::uint32_t width,
    std::uint32_t height,
    float dpi) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_clear_surface(
    void* surface,
    std::uint32_t argb) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_begin_frame(
    void* surface,
    std::uint32_t argb) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_create_bitmap(
    void* surface,
    const void* bgra_pixels,
    std::uint32_t width,
    std::uint32_t height,
    std::uint32_t stride,
    void** bitmap) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_draw_bitmap(
    void* surface,
    void* bitmap,
    float left,
    float top,
    float right,
    float bottom,
    float opacity) noexcept;
SPDF_D2D_API std::int32_t spdf_d2d_end_frame(void* surface) noexcept;
SPDF_D2D_API void spdf_d2d_destroy_bitmap(void* bitmap) noexcept;
SPDF_D2D_API void spdf_d2d_destroy_surface(void* surface) noexcept;
