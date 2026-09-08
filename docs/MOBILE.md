# Mobile notes (not started)

Desktop first. When the desktop app is polished and signed, a mobile version could run the same worker on a phone while it charges overnight.

- **Engine**: llama.cpp (Metal on iOS, CPU/Vulkan on Android) or MLX on Apple silicon; 2B–4B models, quantized.
- **iOS**: background execution is limited; the realistic mode is "screen off, plugged in, app in foreground" or short background windows.
- **Android**: a foreground service with a persistent notification; battery and thermal throttling decide the pace.
- **Identity**: same Ed25519 `did:key`, stored in the OS keystore (Keychain / Android Keystore); rescue file identical to desktop.
- **Store policies**: declare the foreground service and the local model download; no crypto-reward wording.

Contributions welcome; open an issue with measured tokens/s on a real device before proposing a stack.
