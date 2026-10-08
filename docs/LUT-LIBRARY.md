# LUT library and camera profiles

The optional **LUT library & camera presets** section keeps frequently used camera conversions and a chosen local LUT folder together. It starts collapsed to leave grading controls accessible. Choose a folder once and use its .cube dropdown; Refresh reloads the list after adding or removing files. The folder is remembered, not the grade or an automatic camera choice. Folder listings are naturally sorted and display at most 512 .cube entries.

Camera choices cover DJI O4/O4 Pro D-Log M, Osmo Action 4 and Action 5 Pro D-Log M, GoPro GP-Log, and Insta360 Ace Pro 2 I-Log. These are explicitly labeled recording profiles, not promises that every camera/recording has been tested. **Get the official camera LUT** opens the manufacturer's download page. Download/unzip the matching file, choose that file once for the selected profile, and **Use LUT** reselects it later. Canceling or choosing an invalid file never creates a successful binding. Files are validated by the existing bounded .cube parser; missing files show an error and block export.

Manufacturer LUT files are not embedded or redistributed: their free downloads do not establish a redistribution license. This directory contains no user footage or manufacturer LUTs. A profile remembers a local file selected by the user, not an assumed filename. New footage is not graded automatically. GoPro GP-Log differs from Protune Flat, and GoPro LUT versions/gamut must match the recording. Insta360 I-Log is not interchangeable with earlier Flat/Log modes or other models. DJI D-Log differs from D-Log M; use the model's LUT rather than assuming all DJI conversions match.

Only one standard 3D .cube conversion is applied. A creative Rec.709-input LUT alone is not a log-to-Rec.709 conversion. Avoid converting an already graded export a second time. Original footage stays untouched, and projects/queues keep the selected file URL and grade.

These are desktop development changes. Windows and sandboxed library persistence require their own native acceptance before a release claim.
