# Moonlight SK1 Texture v13 — Release notes

**Статус:** экспериментальная сборка для Ugoos SK1, подготовка публикации.  
**Базовый проект:** [Moonlight V+](https://github.com/qiin2333/moonlight-vplus) 12.13.3.  
**Оборудование для проверки:** Ugoos SK1, Amlogic S928X-K, Android 14.

## Зачем эта сборка

Исследуется проблема с рывками HEVC в Moonlight на Ugoos SK1. В отдельном тестовом плеере низкая задержка позволяла декодировать HEVC с полной скоростью, а вывод через `TextureView` показал плавную картинку там, где обычный `SurfaceView` давал рывки. Эти результаты **не подтверждают автоматически**, что присланный APK v13 уже устраняет проблему во всех сценариях Moonlight.

Назначение этой сборки — проверка экспериментального пути представления HEVC с сохранением аппаратного декодирования, а не универсальное исправление для всех Android TV.

## Идентификация APK (прочитано непосредственно из файла)

| Поле | Значение |
| --- | --- |
| Исходное имя файла | `Moonlight-SK1-Texture-v13-direct-noautoupdate.apk` |
| Имя приложения | `Moonlight SK1 Texture` |
| Android `applicationId` | `com.limelight.vplus_sk1texture` |
| `versionName` | `12.13.3-sk1texture13-direct-noautoupdate` |
| `versionCode` | `121303013` |
| Минимальный Android | API 22 (Android 5.1) |
| Целевой Android API | 35 |
| ABI | `arm64-v8a`, `armeabi-v7a` |
| Размер | 37 916 510 байт (≈36.16 MiB) |
| Тип | Отдельно подписанная диагностическая APK; `android:debuggable=true` |

Файл можно устанавливать **рядом** с обычным Moonlight V+, поскольку `applicationId` отличается. Это не означает совместимости настроек или данных между приложениями.

### Проверка целостности

```text
SHA-256 (APK):
45d4ccddc081ae75139e3001536df09ef72e1ab1a3d5e03a6f8183f1091d43a2
```

Сертификат подписи: `CN=SK1 Texture Diagnostic`. Отпечаток SHA-256:

```text
5F:A6:E3:86:3C:B2:83:63:2A:4D:7A:51:13:41:A4:9F:DE:20:4A:61:ED:65:32:4E:E6:4C:70:1F:6F:5F:C2:3E
```

APK прошёл проверку целостности ZIP (CRC). Наличие сертификата и CRC **не означает аудит безопасности кода или подтверждение работоспособности на устройстве**.

## Как проверять

1. Установить отдельную диагностическую сборку на Ugoos SK1.
2. Проверить поток Sunshine **HEVC, 1080p60, SDR, режим малой задержки «Вкл.»** — это повторяет условия предыдущих исследований.
3. Отметить фактическую плавность изображения, `Rx/Rd FPS`, ошибки декодирования и задержки.
4. Затем, только при положительном результате, отдельно исследовать 4K60 и HDR.

**Внимание:** наличие `direct-noautoupdate` в имени и `versionName` **не доказывает отключение автоматических обновлений**. Это поведение должно подтверждаться кодом или тестом. В манифесте APK всё ещё указан `UpdateDownloadReceiver`.

## Публикация и соответствие исходникам

В текущей `master`-ветке репозитория указаны `versionName=12.13.3` и обычный идентификатор пакета. **Точные исходные изменения APK v13 пока не представлены в коммитах GitHub.** Существующий [PR #1](https://github.com/DHBender/moonlight-vplus_UGOOS_SK1/pull/1) содержит более ранний эксперимент с `TextureView` и не должен без проверки объявляться точным исходным кодом этой APK.

До публикации публичного релиза следует добавить **соответствующий исходный код и инструкцию воспроизводимой сборки** (проект распространяется на условиях GPLv3), затем прикрепить APK в GitHub Release.

### Предлагаемое оформление GitHub Release

- **Tag:** `sk1-texture-v13` (создавать только после фиксации соответствующих исходников).
- **Title:** `Moonlight SK1 Texture v13 — HEVC presentation experiment`.
- **Тип:** *Pre-release*.
- **Asset:** `Moonlight-SK1-Texture-v13-direct-noautoupdate.apk`.
- **Description:** содержание этой страницы без раздела «Публикация и соответствие исходникам», после проверки формулировок и добавления исходников.

---

**English summary:** Experimental, separately signed Android build for Ugoos SK1 (Amlogic S928X-K). Intended to test HEVC presentation via TextureView while retaining hardware decoding. APK internal version: `12.13.3-sk1texture13-direct-noautoupdate`; package: `com.limelight.vplus_sk1texture`. This APK is debuggable and is not yet linked to matching reproducible source changes. Treat it as a diagnostic pre-release, not a stable general-purpose app.
