# PyroWave Lab for Ugoos SK1

This branch is a dedicated, updateable laboratory app. It does not overwrite
the working SK1 HEVC v14 APK or the earlier PyroWave test builds.

- Android package: `com.limelight.vplus_sk1_pyrowave_lab`
- TV launcher label: **PyroWave Lab**
- Build: `.github/workflows/sk1-pyrowave-lab.yml`
- APK artifact: `SK1-PyroWave-Lab-APK`
- New builds keep the same package and signing certificate; versionCode increases
  with the GitHub Actions workflow run number.

## One-time setup (repo Settings > Secrets and variables > Actions)

Generate a **dedicated** signing keystore locally and keep a private backup:

```powershell
keytool -genkeypair -v -keystore sk1-pyrowave-lab.jks -storetype PKCS12 -alias pyrowave-lab -keyalg RSA -keysize 3072 -validity 3650
[Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path '.\sk1-pyrowave-lab.jks'))) | Set-Clipboard
```

The `keytool` utility ships with the JDK. In GitHub Secrets, set:

| Secret | Meaning |
| --- | --- |
| `LAB_KEYSTORE_BASE64` | Paste clipboard (Base64 of the .jks file) |
| `LAB_KEYSTORE_PASSWORD` | Keystore password |
| `LAB_KEY_ALIAS` | `pyrowave-lab` |
| `LAB_KEY_PASSWORD` | Private key password (often the same) |

**Never commit the keystore or secrets.** Preserve the local backup: replacing
the key will stop Android from updating the existing Lab app.

Run the Lab workflow manually once secrets are configured. Install the first
APK using `adb install -r app-nonRoot-debug.apk`, pair with Sunshine **one time**,
and use `adb install -r` for all subsequent Lab APKs.

To open via ADB:

```powershell
adb shell monkey -p com.limelight.vplus_sk1_pyrowave_lab 1
```

Do not use `adb uninstall`, `pm clear`, or `adb install -r -d` for routine
upgrades. The first install of Lab is a **new app** and cannot inherit pairing
from the old per-version app IDs without an explicit data migration.
