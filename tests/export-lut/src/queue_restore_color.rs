// SPDX-License-Identifier: GPL-3.0-or-later
//! A render queue saved with project jobs and restored after a restart:
//! every job keeps its own LUT and eight controls even when the project file
//! was saved again with another grade, and nothing else changes.
use crate::queued_color::{restore, snapshot, FIELDS};
use serde_json::{json, Value};

const CONTROLS: [&str; 8] = ["brightness", "contrast", "shadows", "highlights", "exposure", "saturation", "warmth", "tint"];

/// `output` as `serde_json::to_value(&RenderOptions)` writes it (all fields
/// present), with the given grade.
fn render_options(lut_url: &str, controls: [f64; 8]) -> Value {
    let mut output = json!({
        "codec": "H.265/HEVC", "codec_options": "", "output_folder": "file:///exports/", "output_filename": "clip_stabilized.mp4",
        "output_width": 3840, "output_height": 2160, "input_filename": "clip.mp4", "input_url": "file:///media/clip.mp4",
        "bitrate": 150.0, "use_gpu": true, "audio": true, "pixel_format": "", "lut_url": lut_url,
        "encoder_options": "", "metadata": { "comment": "" }, "keyframe_distance": 1.0, "preserve_other_tracks": false,
        "pad_with_black": false, "export_trims_separately": false, "audio_codec": "AAC", "interpolation": "Lanczos4",
    });
    for (key, v) in CONTROLS.iter().zip(controls) {
        output[*key] = json!(v);
    }
    output
}

const GRADE_X: [f64; 8] = [0.12, -0.3, 0.25, -0.5, 1.37, 0.42, -0.07, 0.5];
const GRADE_Y: [f64; 8] = [-0.4, 0.2, -0.13, 0.33, -1.8, -1.0, 0.5, -0.29];

/// The entry `save_render_queue` writes for a project job, after the trip
/// through the settings store (a JSON string), and the colour that
/// `restore_render_queue` hands to `add_file_with_color`.
fn saved_and_reloaded(job: &Value, create_bookmark: impl Fn(&str) -> Option<String>) -> Option<Value> {
    let color = snapshot(job, create_bookmark);
    let entry = json!({ "project_file": "file:///projects/clip.gyroflow", "queued_color": color }).to_string();
    let reloaded: Value = serde_json::from_str(&entry).unwrap();
    reloaded.get("queued_color").cloned()
}

fn no_bookmarks(_: &str) -> Option<String> { None }

/// The nine fields as RenderOptions::update_from_json reads them.
fn color_of(output: &Value) -> (String, Vec<u64>) {
    (
        output["lut_url"].as_str().expect("lut_url must stay a string").to_owned(),
        CONTROLS.iter().map(|k| output[*k].as_f64().unwrap_or_else(|| panic!("{k} must stay a number")).to_bits()).collect(),
    )
}

fn without_color(output: &Value) -> Value {
    let mut output = output.clone();
    for key in FIELDS {
        output.as_object_mut().unwrap().remove(key);
    }
    output
}

#[test]
fn each_of_the_nine_fields_comes_back_from_the_job_not_the_project() {
    // The project file was saved last with grade Y; the job was queued with X.
    let project = render_options("file:///luts/y.cube", GRADE_Y);
    let job = render_options("file:///luts/x.cube", GRADE_X);
    let restored = restore(&project, saved_and_reloaded(&job, no_bookmarks).as_ref(), no_bookmarks);
    assert_eq!(color_of(&restored), color_of(&job));
    assert_eq!(without_color(&restored), without_color(&project), "only the nine colour fields may change");

    // One field at a time, so a field dropped on either side is caught by name.
    for (i, field) in FIELDS.iter().enumerate() {
        let mut job = project.clone();
        if i == 0 {
            job["lut_url"] = json!("file:///luts/only.cube");
        } else {
            job[*field] = json!(GRADE_X[i - 1]);
        }
        let restored = restore(&project, saved_and_reloaded(&job, no_bookmarks).as_ref(), no_bookmarks);
        assert_eq!(restored, job, "{field}");
    }
}

#[test]
fn explicit_neutral_values_win_over_a_graded_project() {
    let project = render_options("file:///luts/y.cube", GRADE_Y);
    let neutral = render_options("", [0.0; 8]);
    let color = saved_and_reloaded(&neutral, |_| panic!("no bookmark for an empty LUT")).unwrap();
    for key in FIELDS {
        assert!(color.get(key).is_some(), "{key}: a neutral value must be saved, not left out");
    }
    assert!(color.get("lut_bookmark").is_none());
    let restored = restore(&project, Some(&color), |_| panic!("no bookmark to resolve"));
    assert_eq!(color_of(&restored), color_of(&neutral));
    assert_eq!(restored, neutral);
}

#[test]
fn every_slider_position_survives_the_saved_queue_bit_for_bit() {
    // Export.qml saves the controls as slider / 100 (exposure as set, 0.01 steps).
    let project = render_options("", [0.0; 8]);
    for k in -200..=200 {
        let v = k as f64 / 100.0;
        let job = render_options("", [v; 8]);
        let restored = restore(&project, saved_and_reloaded(&job, no_bookmarks).as_ref(), no_bookmarks);
        assert_eq!(color_of(&restored), color_of(&job), "{v}");
    }
}

#[test]
fn queues_saved_before_this_change_restore_exactly_as_before() {
    let project = render_options("file:///luts/y.cube", GRADE_Y);
    // No "queued_color" key at all, or the null written when a job had no output.
    for saved in [None, Some(Value::Null), Some(json!("x")), Some(json!({}))] {
        assert_eq!(restore(&project, saved.as_ref(), |_| panic!("nothing to resolve")), project, "{saved:?}");
    }
    assert_eq!(snapshot(&Value::Null, no_bookmarks), None);
}

#[test]
fn partial_project_output_takes_the_queued_colour_and_keeps_everything_else() {
    let job = render_options("file:///luts/x.cube", GRADE_X);
    let color = saved_and_reloaded(&job, no_bookmarks);
    // An older project: no LUT or new controls, only some output fields.
    let project = json!({ "codec": "ProRes", "codec_options": "422 HQ", "output_folder": "file:///exports/", "brightness": 0.2 });
    let restored = restore(&project, color.as_ref(), no_bookmarks);
    assert_eq!(color_of(&restored), color_of(&job));
    assert_eq!(without_color(&restored), without_color(&project));
    // Not an object: left as it is (add_file then adds no job, as before).
    for project in [Value::Null, json!([1, 2]), json!("output")] {
        assert_eq!(restore(&project, color.as_ref(), no_bookmarks), project);
    }
}

#[test]
fn a_partial_or_damaged_saved_colour_only_replaces_the_fields_it_holds() {
    let project = render_options("file:///luts/y.cube", GRADE_Y);
    let saved = json!({ "lut_url": 5, "brightness": "0.5", "contrast": null, "shadows": 0.0, "tint": -0.25 });
    let restored = restore(&project, Some(&saved), no_bookmarks);
    let mut expected = project.clone();
    expected["shadows"] = json!(0.0);
    expected["tint"] = json!(-0.25);
    assert_eq!(restored, expected);
}

#[test]
fn each_job_resolves_its_own_lut_bookmark_like_a_project_does() {
    // Stand-in for filesystem::apple: a bookmark names its file; "moved:"
    // bookmarks resolve to where the file is now, "lost:" ones to nothing.
    let create = |url: &str| Some(format!("bm:{url}"));
    let resolve = |bookmark: &str| {
        let url = bookmark.strip_prefix("bm:").unwrap();
        Some(if url.contains("lost") { String::new() } else { url.replace("/old/", "/moved/") })
    };
    let project = render_options("file:///luts/project.cube", GRADE_Y);
    let jobs = [
        ("file:///old/a.cube", "file:///moved/a.cube"),       // moved since queueing: bookmark wins
        ("file:///luts/b.cube", "file:///luts/b.cube"),       // in place
        ("file:///old/lost.cube", "file:///old/lost.cube"),   // unresolvable: keep the saved URL (export then fails closed)
    ];
    for (queued, expected) in jobs {
        let job = render_options(queued, GRADE_X);
        let color = saved_and_reloaded(&job, create).unwrap();
        assert_eq!(color["lut_bookmark"], json!(format!("bm:{queued}")), "bookmark must belong to this job's LUT");
        let restored = restore(&project, Some(&color), resolve);
        assert_eq!(restored["lut_url"], json!(expected), "{queued}");
        assert_eq!(restored.get("lut_bookmark"), project.get("lut_bookmark"));
    }

    // Core resolves only next to a non-empty URL; an empty or missing bookmark resolves nothing.
    for saved in [
        json!({ "lut_url": "", "lut_bookmark": "bm:file:///old/a.cube" }),
        json!({ "lut_url": "file:///old/a.cube", "lut_bookmark": "" }),
        json!({ "lut_url": "file:///old/a.cube" }),
    ] {
        let restored = restore(&project, Some(&saved), |_| panic!("must not resolve {saved}"));
        assert_eq!(restored["lut_url"], saved["lut_url"]);
    }
    // An empty bookmark from the platform is not stored.
    assert!(snapshot(&render_options("file:///luts/b.cube", GRADE_X), |_| Some(String::new())).unwrap().get("lut_bookmark").is_none());
}
