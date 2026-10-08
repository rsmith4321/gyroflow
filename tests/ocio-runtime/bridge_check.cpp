// SPDX-License-Identifier: GPL-3.0-or-later
// Isolated C ABI contract/concurrency checks. This is not Rust layout validation,
// app preview, real-video, encoder or portable-package acceptance.
#include "../../src/rendering/ocio/bridge.h"
extern "C" {
#include <libavutil/frame.h>
#include <libavutil/pixfmt.h>
}
#include <array>
#include <atomic>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {
constexpr uint32_t width = 167, height = 17;
constexpr size_t guard = 8;
constexpr float sentinel = -123.5f;

void require(bool value, const char * message) {
    if (!value) throw std::runtime_error(message);
}

struct Planes {
    std::array<size_t, 3> strides;
    std::array<std::vector<float>, 3> data;
    explicit Planes(std::array<size_t, 3> rows = {174, 174, 174}) : strides(rows) {
        for (size_t p = 0; p < 3; ++p) {
            data[p].assign(2 * guard + strides[p] * height, sentinel);
            for (size_t y = 0; y < height; ++y)
                for (size_t x = 0; x < width; ++x)
                    data[p][guard + y * strides[p] + x] = float((p + x + y) % 13) / 12;
        }
    }
    float * plane(size_t p) { return data[p].data() + guard; }
    float sample(size_t p, size_t x, size_t y) const { return data[p][guard + y * strides[p] + x]; }
    void check_guards() const {
        for (size_t p = 0; p < 3; ++p) {
            for (size_t i = 0; i < guard; ++i) {
                require(data[p][i] == sentinel, "Prefix guard changed");
                require(data[p][guard + strides[p] * height + i] == sentinel, "Suffix guard changed");
            }
            for (size_t y = 0; y < height; ++y)
                for (size_t x = width; x < strides[p]; ++x)
                    require(data[p][guard + y * strides[p] + x] == sentinel, "Row padding changed");
        }
    }
};

void apply(const void * processor, Planes & image) {
    char error[4096] = {};
    const auto & s = image.strides;
    require(gp_ocio_apply(processor, image.plane(0), image.plane(1), image.plane(2),
        width, height, s[0] * sizeof(float), s[1] * sizeof(float), s[2] * sizeof(float),
        error, sizeof(error)) == 1, error);
    image.check_guards();
}

struct Processor {
    void * handle;
    explicit Processor(const std::array<double, 8> & parameters) : handle(nullptr) {
        char error[4096] = {};
        handle = gp_ocio_create(parameters.data(), error, sizeof(error));
        require(handle != nullptr, error);
    }
    ~Processor() { gp_ocio_destroy(handle); }
    Processor(const Processor &) = delete;
    Processor & operator=(const Processor &) = delete;
};

void negative_stride_contract() {
    // av_frame_make_writable does not normalize a writable negative-stride
    // image. Rust must inspect signed raw linesizes before ffmpeg-next's data()
    // wrappers. This demonstrates that precondition; it does not call the Rust
    // validator and does not pass invalid unsigned strides to OCIO.
    AVFrame * frame = av_frame_alloc();
    require(frame != nullptr, "Cannot allocate AVFrame");
    frame->format = AV_PIX_FMT_GBRPF32LE;
    frame->width = 17; frame->height = 5;
    if (av_frame_get_buffer(frame, 32) != 0) {
        av_frame_free(&frame); throw std::runtime_error("Cannot allocate frame data");
    }
    for (int p = 0; p < 3; ++p) {
        frame->data[p] += (frame->height - 1) * frame->linesize[p];
        frame->linesize[p] = -frame->linesize[p];
    }
    const int stride = frame->linesize[0];
    const int result = av_frame_make_writable(frame);
    const bool retained = frame->linesize[0] == stride && stride < 0;
    av_frame_free(&frame);
    require(result == 0 && retained, "Expected writable negative stride contract changed");
}

void rejected_parameters() {
    const std::array<double, 8> limits = {.5, .5, .5, .5, 2, 1, 1, 1};
    for (size_t p = 0; p < limits.size(); ++p) {
        for (double invalid : {std::numeric_limits<double>::quiet_NaN(),
                std::numeric_limits<double>::infinity(), -limits[p] - .01, limits[p] + .01}) {
            std::array<double, 8> settings = {};
            settings[p] = invalid;
            // Error output must stay within a capacity of two bytes and end in
            // NUL even when the upstream exception message is much longer.
            char buffer[4] = {'L', '?', '?', 'R'};
            void * handle = gp_ocio_create(settings.data(), buffer + 1, 2);
            if (handle) gp_ocio_destroy(handle);
            require(handle == nullptr, "Invalid parameter accepted");
            require(buffer[0] == 'L' && buffer[2] == 0 && buffer[3] == 'R', "Error buffer bounds changed");
        }
    }
    char error[16] = {};
    require(gp_ocio_create(nullptr, error, sizeof(error)) == nullptr && error[0] != 0,
        "Missing parameters accepted");
    require(gp_ocio_create(nullptr, nullptr, 0) == nullptr, "Null error buffer was not supported");
    gp_ocio_destroy(nullptr);
}
}

int main() {
    try {
        negative_stride_contract();
        rejected_parameters();
        Processor processor({.12, .18, .3, -.4, .37, .23, .41, -.27});
        Planes original, expected;
        apply(processor.handle, expected);
        require(original.data != expected.data, "Combined grade was bypassed");

        // Share one immutable official CPU processor across eight actual threads.
        // Every call owns disjoint buffers; compare every byte with serial output.
        std::atomic<unsigned> errors{0};
        std::vector<std::thread> threads;
        for (int t = 0; t < 8; ++t) threads.emplace_back([&] {
            for (int n = 0; n < 100; ++n) {
                try {
                    Planes image = original;
                    apply(processor.handle, image);
                    if (image.data != expected.data) ++errors;
                } catch (...) { ++errors; }
            }
        });
        for (auto & thread : threads) thread.join();
        require(errors == 0, "Concurrent processor differed from serial output");

        Planes unequal({174, 177, 181});
        apply(processor.handle, unequal);
        for (size_t p = 0; p < 3; ++p)
            for (size_t y = 0; y < height; ++y)
                for (size_t x = 0; x < width; ++x)
                    require(unequal.sample(p, x, y) == expected.sample(p, x, y),
                        "Unequal-stride output differed from equal-stride output");

        Processor neutral({});
        Planes unchanged = original;
        apply(neutral.handle, unchanged);
        require(unchanged.data == original.data, "Neutral processor changed pixels or padding");

        char error[4096] = {};
        char tiny[8] = {};
        require(gp_ocio_shader(processor.handle, tiny, sizeof(tiny), error, sizeof(error)) == 0
            && error[0] != 0, "Small shader buffer accepted");
        std::vector<char> shader(256 * 1024);
        require(gp_ocio_shader(processor.handle, shader.data(), shader.size(), error, sizeof(error)) > 0,
            "Shader extraction failed");
        require(gp_ocio_shader(nullptr, shader.data(), shader.size(), error, sizeof(error)) == 0,
            "Missing shader processor accepted");
        Planes rejected = original;
        require(gp_ocio_apply(processor.handle, rejected.plane(0), rejected.plane(1), rejected.plane(2),
            width, height, width * 4 - 1, 174 * 4, 174 * 4, error, sizeof(error)) == 0,
            "Short row stride accepted");
        require(gp_ocio_apply(nullptr, rejected.plane(0), rejected.plane(1), rejected.plane(2),
            width, height, 174 * 4, 174 * 4, 174 * 4, error, sizeof(error)) == 0,
            "Missing apply processor accepted");
        require(gp_ocio_apply(processor.handle, rejected.plane(0), rejected.plane(1), rejected.plane(2),
            0, height, 174 * 4, 174 * 4, 174 * 4, error, sizeof(error)) == 0,
            "Empty image accepted");
        require(rejected.data == original.data, "Rejected image was modified");

        std::cout << "bridge_check: 800 concurrent calls match serial output; unequal strides, "
            "neutral, guards/padding, 32 invalid parameters, error bounds, shader capacities "
            "and writable negative-stride contract passed\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "bridge_check: " << error.what() << '\n'; return 1;
    }
}
