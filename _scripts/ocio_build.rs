// SPDX-License-Identifier: GPL-3.0-or-later
// Shared app/fixture build configuration. The caller checks the Cargo feature.
pub fn build_bridge(repository: &std::path::Path) {
    use std::{env, path::PathBuf};
    for name in ["OCIO_ROOT", "OCIO_LINK_NAME"] {
        println!("cargo:rerun-if-env-changed={name}");
    }
    let root = PathBuf::from(
        env::var("OCIO_ROOT")
            .expect("ocio-runtime requires a pinned OpenColorIO 2.4.2 install prefix in OCIO_ROOT"),
    );
    let source = repository.join("src/rendering/ocio");
    for file in ["grade.hpp", "bridge.h", "bridge.cpp"] {
        println!("cargo:rerun-if-changed={}", source.join(file).display());
    }
    let mut config = cc::Build::new();
    config
        .cpp(true)
        .std("c++17")
        .include(root.join("include"))
        .file(source.join("bridge.cpp"));
    if env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") {
        // OCIO errors must unwind C++ objects before the C ABI catches them.
        config.flag("/EHsc");
    }
    config.compile("gyroflow_ocio_bridge");
    println!(
        "cargo:rustc-link-search=native={}",
        root.join("lib").display()
    );
    println!(
        "cargo:rustc-link-lib={}",
        env::var("OCIO_LINK_NAME").unwrap_or("OpenColorIO".into())
    );
    if env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos")
        || env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("linux")
    {
        println!(
            "cargo:rustc-link-arg=-Wl,-rpath,{}",
            root.join("lib").display()
        );
    }
}
