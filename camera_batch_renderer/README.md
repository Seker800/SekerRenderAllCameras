# Render All Cameras

Render still images from every camera in the current Blender Scene. The Extension uses the saved
`.blend` name, camera name, channel and important render parameters in each filename.

## Use

1. Save the `.blend` file.
2. In the 3D Viewport, press **N** and open **Batch Render → Render All Cameras**. The same
   controls remain available under **Output Properties → Render All Cameras**.
3. Choose a batch prefix and optionally enable Alpha or Object ID.
4. Click **Render All Cameras**.

Outputs are written to `RenderOutput/<batch>/` next to the `.blend`. Beauty preserves the current
render settings. Alpha is a lossless grayscale PNG. Object ID is an un-antialiased RGB PNG whose
exact colors are documented in the accompanying `ObjectID.json` file.

The Extension never saves the `.blend`. Temporary auxiliary scenes are removed and the active
camera, frame, Film Transparent setting, and render filepath are restored after completion,
cancellation, or a handled failure.
