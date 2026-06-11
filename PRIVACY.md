# Privacy

SpineSpy processes all webcam imagery **on your device**.

- The camera opens only briefly each interval, is analyzed in memory, and is
  released immediately. No image is stored or transmitted.
- The pose model is bundled in the installer — the app needs no network to
  monitor posture and works fully offline.
- No telemetry or analytics libraries are included.
- The only outbound network request is an optional update check: an
  unauthenticated request to GitHub's public releases API that returns a
  version number. It sends no image and no personal data, and can be turned off.
- The only files written are your settings (`%APPDATA%\SpineSpy\config.json`)
  and, if you explicitly choose "Save debug snapshot", a single JPG.
